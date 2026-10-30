#include "Geometry/GdmlInputCapture.hh"
#include "Config/InputProvenance.hh"
#ifdef G4USIM_HAVE_GDML
#include <xercesc/util/XMLFileMgr.hpp>
#include <xercesc/util/XMLNetAccessor.hpp>
#include <xercesc/util/PlatformUtils.hpp>
#include <xercesc/util/BinInputStream.hpp>
#include <xercesc/util/XMLString.hpp>
#include <algorithm>
#include <array>
#include <cstring>
#include <filesystem>
#include <map>
#include <stdexcept>
#include <thread>
#include <utility>

namespace GdmlIO {
namespace {
using namespace xercesc;
std::string Utf8(const XMLCh* text) {
    std::u16string value;
    if (text) while (*text) value.push_back(static_cast<char16_t>(*text++));
    return std::filesystem::path(value).u8string();
}
struct Records {
    std::vector<AcceptedInput> accepted;
    std::vector<std::string> unknown;
    void Accept(const std::string& path, const std::string& bytes, const std::string& method) {
        // Reopening an input is a distinct native parse observation. Do not
        // collapse different bytes under one path into a false unique hash.
        const auto digest = input_provenance::Sha256(bytes);
        input_provenance::RecordRead(path, {digest, static_cast<std::uint64_t>(bytes.size())},
            "gdml_dependency", "native_gdml_parse", method);
        accepted.push_back({path, digest});
    }
};
struct FileBuffer { std::string bytes; std::size_t offset = 0; };
class Files final : public XMLFileMgr {
public:
    Files(XMLFileMgr& source, std::shared_ptr<Records> records)
        : source_(source), records_(std::move(records)), owner_(std::this_thread::get_id()) {}
    FileHandle fileOpen(const XMLCh* path, bool write, MemoryManager* const manager) override {
        auto handle = source_.fileOpen(path, write, manager);
        if (!handle || write) return handle;
        if (std::this_thread::get_id() != owner_) {
            try {
                input_provenance::MarkUnobserved("gdml:non_owner_file_stream", "Xerces non-owner thread file input is passed through without byte capture", "gdml_dependency", "native_gdml_parse");
            } catch (...) { source_.fileClose(handle, manager); throw; }
            return handle;
        }
        XMLCh* full = nullptr;
        std::string name;
        try {
            full = source_.getFullPath(path, manager);
            name = Utf8(full ? full : path);
            if (full) { XMLString::release(&full, manager); }
        } catch (...) {
            if (full) XMLString::release(&full, manager);
            source_.fileClose(handle, manager);
            throw;
        }
        return Capture(handle, name, manager);
    }
    FileHandle fileOpen(const char* path, bool write, MemoryManager* const manager) override {
        // Keep the native overload's opening and locale semantics unchanged.
        auto handle = source_.fileOpen(path, write, manager);
        if (!handle || write) return handle;
        if (std::this_thread::get_id() != owner_) {
            try {
                input_provenance::MarkUnobserved("gdml:non_owner_file_stream", "Xerces non-owner thread file input is passed through without byte capture", "gdml_dependency", "native_gdml_parse");
            } catch (...) { source_.fileClose(handle, manager); throw; }
            return handle;
        }
        XMLCh* wide = nullptr;
        XMLCh* full = nullptr;
        std::string name;
        try {
            wide = XMLString::transcode(path, manager);
            full = source_.getFullPath(wide, manager);
            name = Utf8(full ? full : wide);
            XMLString::release(&full, manager);
            XMLString::release(&wide, manager);
        } catch (...) {
            if (full) XMLString::release(&full, manager);
            if (wide) XMLString::release(&wide, manager);
            source_.fileClose(handle, manager);
            throw;
        }
        return Capture(handle, name, manager);
    }
    FileHandle openStdIn(MemoryManager* const manager) override {
        auto handle = source_.openStdIn(manager);
        if (handle) {
            try {
                input_provenance::MarkUnobserved("stdin:", "Native GDML stdin stream is not captured", "gdml_dependency", "native_gdml_parse");
                if (std::this_thread::get_id() == owner_) records_->unknown.push_back("stdin: native stream not captured");
            } catch (...) { source_.fileClose(handle, manager); throw; }
        }
        return handle;
    }
    void fileClose(FileHandle file, MemoryManager* const manager) override {
        if (std::this_thread::get_id() == owner_ && buffers_.erase(file)) return;
        source_.fileClose(file, manager);
    }
    void fileReset(FileHandle file, MemoryManager* const manager) override {
        if (std::this_thread::get_id() != owner_) { return source_.fileReset(file, manager); }
        auto found = buffers_.find(file);
        if (found == buffers_.end()) source_.fileReset(file, manager);
        else found->second->offset = 0;
    }
    XMLFilePos curPos(FileHandle file, MemoryManager* const manager) override {
        if (std::this_thread::get_id() != owner_) { return source_.curPos(file, manager); }
        auto found = buffers_.find(file);
        return found == buffers_.end() ? source_.curPos(file, manager) : found->second->offset;
    }
    XMLFilePos fileSize(FileHandle file, MemoryManager* const manager) override {
        if (std::this_thread::get_id() != owner_) { return source_.fileSize(file, manager); }
        auto found = buffers_.find(file);
        return found == buffers_.end() ? source_.fileSize(file, manager) : found->second->bytes.size();
    }
    XMLSize_t fileRead(FileHandle file, XMLSize_t count, XMLByte* output, MemoryManager* const manager) override {
        if (std::this_thread::get_id() != owner_) { return source_.fileRead(file, count, output, manager); }
        auto found = buffers_.find(file);
        if (found == buffers_.end()) return source_.fileRead(file, count, output, manager);
        auto& buffer = *found->second;
        auto size = std::min<std::size_t>(count, buffer.bytes.size() - buffer.offset);
        if (size) std::memcpy(output, buffer.bytes.data() + buffer.offset, size);
        buffer.offset += size;
        return size;
    }
    void fileWrite(FileHandle file, XMLSize_t count, const XMLByte* buffer, MemoryManager* const manager) override {
        source_.fileWrite(file, count, buffer, manager);
    }
    XMLCh* getFullPath(const XMLCh* const path, MemoryManager* const manager) override { return source_.getFullPath(path, manager); }
    XMLCh* getCurrentDirectory(MemoryManager* const manager) override { return source_.getCurrentDirectory(manager); }
    bool isRelative(const XMLCh* const path, MemoryManager* const manager) override { return source_.isRelative(path, manager); }
private:
    FileHandle Capture(FileHandle source, const std::string& name, MemoryManager* manager) {
        auto buffer = std::make_unique<FileBuffer>();
        try {
            std::array<XMLByte, 65536> block;
            for (;;) {
                auto count = source_.fileRead(source, block.size(), block.data(), manager);
                if (!count) break;
                buffer->bytes.append(reinterpret_cast<const char*>(block.data()), count);
            }
            // Digest the retained buffer before making it visible to Xerces.
            records_->Accept(name, buffer->bytes, "xerces_file_buffer");
        } catch (...) { source_.fileClose(source, manager); throw; }
        source_.fileClose(source, manager);
        auto key = static_cast<FileHandle>(buffer.get());
        buffers_.emplace(key, std::move(buffer));
        return key;
    }
    XMLFileMgr& source_;
    std::shared_ptr<Records> records_;
    std::thread::id owner_;
    // Only the synchronous owner reads buffered handles. Other Xerces threads
    // always receive native handles, so they survive restoration unchanged.
    std::map<FileHandle, std::unique_ptr<FileBuffer>> buffers_;
};
class ObservedStream final : public BinInputStream {
public:
    ObservedStream(BinInputStream* stream, std::shared_ptr<Records> records, std::string url)
        : stream_(stream), records_(std::move(records)), url_(std::move(url)) {}
    ~ObservedStream() override {
        if (!complete_) {
            try {
                input_provenance::MarkUnobserved(url_, "Native GDML network stream did not reach EOF", "gdml_dependency", "native_gdml_parse", "xerces_network_stream");
                records_->unknown.push_back(url_ + " (stream did not reach EOF)");
            } catch (...) {}
        }
    }
    XMLFilePos curPos() const override { return stream_->curPos(); }
    const XMLCh* getContentType() const override { return stream_->getContentType(); }
    const XMLCh* getEncoding() const override { return stream_->getEncoding(); }
    XMLSize_t readBytes(XMLByte* const output, const XMLSize_t count) override {
        auto read = stream_->readBytes(output, count);
        if (read) bytes_.append(reinterpret_cast<const char*>(output), read);
        else if (count && !complete_) {
            records_->Accept(url_, bytes_, "xerces_network_eof");
            bytes_.clear();
            complete_ = true;
        }
        return read;
    }
private:
    std::unique_ptr<BinInputStream> stream_;
    std::shared_ptr<Records> records_;
    std::string url_, bytes_;
    bool complete_ = false;
};
class Network final : public XMLNetAccessor {
public:
    Network(XMLNetAccessor& source, std::shared_ptr<Records> records)
        : source_(source), records_(std::move(records)), owner_(std::this_thread::get_id()) {}
    const XMLCh* getId() const override { return source_.getId(); }
    BinInputStream* makeNew(const XMLURL& url, const XMLNetHTTPInfo* info = nullptr) override {
        std::unique_ptr<BinInputStream> native(source_.makeNew(url, info));
        if (!native) return nullptr;
        if (std::this_thread::get_id() != owner_) {
            input_provenance::MarkUnobserved(Utf8(url.getURLText()), "Xerces non-owner network stream is passed through without byte capture", "gdml_dependency", "native_gdml_parse");
            return native.release();
        }
        // Preserve native URL resolution, HTTP options, content type and encoding.
        auto wrapper = std::make_unique<ObservedStream>(native.get(), records_, Utf8(url.getURLText()));
        native.release();
        return wrapper.release();
    }
private:
    XMLNetAccessor& source_;
    std::shared_ptr<Records> records_;
    std::thread::id owner_;
};
}
std::recursive_mutex& GdmlInputCapture::NativeMutex() {
    static std::recursive_mutex mutex;
    return mutex;
}
class GdmlInputCapture::Impl {
public:
    std::unique_lock<std::recursive_mutex> lock{NativeMutex()};
    std::shared_ptr<Records> records = std::make_shared<Records>();
    XMLFileMgr* originalFiles = XMLPlatformUtils::fgFileMgr;
    XMLNetAccessor* originalNetwork = XMLPlatformUtils::fgNetAccessor;
    std::unique_ptr<Files> files;
    std::unique_ptr<Network> network;
    Impl() {
        if (!originalFiles) throw std::logic_error("GDML capture requires initialized Xerces");
        files = std::make_unique<Files>(*originalFiles, records);
        if (originalNetwork) network = std::make_unique<Network>(*originalNetwork, records);
        // Publish only after all potentially throwing construction completes.
        XMLPlatformUtils::fgFileMgr = files.get();
        if (network) XMLPlatformUtils::fgNetAccessor = network.get();
    }
    ~Impl() {
        XMLPlatformUtils::fgFileMgr = originalFiles;
        XMLPlatformUtils::fgNetAccessor = originalNetwork;
    }
};
GdmlInputCapture::GdmlInputCapture() : impl_(std::make_unique<Impl>()) {}
GdmlInputCapture::~GdmlInputCapture() = default;
std::vector<AcceptedInput> GdmlInputCapture::AcceptedInputs() const { return impl_->records->accepted; }
std::vector<std::string> GdmlInputCapture::UntrackedInputs() const { return impl_->records->unknown; }
}
#endif
