// main.cc - G4UniversalSim Main Entry Point
#include <iostream>
#include "Core/SimulationManager.hh"

int main(int argc, char** argv) {
    std::cout << "G4UniversalSim - Universal Geant4 Simulation Framework" << std::endl;
    
    SimulationManager* manager = new SimulationManager();
    
    // TODO: Initialize and run simulation
    
    delete manager;
    
    return 0;
}
