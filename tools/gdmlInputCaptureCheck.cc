
#include "Geometry/GdmlInputCapture.hh"
#include <xercesc/util/PlatformUtils.hpp>
#include <xercesc/util/XMLFileMgr.hpp>
#include <xercesc/util/XMLNetAccessor.hpp>
#include <xercesc/util/BinInputStream.hpp>
#include <xercesc/util/XMLString.hpp>
#include <xercesc/parsers/XercesDOMParser.hpp>
#include <xercesc/dom/DOM.hpp>
#include <xercesc/sax/HandlerBase.hpp>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <cstring>
#include <thread>
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
int main(int argc,char** argv) {
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
        Print(capture);
    }
    Check(XMLPlatformUtils::fgFileMgr==originalFiles,"restore file manager");
    Check(XMLPlatformUtils::fgNetAccessor==originalNetwork,"restore net accessor");
    // Unrelated Xerces clients keep native handles even while capture is live.
    FileHandle other=nullptr;
    {
        GdmlIO::GdmlInputCapture capture;
        std::thread reader([&] {
            other=XMLPlatformUtils::fgFileMgr->fileOpen((directory+"/entity.txt").c_str(),false,XMLPlatformUtils::fgMemoryManager);
            Check(other!=nullptr,"other thread native handle");
        });
        reader.join();
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
        Print(capture);
    }
    Check(XMLPlatformUtils::fgNetAccessor==&native,"network restore");
    XMLPlatformUtils::fgNetAccessor=originalNetwork;
    XMLPlatformUtils::Terminate();
    std::cout << "PASS native capture\n";
}
