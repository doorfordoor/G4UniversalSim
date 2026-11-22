#pragma once
#include <string>
class G4Material;
class G4VPhysicalVolume;
namespace engineering_water {
// Written by the master during configuration and geometry initialization;
// read by workers after the native initialization barrier.
inline const G4Material* acceptedMaterial=nullptr;
inline const G4VPhysicalVolume* acceptedWorld=nullptr;
inline bool thermal=false;
inline bool thinWorld=false;
inline bool captureFirstWorkerState=false;
inline std::string parsedMainSha256;
inline double requestedTemperature=0;
}
