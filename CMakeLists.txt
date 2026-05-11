# CMakeLists.txt for G4UniversalSim

cmake_minimum_required(VERSION 3.10)
project(G4UniversalSim VERSION 1.0.0 LANGUAGES CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find Geant4 package
find_package(Geant4 REQUIRED ui_all vis_all)

# Include Geant4 directories
include(${Geant4_USE_FILE})

# Include directories
include_directories(${PROJECT_SOURCE_DIR}/include)

# Source files
file(GLOB_RECURSE SOURCES ${PROJECT_SOURCE_DIR}/src/*.cc)

# Executable
add_executable(G4UniversalSim main.cc ${SOURCES})

# Link Geant4 libraries
target_link_libraries(G4UniversalSim ${Geant4_LIBRARIES})

# Standalone post-processing tool. This executable intentionally does not
# include or link Geant4.
add_executable(mergeHistograms tools/mergeHistograms.cc)
target_compile_features(mergeHistograms PRIVATE cxx_std_17)

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
