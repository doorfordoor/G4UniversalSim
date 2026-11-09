# Internal backend archives. The root finds Geant4 and generates BuildInfo.hh
# before including this file. CTest, runtime resources and install stay in root.

set(G4USIM_LOGIC_MEMBERS
    src/Actions/RunProgress.cc
    src/Config/ConfigManager.cc
    src/Config/ConfigValue.cc
    src/Config/EffectiveConfig.cc
    src/Config/IniReader.cc
    src/Config/InputProvenance.cc
    src/Core/SessionJson.cc
    src/Core/SimulationContext.cc
    src/Geometry/GeometryConfigDiagnostic.cc
    src/Geometry/StlReader.cc
    src/Scoring/HistoryStatistics.cc
    src/Utils/CommandParser.cc
    src/Utils/FileUtils.cc
    src/Utils/G4NameUtils.cc
    src/Utils/StringUtils.cc
)

set(G4USIM_GEANT_MEMBERS
    src/Actions/ActionInitialization.cc
    src/Actions/EventAction.cc
    src/Actions/PhaseSpaceStackingAction.cc
    src/Actions/RunAction.cc
    src/Actions/RunManagerFactory.cc
    src/Actions/SteppingAction.cc
    src/Actions/TrackingAction.cc
    src/Actions/WorkerRunContext.cc
    src/Biasing/BiasingImportance.cc
    src/Biasing/BiasingManager.cc
    src/Biasing/BiasingMessenger.cc
    src/Biasing/BiasingMultiParticleXS.cc
    src/Biasing/BiasingRegion.cc
    src/Biasing/BiasingXS.cc
    src/Biasing/EffectiveBiasing.cc
    src/Core/AppMessenger.cc
    src/Core/ConfigurationCoordinator.cc
    src/Core/EffectiveSimulation.cc
    src/Core/Geant4DataLocator.cc
    src/Core/MacroPreflight.cc
    src/Core/RandomCommandGuard.cc
    src/Core/RunFinalization.cc
    src/Core/RuntimeExecution.cc
    src/Core/RuntimeSession.cc
    src/Core/SessionServer.cc
    src/Core/SimulationManager.cc
    src/Detector/DetectorConstruction.cc
    src/Detector/DetectorMessenger.cc
    src/Field/FieldConfig.cc
    src/Field/FieldSetup.cc
    src/Geometry/GeometryConfig.cc
    src/Geometry/GeometryExport.cc
    src/Geometry/GeometryManager.cc
    src/Geometry/GeometryMessenger.cc
    src/Geometry/GeometryRegistry.cc
    src/Geometry/GeometrySafety.cc
    src/Geometry/GeometryUtils.cc
    src/Geometry/RegionCutPlan.cc
    src/Geometry/SolidRegistry.cc
    src/Geometry/VolumeBuilder.cc
    src/Geometry/VolumeNode.cc
    src/Hits/ParticleHit.cc
    src/Hits/ParticleHitCollection.cc
    src/Hits/SensitiveDetector.cc
    src/Hits/TrackInformation.cc
    src/Materials/MaterialCommandParser.cc
    src/Materials/MaterialFactory.cc
    src/Materials/MaterialIniReader.cc
    src/Materials/MaterialManager.cc
    src/Materials/MaterialMessenger.cc
    src/Output/AnalysisOutput.cc
    src/Output/CsvWriter.cc
    src/Output/EffectiveOutput.cc
    src/Output/Histogram1D.cc
    src/Output/Histogram2D.cc
    src/Output/OutputManager.cc
    src/Output/OutputMessenger.cc
    src/Output/RunSummary.cc
    src/ParallelWorld/ParallelScoringDetector.cc
    src/ParallelWorld/ParallelWorldConfig.cc
    src/ParallelWorld/ScoringParallelWorld.cc
    src/Physics/ElectronCapture.cc
    src/Physics/MicroElecPhysics.cc
    src/Physics/PhysicsFactory.cc
    src/Physics/PhysicsList.cc
    src/Physics/PhysicsManager.cc
    src/Physics/PhysicsMessenger.cc
    src/Physics/ProcessDump.cc
    src/Scoring/DisplacementScorer.cc
    src/Scoring/DoseScorer.cc
    src/Scoring/EdepScorer.cc
    src/Scoring/EffectiveScoring.cc
    src/Scoring/FluenceScorer.cc
    src/Scoring/LETScorer.cc
    src/Scoring/NielTable.cc
    src/Scoring/ParticleAggregator.cc
    src/Scoring/PhaseSpace.cc
    src/Scoring/ScorerBase.cc
    src/Scoring/ScorerFactory.cc
    src/Scoring/ScoringManager.cc
    src/Scoring/ScoringMeshConfig.cc
    src/Scoring/ScoringMeshExport.cc
    src/Scoring/ScoringMessenger.cc
    src/Scoring/ThreadLocalScoringContext.cc
    src/Scoring/TrajectoryRecorder.cc
    src/Scoring/VolumeSpectrum.cc
    src/Source/PhaseSpaceReplayState.cc
    src/Source/PrimaryGeneratorAction.cc
    src/Source/SourceManager.cc
    src/Source/SourceMessenger.cc
    src/Templates/ArrayTemplate.cc
    src/Templates/GDMLTemplate.cc
    src/Templates/GeometryTemplate.cc
    src/Templates/HierarchicalVolumeTemplate.cc
    src/Templates/LayeredDeviceTemplate.cc
    src/Templates/ShieldingTemplate.cc
    src/Templates/SimpleBoxTemplate.cc
    src/Templates/TemplateFactory.cc
    src/Utils/UnitParser.cc
)

set(G4USIM_GDML_MEMBERS
    src/Geometry/GdmlIO.cc
    src/Geometry/GdmlInputCapture.cc
)

# Explicit ownership: reject newly globbed or multiply owned production TUs.
set(_g4usim_owned ${G4USIM_LOGIC_MEMBERS} ${G4USIM_GEANT_MEMBERS} ${G4USIM_GDML_MEMBERS})
list(LENGTH _g4usim_owned _g4usim_n)
list(REMOVE_DUPLICATES _g4usim_owned)
list(LENGTH _g4usim_owned _g4usim_unique_n)
if(NOT _g4usim_n EQUAL _g4usim_unique_n)
    message(FATAL_ERROR "Production source has multiple logical owners")
endif()
set(_g4usim_observed)
foreach(_source IN LISTS SOURCES)
    file(RELATIVE_PATH _relative "${PROJECT_SOURCE_DIR}" "${_source}")
    list(APPEND _g4usim_observed "${_relative}")
endforeach()
list(SORT _g4usim_owned)
list(SORT _g4usim_observed)
if(NOT "${_g4usim_owned}" STREQUAL "${_g4usim_observed}")
    message(FATAL_ERROR "Assign new/removed source explicitly in BackendTargets.cmake")
endif()
foreach(_group LOGIC GEANT GDML)
    set(G4USIM_${_group}_SOURCES)
    foreach(_member IN LISTS G4USIM_${_group}_MEMBERS)
        list(APPEND G4USIM_${_group}_SOURCES "${PROJECT_SOURCE_DIR}/${_member}")
    endforeach()
endforeach()

find_package(Threads REQUIRED)
add_library(g4usim_logic STATIC ${G4USIM_LOGIC_SOURCES})
target_compile_features(g4usim_logic PUBLIC cxx_std_17)
target_include_directories(g4usim_logic PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>")
target_link_libraries(g4usim_logic PUBLIC Threads::Threads)

add_library(g4usim_geant STATIC ${G4USIM_GEANT_SOURCES})
target_compile_features(g4usim_geant PUBLIC cxx_std_17)
target_include_directories(g4usim_geant PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<BUILD_INTERFACE:${PROJECT_BINARY_DIR}/generated>")
target_include_directories(g4usim_geant SYSTEM PUBLIC ${Geant4_INCLUDE_DIRS})
target_compile_definitions(g4usim_geant PRIVATE
    G4USIM_BUILD_CONFIGURATION="$<IF:$<BOOL:$<CONFIG>>,$<CONFIG>,unknown>")
target_link_libraries(g4usim_geant PUBLIC g4usim_logic ${Geant4_LIBRARIES})

# The ONLY intentional dual compilation: these two TUs read the GDML flag.
# Their API headers have no conditional ABI, and their project dependency is
# InputProvenance only. No reverse dependency to g4usim_geant exists.
if(Geant4_gdml_FOUND)
    add_library(g4usim_gdml_native STATIC ${G4USIM_GDML_SOURCES})
    target_compile_features(g4usim_gdml_native PUBLIC cxx_std_17)
    target_include_directories(g4usim_gdml_native PUBLIC
        "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>")
    target_include_directories(g4usim_gdml_native SYSTEM PUBLIC ${Geant4_INCLUDE_DIRS})
    target_compile_definitions(g4usim_gdml_native PRIVATE G4USIM_HAVE_GDML=1)
    target_link_libraries(g4usim_gdml_native PUBLIC g4usim_logic ${Geant4_LIBRARIES})
endif()
if(NOT Geant4_gdml_FOUND OR BUILD_TESTING)
    add_library(g4usim_gdml_stub STATIC ${G4USIM_GDML_SOURCES})
    target_compile_features(g4usim_gdml_stub PUBLIC cxx_std_17)
    target_include_directories(g4usim_gdml_stub PUBLIC
        "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>")
    target_include_directories(g4usim_gdml_stub SYSTEM PUBLIC ${Geant4_INCLUDE_DIRS})
    target_link_libraries(g4usim_gdml_stub PUBLIC g4usim_logic ${Geant4_LIBRARIES})
endif()

# In direct link order common precedes the selected provider; the provider
# references only logic/SDK, never common. Never link both providers into an exe.
# Profiles: native=application's SDK capability; legacy=old parallel no-GDML;
# none=old h2/random subset has no GDML source or unresolved GDML calls.
function(g4usim_link_backend target profile)
    get_property(_profile_set TARGET ${target} PROPERTY G4USIM_BACKEND_PROFILE SET)
    if(_profile_set)
        get_property(_previous TARGET ${target} PROPERTY G4USIM_BACKEND_PROFILE)
        if(NOT "${_previous}" STREQUAL "${profile}")
            message(FATAL_ERROR "Do not mix GDML providers in ${target}")
        endif()
        return()
    endif()
    set_property(TARGET ${target} PROPERTY G4USIM_BACKEND_PROFILE "${profile}")
    target_link_libraries(${target} PRIVATE g4usim_geant)
    if(profile STREQUAL "native")
        if(Geant4_gdml_FOUND)
            target_link_libraries(${target} PRIVATE g4usim_gdml_native)
            target_compile_definitions(${target} PRIVATE G4USIM_HAVE_GDML=1)
        else()
            target_link_libraries(${target} PRIVATE g4usim_gdml_stub)
        endif()
    elseif(profile STREQUAL "legacy")
        target_link_libraries(${target} PRIVATE g4usim_gdml_stub)
    elseif(NOT profile STREQUAL "none")
        message(FATAL_ERROR "Unknown backend profile ${profile}")
    endif()
endfunction()
