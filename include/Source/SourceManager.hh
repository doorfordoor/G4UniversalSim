#pragma once

#include "Scoring/PhaseSpace.hh"

#include <map>
#include <memory>
#include <string>
#include <utility>
#include <vector>

class ConfigManager;
class G4Event;
class G4GeneralParticleSource;
class G4ParticleDefinition;
class G4SingleParticleSource;

// Primary-particle source on top of Geant4's G4GeneralParticleSource (GPS).
//
// The main INI defines either one source in [source] or several weighted
// sources in [source.<name>] sections (roadmap A4); each maps onto one GPS
// source. Native /gps/... commands remain available for anything not covered.
class SourceManager {
public:
    // Everything one GPS source needs. Lengths, energies and angles are in
    // Geant4 internal units.
    struct SourceSpec {
        std::string name;          // "" for [source], otherwise the [source.<name>] suffix
        double intensity = 1.0;    // relative weight among sources

        std::string particleName;
        bool ion = false;          // particle = ion: ionZ/ionA/ionCharge/ionExcitation
        int ionZ = 0;
        int ionA = 0;
        double ionCharge = 0.0;    // in units of eplus
        double ionExcitation = 0.0;

        // Energy: "mono" (monoEnergy) or an advanced spectrum.
        std::string energyType = "mono";  // mono|gauss|uniform|power|exp|histogram|points
        double monoEnergy = 0.0;
        double energySigma = 0.0;
        double energyMin = 0.0;
        double energyMax = 0.0;
        double alpha = 0.0;
        double ezero = 0.0;
        std::string spectrumFile;
        std::vector<std::pair<double, double>> spectrum;  // histogram: (upper edge, weight), first = (lower edge, 0); points: (E, density)

        // Position. type/shape use GPS names: Point, Plane, Volume, Beam;
        // Circle, Annulus, Ellipse, Square, Rectangle, Sphere, Cylinder, Para.
        bool hasPosition = false;
        std::string positionType;
        std::string positionShape;
        std::vector<double> positionParams;  // centre x,y,z then shape parameters (legacy layout)
        double halfX = 0.0, halfY = 0.0, halfZ = 0.0, radius = 0.0, innerRadius = 0.0;
        double beamSigmaR = 0.0, beamSigmaX = 0.0, beamSigmaY = 0.0;
        bool hasRotation = false;
        std::vector<double> rot1, rot2;
        std::string confineVolume;

        // Angular distribution: "" (legacy: fixed direction or isotropic flag),
        // fixed, isotropic, cos, beam1d, beam2d, focused.
        std::string angular;
        bool hasDirection = false;
        std::vector<double> direction;
        bool isotropic = false;
        bool hasThetaRange = false;
        double minTheta = 0.0, maxTheta = 0.0;
        double angularSigma = 0.0, angularSigmaX = 0.0, angularSigmaY = 0.0;
        std::vector<double> focus;

        bool restEnergy = false;   // ion with energy = 0 (decay at rest)
        bool advanced = false;     // uses a roadmap-A4 field beyond the legacy subset
        std::string Describe() const;
    };

    SourceManager();
    ~SourceManager();

    G4GeneralParticleSource* GetGPS();
    const G4GeneralParticleSource* GetGPS() const;
    bool HasGPS() const;
    void InitializeAfterPhysicsListRegistered();
    // Master/sequential BeginOfRunAction: apply settings that need the built
    // geometry or ion table (volume confinement, ions, phase-space particles).
    // Throws if a confinement volume is missing or a phase-space file is too
    // short for plannedEvents without recycling.
    void PrepareForRun(long long plannedEvents = 0);

    // Phase-space source ([source] phase_space_file): event k replays history
    // k (modulo the number of histories when recycling), so the result does
    // not depend on which worker processes the event.
    bool UsesPhaseSpace() const;
    void GeneratePhaseSpaceEvent(G4Event* event) const;
    std::size_t GetPhaseSpaceHistoryCount() const;
    std::size_t GetPhaseSpaceParticleCount() const;
    const std::vector<std::string>& GetPhaseSpaceFiles() const;
    bool IsPhaseSpaceRecycled() const;

    void ResetGPS();
    void LoadFromConfig(const ConfigManager& config);
    void ApplyPreset(const std::string& presetName);

    void SetParticle(const std::string& particleName);
    std::string GetParticleName() const;

    void SetMonoEnergy(double energy);
    double GetMonoEnergy() const;

    void SetPosition(const std::string& type, const std::string& shape, const std::vector<double>& params);
    void SetPointPosition(double x, double y, double z);
    void SetDirection(double x, double y, double z);
    void SetIsotropic();
    void SetPlaneBeam(double radius, double z, const std::string& direction = "-z");
    void SetPlaneBeamAt(double radius, double x, double y, double z, const std::string& direction);
    void SetPlaneRectangleAt(double halfX, double halfY, double x, double y, double z,
                             const std::string& direction);

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

    void PrintSummary() const;
    bool IsConfigured() const;

    const std::string& GetPresetName() const;

    std::size_t GetSourceCount() const;
    const std::vector<SourceSpec>& GetSources() const;

private:
    SourceSpec& Current();
    const SourceSpec& Current() const;
    void RequireSingleSourceForCommand(const char* what) const;
    void LoadSection(const ConfigManager& config, const std::string& section, bool namedSource);
    void LoadAdvancedSection(const ConfigManager& config, const std::string& section, SourceSpec& spec);

    void EnsureGPS() const;
    void MarkGPSConfigDirty();
    void ApplyCurrentConfigurationToGPS() const;
    G4SingleParticleSource* CurrentGPSSource() const;
    void ApplyParticleToGPS() const;
    void ApplyMonoEnergyToGPS() const;
    void ApplyPositionToGPS() const;
    void ApplyAngularDistributionToGPS() const;
    static void ApplySpec(const SourceSpec& spec, G4SingleParticleSource& source);
    static void ApplyParticle(const SourceSpec& spec, G4SingleParticleSource& source);
    static void ApplyEnergy(const SourceSpec& spec, G4SingleParticleSource& source);
    static void ApplyPosition(const SourceSpec& spec, G4SingleParticleSource& source);
    static void ApplyAngular(const SourceSpec& spec, G4SingleParticleSource& source);
    static std::vector<double> ParseDirectionVector(const std::string& text);
    static std::string NormalizeDirectionToken(const std::string& direction);

    mutable std::unique_ptr<G4GeneralParticleSource> gps_;
    mutable bool gpsConfigDirty_ = true;
    mutable bool deferredApplied_ = false;  // ions / confinement applied for this configuration
    std::vector<SourceSpec> sources_{1};
    std::size_t current_ = 0;
    bool loadingNamedSources_ = false;
    std::vector<std::string> phaseSpaceFiles_;
    std::shared_ptr<const std::vector<std::vector<PhaseSpaceParticle>>> phaseSpace_;
    std::size_t phaseSpaceParticleCount_ = 0;
    bool phaseSpaceRecycle_ = false;
    std::map<int, G4ParticleDefinition*> phaseSpaceDefinitions_;  // filled by PrepareForRun
    std::string presetName_;
    int verboseLevel_ = 0;
    bool configured_ = false;
};
