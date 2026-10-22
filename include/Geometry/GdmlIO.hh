#pragma once

// GDML import/export through Geant4's G4GDMLParser (roadmap A5).
//
// Compiled with G4USIM_HAVE_GDML only when the Geant4 installation provides
// GDML (Geant4_gdml_FOUND, XercesC). Without it every function except
// Available() throws with an explanation, so configurations fail before any
// geometry object is created.

#include <string>
#include <vector>

class G4LogicalVolume;
class G4VPhysicalVolume;

namespace GdmlIO {

bool Available();

struct ImportResult {
    G4VPhysicalVolume* world = nullptr;
    // Logical volumes tagged <auxiliary auxtype="SensDet"> in the file.
    std::vector<G4LogicalVolume*> auxSensitive;
};

// Reads the file (optional XML schema validation, optional overlap check).
// The parser is kept alive for the lifetime of the process.
ImportResult Read(const std::string& path, bool validate, bool checkOverlaps);

// Writes the world to a new file (refuses to overwrite). Names are written
// without pointer suffixes so they stay readable and re-importable.
void Write(const std::string& path, G4VPhysicalVolume* world);

}  // namespace GdmlIO
