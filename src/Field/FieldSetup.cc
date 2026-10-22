#include "Field/FieldSetup.hh"

#include "Field/FieldConfig.hh"

#include "G4AutoDelete.hh"
#include "G4ChordFinder.hh"
#include "G4DormandPrince745.hh"
#include "G4ElectroMagneticField.hh"
#include "G4EqMagElectricField.hh"
#include "G4FieldManager.hh"
#include "G4LogicalVolume.hh"
#include "G4LogicalVolumeStore.hh"
#include "G4MagIntegratorDriver.hh"
#include "G4MagneticField.hh"
#include "G4Mag_UsualEqRhs.hh"
#include "G4TransportationManager.hh"

#include <stdexcept>
#include <string>

namespace {

// Uniform values or maps for B and/or E, evaluated in global coordinates.
void Evaluate(const FieldSpec& spec, const G4double point[4], G4double* field)
{
    const G4ThreeVector position(point[0], point[1], point[2]);
    const G4ThreeVector b = spec.magneticMap ? spec.magneticMap->Value(position) : spec.magnetic;
    field[0] = b.x();
    field[1] = b.y();
    field[2] = b.z();
    if (spec.hasElectric) {
        const G4ThreeVector e = spec.electricMap ? spec.electricMap->Value(position) : spec.electric;
        field[3] = e.x();
        field[4] = e.y();
        field[5] = e.z();
    }
}

// B only: driven by G4Mag_UsualEqRhs.
class ConfiguredMagneticField : public G4MagneticField {
public:
    explicit ConfiguredMagneticField(const FieldSpec& spec) : spec_(spec) {}
    void GetFieldValue(const G4double point[4], G4double* field) const override { Evaluate(spec_, point, field); }

private:
    FieldSpec spec_;  // copies share the read-only maps
};

// B and E (field[3..5]): driven by G4EqMagElectricField, changes the energy.
class ConfiguredElectroMagneticField : public G4ElectroMagneticField {
public:
    explicit ConfiguredElectroMagneticField(const FieldSpec& spec) : spec_(spec) {}
    void GetFieldValue(const G4double point[4], G4double* field) const override { Evaluate(spec_, point, field); }
    G4bool DoesFieldChangeEnergy() const override { return true; }

private:
    FieldSpec spec_;
};

G4FieldManager* MakeFieldManager(const FieldSpec& spec, G4FieldManager* existing)
{
    G4Field* field = nullptr;
    G4MagIntegratorStepper* stepper = nullptr;
    G4int variables = 6;
    if (spec.hasElectric) {
        auto* emField = new ConfiguredElectroMagneticField(spec);
        auto* equation = new G4EqMagElectricField(emField);
        G4AutoDelete::Register(emField);
        G4AutoDelete::Register(equation);
        variables = 8;
        stepper = new G4DormandPrince745(equation, variables);
        field = emField;
    } else {
        auto* magField = new ConfiguredMagneticField(spec);
        auto* equation = new G4Mag_UsualEqRhs(magField);
        G4AutoDelete::Register(magField);
        G4AutoDelete::Register(equation);
        stepper = new G4DormandPrince745(equation, variables);
        field = magField;
    }
    auto* driver = new G4MagInt_Driver(spec.minStep, stepper, variables);
    auto* chordFinder = new G4ChordFinder(driver);
    chordFinder->SetDeltaChord(spec.deltaChord);
    G4AutoDelete::Register(chordFinder);  // owns the driver and the stepper

    // G4FieldManagerStore owns and deletes every G4FieldManager; do not register it.
    G4FieldManager* manager = existing ? existing : new G4FieldManager();
    manager->SetDetectorField(field);
    manager->SetChordFinder(chordFinder);
    manager->SetDeltaOneStep(spec.deltaOneStep);
    manager->SetDeltaIntersection(spec.deltaIntersection);
    return manager;
}

}  // namespace

namespace FieldSetup {

void Construct(const FieldConfig& config)
{
    for (const FieldSpec& spec : config.GetFields()) {
        if (spec.IsGlobal()) {
            MakeFieldManager(spec, G4TransportationManager::GetTransportationManager()->GetFieldManager());
            continue;
        }
        G4FieldManager* manager = MakeFieldManager(spec, nullptr);
        for (const std::string& volume : spec.volumes) {
            G4LogicalVolume* logical = G4LogicalVolumeStore::GetInstance()->GetVolume(volume, false);
            if (!logical) logical = G4LogicalVolumeStore::GetInstance()->GetVolume(volume + "_LV", false);
            if (!logical) {
                throw std::runtime_error("[field." + spec.name + "]/volumes names unknown logical volume '" + volume + "'");
            }
            // Also applies to daughters that do not have a field manager of their own.
            logical->SetFieldManager(manager, false);
        }
    }
}

}  // namespace FieldSetup
