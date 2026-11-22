#include "Biasing/BiasingImportance.hh"
#include "Biasing/BiasingManager.hh"

BiasingImportance::BiasingImportance(const BiasingManager* manager)
    : G4VPhysicsConstructor("G4USimMassGeometrySampling"), manager_(manager) {}
BiasingImportance::~BiasingImportance() { manager_->TerminateGeometricSamplingThread(); }
void BiasingImportance::ConstructParticle() {}
void BiasingImportance::ConstructProcess() { manager_->ConstructGeometricSamplingProcess(); }
void BiasingImportance::TerminateWorker()
{
    manager_->TerminateGeometricSamplingThread();
    G4VPhysicsConstructor::TerminateWorker();
}
