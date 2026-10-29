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
#include "G4VPhysicalVolume.hh"

#include <functional>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

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

void ConstructImpl(const FieldConfig& config, bool validateOnly)
{
    if (config.GetFields().empty()) return;
    auto* store = G4LogicalVolumeStore::GetInstance();
    std::map<G4LogicalVolume*, const FieldSpec*> explicitFields;
    const FieldSpec* global = nullptr;
    for (const FieldSpec& spec : config.GetFields()) {
        if (spec.IsGlobal()) {
            global = &spec;
            continue;
        }
        for (const std::string& volume : spec.volumes) {
            const auto unique = [&](const std::string& name) {
                G4LogicalVolume* selected = nullptr;
                for (auto* candidate : *store) {
                    if (candidate->GetName() != name) continue;
                    if (selected && selected != candidate)
                        throw std::runtime_error("ambiguous local field logical volume name '" + name + "'");
                    selected = candidate;
                }
                return selected;
            };
            G4LogicalVolume* logical = unique(volume);
            if (!logical) logical = unique(volume + "_LV");
            if (!logical) {
                throw std::runtime_error("[field." + spec.name + "]/volumes names unknown logical volume '" + volume + "'");
            }
            const auto inserted = explicitFields.emplace(logical, &spec);
            if (!inserted.second && inserted.first->second != &spec) {
                throw std::runtime_error("conflicting explicit local fields for logical volume '" +
                                         std::string(logical->GetName()) + "': [field." +
                                         inserted.first->second->name + "] and [field." + spec.name + "]");
            }
        }
    }

    // Resolve scope before touching Geant4 managers. Logical volumes may be shared
    // by multiple placements; a single thread-local manager cannot represent two
    // different inherited fields on the same logical volume.
    std::set<G4LogicalVolume*> daughters;
    for (auto* logical : *store) {
        for (G4int i = 0; i < logical->GetNoDaughters(); ++i)
            daughters.insert(logical->GetDaughter(i)->GetLogicalVolume());
    }
    std::map<G4LogicalVolume*, const FieldSpec*> resolved;
    std::set<G4LogicalVolume*> active;
    std::vector<G4LogicalVolume*> postorder;
    std::function<void(G4LogicalVolume*, const FieldSpec*)> visit =
        [&](G4LogicalVolume* logical, const FieldSpec* inherited) {
            const auto explicitIt = explicitFields.find(logical);
            const FieldSpec* selected = explicitIt == explicitFields.end() ? inherited : explicitIt->second;
            if (active.count(logical)) throw std::runtime_error("cyclic logical-volume field hierarchy");
            const auto inserted = resolved.emplace(logical, selected);
            if (!inserted.second) {
                if (inserted.first->second != selected)
                    throw std::runtime_error("conflicting inherited local fields for reused logical volume '" +
                                             std::string(logical->GetName()) + "'; bind an explicit field to this volume");
                return;
            }
            active.insert(logical);
            for (G4int i = 0; i < logical->GetNoDaughters(); ++i)
                visit(logical->GetDaughter(i)->GetLogicalVolume(), selected);
            active.erase(logical);
            postorder.push_back(logical);
        };
    for (auto* logical : *store) {
        if (!daughters.count(logical)) visit(logical, nullptr);
    }
    if (resolved.size() != store->size()) throw std::runtime_error("cyclic logical-volume field hierarchy");
    if (validateOnly) return;

    if (global) MakeFieldManager(*global, G4TransportationManager::GetTransportationManager()->GetFieldManager());
    std::map<const FieldSpec*, G4FieldManager*> managers;
    for (const auto& binding : explicitFields) {
        if (!managers.count(binding.second)) managers.emplace(binding.second, MakeFieldManager(*binding.second, nullptr));
    }
    // Descendants are assigned first: false must never preserve an accidental
    // parent inheritance instead of their already resolved nearest explicit field.
    for (auto* logical : postorder) {
        const auto* selected = resolved.at(logical);
        logical->SetFieldManager(selected ? managers.at(selected) : nullptr, false);
    }
}

void Validate(const FieldConfig& config) { ConstructImpl(config, true); }
void Construct(const FieldConfig& config) { ConstructImpl(config, false); }

}  // namespace FieldSetup
