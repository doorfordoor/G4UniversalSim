#pragma once

#include "Geometry/GdmlIO.hh"
#include "Geometry/SolidRegistry.hh"

#include "Templates/TemplateFactory.hh"
#include "BuildInfo.hh"
#include "G4Version.hh"

#include <ostream>

// Versioned facts about this executable, not a promise of physical validation.
// Keep unavailable entries visible so clients can explain fail-fast boundaries.
inline void WriteBackendCapabilities(std::ostream& out)
{
    out << "{\"schema\":\"G4UniversalSimCapabilities\",\"version\":1,"
        << "\"launch\":{\"working_directory\":true},"
        << "\"source_fingerprint\":\"" << G4USIM_SOURCE_FINGERPRINT << "\","
        << "\"build_git_commit\":\"" << G4USIM_GIT_COMMIT << "\","
        << "\"build_git_source_state\":\"" << G4USIM_GIT_SOURCE_STATE << "\","
        << "\"build_configuration\":\"" << G4USIM_BUILD_CONFIGURATION << "\","
        << "\"compiler_id\":\"" << G4USIM_COMPILER_ID << "\","
        << "\"compiler_version\":\"" << G4USIM_COMPILER_VERSION << "\","
        << "\"geant4_version_number\":" << G4VERSION_NUMBER << ','
#ifdef G4MULTITHREADED
        << "\"multithreaded\":true,"
#else
        << "\"multithreaded\":false,"
#endif
        << "\"templates\":[";
    bool first = true;
    for (const auto& name : TemplateFactory::AvailableTemplates()) {
        if (!first) out << ',';
        first = false;
        out << "{\"id\":\"" << name << "\",\"runtime\":"
            << (name == "gdml" && !GdmlIO::Available() ? "false" : "true") << '}';
    }
    out << "],\"solid_registry\":" << SolidRegistry::Describe().ToJson() << ",\"solids\":[";
    first = true;
    for (const auto& entry : SolidRegistry::Entries()) {
        if (!first) out << ',';
        first = false;
        std::string contract = entry.usesSize ? "size: three full lengths; " : "";
        for (const auto& field : entry.parameters) contract += field.name + " (" + field.dimension + "); ";
        for (const auto& field : entry.properties) contract += field.name + " (" + field.dimension + "); ";
        using V = effective_config::Value;
        out << V(V::Object{{"id", entry.name}, {"runtime", true},
            {"parameters", entry.parameterCounts.empty() ? V() : V(entry.parameterCounts.back())},
            {"contract", contract}}).ToJson();
    }
    out << R"json(],
"placements":[{"id":"normal","runtime":true},{"id":"replica","runtime":true,"contract":"box mother x/y/z or tubs mother phi; only daughter"},{"id":"parameterised","runtime":true,"contract":"copies_file or copies + copy_step; only daughter"},{"id":"assembly","runtime":false}],
"materials":[{"id":"nist","runtime":true},{"id":"isotope","runtime":true},{"id":"element","runtime":true},{"id":"mass_fraction","runtime":true},{"id":"atom_count","runtime":true},{"id":"volume_fraction","runtime":true},{"id":"temperature","runtime":false},{"id":"pressure","runtime":false}],
"physics":[{"id":"constructor_replacement","runtime":true,"contract":"replace_modules explicitly replaces existing nonzero physics types; conflicts fail"},{"id":"reference","runtime":true},{"id":"manual","runtime":true},{"id":"geometry_region_cuts","runtime":true},{"id":"physics_region_cuts","runtime":true,"contract":"[physics.region.<name>] gamma/e-/e+/proton"},{"id":"region_step_limits","runtime":true,"contract":"max_step, max_track_length, max_time, min_kinetic_energy (G4StepLimiterPhysics)"},{"id":"radioactive_decay","runtime":true,"contract":"[physics.radioactive_decay] enabled, time_threshold"},{"id":"process_dump","runtime":true,"contract":"/AIHL/physics/dumpProcesses, g4usim_process_dump_v1"},{"id":"uniform_fields","runtime":true,"contract":"[field] / [field.<name>] magnetic, electric"},{"id":"field_maps","runtime":true,"contract":"magnetic_map / electric_map CSV grid, trilinear"},{"id":"local_fields","runtime":true,"contract":"[field.<name>] volumes"},{"id":"process_xs_biasing","runtime":true,"physical_validation":false}],
"sources":[{"id":"point_fixed","runtime":true},{"id":"point_isotropic","runtime":true},{"id":"plane_circle","runtime":true},{"id":"rectangle","runtime":true,"contract":"XY plane, halfx/halfy, center, fixed/isotropic"},{"id":"annulus","runtime":true},{"id":"ellipse","runtime":true},{"id":"square","runtime":true},{"id":"volume","runtime":true},{"id":"beam_spot","runtime":true},{"id":"confine","runtime":true},{"id":"cone","runtime":true},{"id":"cosine","runtime":true},{"id":"beam1d","runtime":true},{"id":"beam2d","runtime":true},{"id":"focused","runtime":true},{"id":"energy_spectra","runtime":true},{"id":"multi_source","runtime":true,"contract":"intensity-weighted selection by default"},{"id":"multiple_vertex","runtime":true,"contract":"all named sources per event; flat_sampling=false, intensity does not change vertex weights"},{"id":"surface_sphere","runtime":true,"contract":"position_type=surface shape=sphere samples the surface; volume/sphere samples the interior"},{"id":"ion","runtime":true},{"id":"phase_space","runtime":true}],
"scorers":[{"id":"hits","runtime":true},{"id":"edep","runtime":true},{"id":"let","runtime":true,"validation":"track/dose-averaged unrestricted electronic stopping power per sensitive touchable; proton LET_t checked against Bethe formula"},{"id":"dose","runtime":true,"validation":"per sensitive touchable, Geant4 mass; no physical benchmark"},{"id":"fluence","runtime":true,"validation":"per daughter-free sensitive touchable, track length / solid volume; no physical benchmark"},{"id":"displacement","runtime":true,"validation":"track-length fluence folded with user-supplied NIEL tables per daughter-free sensitive touchable; fold checked against an independent hits recomputation, NIEL data not benchmarked"}],
"outputs":{"schema_version":3,"run_summary_schema_version":1,"worker_suffix":"_tN","subsequent_run_suffix":"_rR","csv_units_in_header":true,"automatic_merge":false,"formats":["csv","root","both","auto"],"default_format":"csv","auto_rule":"ROOT when scoring is enabled and hits or event_edep is enabled; CSV otherwise","provenance_schema":"g4usim_provenance_v1",
"root":{"schema_version":4,"file":"g4usim.root","subsequent_run_file":"g4usim_rR.root","thread_merge":true,"histograms":["edep_raw","edep_weighted"],"ntuples":["hits","events","edep_volume","edep_particle","dose","fluence","mesh","let"]},"scoring_meshes":{"commands":"/score/","shapes":["box","cylinder"],"thread_merge":true,"uncertainty":"sum_sq per event, rel_error"},"run_metadata":"run_metadata.json","scorer_statistics":"scorer_statistics.csv","phase_space":"phase_space_tN.csv","trajectories":"trajectories_tN.json (g4usim_trajectories_v1, [output] trajectories = N events)","geometry_mesh":"g4usim_geometry_mesh_v1"},
"validation_scope":"configuration and runtime smoke; not physical benchmark",
"geometry_schema_version":null
}
)json";
}
