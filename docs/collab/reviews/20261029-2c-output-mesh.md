# Output / mesh consumer handoff

Implemented OutputManager typed fields (/output/directory, /output/format, /output/thread_suffix), copied parser provenance, duplicate/alias chain, explicit accepted-command hook, thread clone isolation, writer-open actual-state receipts. Existing failure latching and generated-file registration unchanged.

ScoringMeshConfig BuildCommands publishes accepted typed mesh/quantity projection only after all meshes validate. Namespace export/evidence/confirmation hooks. Native /score commands mark the INI projection unknown. RecordEffectiveConfigDispatch records command dispatch as unknown, never claims observed G4 mesh construction or worker application. No ScoringMeshManager exists in current repository. No external file is read by these consumers.

Root hooks required:
- after Configure accepts OutputManager: output.AcceptEffectiveConfig(config.GetMainReader()); use after all directory/format setters and before cloning.
- registry replace output with output.ExportEffectiveConfigFields(); mesh with ScoringMeshConfig::ExportEffectiveConfigFields().
- route only successful commands to both ConfirmEffectiveConfigMutation(command, origin); output handles setDir/setOutputDir/setThreadSuffix; mesh handles /score commands conservatively.
- after all generated mesh commands succeed call ScoringMeshConfig::RecordEffectiveConfigDispatch(). This is not kernel observation.
- call OutputManager::RecordEffectiveConfigState(stage) at desired real run_begin/finalization boundaries, collect each actual thread ExportEffectiveConfigEvidence() before thread destruction; clones own evidence buffers. Writer-open records automatically.
- Collect mesh export evidence in master snapshot. Native mesh object observation and worker inventories remain integration work; do not upgrade unknown dispatch receipts.

Validation executed: g++ -std=c++17 -fsyntax-only -Iinclude -ID:/ProgramFiles/Geant4/include/Geant4 for EffectiveOutput.cc, ScoringMeshConfig.cc, OutputManager.cc, exit 0; Python new script py_compile exit 0. Real backend test scripts/test_effective_output_mesh.py requires fresh G4USIM_EXE and root integration; not yet executed. Test checks formats/aliases, side-effect-free dump, parsed-byte source hash, typed sizes/bins/center/particles/energies, box/cylinder, and rejected invalid mesh/output.
