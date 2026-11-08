#pragma once
#include "G4UserStackingAction.hh"
#include <memory>
struct WorkerRunContext;
class PhaseSpaceStackingAction final:public G4UserStackingAction {
public:
    explicit PhaseSpaceStackingAction(std::shared_ptr<WorkerRunContext>);
    ~PhaseSpaceStackingAction() override;
    G4ClassificationOfNewTrack ClassifyNewTrack(const G4Track*) override;
private:
    std::shared_ptr<WorkerRunContext> context_;
};
