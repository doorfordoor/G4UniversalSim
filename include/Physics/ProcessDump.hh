#pragma once

// Active-process dump (roadmap A6): what Geant4 actually set up, as JSON
// (schema g4usim_process_dump_v1), written by /AIHL/physics/dumpProcesses.
//
//   physics_list           name of the registered list and its constructors
//   radioactive_decay      time threshold in years (G4HadronicParameters)
//   particles[]            name, pdg, processes[] (name, type, sub_type, active,
//                          models[] with name and energy range in MeV; EM models
//                          for EM processes, hadronic interactions for hadronic ones)
//   regions[]              name, root logical volumes, production range cuts (mm),
//                          user limits (max_step_mm, max_track_length_mm,
//                          max_time_ns, min_kinetic_energy_MeV)
//   couples[]              material, region, range cuts (mm) and the energy
//                          thresholds Geant4 converted them to (MeV)
//
// Available after /run/initialize (Idle state); the couples and energy
// thresholds are already final then.

#include <string>
#include <vector>

namespace ProcessDump {

// particles empty = gamma, e-, e+, proton, neutron, alpha, GenericIon, mu-, mu+, pi-, pi+.
// Returns the number of particles written.
int WriteJson(const std::string& path, const std::vector<std::string>& particles);

}  // namespace ProcessDump
