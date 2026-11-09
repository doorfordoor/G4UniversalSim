# CMakeLists.txt for G4UniversalSim

cmake_minimum_required(VERSION 3.10 FATAL_ERROR)
project(G4UniversalSim VERSION 1.1.0 LANGUAGES CXX)

# K2-2: the exported standalone project ships a template copy of this file.
# With G4USIM_STANDALONE_EXPORT=ON the Python-driven m0 regression suite (which
# needs the GUI/test tree) is not registered, and scripts/ is not copied next to
# the executable; the C++ application and its component tests build unchanged.
# The checkout default stays OFF so the developer tree keeps its CTest surface.
option(G4USIM_STANDALONE_EXPORT "Configure the exported standalone project" OFF)

# CMake 4.x may decode localized MSVC /showIncludes output with the wrong
# Windows code page. The resulting mojibake prefix prevents Ninja from
# tracking *any* included headers, so incremental builds can retain stale
# objects and a stale source fingerprint. Correct only this detected case.
if(MSVC AND CMAKE_GENERATOR MATCHES "Ninja" AND
   CMAKE_CL_SHOWINCLUDES_PREFIX MATCHES "娉ㄦ剰")
    set(CMAKE_CL_SHOWINCLUDES_PREFIX "注意: 包含文件: ")
endif()

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find Geant4 package
# A Geant4 built with GDML needs XercesC; the machine-wide install keeps it in
# the Geant4 prefix, so derive the hint from Geant4_DIR when none is given.
if(NOT DEFINED XercesC_ROOT AND NOT DEFINED ENV{XercesC_ROOT} AND DEFINED Geant4_DIR)
  get_filename_component(_g4usim_geant4_prefix "${Geant4_DIR}/../../.." ABSOLUTE)
  if(EXISTS "${_g4usim_geant4_prefix}/include/xercesc")
    set(XercesC_ROOT "${_g4usim_geant4_prefix}")
  endif()
endif()
find_package(Geant4 REQUIRED ui_all vis_all)

# Include Geant4 directories
include(${Geant4_USE_FILE})

# Source files
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS ${PROJECT_SOURCE_DIR}/src/*.cc)

# Fingerprint the exact C++ worktree inputs used at configure/build time.
# CONFIGURE_DEPENDS makes a source/header edit regenerate this header before
# the next build, even when Git HEAD is unchanged by uncommitted work.
file(GLOB_RECURSE G4USIM_HEADERS CONFIGURE_DEPENDS ${PROJECT_SOURCE_DIR}/include/*.hh)
file(GLOB_RECURSE G4USIM_CMAKE_INPUTS CONFIGURE_DEPENDS ${PROJECT_SOURCE_DIR}/cmake/*.cmake)
set(G4USIM_BUILD_INPUTS ${SOURCES} ${G4USIM_HEADERS}
    ${G4USIM_CMAKE_INPUTS}
    ${PROJECT_SOURCE_DIR}/main.cc ${PROJECT_SOURCE_DIR}/CMakeLists.txt
    ${PROJECT_SOURCE_DIR}/include/Core/BuildInfo.hh.in)
list(SORT G4USIM_BUILD_INPUTS)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${G4USIM_BUILD_INPUTS})
include("${PROJECT_SOURCE_DIR}/cmake/BuildIdentity.cmake")
g4usim_capture_source_fingerprint("${PROJECT_SOURCE_DIR}" "${G4USIM_BUILD_INPUTS}"
    G4USIM_SOURCE_FINGERPRINT)
g4usim_capture_build_identity("${PROJECT_SOURCE_DIR}" "${G4USIM_BUILD_INPUTS}"
    G4USIM_GIT_COMMIT G4USIM_GIT_SOURCE_STATE)
configure_file(
    ${PROJECT_SOURCE_DIR}/include/Core/BuildInfo.hh.in
    ${PROJECT_BINARY_DIR}/generated/BuildInfo.hh
    @ONLY
)

# Establish BUILD_TESTING before selecting the GDML archive variants.
# Existing CTest registrations below retain the standalone boundary.
include(CTest)
include("${PROJECT_SOURCE_DIR}/cmake/BackendTargets.cmake")

# The executable advertises this generated fingerprint from main.cc.
# Make this build-time dependency explicit even on hosts with broken
# localized MSVC include-output detection.
set_source_files_properties(main.cc PROPERTIES
    OBJECT_DEPENDS "${PROJECT_BINARY_DIR}/generated/BuildInfo.hh")

# Executable
add_executable(G4UniversalSim main.cc)
include(${PROJECT_SOURCE_DIR}/cmake/WindowsRuntime.cmake)
g4usim_configure_windows_runtime(G4UniversalSim)
# GDML import/export (roadmap A5) needs a Geant4 built with GDML (XercesC).
if(Geant4_gdml_FOUND)
  message(STATUS "G4UniversalSim: GDML support enabled")
else()
  message(STATUS "G4UniversalSim: Geant4 has no GDML; [gdml] geometry will be rejected")
endif()
target_include_directories(G4UniversalSim PRIVATE ${PROJECT_BINARY_DIR}/generated)
target_compile_definitions(G4UniversalSim PRIVATE
    G4USIM_BUILD_CONFIGURATION="$<IF:$<BOOL:$<CONFIG>>,$<CONFIG>,unknown>")

g4usim_link_backend(G4UniversalSim native)

# Standalone post-processing tool. This executable intentionally does not
# include or link Geant4.
add_executable(mergeHistograms tools/mergeHistograms.cc)
target_compile_features(mergeHistograms PRIVATE cxx_std_17)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    ${PROJECT_SOURCE_DIR}/tools/mergeHistograms.cc)
file(SHA256 ${PROJECT_SOURCE_DIR}/tools/mergeHistograms.cc G4USIM_MERGE_SOURCE_SHA256)
target_compile_definitions(mergeHistograms PRIVATE
    G4USIM_MERGE_SOURCE_SHA256="${G4USIM_MERGE_SOURCE_SHA256}")

if(BUILD_TESTING)
    if(Geant4_gdml_FOUND)
        add_executable(gdmlInputCaptureCheck tools/gdmlInputCaptureCheck.cc)
        target_compile_features(gdmlInputCaptureCheck PRIVATE cxx_std_17)
        target_compile_definitions(gdmlInputCaptureCheck PRIVATE G4USIM_HAVE_GDML=1)
        target_link_libraries(gdmlInputCaptureCheck PRIVATE g4usim_gdml_native)
    endif()
    # Exercise real numeric accumulation/merge code independently of transport.
    add_executable(scoringNumericCheck tools/scoringNumericCheck.cc)
    target_compile_features(scoringNumericCheck PRIVATE cxx_std_17)
    target_link_libraries(scoringNumericCheck PRIVATE g4usim_logic)
    add_executable(randomCommandGuardCheck tools/randomCommandGuardCheck.cc)
    target_compile_features(randomCommandGuardCheck PRIVATE cxx_std_17)
    g4usim_link_backend(randomCommandGuardCheck none)
    # Exercise the real volume-filter/spectrum scorer path without transport
    # (H2-2 component checks: partitions, weight-once, spectrum boundaries).
    add_executable(h2VolumeScoringCheck tools/h2VolumeScoringCheck.cc)
    target_compile_features(h2VolumeScoringCheck PRIVATE cxx_std_17)
    target_include_directories(h2VolumeScoringCheck PRIVATE ${PROJECT_BINARY_DIR}/generated)
    g4usim_link_backend(h2VolumeScoringCheck none)
    add_test(
        NAME h2_volume_scoring_check
        COMMAND h2VolumeScoringCheck ${PROJECT_BINARY_DIR}/h2-component-output ${PROJECT_SOURCE_DIR}
    )
    set_tests_properties(h2_volume_scoring_check PROPERTIES
        LABELS "h2;component"
        TIMEOUT 120
    )
    # H3-2 component checks: the dedicated parallel-scoring entry point must
    # reach dose/fluence only, never fold into event Edep or write hits.
    add_executable(parallelScoringCheck tools/parallelScoringCheck.cc)
    target_compile_features(parallelScoringCheck PRIVATE cxx_std_17)
    target_include_directories(parallelScoringCheck PRIVATE ${PROJECT_BINARY_DIR}/generated)
    target_compile_definitions(parallelScoringCheck PRIVATE
        G4USIM_BUILD_CONFIGURATION="$<IF:$<BOOL:$<CONFIG>>,$<CONFIG>,unknown>")
    g4usim_link_backend(parallelScoringCheck legacy)
    add_test(
        NAME parallel_scoring_component
        COMMAND parallelScoringCheck ${PROJECT_BINARY_DIR}/h3-component-output
    )
    set_tests_properties(parallel_scoring_component PROPERTIES
        LABELS "h3;component"
        TIMEOUT 180
    )
    if(NOT G4USIM_STANDALONE_EXPORT)
        add_executable(rootLifecycleCheck tools/rootLifecycleCheck.cc)
        target_include_directories(rootLifecycleCheck PRIVATE ${PROJECT_BINARY_DIR}/generated)
        target_compile_definitions(rootLifecycleCheck PRIVATE
            G4USIM_BUILD_CONFIGURATION="$<IF:$<BOOL:$<CONFIG>>,$<CONFIG>,unknown>")
        g4usim_link_backend(rootLifecycleCheck native)
        g4usim_configure_windows_runtime(rootLifecycleCheck)
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
            ${PROJECT_SOURCE_DIR}/tools/rootLifecycleCheck.cc)
        file(SHA256 ${PROJECT_SOURCE_DIR}/tools/rootLifecycleCheck.cc G4USIM_ROOT_LIFECYCLE_PROBE_SHA256)
        set_source_files_properties(tools/rootLifecycleCheck.cc PROPERTIES
            COMPILE_DEFINITIONS G4USIM_ROOT_LIFECYCLE_PROBE_SHA256="${G4USIM_ROOT_LIFECYCLE_PROBE_SHA256}")
        add_executable(phaseSpaceStateCheck tools/phaseSpaceStateCheck.cc)
        target_include_directories(phaseSpaceStateCheck PRIVATE ${PROJECT_BINARY_DIR}/generated)
        target_compile_definitions(phaseSpaceStateCheck PRIVATE
            G4USIM_BUILD_CONFIGURATION="$<IF:$<BOOL:$<CONFIG>>,$<CONFIG>,unknown>")
        g4usim_link_backend(phaseSpaceStateCheck native)
        g4usim_configure_windows_runtime(phaseSpaceStateCheck)
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
            ${PROJECT_SOURCE_DIR}/tools/phaseSpaceStateCheck.cc)
        file(SHA256 ${PROJECT_SOURCE_DIR}/tools/phaseSpaceStateCheck.cc G4USIM_PHASE_STATE_PROBE_SHA256)
        set_source_files_properties(tools/phaseSpaceStateCheck.cc PROPERTIES
            COMPILE_DEFINITIONS G4USIM_PHASE_STATE_PROBE_SHA256="${G4USIM_PHASE_STATE_PROBE_SHA256}")
        add_executable(runtimeSessionCheck tools/runtimeSessionCheck.cc)
        target_include_directories(runtimeSessionCheck PRIVATE ${PROJECT_BINARY_DIR}/generated)
        target_compile_definitions(runtimeSessionCheck PRIVATE
            G4USIM_BUILD_CONFIGURATION="$<IF:$<BOOL:$<CONFIG>>,$<CONFIG>,unknown>")
        g4usim_link_backend(runtimeSessionCheck native)
        g4usim_configure_windows_runtime(runtimeSessionCheck)
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
            ${PROJECT_SOURCE_DIR}/tools/runtimeSessionCheck.cc)
        file(SHA256 ${PROJECT_SOURCE_DIR}/tools/runtimeSessionCheck.cc G4USIM_RUNTIME_SESSION_PROBE_SHA256)
        set_source_files_properties(tools/runtimeSessionCheck.cc PROPERTIES
            COMPILE_DEFINITIONS G4USIM_RUNTIME_SESSION_PROBE_SHA256="${G4USIM_RUNTIME_SESSION_PROBE_SHA256}")
        add_executable(rootFileFinalizationCheck tools/rootFileFinalizationCheck.cc)
        target_compile_features(rootFileFinalizationCheck PRIVATE cxx_std_17)
        target_include_directories(rootFileFinalizationCheck PRIVATE "${PROJECT_SOURCE_DIR}/include")
        add_test(NAME root_file_finalization_component COMMAND rootFileFinalizationCheck)
        set_tests_properties(root_file_finalization_component PROPERTIES LABELS "ar3;component")
        # Repository-only real Manager transaction probe (not exported).
        add_executable(geometryTransactionCheck tools/geometryTransactionCheck.cc)
        target_include_directories(geometryTransactionCheck PRIVATE ${PROJECT_BINARY_DIR}/generated)
        target_compile_definitions(geometryTransactionCheck PRIVATE
            G4USIM_BUILD_CONFIGURATION="$<IF:$<BOOL:$<CONFIG>>,$<CONFIG>,unknown>")
        g4usim_link_backend(geometryTransactionCheck native)
        g4usim_configure_windows_runtime(geometryTransactionCheck)
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
            ${PROJECT_SOURCE_DIR}/tools/geometryTransactionCheck.cc)
        file(SHA256 ${PROJECT_SOURCE_DIR}/tools/geometryTransactionCheck.cc G4USIM_TRANSACTION_PROBE_SHA256)
        set_source_files_properties(tools/geometryTransactionCheck.cc PROPERTIES
            COMPILE_DEFINITIONS G4USIM_TRANSACTION_PROBE_SHA256="${G4USIM_TRANSACTION_PROBE_SHA256}")
        add_executable(geometryShapesCheck tools/geometryShapesCheck.cc)
        target_include_directories(geometryShapesCheck PRIVATE ${PROJECT_BINARY_DIR}/generated)
        target_compile_definitions(geometryShapesCheck PRIVATE
            G4USIM_BUILD_CONFIGURATION="$<IF:$<BOOL:$<CONFIG>>,$<CONFIG>,unknown>")
        g4usim_link_backend(geometryShapesCheck native)
        g4usim_configure_windows_runtime(geometryShapesCheck)
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
            ${PROJECT_SOURCE_DIR}/tools/geometryShapesCheck.cc)
        file(SHA256 ${PROJECT_SOURCE_DIR}/tools/geometryShapesCheck.cc G4USIM_SHAPES_PROBE_SHA256)
        set_source_files_properties(tools/geometryShapesCheck.cc PROPERTIES
            COMPILE_DEFINITIONS G4USIM_SHAPES_PROBE_SHA256="${G4USIM_SHAPES_PROBE_SHA256}")
        add_executable(iniReaderContractCheck tools/iniReaderContractCheck.cc)
        target_include_directories(iniReaderContractCheck PRIVATE ${PROJECT_BINARY_DIR}/generated)
        target_compile_definitions(iniReaderContractCheck PRIVATE
            G4USIM_BUILD_CONFIGURATION="$<IF:$<BOOL:$<CONFIG>>,$<CONFIG>,unknown>")
        g4usim_link_backend(iniReaderContractCheck native)
        g4usim_configure_windows_runtime(iniReaderContractCheck)
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
            ${PROJECT_SOURCE_DIR}/tools/iniReaderContractCheck.cc)
        file(SHA256 ${PROJECT_SOURCE_DIR}/tools/iniReaderContractCheck.cc G4USIM_INI_READER_CONTRACT_PROBE_SHA256)
        set_source_files_properties(tools/iniReaderContractCheck.cc PROPERTIES
            COMPILE_DEFINITIONS G4USIM_INI_READER_CONTRACT_PROBE_SHA256="${G4USIM_INI_READER_CONTRACT_PROBE_SHA256}")
        add_executable(scorerFactoryCheck tools/scorerFactoryCheck.cc)
        target_include_directories(scorerFactoryCheck PRIVATE ${PROJECT_BINARY_DIR}/generated)
        target_compile_definitions(scorerFactoryCheck PRIVATE
            G4USIM_BUILD_CONFIGURATION="$<IF:$<BOOL:$<CONFIG>>,$<CONFIG>,unknown>")
        g4usim_link_backend(scorerFactoryCheck native)
        g4usim_configure_windows_runtime(scorerFactoryCheck)
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
            ${PROJECT_SOURCE_DIR}/tools/scorerFactoryCheck.cc)
        file(SHA256 ${PROJECT_SOURCE_DIR}/tools/scorerFactoryCheck.cc G4USIM_SCORER_FACTORY_PROBE_SHA256)
        set_source_files_properties(tools/scorerFactoryCheck.cc PROPERTIES
            COMPILE_DEFINITIONS G4USIM_SCORER_FACTORY_PROBE_SHA256="${G4USIM_SCORER_FACTORY_PROBE_SHA256}")
        add_executable(scoringLifecycleCheck tools/scoringLifecycleCheck.cc)
        target_include_directories(scoringLifecycleCheck PRIVATE ${PROJECT_BINARY_DIR}/generated)
        target_compile_definitions(scoringLifecycleCheck PRIVATE
            G4USIM_BUILD_CONFIGURATION="$<IF:$<BOOL:$<CONFIG>>,$<CONFIG>,unknown>")
        g4usim_link_backend(scoringLifecycleCheck native)
        g4usim_configure_windows_runtime(scoringLifecycleCheck)
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
            ${PROJECT_SOURCE_DIR}/tools/scoringLifecycleCheck.cc)
        file(SHA256 ${PROJECT_SOURCE_DIR}/tools/scoringLifecycleCheck.cc G4USIM_SCORING_LIFECYCLE_PROBE_SHA256)
        set_source_files_properties(tools/scoringLifecycleCheck.cc PROPERTIES
            COMPILE_DEFINITIONS G4USIM_SCORING_LIFECYCLE_PROBE_SHA256="${G4USIM_SCORING_LIFECYCLE_PROBE_SHA256}")
        find_package(Python3 COMPONENTS Interpreter QUIET)
        if(Python3_Interpreter_FOUND)
            foreach(profile static gui backend integration)
                add_test(
                    NAME m0_${profile}
                    COMMAND ${Python3_EXECUTABLE} -B
                            ${PROJECT_SOURCE_DIR}/scripts/run_m0_tests.py
                            --profile ${profile}
                            --executable $<TARGET_FILE:G4UniversalSim>
                            --merge-executable $<TARGET_FILE:mergeHistograms>
                )
                set_tests_properties(m0_${profile} PROPERTIES
                    LABELS "m0;${profile}"
                    SKIP_RETURN_CODE 2
                    TIMEOUT 2400
                )
            endforeach()
        endif()
    endif()
endif()

# ------------------------------------------------------------
# Copy runtime resource directories next to the executable
# ------------------------------------------------------------

set(G4USIM_RUNTIME_DIRS
    config
    macros
)

if(NOT G4USIM_STANDALONE_EXPORT)
    list(APPEND G4USIM_RUNTIME_DIRS scripts)
endif()

foreach(runtime_dir ${G4USIM_RUNTIME_DIRS})
    if(EXISTS "${PROJECT_SOURCE_DIR}/${runtime_dir}")
        add_custom_command(
            TARGET G4UniversalSim
            POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_directory
                    "${PROJECT_SOURCE_DIR}/${runtime_dir}"
                    "$<TARGET_FILE_DIR:G4UniversalSim>/${runtime_dir}"
            COMMENT "Copying ${runtime_dir}/ to runtime output directory"
        )
    endif()
endforeach()

# Optional: also copy examples/scripts/tools if you want them beside exe
# foreach(runtime_dir examples scripts tools)
#     if(EXISTS "${PROJECT_SOURCE_DIR}/${runtime_dir}")
#         add_custom_command(
#             TARGET G4UniversalSim
#             POST_BUILD
#             COMMAND ${CMAKE_COMMAND} -E copy_directory
#                     "${PROJECT_SOURCE_DIR}/${runtime_dir}"
#                     "$<TARGET_FILE_DIR:G4UniversalSim>/${runtime_dir}"
#             COMMENT "Copying ${runtime_dir}/ to runtime output directory"
#         )
#     endif()
# endforeach()

# Install targets
install(TARGETS G4UniversalSim DESTINATION bin)
install(DIRECTORY config/ DESTINATION config)
install(DIRECTORY macros/ DESTINATION macros)
