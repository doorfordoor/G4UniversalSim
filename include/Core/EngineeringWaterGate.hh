#pragma once
#include "Config/InputProvenance.hh"
#include "G4WaterObservation.hh"
#include "water_approval_digest.hh"
#include <algorithm>
#include "Core/EngineeringWaterState.hh"
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <dlfcn.h>
#endif
#include <filesystem>
#include <cstdlib>
#include <sstream>
#include <set>
#include <iostream>
#include <map>
#include <stdexcept>
#ifdef _WIN32
// The 11.3.2 x64 SDK declaration lacks dllimport. Refer to the actual COFF
// import pointer used by the linker thunk instead of taking the thunk address.
extern "C" decltype(&G4WaterObservation::SetThreadSink) g4usimWaterSetterImport;
#pragma comment(linker, "/alternatename:g4usimWaterSetterImport=__imp_?SetThreadSink@G4WaterObservation@@YAP6AXAEBURecord@1@@_EP6AX0@_E@Z")
#endif
namespace engineering_water {
inline std::string approvedMacro,approvedMain;
inline bool approvedEventLocal=false;
inline int approvedEvents=0;
inline std::filesystem::path observationModule() {
#ifdef _WIN32
    const auto setter = g4usimWaterSetterImport;
    HMODULE owner = nullptr;
    if (!setter || !GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
        GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, reinterpret_cast<LPCWSTR>(setter), &owner))
        throw std::runtime_error("unresolved water import owner");
    const auto exported = GetProcAddress(owner,
        "?SetThreadSink@G4WaterObservation@@YAP6AXAEBURecord@1@@_EP6AX0@_E@Z");
    if (exported != reinterpret_cast<FARPROC>(setter))
        throw std::runtime_error("water import does not match owner export");
    std::wstring path(32768, L'\0');
    const auto size = GetModuleFileNameW(owner, path.data(), static_cast<DWORD>(path.size()));
    if (!size || size >= path.size())
        throw std::runtime_error("unresolved water module path");
    path.resize(size);
    return std::filesystem::canonical(path);
#else
    Dl_info lib{};
    if(!dladdr(reinterpret_cast<void*>(&G4WaterObservation::SetThreadSink),&lib) || !lib.dli_fname)
        throw std::runtime_error("unresolved water observation symbol");
    return std::filesystem::canonical(lib.dli_fname);
#endif
}
inline void guard(int argc,char** argv) {
    namespace fs=std::filesystem;
    if(std::getenv("G4FORCENUMBEROFTHREADS") || std::getenv("G4PARTICLEHPDATA"))
        throw std::runtime_error("water approval rejects kernel override");
    if(argc!=7 || std::string(argv[1])!="--config" || std::string(argv[2])!="main.ini" ||
       std::string(argv[3])!="--macro" || std::string(argv[4])!="run.mac" ||
       std::string(argv[5])!="--output" || std::string(argv[6])!="output")
        throw std::runtime_error("water engineering requires approved batch arguments");
    auto* path=std::getenv("G4USIM_WATER_APPROVAL");
    auto* data=std::getenv("G4NEUTRONHPDATA");
    if(!path || !data) throw std::runtime_error("missing approval or neutron data path");
    const auto manifest=input_provenance::ReadFile(path,"engineering_water_manifest","admission");
    if(manifest.sha256!=WATER_APPROVAL_SHA256) throw std::runtime_error("unapproved water manifest digest");
    std::istringstream stream(manifest.bytes);
    std::string line,kind,identifier,value,extra;
    std::getline(stream,line);
#ifdef _WIN32
    const std::string sdkIdentity=" Geant4-11.3.2 G4NDL-4.7.1";
#else
    const std::string sdkIdentity=" Geant4-11.4.3 G4NDL-4.7.1";
#endif
    const bool regularRng=(line=="G4USIM_WATER_COLLISION_RNG_R11"+sdkIdentity);
    const bool thinRng=(line=="G4USIM_WATER_THIN_RNG_R10"+sdkIdentity);
    thinWorld=thinRng || line=="G4USIM_WATER_THIN_R9"+sdkIdentity;
    captureFirstWorkerState=thinRng || regularRng;
    if(!thinWorld && !regularRng && line!="G4USIM_WATER_APPROVAL_V2"+sdkIdentity)
        throw std::runtime_error("unsupported water approval version");
    std::map<std::string,std::string> modules;
    std::map<std::string,bool> mains;
    std::map<std::string,std::string> headers;
    bool geo=false,mac=false;
    unsigned dataRows=0;
    while(std::getline(stream,line)){
        std::istringstream row(line);
        if(!(row>>kind>>identifier>>value) || row>>extra)throw std::runtime_error("invalid water manifest record");
        auto check=[&](const fs::path& p){if(input_provenance::HashFile(p.u8string()).sha256!=value)
            throw std::runtime_error("water approval file mismatch: "+p.u8string());};
        if(kind=="module") modules.emplace(identifier,value);
        else if(kind=="data"){check(fs::u8path(data)/identifier);++dataRows;}
        else if(kind=="legacy" || kind=="event_local"){
            if(!mains.emplace(value,kind=="event_local").second) throw std::runtime_error("ambiguous cache policy approval");
        } else if(kind=="header") headers.emplace(identifier,value);
        else if(kind=="geometry"){check(identifier);geo=true;}
        else if(kind=="macro"){check(identifier);approvedMacro=value;mac=true;}
        else if(kind=="events") approvedEvents=std::stoi(value);
        else throw std::runtime_error("unknown approval record");
    }
    const auto actual=observationModule();
    if(modules.size()!=1 || modules.at(actual.filename().u8string())!=input_provenance::HashFile(actual.u8string()).sha256)
        throw std::runtime_error("unapproved loaded water module");
    approvedMain=input_provenance::HashFile("main.ini").sha256;
    if(!mains.count(approvedMain) || !geo || !mac || !dataRows || approvedEvents<1)
        throw std::runtime_error("incomplete or mismatched water approval");
    approvedEventLocal=mains.at(approvedMain);
    if(thinWorld && (approvedEvents!=1 || !approvedEventLocal || mains.size()!=1))
        throw std::runtime_error("thin water requires one event-local approved configuration");
    if(regularRng && (approvedEvents!=1 || mains.size()!=2 ||
       !std::all_of(mains.begin(),mains.end(),[](const auto& entry){return entry.second;})))
        throw std::runtime_error("regular water RNG requires one event and two event-local approved configurations");
    if(headers.size()!=2)throw std::runtime_error("incomplete native cache capability identity");
    for(const auto& h:headers){
        const auto installed=actual.parent_path().parent_path()/"include"/"Geant4"/h.first;
        if(input_provenance::HashFile(installed.u8string()).sha256!=h.second)
            throw std::runtime_error("loaded SDK prefix lacks approved native cache header: "+h.first);
    }
    std::cout << "WATER_APPROVAL " << manifest.sha256 << " module=" << actual.u8string()
              << " data=" << fs::canonical(fs::u8path(data)).u8string() << " verified_files=" << dataRows << std::endl;
}
}
