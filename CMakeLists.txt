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

# Install targets
install(TARGETS G4UniversalSim DESTINATION bin)
install(DIRECTORY config/ DESTINATION config)
install(DIRECTORY macros/ DESTINATION macros)
