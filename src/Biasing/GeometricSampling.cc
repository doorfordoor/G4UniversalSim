#include "Biasing/BiasingManager.hh"
#include "Biasing/BiasingImportance.hh"
#include "Biasing/detail/GeometricSamplingObservation.hh"
#include "Config/ConfigManager.hh"
#include "Config/EffectiveRuntime.hh"
#include "Geometry/GeometryRegistry.hh"
#include "Scoring/ScoringManager.hh"
#include "Scoring/ThreadLocalScoringContext.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include "G4GeometryCell.hh"
#include "G4ImportanceAlgorithm.hh"
#include "G4ImportanceProcess.hh"
#include "G4IStore.hh"
#include "G4LogicalVolume.hh"
#include "G4ParticleTable.hh"
#include "G4ParticleDefinition.hh"
#include "G4ProcessManager.hh"
#include "G4ProcessPlacer.hh"
#include "G4Threading.hh"
#include "G4TransportationManager.hh"
#include "G4Navigator.hh"
#include "G4VModularPhysicsList.hh"
#include "G4VPhysicalVolume.hh"
#include "G4VSampler.hh"
#include "G4WeightWindowAlgorithm.hh"
#include "G4WeightWindowProcess.hh"
#include "G4WeightWindowStore.hh"

#include <cmath>
#include <cstdint>
#include <memory>
#include <limits>
#include <iostream>
#include <set>
#include <sstream>
#include <stdexcept>

namespace {
using biasing_detail::SamplingObservation;
using biasing_detail::ObservedImportanceAlgorithm;
using biasing_detail::ObservedWeightWindowAlgorithm;
using biasing_detail::WeightWindowStore;
void Require(bool ok, const std::string& why)
{
    if (!ok) throw std::runtime_error("H4 mass geometry sampling: " + why);
}
std::string Pointer(const void* pointer)
{
    std::ostringstream out; out << pointer; return out.str();
}
// Thread state owns the native process; each process owns its native algorithm.
// Cleanup removes the process while its PM still exists, before deletion.
// The native base destructors do not dereference the algorithms.
class ImportanceProcess final : public G4ImportanceProcess {
public:
    ImportanceProcess(std::unique_ptr<G4ImportanceAlgorithm> algorithm, const G4VIStore& store)
        : G4ImportanceProcess(*algorithm, store, nullptr, "H4ImportanceProcess", false),
          algorithm_(std::move(algorithm)) {}
private:
    std::unique_ptr<G4ImportanceAlgorithm> algorithm_;
};
class WeightWindowProcess final : public G4WeightWindowProcess {
public:
    WeightWindowProcess(std::unique_ptr<G4WeightWindowAlgorithm> algorithm, const G4VWeightWindowStore& store)
        : G4WeightWindowProcess(*algorithm, store, nullptr, onBoundary, "H4WeightWindowProcess", false),
          algorithm_(std::move(algorithm)) {}
private:
    std::unique_ptr<G4WeightWindowAlgorithm> algorithm_;
};
#if G4VERSION_NUMBER >= 1140
using biasing_detail::ImportanceStore;
constexpr const char* storeOwner = "execution_thread_state; owned Geant4 store interface implementation";
constexpr const char* bindingDescription = "Actual execution-thread native process and owned interface store/cell readback";
#else
constexpr const char* storeOwner = "execution_thread_state; native store implementation";
constexpr const char* bindingDescription = "Actual execution-thread native process and owned native store/cell readback";
// The native stores have protected ctors/dtors and unmanaged singleton APIs.
// Expose only ownership, retaining all native lookup/insertion semantics. Each
// execution thread owns its store; no GetInstance singleton is created/deleted.
class ImportanceStore final : public G4IStore {
public:
    ImportanceStore() = default;
    ~ImportanceStore() override = default;
};
#endif
}

struct BiasingManager::GeometricThreadState {
    G4VPhysicalVolume* world = nullptr;
    SamplingObservation observation;
    std::unique_ptr<ImportanceStore> importanceStore;
    std::unique_ptr<WeightWindowStore> windowStore;
    int creatorThreadId = G4Threading::G4GetThreadId();
    G4ProcessManager* manager = nullptr;
    std::unique_ptr<G4VProcess> process;
};

bool BiasingManager::IsGeometricSamplingEnabled() const { return geometricConfig_.Enabled(); }
const GeometricSamplingConfig& BiasingManager::GetGeometricSamplingConfig() const { return geometricConfig_; }

void BiasingManager::LoadGeometricSamplingConfig(const ConfigManager& config)
{
    GeometricSamplingConfig next;
    const std::string section = "biasing.geometry";
    next.mode = StringUtils::ToLower(StringUtils::Trim(config.GetString(section, "mode", "off")));
    Require(next.mode == "off" || next.mode == "importance" || next.mode == "weight_window",
            "[biasing.geometry]/mode must be off, importance or weight_window");
    next.particle = StringUtils::ToLower(StringUtils::Trim(config.GetString(section, "particle", "neutron")));
    if (next.Enabled()) {
        Require(next.particle == "neutron", "only neutron mass-geometry sampling is supported");
        Require(!interactiveSessionMode_, "use a fresh batch process; interactive sampling is unsupported");
        Require(!config.GetBool("run", "interactive", false), "[run]/interactive must be false");
        Require(!config.GetBool("biasing", "enabled", false), "geometric sampling cannot be combined with the legacy XS gate");
        Require(!config.GetBool("physics", "biasing", false), "geometric sampling cannot be combined with generic XS physics");
    }
    if (next.mode == "weight_window") {
        for (const auto& text : config.GetVector(section, "energy_upper_bounds", std::vector<std::string>{}))
            next.energyUpperBounds.push_back(StringUtils::ToLower(StringUtils::Trim(text)) == "inf"
                ? std::numeric_limits<double>::infinity() : UnitParser::ParseEnergy(text));
        Require(!next.energyUpperBounds.empty(), "weight_window requires energy_upper_bounds");
        Require(next.energyUpperBounds.back() == std::numeric_limits<double>::infinity(),
                "energy_upper_bounds must end with explicit inf to cover every finite kinetic energy");
        double previous = 0;
        for (std::size_t i = 0; i < next.energyUpperBounds.size(); ++i) {
            double bound = next.energyUpperBounds[i];
            Require(bound > previous && (std::isfinite(bound) || i + 1 == next.energyUpperBounds.size()),
                    "energy_upper_bounds must be positive and strictly increasing, with inf only last");
            previous = bound;
        }
        next.upperLimitFactor = config.GetDouble(section, "upper_limit_factor", 5.0);
        next.survivalFactor = config.GetDouble(section, "survival_factor", 3.0);
        next.maxNumberOfSplits = config.GetInt(section, "max_number_of_splits", 5);
        Require(std::isfinite(next.upperLimitFactor) && std::isfinite(next.survivalFactor)
                && next.upperLimitFactor >= next.survivalFactor && next.survivalFactor >= 1,
                "require 1 <= survival_factor <= upper_limit_factor");
        Require(next.maxNumberOfSplits > 0, "max_number_of_splits must be positive");
    } else {
        for (const char* key : {"energy_upper_bounds", "upper_limit_factor", "survival_factor", "max_number_of_splits"})
            Require(!config.HasKey(section, key), std::string(key) + " is only valid for weight_window");
    }
    for (const auto& info : config.GetSectionInfo()) {
        const auto name = StringUtils::ToLower(StringUtils::Trim(info.section));
        if (!StringUtils::StartsWith(name, "biasing.geometry.cell.")) continue;
        Require(next.Enabled(), "cell declarations require an active geometric mode");
        GeometricSamplingCell cell;
        cell.section = info.section;
        cell.volume = StringUtils::Trim(config.GetString(info.section, "volume"));
        Require(!cell.volume.empty(), info.section + "/volume is required");
        cell.copyNumber = config.GetInt(info.section, "copy_number", 0);
        Require(cell.copyNumber >= 0, info.section + "/copy_number must be nonnegative");
        if (next.mode == "importance") {
            Require(config.HasKey(info.section, "importance"), info.section + "/importance is required");
            cell.importance = config.GetDouble(info.section, "importance");
            Require(std::isfinite(cell.importance) && cell.importance > 0, info.section + "/importance must be finite and positive");
            Require(!config.HasKey(info.section, "lower_weights"), "lower_weights requires weight_window mode");
        } else {
            Require(!config.HasKey(info.section, "importance"), "importance requires importance mode");
            for (const auto& text : config.GetVector(info.section, "lower_weights", std::vector<std::string>{}))
                cell.lowerWeights.push_back(UnitParser::ParseDouble(text));
            Require(cell.lowerWeights.size() == next.energyUpperBounds.size(), info.section + "/lower_weights must match every energy upper bound");
            for (double value : cell.lowerWeights)
                Require(std::isfinite(value) && value > 0 && std::isfinite(value * next.upperLimitFactor),
                        info.section + "/lower_weights and derived upper weights must be finite and positive");
        }
        next.cells.push_back(std::move(cell));
    }
    Require(!next.Enabled() || !next.cells.empty(), "active mode requires explicit cells, including world");
    geometricConfig_ = std::move(next);
}

void BiasingManager::RegisterGeometricSamplingPhysics(G4VModularPhysicsList* list) const
{
    if (IsGeometricSamplingEnabled()) list->RegisterPhysics(new BiasingImportance(this));
}

void BiasingManager::BindGeometricSamplingCells(const GeometryRegistry& registry)
{
    if (!IsGeometricSamplingEnabled()) return;
    Require(!geometricWorld_, "geometry reconstruction is unsupported; start a fresh process");
    G4VPhysicalVolume* world = nullptr;
    for (const auto& name : registry.GetPhysicalVolumeNames()) {
        auto* volume = registry.GetPhysicalVolume(name);
        if (!volume->GetMotherLogical()) {
            Require(!world || world == volume, "mass world is ambiguous");
            world = volume;
        }
    }
    Require(world != nullptr, "mass world is not registered");
    std::set<G4VPhysicalVolume*> placements;
    std::vector<G4VPhysicalVolume*> pending{world};
    while (!pending.empty()) {
        auto* volume = pending.back(); pending.pop_back();
        Require(placements.insert(volume).second, "reused placement path is ambiguous");
        Require(!volume->IsReplicated() && !volume->IsParameterised(), "only ordinary placements are supported, including all daughters");
        auto* logical = volume->GetLogicalVolume();
        for (int i = 0; i < logical->GetNoDaughters(); ++i) pending.push_back(logical->GetDaughter(i));
    }
    std::vector<GeometricBoundCell> bound;
    std::set<G4VPhysicalVolume*> declared;
    for (const auto& cell : geometricConfig_.cells) {
        auto* volume = registry.GetPhysicalVolume(cell.volume);
        Require(placements.count(volume) != 0, cell.section + " is outside current mass world");
        Require(volume->GetCopyNo() == cell.copyNumber, cell.section + " copy_number differs from actual physical placement");
        Require(declared.insert(volume).second, "duplicate physical cell in " + cell.section);
        bound.push_back({volume, cell});
    }
    Require(declared == placements, "every mass placement must have exactly one cell declaration, including world");
    geometricCells_ = std::move(bound);
    geometricWorld_ = world;
}

void BiasingManager::ConstructGeometricSamplingProcess() const
{
    if (!IsGeometricSamplingEnabled()) return;
    Require(geometricWorld_ && !geometricCells_.empty(), "geometry cells were not bound before ConstructProcess");
    Require(!geometricThreadState_.Get(), "physics reconstruction is unsupported; start a fresh process");
    auto* particle = G4ParticleTable::GetParticleTable()->FindParticle(geometricConfig_.particle);
    Require(particle && particle->GetProcessManager(), "neutron process manager is unavailable");
    auto* manager = particle->GetProcessManager();
    for (int i = 0; i < manager->GetProcessListLength(); ++i)
        Require(!dynamic_cast<G4ImportanceProcess*>((*manager->GetProcessList())[i])
                && !dynamic_cast<G4WeightWindowProcess*>((*manager->GetProcessList())[i]), "another geometric sampling process is already registered");
    auto state = std::make_unique<GeometricThreadState>();
    state->world = geometricWorld_;
    state->manager = manager;
#if G4VERSION_NUMBER >= 1140
    auto* trackingWorld = G4TransportationManager::GetTransportationManager()
                              ->GetNavigatorForTracking()->GetWorldVolume();
    Require(trackingWorld == geometricWorld_, "execution-thread tracking world differs from bound mass world");
#endif
    std::unique_ptr<G4VProcess> process;
    if (geometricConfig_.mode == "importance") {
#if G4VERSION_NUMBER >= 1140
        state->importanceStore = std::make_unique<ImportanceStore>(*trackingWorld);
#else
        state->importanceStore = std::make_unique<ImportanceStore>();
        state->importanceStore->SetWorldVolume();
#endif
        auto* store = state->importanceStore.get();
        Require(&store->GetWorldVolume() == geometricWorld_, "TLS importance store world differs from current mass world");
#if G4VERSION_NUMBER < 1140
        store->Clear();
#endif
        for (const auto& cell : geometricCells_)
            store->AddImportanceGeometryCell(cell.config.importance, *cell.physical, cell.config.copyNumber);
        process = std::make_unique<ImportanceProcess>(std::make_unique<ObservedImportanceAlgorithm>(state->observation), *store);
    } else {
#if G4VERSION_NUMBER >= 1140
        state->windowStore = std::make_unique<WeightWindowStore>(state->observation, *trackingWorld);
#else
        state->windowStore = std::make_unique<WeightWindowStore>(state->observation);
        state->windowStore->SetWorldVolume();
#endif
        auto* store = state->windowStore.get();
        Require(&store->GetWorldVolume() == geometricWorld_, "TLS weight-window store world differs from current mass world");
#if G4VERSION_NUMBER < 1140
        store->Clear();
#endif
        for (const auto& cell : geometricCells_) {
            G4UpperEnergyToLowerWeightMap weights;
            for (std::size_t i = 0; i < geometricConfig_.energyUpperBounds.size(); ++i)
                weights.emplace(geometricConfig_.energyUpperBounds[i], cell.config.lowerWeights[i]);
            store->AddUpperEboundLowerWeightPairs(G4GeometryCell(*cell.physical, cell.config.copyNumber), weights);
        }
        process = std::make_unique<WeightWindowProcess>(std::make_unique<ObservedWeightWindowAlgorithm>(
            geometricConfig_.upperLimitFactor, geometricConfig_.survivalFactor, geometricConfig_.maxNumberOfSplits, state->observation), *store);
    }
    G4ProcessPlacer placer(geometricConfig_.particle);
    placer.AddProcessAsSecondDoIt(process.get());
    state->process = std::move(process);
    auto* installed = state.release();
    geometricThreadState_.Put(installed);
    std::lock_guard<std::mutex> lock(evidenceMutex_);
    std::cout << "[G4USimH4] {\"stage\":\"constructed\",\"thread_id\":" << installed->creatorThreadId
              << ",\"mode\":\"" << geometricConfig_.mode << "\",\"cell_count\":" << geometricCells_.size()
              << ",\"process\":\"" << installed->process->GetProcessName() << "\",\"store_owner\":\"thread_state\"}\n";
}

void BiasingManager::TerminateGeometricSamplingThread() const
{
    auto* state = geometricThreadState_.Get();
    if (!state) return;
    // Both the worker hook and master constructor destructor run before the
    // physics list removes process managers. DeRegister occurs in VProcess dtor.
    state->manager->RemoveProcess(state->process.get());
    bool removed = true;
    for (int i = 0; i < state->manager->GetProcessListLength(); ++i)
        removed = removed && (*state->manager->GetProcessList())[i] != state->process.get();
    const int threadId = state->creatorThreadId;
    state->process.reset();
    geometricThreadState_.Put(nullptr);
    delete state;
    std::lock_guard<std::mutex> lock(evidenceMutex_);
    std::cout << "[G4USimH4] {\"stage\":\"terminated\",\"thread_id\":" << threadId
              << ",\"process_removed\":" << (removed ? "true" : "false")
              << ",\"owned_process_algorithm_store_released\":true}\n";
}

void BiasingManager::ValidateGeometricSamplingThread(int runId, bool endRun) const
{
    if (!IsGeometricSamplingEnabled()) return;
    using effective_config::Value;
    auto* state = geometricThreadState_.Get();
    Require(state && state->world == geometricWorld_ && state->creatorThreadId == G4Threading::G4GetThreadId(),
            "execution thread has no current sampling state");
    if (!endRun) state->observation.Reset(runId);
    else {
        Require(state->observation.runId == runId, "observation run identity differs");
        state->observation.active = false;
    }
    auto* particle = G4ParticleTable::GetParticleTable()->FindParticle(geometricConfig_.particle);
    Require(particle && particle->GetProcessManager(), "execution-thread neutron process manager is unavailable");
    auto* manager = particle->GetProcessManager();
    int matches = 0;
    for (int i = 0; i < manager->GetProcessListLength(); ++i)
        if ((*manager->GetProcessList())[i] == state->process.get()) ++matches;
    Require(matches == 1, "execution-thread native sampling process binding differs");
    Require(G4TransportationManager::GetTransportationManager()->GetNavigatorForTracking()->GetWorldVolume() == state->world,
            "execution-thread navigator world differs");
    Value::Array cells;
    for (const auto& cell : geometricCells_) {
        Require(cell.physical->GetCopyNo() == cell.config.copyNumber, "execution-thread cell copy changed");
        const G4GeometryCell key(*cell.physical, cell.config.copyNumber);
        Value::Object row{{"volume", cell.config.volume}, {"physical_name", std::string(cell.physical->GetName())},
            {"physical_pointer", Pointer(cell.physical)}, {"copy_number", cell.config.copyNumber}};
        if (state->importanceStore) {
            Require(&state->importanceStore->GetWorldVolume() == state->world
                    && state->importanceStore->IsKnown(key), "execution-thread importance TLS store/cell differs");
            double value = state->importanceStore->GetImportance(key);
            Require(value == cell.config.importance, "actual importance value differs");
            row["importance"] = value;
        } else {
            Require(&state->windowStore->GetWorldVolume() == state->world
                    && state->windowStore->IsKnown(key), "execution-thread weight-window TLS store/cell differs");
            Value::Array windows;
            double previous = 0;
            for (std::size_t i = 0; i < geometricConfig_.energyUpperBounds.size(); ++i) {
                double bound = geometricConfig_.energyUpperBounds[i];
                double probe = std::isfinite(bound) ? previous + (bound - previous) / 2 : std::numeric_limits<double>::max();
                double value = state->windowStore->ReadLowerWeight(key, probe);
                Require(value == cell.config.lowerWeights[i], "actual energy-window lower weight differs");
                Require(state->windowStore->ReadLowerWeight(key, previous) == cell.config.lowerWeights[i],
                        "actual energy-window equality boundary differs");
                Value upper = std::isfinite(bound) ? Value(bound) : Value("inf");
                windows.emplace_back(Value::Object{{"energy_lower_MeV", previous}, {"energy_upper_MeV", upper}, {"lower_weight", value},
                    {"boundary_equal_verified", true}, {"interior_probe_MeV", probe},
                    {"upper_weight", value * geometricConfig_.upperLimitFactor}, {"survival_weight", value * geometricConfig_.survivalFactor}});
                previous = bound;
            }
            row["windows"] = std::move(windows);
        }
        cells.emplace_back(std::move(row));
    }
    const int threadId = G4Threading::G4GetThreadId();
    Value evidence(Value::Object{{"run_id", runId}, {"thread_id", threadId}, {"mode", geometricConfig_.mode},
        {"process", std::string(state->process->GetProcessName())}, {"process_pointer", Pointer(state->process.get())},
        {"store_pointer", Pointer(state->importanceStore ? static_cast<const void*>(state->importanceStore.get()) : state->windowStore.get())},
        {"store_owner", storeOwner},
        {"world_pointer", Pointer(state->world)}, {"tls_verified", true}, {"end_run_completed", endRun},
        {"upper_limit_factor", geometricConfig_.upperLimitFactor}, {"survival_factor", geometricConfig_.survivalFactor},
        {"max_number_of_splits", geometricConfig_.maxNumberOfSplits}, {"cells", std::move(cells)},
        {"algorithm_source", "Geant4 native algorithm owned by native sampling process"},
        {"physical_effect_status", "not_validated"}});
    auto& observationFields = std::get<Value::Object>(evidence.data);
    for (const auto& field : state->observation.Fields()) observationFields[field.first] = field.second;
    const bool observationValid = !state->observation.invalidEnergy && !state->observation.overflow && state->observation.invalidReturn == 0;
    auto receipt = effective_config::Receipt(effective_config::ObjectFieldPath("biasing", "geometry", "mode"), geometricConfig_.mode,
        endRun ? "run_end" : "run_begin", bindingDescription,
        "thread_applied", observationValid ? "applied" : "failed", "Engineering binding only; no unbiasedness or efficiency validation");
    std::get<Value::Object>(receipt.data)["native_binding"] = evidence;
    effectiveState_->Record(std::move(receipt));
    std::lock_guard<std::mutex> lock(evidenceMutex_);
    geometricEvidence_[{runId, threadId}] = std::move(evidence);
    Require(observationValid, "native sampling observation failed: invalid tracked neutron energy, algorithm return or counter overflow");
}

effective_config::Value BiasingManager::ExportGeometricSamplingEvidence() const
{
    effective_config::Value::Array result;
    std::lock_guard<std::mutex> lock(evidenceMutex_);
    for (const auto& row : geometricEvidence_) result.push_back(row.second);
    return result;
}
