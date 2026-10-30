#!/usr/bin/env python3
"""F1 streaming SHA and process input-observation ledger regression."""
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    configured = os.environ.get("CXX")
    compiler = shlex.split(configured, posix=os.name != "nt") if configured else []
    if not compiler:
        found = next((shutil.which(name) for name in ("g++", "clang++", "cl") if shutil.which(name)), None)
        assert found, "C++17 compiler required (set CXX or configure PATH)"
        compiler = [found]
    source = r'''
#include "Config/InputProvenance.hh"
#include "Config/IniReader.hh"
#include "G4USIM_INPUT_IMPLEMENTATION"
#include <cassert>
#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <thread>
#include <vector>
using namespace input_provenance;
class FailingReadBuffer : public std::streambuf {
 std::string prefix=std::string(65536,'a');
 bool delivered=false;
 std::streamsize xsgetn(char* output,std::streamsize count) override {
  if(delivered)throw std::runtime_error("injected input device failure");
  delivered=true;const auto n=std::min<std::streamsize>(count,prefix.size());std::copy_n(prefix.data(),n,output);return n;
 }
};
void write(const std::string& path,const std::string& bytes){std::ofstream file(path,std::ios::binary);file.write(bytes.data(),bytes.size());file.close();assert(!file.fail());}
int main(){
 assert(Snapshot().empty());
 FailingReadBuffer faulty;std::istream broken(&faulty);bool ioRefused=false;
 try{input_provenance::ReadBuffered(broken,"injected.ini");}catch(const std::runtime_error&){ioRefused=true;}
 assert(ioRefused&&Snapshot().empty());
 for(std::size_t size : {0u,1u,55u,56u,63u,64u,65u,119u,120u,127u,128u,129u,65535u,65536u,65537u,1048579u}){
  std::string bytes;bytes.resize(size);for(std::size_t i=0;i<size;++i)bytes[i]=static_cast<char>((i*37+19)%256);
  write("stream.bin",bytes);const auto digest=HashFile("stream.bin");
  assert(digest.sha256==Sha256(bytes)&&digest.size_bytes==size);
  std::cout<<"hash "<<size<<" "<<digest.sha256<<"\n";
 }
 assert(Snapshot().empty()); // output hashing must never become input evidence
 const std::string bytes="\xef\xbb\xbf[resource]\r\nx=1\r\n";
 write("input.ini",bytes);
 auto first=ReadFile("input.ini","geometry_ini","geometry_validation");
 auto frozen=Snapshot();assert(frozen.size()==1&&frozen[0].sequence==1);
 assert(frozen[0].path=="input.ini"&&frozen[0].sha256==Sha256(bytes));
 assert(frozen[0].size_bytes==bytes.size()&&frozen[0].kind=="geometry_ini"&&frozen[0].role=="geometry_validation");
 assert(frozen[0].status=="recorded"&&frozen[0].capture_method=="binary_buffer"&&frozen[0].reason.empty());
 const std::string changed="[resource]\nx=2\n";write("input.ini",changed);
 auto second=ReadFile("input.ini","geometry_ini","geometry_construct");
 std::filesystem::remove("input.ini");
 assert(first.bytes==bytes&&first.sha256==Sha256(bytes)&&second.sha256==Sha256(changed));
 assert(frozen.size()==1&&frozen[0].sha256==Sha256(bytes));
 auto ledger=Snapshot();assert(ledger.size()==2&&ledger[1].sha256==Sha256(changed)&&ledger[1].role=="geometry_construct");
 // A rejected parser still consumed the original byte buffer; no acceptance is claimed.
 write("broken.ini","[broken\n");IniReader reader;bool rejected=false;
 try{reader.Load("broken.ini");}catch(...){rejected=true;}assert(rejected);
 assert(Snapshot().size()==3&&Snapshot()[2].sha256==Sha256("[broken\n"));
 for(const auto& path : {"missing.ini","."}){
  auto count=Snapshot().size();rejected=false;try{ReadFile(path);}catch(...){rejected=true;}assert(rejected&&Snapshot().size()==count);
  rejected=false;try{HashFile(path);}catch(...){rejected=true;}assert(rejected&&Snapshot().size()==count);
 }
 MarkUnobserved("/gps/hist/file data.txt","Native file bytes were not captured");
 ledger=Snapshot();assert(ledger.size()==4&&ledger.back().status=="unobserved");
 assert(!ledger.back().sha256&&!ledger.back().size_bytes&&!ledger.back().reason.empty());
 rejected=false;try{RecordRead("bad",{"bogus",0},"file","input","capture");}catch(...){rejected=true;}assert(rejected&&Snapshot().size()==4);
 rejected=false;try{MarkUnobserved("bad","");}catch(...){rejected=true;}assert(rejected&&Snapshot().size()==4);
 write("shared.bin",std::string("a\0b\r\n",5));
 std::vector<std::thread> threads;
 for(int t=0;t<4;++t)threads.emplace_back([t](){for(int i=0;i<16;++i)ReadFile("shared.bin","worker_input",std::to_string(t));});
 for(auto& thread:threads)thread.join();
 ledger=Snapshot();assert(ledger.size()==68);
 for(std::size_t i=0;i<ledger.size();++i)assert(ledger[i].sequence==i+1);
 std::array<int,4> counts{};
 for(std::size_t i=4;i<ledger.size();++i){assert(ledger[i].sha256==Sha256(std::string("a\0b\r\n",5)));assert(ledger[i].size_bytes==5);++counts.at(std::stoi(ledger[i].role));}
 for(auto count:counts)assert(count==16);
 // Same content relocated remains identical without reading the old path again.
 std::filesystem::rename("shared.bin","relocated.bin");
 const auto relocated=ReadFile("relocated.bin","worker_input","relocated");
 assert(relocated.sha256==*ledger.back().sha256&&Snapshot().back().path=="relocated.bin");
 // Hashing large output only streams data and does not change the ledger.
 const auto before=Snapshot().size();HashFile("stream.bin");assert(Snapshot().size()==before);
 std::cout<<"ledger "<<Snapshot().size()<<"\n";
}
'''
    with tempfile.TemporaryDirectory(prefix="g4usim-f1-input-") as temp:
        folder = Path(temp)
        test = folder / "input.cc"
        source = source.replace("G4USIM_INPUT_IMPLEMENTATION", (root / "src/Config/InputProvenance.cc").as_posix())
        test.write_text(source, encoding="utf-8")
        exe = folder / ("input.exe" if os.name == "nt" else "input")
        inputs = [str(test)] + [str(root / f"src/{name}.cc") for name in
                  ("Config/IniReader", "Utils/StringUtils")]
        if Path(compiler[0]).stem.lower() in ("cl", "clang-cl"):
            args = compiler + ["/nologo", "/std:c++17", "/utf-8", "/EHsc", "/I" + str(root / "include")]
            args += inputs + ["/Fe:" + str(exe)]
        else:
            args = compiler + ["-std=c++17", "-pthread", "-Wall", "-Wextra", "-pedantic", "-I", str(root / "include")]
            args += inputs + ["-o", str(exe)]
        built = subprocess.run(args, cwd=folder, capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([str(exe)], cwd=folder, capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        lines = ran.stdout.splitlines()
        assert len(lines) == 17, ran.stdout
        for line in lines[:-1]:
            tag, size, digest = line.split()
            assert tag == "hash"
            expected = bytes((i * 37 + 19) % 256 for i in range(int(size)))
            assert digest == hashlib.sha256(expected).hexdigest(), line
        assert lines[-1] == "ledger 69", ran.stdout
    print("F1 input observation and streaming hash regression passed")


if __name__ == "__main__":
    main()
