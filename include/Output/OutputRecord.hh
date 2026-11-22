#pragma once

#include <array>
#include <cstdint>
#include <optional>
#include <string>

struct VoxelEdepRecord {
    std::array<int, 3> index{};
    std::string material;
    double rawEdep = 0;
    double weightedEdep = 0;
    std::uint64_t steps = 0;
};

inline constexpr const char* kNamedH2CsvHeader =
    "schema_version,x_quantity,y_quantity,x_unit,y_unit,name,run_id,thread_id,scope,"
    "x_bin_index,x_lower_MeV,x_upper_MeV,y_bin_index,y_lower_MeV,y_upper_MeV,count,entries,sum_weight";
inline constexpr const char* kNamedH1CsvHeader =
    "schema_version,name,quantity,unit,run_id,thread_id,scope,bin_index,lower_MeV,upper_MeV,count,entries,sum_weight";
inline constexpr const char* kVoxelRoiMassCsvHeader =
    "execution_id,run_id,grid_id,nx,ny,nz,dx_mm,dy_mm,dz_mm,cx_parent_mm,cy_parent_mm,cz_parent_mm,"
    "x0_world_mm,y0_world_mm,z0_world_mm,cell_volume_mm3,geometry_path,geometry_sha256,descriptor_path,descriptor_sha256,labels_path,labels_sha256,declared_rois,"
    "record_type,roi_id,roi_path,roi_sha256,member_count,q,i,j,k,material,density_g_cm3,mass_g";

inline constexpr const char* kVoxelEdepCsvHeader =
    "execution_id,run_id,event_id,worker_id,record_type,grid_id,q,i,j,k,material,"
    "qualifying_steps,raw_edep_MeV,weighted_edep_MeV";

struct HitRecord {
    int runID = -1;
    int eventID = -1;
    int trackID = -1;
    int parentID = -1;
    std::string particleName;
    double edep = 0.0;
    double ndep = 0.0;
    double stepLength = 0.0;
    double x0 = 0.0;
    double y0 = 0.0;
    double z0 = 0.0;
    double x1 = 0.0;
    double y1 = 0.0;
    double z1 = 0.0;
    double px = 0.0;
    double py = 0.0;
    double pz = 0.0;
    double kineticEnergy = 0.0;
    std::string processName;
    std::string volumeName;
    double weight = 1.0;
    // Internal Geant4 mass units and full touchable path, used only by DoseScorer.
    // These fields are deliberately absent from the existing hits CSV v3 schema.
    double doseMass = 0.0;
    std::string doseVolumePath;
    // Internal sensitive solid volume (Geant4 volume units); not part of hits CSV.
    double fluenceVolume = 0.0;
    // Mean of pre- and post-step kinetic energy (Geant4 units); not part of hits CSV.
    double meanKineticEnergy = 0.0;
    double LETcalc = 0.0;
    double LETstep = 0.0;
};

struct OpticalPhotonCountRecord {
    int runID = -1;
    int eventID = -1;
    std::uint64_t scintillation = 0;
    std::uint64_t cerenkov = 0;
    std::uint64_t other = 0;
};

inline constexpr char kOpticalBoundaryStepCsvHeader[] =
    "runID,eventID,trackID,parentID,stepID,pre_volume_path,post_candidate_volume_path,"
    "pre_material,post_candidate_material,x_mm,y_mm,z_mm,step_length_mm,"
    "pre_kinetic_energy_MeV,post_kinetic_energy_MeV,"
    "pre_dir_x,pre_dir_y,pre_dir_z,post_dir_x,post_dir_y,post_dir_z,"
    "pre_pol_x,pre_pol_y,pre_pol_z,post_pol_x,post_pol_y,post_pol_z,native_status_code,native_status";

struct OpticalBoundaryStepRecord {
    int runID;
    int eventID;
    int trackID;
    int parentID;
    int stepID;
    std::string preVolumePath;
    std::string postCandidateVolumePath;
    std::string preMaterial;
    std::string postCandidateMaterial;
    std::array<double, 3> positionMm;
    double stepLengthMm;
    double preEnergyMeV;
    double postEnergyMeV;
    std::array<double, 3> preDirection;
    std::array<double, 3> postDirection;
    std::array<double, 3> prePolarization;
    std::array<double, 3> postPolarization;
    int nativeStatusCode;
    std::string nativeStatus;
};

inline constexpr char kActivationObservationCsvHeader[] =
    "runID,eventID,trackID,parentID,stepID,kind,process,particle,Z,A,isomer,excitation_keV,"
    "time_s,weight,x_mm,y_mm,z_mm,origin_stepID,secondary_ordinal";
inline constexpr char kActivationObservationCsvV2Columns[] =
    ",creator_model_id,creator_model_name,proper_time_s,pre_global_time_s,pre_proper_time_s,"
    "pre_kinetic_energy_keV,kinetic_energy_keV,post_step_status,post_track_status,"
    "secondary_creator_relation,step_secondary_count,step_excluded_secondary_count";
inline constexpr char kActivationObservationCsvV3Columns[] =
    ",endpoint_transport,pre_mass_touchable,post_mass_touchable,track_next_mass_touchable,post_touchable_matches_next,"
    "generated_primary_neutrons,generated_primary_neutron_weight,unknown_primary_definitions,"
    "capture_creator_matches,capture_pre_weight,capture_target_observation,capture_model,"
    "capture_target_nucleus_Z,capture_target_nucleus_A,capture_target_isotope_Z,capture_target_isotope_A";

struct ActivationObservationRecord {
    int runID;
    int eventID;
    int trackID;
    int parentID;
    int stepID;
    std::string kind;
    std::string process;
    std::string particle;
    int atomicNumber = 0;
    int massNumber = 0;
    int isomer = -1;
    double excitationKeV = 0;
    double timeSeconds;
    double weight;
    std::array<double, 3> positionMm;
    int originStepID = -1;
    int secondaryOrdinal = -1;
    std::optional<int> creatorModelID;
    std::string creatorModelName;
    std::optional<double> properTimeSeconds;
    std::optional<double> preGlobalTimeSeconds;
    std::optional<double> preProperTimeSeconds;
    std::optional<double> preKineticEnergyKeV;
    std::optional<double> kineticEnergyKeV;
    std::string postStepStatus;
    std::string postTrackStatus;
    std::string secondaryCreatorRelation;
    std::optional<int> stepSecondaryCount;
    std::optional<int> stepExcludedSecondaryCount;
    std::string endpointTransport;
    std::string preMassTouchable;
    std::string postMassTouchable;
    std::string trackNextMassTouchable;
    std::optional<bool> postTouchableMatchesNext;
    std::optional<int> generatedPrimaryNeutrons;
    std::optional<double> generatedPrimaryNeutronWeight;
    std::optional<int> unknownPrimaryDefinitions;
    std::optional<int> captureCreatorMatches;
    std::optional<double> capturePreWeight;
    std::string captureTargetObservation;
    std::string captureModel;
    std::optional<int> captureTargetNucleusZ;
    std::optional<int> captureTargetNucleusA;
    std::optional<int> captureTargetIsotopeZ;
    std::optional<int> captureTargetIsotopeA;
};

struct EventEdepRecord {
    int runID = -1;
    int eventID = -1;
    double rawEdep = 0.0;
    double weightedEdep = 0.0;
};
