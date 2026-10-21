#pragma once

#include "Templates/TemplateFactory.hh"
#include "BuildInfo.hh"
#include "G4Version.hh"

#include <ostream>

// Versioned facts about this executable, not a promise of physical validation.
// Keep unavailable entries visible so clients can explain fail-fast boundaries.
inline void WriteBackendCapabilities(std::ostream& out)
{
    out << "{\"schema\":\"G4UniversalSimCapabilities\",\"version\":1,"
        << "\"source_fingerprint\":\"" << G4USIM_SOURCE_FINGERPRINT << "\","
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
            << (name == "gdml" ? "false" : "true") << '}';
    }
    out << R"json(],
"solids":[
{"id":"box","runtime":true,"parameters":null,"contract":"size: three full lengths; parameters rejected"},
{"id":"tubs","runtime":true,"parameters":5,"contract":"rmin,rmax,half_z,start_phi,delta_phi"},
{"id":"sphere","runtime":true,"parameters":6,"contract":"rmin,rmax,start_phi,delta_phi,start_theta,delta_theta"},
{"id":"orb","runtime":true,"parameters":1,"contract":"radius"},
{"id":"cone","runtime":true,"parameters":7,"contract":"rmin1,rmax1,rmin2,rmax2,half_z,start_phi,delta_phi"},
{"id":"trd","runtime":true,"parameters":null,"contract":"named half-length fields dx1,dx2,dy1,dy2,dz; parameters rejected"},
{"id":"trap","runtime":true,"parameters":null,"contract":"named fields only"}
],
"placements":[{"id":"normal","runtime":true},{"id":"replica","runtime":false},{"id":"parameterised","runtime":false},{"id":"assembly","runtime":false}],
"materials":[{"id":"nist","runtime":true},{"id":"isotope","runtime":true},{"id":"element","runtime":true},{"id":"mass_fraction","runtime":true},{"id":"atom_count","runtime":true},{"id":"volume_fraction","runtime":true},{"id":"temperature","runtime":false},{"id":"pressure","runtime":false}],
"physics":[{"id":"reference","runtime":true},{"id":"manual","runtime":true},{"id":"geometry_region_cuts","runtime":true},{"id":"physics_region_cuts","runtime":false},{"id":"process_xs_biasing","runtime":true,"physical_validation":false}],
"sources":[{"id":"point_fixed","runtime":true},{"id":"point_isotropic","runtime":true},{"id":"plane_circle","runtime":true},{"id":"rectangle","runtime":true,"contract":"XY plane, halfx/halfy, center, fixed/isotropic"},{"id":"annulus","runtime":false},{"id":"cone","runtime":false},{"id":"cosine","runtime":false},{"id":"focused","runtime":false}],
"scorers":[{"id":"hits","runtime":true},{"id":"edep","runtime":true},{"id":"let","runtime":false},{"id":"dose","runtime":true,"validation":"per sensitive touchable, Geant4 mass; no physical benchmark"},{"id":"fluence","runtime":true,"validation":"per daughter-free sensitive touchable, track length / solid volume; no physical benchmark"}],
"outputs":{"schema_version":3,"run_summary_schema_version":1,"worker_suffix":"_tN","subsequent_run_suffix":"_rR","csv_units_in_header":true,"automatic_merge":false},
"validation_scope":"configuration and runtime smoke; not physical benchmark",
"geometry_schema_version":null
}
)json";
}
