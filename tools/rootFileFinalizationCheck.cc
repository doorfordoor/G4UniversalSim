#include "Output/RootFileFinalization.hh"

#include <iostream>
#include <string>
#include <vector>

namespace {
int checks = 0;
void Require(bool condition, const char* description)
{
    ++checks;
    if (!condition) throw std::runtime_error(description);
}

struct Manager {
    int writeMode = 0, closeMode = 0;
    bool open = true, queryThrows = false;
    bool stayOpenOnSuccess = false, closeOnFailure = false;
    std::vector<std::string> calls;
    bool Write() {
        calls.push_back("write");
        if (writeMode == 2) throw std::runtime_error("original write exception");
        if (writeMode == 3) throw 17;
        return writeMode == 0;
    }
    bool CloseFile() {
        calls.push_back("close");
        if (closeMode == 2) throw std::runtime_error("original close exception");
        if (closeMode == 3) throw 23;
        open = closeMode == 0 ? stayOpenOnSuccess : !closeOnFailure;
        return closeMode == 0;
    }
    bool IsOpenFile() {
        calls.push_back("is_open");
        if (queryThrows) throw std::runtime_error("query exception");
        return open;
    }
};
}

int main()
{
    try {
        for (int write = 0; write < 4; ++write) {
            for (int close = 0; close < 4; ++close) {
                Manager manager;
                manager.writeMode = write;
                manager.closeMode = close;
                bool pending = true, open = true;
                std::string failure;
                try {
                    Require(AnalysisOutput::detail::FinalizeRootFile(manager, pending, open), "success result");
                } catch (const std::runtime_error& error) {
                    failure = error.what();
                } catch (int value) {
                    failure = std::to_string(value);
                }
                const std::string writeErrors[] = {"", "AnalysisOutput: failed to write ROOT file", "original write exception", "17"};
                const std::string closeErrors[] = {"", "AnalysisOutput: failed to close ROOT file", "original close exception", "23"};
                Require(failure == (write ? writeErrors[write] : closeErrors[close]), "first cause retained");
                Require(manager.calls == std::vector<std::string>{"write", "close", "is_open"}, "write/close each attempted in order");
                Require(!pending, "attempt consumed");
                Require(open == (close != 0), "actual resource state retained");
                Require(!AnalysisOutput::detail::FinalizeRootFile(manager, pending, open), "repeat is no-op");
                Require(manager.calls.size() == 3, "no implicit retry");
            }
        }
        Manager unopened;
        for (int write : {0, 2}) {
            Manager manager;
            manager.stayOpenOnSuccess = true;
            manager.writeMode = write;
            bool pending = true, open = true;
            std::string failure;
            try { AnalysisOutput::detail::FinalizeRootFile(manager, pending, open); }
            catch (const std::runtime_error& error) { failure = error.what(); }
            Require(failure == (write ? "original write exception" :
                "AnalysisOutput: ROOT file remains open after close"), "still-open first cause");
            Require(open && !pending, "successful Close return is not resource evidence");
        }
        {
            Manager manager;
            manager.closeMode = 1;
            manager.closeOnFailure = true;
            bool pending = true, open = true;
            std::string failure;
            try { AnalysisOutput::detail::FinalizeRootFile(manager, pending, open); }
            catch (const std::runtime_error& error) { failure = error.what(); }
            Require(failure == "AnalysisOutput: failed to close ROOT file", "false close lost");
            Require(!open && !pending, "closed resource distinct from failed close report");
        }
        bool pending = false, open = false;
        Require(!AnalysisOutput::detail::FinalizeRootFile(unopened, pending, open), "never-opened no-op");
        Require(unopened.calls.empty(), "never-opened no operations");
        for (int write : {0, 2}) {
            Manager manager;
            manager.writeMode = write;
            manager.queryThrows = true;
            pending = open = true;
            std::string failure;
            try { AnalysisOutput::detail::FinalizeRootFile(manager, pending, open); }
            catch (const std::runtime_error& error) { failure = error.what(); }
            Require(failure == (write ? "original write exception" : "query exception"), "query preserves first cause");
            Require(open && !pending, "query failure conservatively retains open state");
            Require(manager.calls.size() == 3, "query failure follows close");
        }
        std::cout << "rootFileFinalizationCheck: " << checks << " checks passed (controlled adapter faults)\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
