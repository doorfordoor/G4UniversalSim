#pragma once

// Builds the Geant4 field objects for one thread from a FieldConfig (called
// from DetectorConstruction::ConstructSDandField on the master and on every
// worker). Pure magnetic fields use G4Mag_UsualEqRhs on a G4MagneticField;
// fields with an electric part use G4EqMagElectricField on a
// G4ElectroMagneticField (energy changes). Both integrate with
// G4DormandPrince745. The objects live for the rest of the thread (G4AutoDelete).

class FieldConfig;

namespace FieldSetup {

void Construct(const FieldConfig& config);

}  // namespace FieldSetup
