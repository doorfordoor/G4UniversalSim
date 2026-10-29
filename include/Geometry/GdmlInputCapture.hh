#pragma once
#include <memory>
#include <mutex>
#include <string>
#include <vector>

namespace GdmlIO {
struct AcceptedInput {
    std::string path;
    std::string sha256;
};

// Scope after G4GDMLParser construction and around its synchronous Read().
// All project GDML entry points also hold NativeMutex across parser lifetime
// changes, since Xerces initializes/terminates process-global services there.
// Local inputs are buffered once through Xerces' own file manager; the parser
// reads that same buffer. Network streams are transparently observed, and only
// complete EOF-terminated streams receive hashes. No file content is returned.
class GdmlInputCapture {
public:
    static std::recursive_mutex& NativeMutex();
    GdmlInputCapture();
    ~GdmlInputCapture();
    GdmlInputCapture(const GdmlInputCapture&) = delete;
    GdmlInputCapture& operator=(const GdmlInputCapture&) = delete;
    std::vector<AcceptedInput> AcceptedInputs() const;
    std::vector<std::string> UntrackedInputs() const;
private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};
}
