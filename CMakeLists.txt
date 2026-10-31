# CMakeLists.txt for G4UniversalSim

cmake_minimum_required(VERSION 3.10 FATAL_ERROR)
project(G4UniversalSim VERSION 1.0.0 LANGUAGES CXX)

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

# Include directories
include_directories(${PROJECT_SOURCE_DIR}/include)

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
set(G4USIM_SOURCE_MANIFEST "")
foreach(input_file IN LISTS G4USIM_BUILD_INPUTS)
    file(RELATIVE_PATH input_name ${PROJECT_SOURCE_DIR} ${input_file})
    file(SHA256 ${input_file} input_sha)
    string(APPEND G4USIM_SOURCE_MANIFEST "${input_name}:${input_sha}\n")
endforeach()
string(SHA256 G4USIM_SOURCE_FINGERPRINT "${G4USIM_SOURCE_MANIFEST}")
include(${PROJECT_SOURCE_DIR}/cmake/BuildIdentity.cmake)
g4usim_capture_build_identity("${PROJECT_SOURCE_DIR}" "${G4USIM_BUILD_INPUTS}"
    G4USIM_GIT_COMMIT G4USIM_GIT_SOURCE_STATE)
configure_file(
    ${PROJECT_SOURCE_DIR}/include/Core/BuildInfo.hh.in
    ${PROJECT_BINARY_DIR}/generated/BuildInfo.hh
    @ONLY
)

# The executable advertises this generated fingerprint from main.cc.
# Make this build-time dependency explicit even on hosts with broken
# localized MSVC include-output detection.
set_source_files_properties(main.cc PROPERTIES
    OBJECT_DEPENDS "${PROJECT_BINARY_DIR}/generated/BuildInfo.hh")

# Executable
add_executable(G4UniversalSim main.cc ${SOURCES})
include(${PROJECT_SOURCE_DIR}/cmake/WindowsRuntime.cmake)
g4usim_configure_windows_runtime(G4UniversalSim)
# GDML import/export (roadmap A5) needs a Geant4 built with GDML (XercesC).
if(Geant4_gdml_FOUND)
  target_compile_definitions(G4UniversalSim PRIVATE G4USIM_HAVE_GDML=1)
  message(STATUS "G4UniversalSim: GDML support enabled")
else()
  message(STATUS "G4UniversalSim: Geant4 has no GDML; [gdml] geometry will be rejected")
endif()
target_include_directories(G4UniversalSim PRIVATE ${PROJECT_BINARY_DIR}/generated)
target_compile_definitions(G4UniversalSim PRIVATE
    G4USIM_BUILD_CONFIGURATION="$<IF:$<BOOL:$<CONFIG>>,$<CONFIG>,unknown>")

# Link Geant4 libraries
target_link_libraries(G4UniversalSim ${Geant4_LIBRARIES})

# Standalone post-processing tool. This executable intentionally does not
# include or link Geant4.
add_executable(mergeHistograms tools/mergeHistograms.cc)
target_compile_features(mergeHistograms PRIVATE cxx_std_17)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    ${PROJECT_SOURCE_DIR}/tools/mergeHistograms.cc)
file(SHA256 ${PROJECT_SOURCE_DIR}/tools/mergeHistograms.cc G4USIM_MERGE_SOURCE_SHA256)
target_compile_definitions(mergeHistograms PRIVATE
    G4USIM_MERGE_SOURCE_SHA256="${G4USIM_MERGE_SOURCE_SHA256}")

# M0-5: CTest mirrors the standalone Python entrypoint. The standalone
# static/GUI profiles also work on hosts where Geant4 cannot be configured.
include(CTest)
if(BUILD_TESTING)
    if(Geant4_gdml_FOUND)
        add_executable(gdmlInputCaptureCheck tools/gdmlInputCaptureCheck.cc
            src/Geometry/GdmlInputCapture.cc src/Config/InputProvenance.cc)
        target_compile_features(gdmlInputCaptureCheck PRIVATE cxx_std_17)
        target_compile_definitions(gdmlInputCaptureCheck PRIVATE G4USIM_HAVE_GDML=1)
        target_link_libraries(gdmlInputCaptureCheck ${Geant4_LIBRARIES})
    endif()
    # Exercise real numeric accumulation/merge code independently of transport.
    add_executable(scoringNumericCheck tools/scoringNumericCheck.cc src/Scoring/HistoryStatistics.cc)
    target_compile_features(scoringNumericCheck PRIVATE cxx_std_17)
    add_executable(randomCommandGuardCheck tools/randomCommandGuardCheck.cc src/Core/RandomCommandGuard.cc
        src/Config/InputProvenance.cc)
    target_compile_features(randomCommandGuardCheck PRIVATE cxx_std_17)
    target_link_libraries(randomCommandGuardCheck ${Geant4_LIBRARIES})
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

# ------------------------------------------------------------
# Copy runtime resource directories next to the executable
# ------------------------------------------------------------

set(G4USIM_RUNTIME_DIRS
    config
    macros
    scripts
)

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
