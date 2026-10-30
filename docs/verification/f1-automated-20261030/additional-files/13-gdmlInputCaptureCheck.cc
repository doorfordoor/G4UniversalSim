
#include "Geometry/GdmlInputCapture.hh"
#include "Config/InputProvenance.hh"
#include <xercesc/util/PlatformUtils.hpp>
#include <xercesc/util/XMLFileMgr.hpp>
#include <xercesc/util/XMLNetAccessor.hpp>
#include <xercesc/util/BinInputStream.hpp>
#include <xercesc/util/XMLString.hpp>
#include <xercesc/util/OutOfMemoryException.hpp>
#include <xercesc/framework/MemoryManager.hpp>
#include <xercesc/parsers/XercesDOMParser.hpp>
#include <xercesc/dom/DOM.hpp>
#include <xercesc/sax/HandlerBase.hpp>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <cstring>
#include <thread>
#include <cstdlib>
#include <new>
#include <exception>
// One-shot allocation failure after a successful native open. This is only
// this component executable's allocator, never a production runtime hook.
thread_local bool failNextAllocation = false;
void* operator new(std::size_t count) {
    if (failNextAllocation) { failNextAllocation = false; throw std::bad_alloc(); }
    if (void* p = std::malloc(count ? count : 1)) return p;
    throw std::bad_alloc();
}
void operator delete(void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
using namespace xercesc;
void Check(bool value, const char* why) { if (!value) throw std::runtime_error(why); }
void Print(const GdmlIO::GdmlInputCapture& capture) {
    for (const auto& entry: capture.AcceptedInputs()) std::cout << "INPUT " << entry.path << " " << entry.sha256 << "\n";
    for (const auto& entry: capture.UntrackedInputs()) std::cout << "UNKNOWN " << entry << "\n";
}
class FakeStream: public BinInputStream {
    std::string bytes="network bytes\r\n"; XMLFilePos pos=0;
public:
    XMLFilePos curPos() const override { return pos; }
    const XMLCh* getContentType() const override { return u"application/xml"; }
    const XMLCh* getEncoding() const override { return u"UTF-8"; }
    XMLSize_t readBytes(XMLByte* const out, const XMLSize_t count) override {
        auto n=std::min<std::size_t>(count,bytes.size()-pos);
        std::memcpy(out,bytes.data()+pos,n); pos+=n; return n;
    }
};
class FakeNetwork: public XMLNetAccessor {
public:
    const XMLCh* getId() const override { return u"test-native"; }
    BinInputStream* makeNew(const XMLURL&, const XMLNetHTTPInfo*) override { return new FakeStream; }
};
// Move every worker exception to the joining thread. Only the two concrete
// allocation families below count as an expected refusal.
template<class Operation> void InThread(Operation&& operation) {
    std::exception_ptr failure;
    std::thread worker([&] {
        try { operation(); }
        catch (...) { failure = std::current_exception(); }
    });
    worker.join();
    if (failure) std::rethrow_exception(failure);
}
template<class Operation> bool AllocationRefused(Operation&& operation) {
    try { operation(); }
    catch (const std::bad_alloc&) { return true; }
    catch (const OutOfMemoryException&) { return true; }
    return false;
}
class FileManagerOverride {
    XMLFileMgr* original_;
public:
    explicit FileManagerOverride(XMLFileMgr& replacement):original_(XMLPlatformUtils::fgFileMgr) {
        XMLPlatformUtils::fgFileMgr = &replacement;
    }
    ~FileManagerOverride() { XMLPlatformUtils::fgFileMgr = original_; }
};
// Arm after UTF conversion, when the adapter releases getFullPath's result.
// This makes FileBuffer's own allocation the first failing allocation rather
// than relying on implementation-specific path/transcode allocation counts.
class CaptureFaultMemory final : public MemoryManager {
    MemoryManager& source_;
public:
    bool armOnRelease = false;
    explicit CaptureFaultMemory(MemoryManager& source):source_(source) {}
    MemoryManager* getExceptionMemoryManager() override { return source_.getExceptionMemoryManager(); }
    void* allocate(XMLSize_t size) override { return source_.allocate(size); }
    void deallocate(void* p) override {
        source_.deallocate(p);
        if (armOnRelease) { armOnRelease = false; failNextAllocation = true; }
    }
};
class AllocationFaultFiles final : public XMLFileMgr {
    XMLFileMgr& source_;
    std::string path_;
public:
    int opens=0, closes=0;
    bool failOnOpen=true, failBuffer=false, failReadXerces=false;
    AllocationFaultFiles(XMLFileMgr& source, std::string path):source_(source),path_(std::move(path)){}
    FileHandle fileOpen(const XMLCh* p,bool write,MemoryManager* const m) override {
        auto handle=source_.fileOpen(p,write,m);if(handle){++opens;if(failOnOpen)failNextAllocation=true;}return handle;
    }
    FileHandle fileOpen(const char* p,bool write,MemoryManager* const m) override {
        auto handle=source_.fileOpen(p,write,m);if(handle){++opens;if(failOnOpen)failNextAllocation=true;}return handle;
    }
    FileHandle openStdIn(MemoryManager* const m) override {
        auto handle=source_.fileOpen(path_.c_str(),false,m);if(handle){++opens;if(failOnOpen)failNextAllocation=true;}return handle;
    }
    void fileClose(FileHandle h,MemoryManager* const m) override {++closes;source_.fileClose(h,m);}
    void fileReset(FileHandle h,MemoryManager* const m) override {source_.fileReset(h,m);}
    XMLFilePos curPos(FileHandle h,MemoryManager* const m) override {return source_.curPos(h,m);}
    XMLFilePos fileSize(FileHandle h,MemoryManager* const m) override {return source_.fileSize(h,m);}
    XMLSize_t fileRead(FileHandle h,XMLSize_t n,XMLByte* b,MemoryManager* const m) override {
        if(failReadXerces) { failReadXerces=false; throw OutOfMemoryException(); }
        return source_.fileRead(h,n,b,m);
    }
    void fileWrite(FileHandle h,XMLSize_t n,const XMLByte* b,MemoryManager* const m) override {source_.fileWrite(h,n,b,m);}
    XMLCh* getFullPath(const XMLCh* const p,MemoryManager* const m) override {
        auto* full=source_.getFullPath(p,m);
        if(failBuffer) {
            Check(full!=nullptr,"full path for deterministic buffer failure");
            static_cast<CaptureFaultMemory*>(m)->armOnRelease=true;
        }
        return full;
    }
    XMLCh* getCurrentDirectory(MemoryManager* const m) override {return source_.getCurrentDirectory(m);}
    bool isRelative(const XMLCh* const p,MemoryManager* const m) override {return source_.isRelative(p,m);}
};
void CheckOpenFailureCloses(XMLFileMgr& original,const std::string& path) {
    AllocationFaultFiles fault(original,path);
    {
        FileManagerOverride replacement(fault);
        {
            GdmlIO::GdmlInputCapture capture;
            bool refused=AllocationRefused([&] {
                InThread([&] { XMLPlatformUtils::fgFileMgr->fileOpen(path.c_str(),false,XMLPlatformUtils::fgMemoryManager); });
            });
            Check(refused && fault.opens==1 && fault.closes==1,"foreign native handle closed on observation allocation failure");
            refused=AllocationRefused([&] { XMLPlatformUtils::fgFileMgr->openStdIn(XMLPlatformUtils::fgMemoryManager); });
            Check(refused && fault.opens==2 && fault.closes==2,"stdin native handle closed on observation allocation failure");
            refused=AllocationRefused([&] { XMLPlatformUtils::fgFileMgr->fileOpen(path.c_str(),false,XMLPlatformUtils::fgMemoryManager); });
            Check(refused && fault.opens==3 && fault.closes==3,"owner native handle still closed on capture allocation failure");

            fault.failOnOpen=false;
            fault.failBuffer=true;
            CaptureFaultMemory memory(*XMLPlatformUtils::fgMemoryManager);
            XMLCh* wide=XMLString::transcode(path.c_str());
            try {
                refused=AllocationRefused([&] { XMLPlatformUtils::fgFileMgr->fileOpen(wide,false,&memory); });
            } catch (...) { XMLString::release(&wide); throw; }
            XMLString::release(&wide);
            std::cout << "FAULT FileBuffer opens=" << fault.opens << " closes=" << fault.closes << " refused=" << refused << "\n";
            Check(refused && !failNextAllocation && !memory.armOnRelease && fault.opens==4 && fault.closes==4,"FileBuffer allocation failure closes native handle");
            fault.failBuffer=false;
            fault.failReadXerces=true;
            refused=AllocationRefused([&] { XMLPlatformUtils::fgFileMgr->fileOpen(path.c_str(),false,XMLPlatformUtils::fgMemoryManager); });
            Check(refused && fault.opens==5 && fault.closes==5,"Xerces allocation failure during buffered read closes native handle");
        }
        Check(XMLPlatformUtils::fgFileMgr==&fault,"capture restores fault adapter after allocation checks");
    }
    Check(XMLPlatformUtils::fgFileMgr==&original,"fault check restores original file manager");
    bool unexpected=false;
    try {
        FileManagerOverride replacement(fault);
        GdmlIO::GdmlInputCapture capture;
        AllocationRefused([&] { InThread([] { throw std::runtime_error("unexpected worker test failure"); }); });
    }
    catch(const std::runtime_error& error) { unexpected=std::strcmp(error.what(),"unexpected worker test failure")==0; }
    Check(unexpected,"non-allocation worker exception propagates to the joining thread");
    Check(XMLPlatformUtils::fgFileMgr==&original,"fault scope restores original file manager during exception unwind");
    Check(AllocationRefused([&] { InThread([] { throw OutOfMemoryException(); }); }),"Xerces worker allocation exception propagates to the joining thread");
    std::cout << "PASS allocation fault checks opens=" << fault.opens << " closes=" << fault.closes << " adapter_restored=true\n";
}
int RunCaptureChecks(int argc,char** argv) {
    Check(argc==2,"path missing"); std::string directory=argv[1];
    XMLPlatformUtils::Initialize();
    auto* originalFiles=XMLPlatformUtils::fgFileMgr;
    auto* originalNetwork=XMLPlatformUtils::fgNetAccessor;
    {
        GdmlIO::GdmlInputCapture capture;
        auto* files=XMLPlatformUtils::fgFileMgr;
        const auto path=directory+"/replace.xml";
        auto handle=files->fileOpen(path.c_str(),false,XMLPlatformUtils::fgMemoryManager);
        Check(handle!=nullptr,"open");
        { std::ofstream changed(path,std::ios::binary); changed << "changed after native open"; }
        XMLByte bytes[256]{};
        auto size=files->fileRead(handle,256,bytes,XMLPlatformUtils::fgMemoryManager);
        Check(std::string(reinterpret_cast<char*>(bytes),size)=="original bytes\r\n","same buffered bytes");
        Check(files->curPos(handle,XMLPlatformUtils::fgMemoryManager)==size,"position");
        Check(files->fileSize(handle,XMLPlatformUtils::fgMemoryManager)==size,"size");
        files->fileReset(handle,XMLPlatformUtils::fgMemoryManager);
        Check(files->curPos(handle,XMLPlatformUtils::fgMemoryManager)==0,"reset");
        Check(files->fileRead(handle,256,bytes,XMLPlatformUtils::fgMemoryManager)==size,"reset read");
        files->fileClose(handle,XMLPlatformUtils::fgMemoryManager);
        const auto output=directory+"/written.txt";
        auto write=files->fileOpen(output.c_str(),true,XMLPlatformUtils::fgMemoryManager);
        files->fileWrite(write,4,reinterpret_cast<const XMLByte*>("keep"),XMLPlatformUtils::fgMemoryManager);
        files->fileClose(write,XMLPlatformUtils::fgMemoryManager);
        Check(capture.AcceptedInputs().size()==1,"writes not captured as inputs");
        const auto observations = input_provenance::Snapshot();
        Check(observations.size()==1,"ledger excludes native writes");
        Check(observations[0].sha256==input_provenance::Sha256("original bytes\r\n"),"ledger preserves original bytes after replace");
        Check(observations[0].size_bytes==16 && observations[0].capture_method=="xerces_file_buffer","ledger native buffered metadata");
        Print(capture);
    }
    Check(XMLPlatformUtils::fgFileMgr==originalFiles,"restore file manager");
    Check(XMLPlatformUtils::fgNetAccessor==originalNetwork,"restore net accessor");
    // Unrelated Xerces clients keep native handles even while capture is live.
    FileHandle other=nullptr;
    {
        GdmlIO::GdmlInputCapture capture;
        InThread([&] {
            other=XMLPlatformUtils::fgFileMgr->fileOpen((directory+"/entity.txt").c_str(),false,XMLPlatformUtils::fgMemoryManager);
            Check(other!=nullptr,"other thread native handle");
        });
        Check(capture.AcceptedInputs().empty(),"other client not attributed to GDML");
        {
            GdmlIO::GdmlInputCapture nested;
            auto handle=XMLPlatformUtils::fgFileMgr->fileOpen((directory+"/entity.txt").c_str(),false,XMLPlatformUtils::fgMemoryManager);
            XMLPlatformUtils::fgFileMgr->fileClose(handle,XMLPlatformUtils::fgMemoryManager);
            Check(nested.AcceptedInputs().size()==1,"nested module capture");
        }
        Check(capture.AcceptedInputs().size()==1,"nested input in outer scope");
    }
    XMLByte outside[64]{};
    Check(originalFiles->fileRead(other,64,outside,XMLPlatformUtils::fgMemoryManager)==15,"native handle survives restoration");
    originalFiles->fileClose(other,XMLPlatformUtils::fgMemoryManager);
    try { GdmlIO::GdmlInputCapture capture; throw std::runtime_error("test unwind"); } catch(const std::runtime_error&) {}
    Check(XMLPlatformUtils::fgFileMgr==originalFiles,"exception restore");
    {
        GdmlIO::GdmlInputCapture capture;
        XercesDOMParser parser;
        parser.setValidationScheme(XercesDOMParser::Val_Always);
        parser.setDoSchema(true);
        parser.setDoNamespaces(true);
        parser.setLoadExternalDTD(true);
        HandlerBase errors; parser.setErrorHandler(&errors);
        parser.parse((directory+"/main.xml").c_str());
        Check(parser.getErrorCount()==0,"schema/entity parse");
        const auto* root=parser.getDocument()->getDocumentElement();
        Check(XMLString::equals(root->getTextContent(),u"accepted entity"),"entity content");
        Print(capture);
    }
    CheckOpenFailureCloses(*originalFiles,directory+"/entity.txt");
    FakeNetwork native;
    XMLPlatformUtils::fgNetAccessor=&native;
    {
        GdmlIO::GdmlInputCapture capture;
        XMLURL url("http://example.test/schema.xsd");
        auto* stream=XMLPlatformUtils::fgNetAccessor->makeNew(url,nullptr);
        Check(XMLString::equals(stream->getContentType(),u"application/xml"),"content type");
        Check(XMLString::equals(stream->getEncoding(),u"UTF-8"),"encoding");
        XMLByte bytes[3]; while(stream->readBytes(bytes,sizeof bytes)) {}
        delete stream;
        XMLURL partial("http://example.test/partial");
        stream=XMLPlatformUtils::fgNetAccessor->makeNew(partial,nullptr);
        stream->readBytes(bytes,1); delete stream;
        Check(capture.AcceptedInputs().size()==1,"complete network only");
        Check(capture.UntrackedInputs().size()==1,"partial is unknown");
        const auto observations = input_provenance::Snapshot();
        const auto& incomplete = observations.back();
        const auto& complete = observations[observations.size()-2];
        Check(complete.path=="http://example.test/schema.xsd" && complete.sha256==input_provenance::Sha256("network bytes\r\n"),"network EOF ledger original bytes");
        Check(incomplete.status=="unobserved" && !incomplete.sha256 && !incomplete.size_bytes,"partial network ledger cannot invent hash");
        Print(capture);
    }
    Check(XMLPlatformUtils::fgNetAccessor==&native,"network restore");
    XMLPlatformUtils::fgNetAccessor=originalNetwork;
    XMLPlatformUtils::Terminate();
    std::cout << "PASS native capture\n";
    return 0;
}

// Keep assertion failures visible on Windows too: an uncaught C++ exception
// otherwise terminates with 0xC0000409 and can leave redirected stdout empty.
int main(int argc,char** argv) {
    try { return RunCaptureChecks(argc,argv); }
    catch(const OutOfMemoryException&) {
        std::cerr << "GDML capture check failed: unexpected Xerces OutOfMemoryException\n";
        return 1;
    }
    catch(const std::exception& error) {
        std::cerr << "GDML capture check failed: " << error.what() << "\n"
                  << "Usage: gdmlInputCaptureCheck <fixture-directory>; normally run scripts/test_effective_gdml.py\n";
        return 1;
    }
    catch (...) {
        std::cerr << "GDML capture check failed: unexpected non-standard exception\n";
        return 1;
    }
}
