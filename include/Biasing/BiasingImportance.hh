#ifndef BIASING_IMPORTANCE_HH
#define BIASING_IMPORTANCE_HH

#include "G4VPhysicsConstructor.hh"

class BiasingManager;

// A thin registration adapter; all sampling is done by native Geant4 processes.
class BiasingImportance final : public G4VPhysicsConstructor {
public:
    explicit BiasingImportance(const BiasingManager* manager);
    ~BiasingImportance() override;
    void ConstructParticle() override;
    void ConstructProcess() override;
    void TerminateWorker() override;
private:
    const BiasingManager* manager_;
};

#endif
