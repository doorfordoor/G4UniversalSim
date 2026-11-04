# F2 controlled-session baseline: generated evidence summary

Generated from `evidence/index.json`; every number below is read from the raw
files the sessions produced (run summary, phase-space CSV, hits CSV).

## Session overview

| case | exit | sentinel seen | status | run_count | completed | effective energy / particle |
| --- | --- | --- | --- | --- | --- | --- |
| fields | 0 | False | completed | 5 | 50 | 50 MeV / e- |
| native-gps | 0 | False | completed | 2 | 10 | 100 MeV / proton |
| preinit-cache | 0 | False | completed | 1 | 5 | 300 MeV / e- |
| refusal-multisource | 3221226505 | False | — | — | — | — MeV / — |
| refusal-output-state | 1 | False | failed | 0 | 0 | 100 MeV / proton |
| three-round | 0 | False | completed | 3 | 30 | 100 MeV / proton |

## Per-round kernel-consumed primary vertices (phase_space_t*.csv)

| case | run | planned | completed | rows | particles | energy_MeV | x_mm | u |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fields | 0 | 10 | 10 | 10 | e- | 100.000 | 0.000 | 0.000 |
| fields | 1 | 10 | 10 | 10 | e- | 50.000 | 0.000 | 0.000 |
| fields | 2 | 10 | 10 | 10 | e- | 50.000 | 5.000 | 0.000 |
| fields | 3 | 10 | 10 | 10 | e- | 50.000 | 9.020 | 0.100 |
| fields | 4 | 10 | 10 | 10 | e- | 50.000 | -3.089–3.902 | 0.000 |
| native-gps | 0 | 5 | 5 | 5 | proton | 100.000 | 0.000 | 0.000 |
| native-gps | 1 | 5 | 5 | 5 | proton | 2.000 | 0.000 | 0.000 |
| preinit-cache | 0 | 5 | 5 | 5 | e- | 300.000 | 0.000 | 0.000 |
| three-round | 0 | 10 | 10 | 10 | proton | 100.000 | 0.000 | 0.000 |
| three-round | 1 | 10 | 10 | 10 | proton | 200.000 | 0.000 | 0.000 |
| three-round | 2 | 10 | 10 | 10 | proton | 100.000 | 0.000 | 0.000 |

## Refusals and terminal state

### refusal-multisource

- exit_code: `3221226505`; sentinel seen: `False`
- stderr: `-------- EEEE ------- G4Exception-START -------- EEEE -------`
- stderr: `*** G4Exception : AIHL_SOURCE_001`
- stderr: `Source command /AIHL/source/energy failed for input '200 MeV': SourceManager energy cannot target one of several [source.<name>] sources; edit the sources in the main INI or use native /gps/source/... commands.`
- stderr: `-------- EEEE -------- G4Exception-END --------- EEEE -------`

### refusal-output-state

- exit_code: `1`; sentinel seen: `False`
- actual_completed_event_count: `0`
- effective_config_source_coverage: `startup_geometry_source_and_physics_reference`
- effective_source_energy_MeV: `100`
- effective_source_particle: `proton`
- interactive_command_failure_kind: `geant4_illegal_application_state`
- interactive_command_failure_message: `illegal application state -- command refused; Geant4 UI status=200 for command: /AIHL/output/setDir D:\Geant4\G4UniversalSim\out\collab\f2-session-baseline-20261104\evidence\must-not-be-used`
- macro_execution_status: `not_run`
- output_failure_stage: `not_applicable`
- run_count: `0`
- status: `failed`

## Native `/gps` interleave: manager cache vs kernel

- run 0: kernel-consumed energy = 100.000 MeV, rows = 5
- run 1: kernel-consumed energy = 2.000 MeV, rows = 5
- manager print: `Idle> [SourceManager] configured=true, particle=proton, monoEnergy=100, preset=<none>, verbose=0, gps=available, sources=1`
- manager print: `Idle> Idle> [SourceManager] configured=true, particle=proton, monoEnergy=100, preset=<none>, verbose=0, gps=available, sources=1`
- The Manager therefore reports 100 MeV after the native `/gps/ene/mono 2 MeV` command while the kernel consumed 2 MeV in run 1: a controlled csh session cannot produce an authoritative applied-value receipt for native GPS commands.
