#include "Physics/ProcessDump.hh"

#include "G4GammaGeneralProcess.hh"
#include "G4HadronicInteraction.hh"
#include "G4HadronicParameters.hh"
#include "G4HadronicProcess.hh"
#include "G4LogicalVolume.hh"
#include "G4MaterialCutsCouple.hh"
#include "G4ParticleDefinition.hh"
#include "G4ParticleTable.hh"
#include "G4ProcessManager.hh"
#include "G4ProcessVector.hh"
#include "G4ProductionCuts.hh"
#include "G4ProductionCutsTable.hh"
#include "G4Region.hh"
#include "G4RegionStore.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4Track.hh"
#include "G4UserLimits.hh"
#include "G4VEmModel.hh"
#include "G4VEmProcess.hh"
#include "G4VEnergyLossProcess.hh"
#include "G4VModularPhysicsList.hh"
#include "G4VMscModel.hh"
#include "G4VMultipleScattering.hh"
#include "G4VPhysicsConstructor.hh"
#include "G4VProcess.hh"
#include "G4VUserPhysicsList.hh"

#include <cfloat>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace {

std::string Escape(const std::string& text)
{
    std::string out;
    for (char c : text) {
        if (c == '"' || c == '\\') out += '\\';
        out += c;
    }
    return out;
}

std::string Number(double value)
{
    if (value >= DBL_MAX * 0.5) return "null";
    std::ostringstream out;
    out << std::setprecision(10) << value;
    return out.str();
}

struct Model {
    std::string name;
    double emin = 0.0;
    double emax = 0.0;
};

void AddEmModel(std::vector<Model>& models, const G4VEmModel* model)
{
    if (model) models.push_back({model->GetName(), model->LowEnergyLimit(), model->HighEnergyLimit()});
}

std::vector<Model> ModelsOf(G4VProcess* process)
{
    std::vector<Model> models;
    if (auto* em = dynamic_cast<G4VEmProcess*>(process)) {
        for (G4int i = 0; i < em->NumberOfModels(); ++i) AddEmModel(models, em->EmModel(i));
    } else if (auto* loss = dynamic_cast<G4VEnergyLossProcess*>(process)) {
        for (std::size_t i = 0; i < loss->NumberOfModels(); ++i) AddEmModel(models, loss->EmModel(i));
    } else if (auto* msc = dynamic_cast<G4VMultipleScattering*>(process)) {
        for (G4int i = 0; i < msc->NumberOfModels(); ++i) AddEmModel(models, msc->EmModel(i));
    } else if (auto* hadronic = dynamic_cast<G4HadronicProcess*>(process)) {
        for (G4HadronicInteraction* interaction : hadronic->GetHadronicInteractionList()) {
            if (interaction) {
                models.push_back({interaction->GetModelName(), interaction->GetMinEnergy(), interaction->GetMaxEnergy()});
            }
        }
    }
    return models;
}

void WriteModels(std::ostream& out, const std::vector<Model>& models)
{
    out << "[";
    for (std::size_t m = 0; m < models.size(); ++m) {
        out << (m ? ", " : "") << "{\"name\": \"" << Escape(models[m].name) << "\", \"emin\": "
            << Number(models[m].emin / MeV) << ", \"emax\": " << Number(models[m].emax / MeV) << "}";
    }
    out << "]";
}

void WriteProductionCuts(std::ostream& out, const G4ProductionCuts* cuts)
{
    out << "{";
    if (cuts) {
        out << "\"gamma\": " << Number(cuts->GetProductionCut("gamma") / mm) << ", \"e-\": "
            << Number(cuts->GetProductionCut("e-") / mm) << ", \"e+\": " << Number(cuts->GetProductionCut("e+") / mm)
            << ", \"proton\": " << Number(cuts->GetProductionCut("proton") / mm);
    }
    out << "}";
}

}  // namespace

namespace ProcessDump {

int WriteJson(const std::string& path, const std::vector<std::string>& requested)
{
    G4RunManager* runManager = G4RunManager::GetRunManager();
    if (!runManager || !runManager->GetUserPhysicsList()) {
        throw std::runtime_error("dumpProcesses: no physics list; run /run/initialize first");
    }
    G4ProductionCutsTable* cutsTable = G4ProductionCutsTable::GetProductionCutsTable();
    if (cutsTable->GetTableSize() == 0) {
        throw std::runtime_error("dumpProcesses: no material-cuts couples yet; run /run/initialize first");
    }
    std::vector<std::string> particles = requested;
    if (particles.empty()) {
        particles = {"gamma", "e-", "e+", "proton", "neutron", "alpha", "GenericIon", "mu-", "mu+", "pi-", "pi+"};
    }

    std::ostringstream out;
    out << "{\"schema\": \"g4usim_process_dump_v1\", \"energy_unit\": \"MeV\", \"length_unit\": \"mm\",\n";
    const auto* modular = dynamic_cast<const G4VModularPhysicsList*>(runManager->GetUserPhysicsList());
    out << " \"physics_list\": {\"constructors\": [";
    if (modular) {
        for (G4int index = 0;; ++index) {
            const G4VPhysicsConstructor* physics = modular->GetPhysics(index);
            if (!physics) break;
            out << (index ? ", " : "") << "\"" << Escape(physics->GetPhysicsName()) << "\"";
        }
    }
    // A negative threshold means "not set": Geant4 then uses its built-in default (1 year).
    const double threshold = G4HadronicParameters::Instance()->GetTimeThresholdForRadioactiveDecay();
    out << "]},\n \"radioactive_decay\": {\"time_threshold_years\": "
        << (threshold > 0.0 ? Number(threshold / CLHEP::year) : std::string("null"))
        << ", \"geant4_default\": " << (threshold > 0.0 ? "false" : "true") << "},\n";

    out << " \"particles\": [";
    int written = 0;
    for (const std::string& name : particles) {
        G4ParticleDefinition* particle = G4ParticleTable::GetParticleTable()->FindParticle(name);
        if (!particle) throw std::runtime_error("dumpProcesses: unknown particle '" + name + "'");
        G4ProcessManager* manager = particle->GetProcessManager();
        out << (written ? ",\n  " : "\n  ") << "{\"name\": \"" << Escape(name) << "\", \"pdg\": "
            << particle->GetPDGEncoding() << ", \"processes\": [";
        if (manager) {
            G4ProcessVector* list = manager->GetProcessList();
            for (G4int i = 0; i < static_cast<G4int>(list->size()); ++i) {
                G4VProcess* process = (*list)[i];
                out << (i ? ",\n    " : "\n    ") << "{\"name\": \"" << Escape(process->GetProcessName())
                    << "\", \"type\": \"" << Escape(G4VProcess::GetProcessTypeName(process->GetProcessType()))
                    << "\", \"sub_type\": " << process->GetProcessSubType() << ", \"active\": "
                    << (manager->GetProcessActivation(process) ? "true" : "false") << ", \"models\": ";
                WriteModels(out, ModelsOf(process));
                // Geant4 11 wraps the gamma processes in G4GammaGeneralProcess.
                if (auto* general = dynamic_cast<G4GammaGeneralProcess*>(process)) {
                    out << ", \"sub_processes\": [";
                    bool firstSub = true;
                    for (const char* sub : {"phot", "compt", "conv", "Rayl"}) {
                        G4VEmProcess* subProcess = general->GetEmProcess(sub);
                        if (!subProcess) continue;
                        out << (firstSub ? "" : ", ") << "{\"name\": \"" << sub << "\", \"models\": ";
                        WriteModels(out, ModelsOf(subProcess));
                        out << "}";
                        firstSub = false;
                    }
                    out << "]";
                }
                out << "}";
            }
        }
        out << "]}";
        ++written;
    }
    out << "\n ],\n \"regions\": [";
    bool firstRegion = true;
    for (const G4Region* region : *G4RegionStore::GetInstance()) {
        out << (firstRegion ? "\n  " : ",\n  ") << "{\"name\": \"" << Escape(region->GetName()) << "\", \"root_volumes\": [";
        firstRegion = false;
        bool firstRoot = true;
        auto roots = const_cast<G4Region*>(region)->GetRootLogicalVolumeIterator();
        for (std::size_t i = 0; i < const_cast<G4Region*>(region)->GetNumberOfRootVolumes(); ++i, ++roots) {
            out << (firstRoot ? "" : ", ") << "\"" << Escape((*roots)->GetName()) << "\"";
            firstRoot = false;
        }
        out << "], \"production_cuts_mm\": ";
        WriteProductionCuts(out, region->GetProductionCuts());
        out << ", \"user_limits\": ";
        if (G4UserLimits* limits = region->GetUserLimits()) {  // Geant4 getters are non-const
            G4Track dummy;
            out << "{\"max_step_mm\": " << Number(limits->GetMaxAllowedStep(dummy) / mm)
                << ", \"max_track_length_mm\": " << Number(limits->GetUserMaxTrackLength(dummy) / mm)
                << ", \"max_time_ns\": " << Number(limits->GetUserMaxTime(dummy) / ns)
                << ", \"min_kinetic_energy_MeV\": " << Number(limits->GetUserMinEkine(dummy) / MeV) << "}";
        } else {
            out << "null";
        }
        out << "}";
    }
    out << "\n ],\n \"couples\": [";
    const char* particlesForCuts[4] = {"gamma", "e-", "e+", "proton"};
    for (std::size_t i = 0; i < cutsTable->GetTableSize(); ++i) {
        const G4MaterialCutsCouple* couple = cutsTable->GetMaterialCutsCouple(static_cast<G4int>(i));
        std::string regionName;
        for (const G4Region* region : *G4RegionStore::GetInstance()) {
            if (region->GetProductionCuts() == couple->GetProductionCuts()) {
                regionName = region->GetName();
                break;
            }
        }
        out << (i ? ",\n  " : "\n  ") << "{\"material\": \"" << Escape(couple->GetMaterial()->GetName())
            << "\", \"region\": \"" << Escape(regionName) << "\", \"used\": " << (couple->IsUsed() ? "true" : "false")
            << ", \"range_cuts_mm\": ";
        WriteProductionCuts(out, couple->GetProductionCuts());
        out << ", \"energy_cuts_MeV\": {";
        for (std::size_t p = 0; p < 4; ++p) {
            const std::vector<G4double>* energies = cutsTable->GetEnergyCutsVector(p);
            out << (p ? ", " : "") << "\"" << particlesForCuts[p] << "\": "
                << Number(energies && i < energies->size() ? (*energies)[i] / MeV : 0.0);
        }
        out << "}}";
    }
    out << "\n ]\n}\n";

    const std::filesystem::path file = std::filesystem::u8path(path);
    if (file.has_parent_path()) std::filesystem::create_directories(file.parent_path());
    std::ofstream stream(file);
    if (!stream) throw std::runtime_error("dumpProcesses: cannot write '" + path + "'");
    stream << out.str();
    stream.close();
    if (!stream) throw std::runtime_error("dumpProcesses: failed to write '" + path + "'");
    return written;
}

}  // namespace ProcessDump
