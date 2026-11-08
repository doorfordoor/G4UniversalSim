#pragma once
#include <string>

class G4RunManager;

namespace runtime {

// Main-thread, synchronous native operations. A returned UI status is not a
// successful-run receipt; callers retain their existing failure/receipt checks.
class NativeExecutionPort {
public:
    virtual ~NativeExecutionPort() = default;
    virtual int ApplyCommand(const std::string& command) = 0;
    virtual void InitializeKernel() = 0;
    virtual void BeamOn(int events) = 0;
};

// Borrows a kernel, or resolves the current kernel at invocation for the
// legacy SessionServer constructor. Does not cache any configuration/state.
class Geant4Execution final : public NativeExecutionPort {
public:
    explicit Geant4Execution(G4RunManager* manager = nullptr) noexcept;
    int ApplyCommand(const std::string& command) override;
    void InitializeKernel() override;
    void BeamOn(int events) override;
private:
    G4RunManager* RunManager() const;
    G4RunManager* manager_;
};

}  // namespace runtime
