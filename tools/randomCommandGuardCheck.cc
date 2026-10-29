#include "Core/RandomCommandGuard.hh"

#include "G4StateManager.hh"
#include "Randomize.hh"
#include "CLHEP/Random/DoubConv.h"
#include "CLHEP/Random/JamesRandom.h"
#include "CLHEP/Random/MixMaxRng.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
int checks = 0;
void Require(bool condition, const char* label)
{
    if (!condition) throw std::runtime_error(label);
    ++checks;
}
template<class F> void Reject(F operation, const char* label)
{
    bool rejected = false;
    try { operation(); } catch (const std::runtime_error&) { rejected = true; }
    Require(rejected, label);
}
struct ScopedEngine {
    CLHEP::HepRandomEngine* previous = G4Random::getTheEngine();
    explicit ScopedEngine(CLHEP::HepRandomEngine& engine) { G4Random::setTheEngine(&engine); }
    ~ScopedEngine() { G4Random::setTheEngine(previous); }
};

std::string Read(const std::filesystem::path& path)
{
    std::ifstream input(path, std::ios::binary);
    return std::string(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
}
void Write(const std::filesystem::path& path, const std::string& bytes)
{
    std::ofstream output(path, std::ios::binary);
    output << bytes;
    output.close();
    Require(!output.fail(), "write test state");
}
std::string Command(const std::filesystem::path& path)
{
    return "/random/resetEngineFrom \"" + path.generic_string() + "\"";
}
void InvalidRestore(CLHEP::HepRandomEngine& engine, const std::filesystem::path& file, const std::string& bytes)
{
    Write(file, bytes);
    const auto before = engine.put();
    Reject([&]() { RandomCommandGuard::ExecuteRestoreIfRequested(Command(file)); }, "invalid restore refused");
    Require(engine.put() == before, "invalid restore preserves current engine");
}

std::string ReplaceField(std::string bytes, const std::string& field, const std::string& replacement)
{
    const auto begin = bytes.find(field);
    Require(begin != std::string::npos, "native field exists");
    const auto value = begin + field.size();
    const auto end = bytes.find(';', value);
    Require(end != std::string::npos, "native field terminates");
    bytes.replace(value, end - value, replacement);
    return bytes;
}

template<class Engine> void NativeRoundTrip(Engine& engine, const std::filesystem::path& directory, const std::string& stem)
{
    ScopedEngine use(engine);
    const auto file = directory / (stem + " native state.rndm");
    const auto saved = engine.put();
    engine.saveStatus(file.string().c_str());
    Require(std::filesystem::is_regular_file(file), "native saveStatus produced file");
    for (int i = 0; i < 17; ++i) engine.flat();
    Require(engine.put() != saved, "engine advanced before restore");
    Require(RandomCommandGuard::ExecuteRestoreIfRequested(Command(file)), "quoted native restore handled");
    Require(engine.put() == saved, "native restore exact state");
    Require(RandomCommandGuard::ExecuteRestoreIfRequested(Command(file)), "same-state restore accepted");
    Require(engine.put() == saved, "same-state restore exact state");
    Require(RandomCommandGuard::ExecuteRestoreIfRequested("/random/resetEngineFrom " + file.generic_string()), "unquoted space path accepted");
    Require(engine.put() == saved, "unquoted path exact state");
    const auto beforeMissing = engine.put();
    Reject([&]() { RandomCommandGuard::ExecuteRestoreIfRequested(Command(directory / "missing.rndm")); }, "missing state rejected");
    Require(engine.put() == beforeMissing, "missing file preserves engine");
    InvalidRestore(engine, directory / (stem + "_bad.rndm"), "");
    InvalidRestore(engine, directory / (stem + "_bad.rndm"), Read(file).substr(0, 35));
    InvalidRestore(engine, directory / (stem + "_bad.rndm"), Read(file) + "extra-token");
}

std::string JamesVector(const std::vector<unsigned long>& state)
{
    std::ostringstream text;
    text << "Uvec\n";
    for (auto value : state) text << value << '\n';
    return text.str();
}
}  // namespace

int main()
{
    const auto oldDirectory = std::filesystem::current_path();
    const auto directory = std::filesystem::temp_directory_path() /
        ("g4usim-random-guard-" + std::to_string(std::chrono::high_resolution_clock::now().time_since_epoch().count()));
    try {
        Require(std::filesystem::create_directory(directory), "unique test directory created");
        using namespace RandomCommandGuard;
        Validate("/random/setSeeds 1 2");
        Validate("/random/setSeeds +1 -2");
        Validate("/random/setSeeds " + std::to_string(std::numeric_limits<long>::max()) + " 1");
        Validate("/random/setSeeds " + std::to_string(std::numeric_limits<long>::min() + 1) + " 1");
        ++checks;
        std::string many = "/random/setSeeds";
        for (int i = 0; i < 99; ++i) many += " 1";
        Validate(many); ++checks;
        Reject([&]() { Validate(many + " 1"); }, "100 seed values rejected");
        for (const auto* command : {"/random/setSeeds 1", "/random/setSeeds 1 2 0", "/random/setSeeds 0 2",
                                   "/random/setSeeds 1 0 3", "/random/setSeeds 1 2junk", "/random/setSeeds 1 1.5",
                                   "/random/setSeeds 1 999999999999999999999999999999"}) {
            Reject([&]() { Validate(command); }, "malformed seed list rejected");
        }
        Reject([&]() { Validate("/random/setSeeds 1 " + std::to_string(std::numeric_limits<long>::min())); }, "LONG_MIN rejected");
        Validate("/random/resetEngineFrom missing file.rndm");
        Validate("/random/resetEngineFrom");
        Validate("/random/resetEngineFromEachEvent false");
        ++checks;
        for (const auto* command : {"/random/resetEngineFrom \"\"", "/random/resetEngineFrom \"unterminated",
                                   "/random/resetEngineFromEachEvent true", "/random/resetEngineFromEachEvent 1"}) {
            Reject([&]() { Validate(command); }, "unsupported restore syntax rejected");
        }
        Require(!ExecuteRestoreIfRequested("/run/initialize"), "non-restore returned false");

        CLHEP::MixMaxRng mixmax(12345);
        CLHEP::HepJamesRandom james(98765);
        NativeRoundTrip(mixmax, directory, "mixmax");
        NativeRoundTrip(james, directory, "james");
        {
            ScopedEngine use(mixmax);
            const std::string native = Read(directory / "mixmax native state.rndm");
            InvalidRestore(mixmax, directory / "mix_bad.rndm", ReplaceField(native, "sumtot=", "0"));
            InvalidRestore(mixmax, directory / "mix_bad.rndm", ReplaceField(native, "counter=", "999"));
            InvalidRestore(mixmax, directory / "mix_bad.rndm", ReplaceField(native, "counter=", "-1"));
            InvalidRestore(mixmax, directory / "mix_bad.rndm", ReplaceField(native, "N=", "999"));
            InvalidRestore(mixmax, directory / "mix_bad.rndm", Read(directory / "james native state.rndm"));
            std::filesystem::current_path(directory);
            mixmax.saveStatus("currentRun.rndm");
            const auto state = mixmax.put();
            mixmax.flat();
            Require(ExecuteRestoreIfRequested("/random/resetEngineFrom"), "default filename accepted");
            Require(mixmax.put() == state, "default file restored exact state");
            const auto priorState = G4StateManager::GetStateManager()->GetCurrentState();
            G4StateManager::GetStateManager()->SetNewState(G4State_EventProc);
            Reject([&]() { ExecuteRestoreIfRequested("/random/resetEngineFrom"); }, "event-processing restore rejected");
            Require(mixmax.put() == state, "state refusal preserves engine");
            G4StateManager::GetStateManager()->SetNewState(priorState);
            std::filesystem::current_path(oldDirectory);
        }
        {
            ScopedEngine use(james);
            auto state = james.put();
            state[201] = 97;
            InvalidRestore(james, directory / "james_bad.rndm", JamesVector(state));
            state = james.put(); state[0] ^= 1UL;
            InvalidRestore(james, directory / "james_bad.rndm", JamesVector(state));
            state = james.put();
            const auto nan = CLHEP::DoubConv::dto2longs(std::numeric_limits<double>::quiet_NaN());
            state[1] = nan[0]; state[2] = nan[1];
            InvalidRestore(james, directory / "james_bad.rndm", JamesVector(state));
            state = james.put();
            const auto otherConstant = CLHEP::DoubConv::dto2longs(0.25);
            state[197] = otherConstant[0]; state[198] = otherConstant[1];
            InvalidRestore(james, directory / "james_bad.rndm", JamesVector(state));
            InvalidRestore(james, directory / "james_bad.rndm", Read(directory / "mixmax native state.rndm"));
        }
        std::filesystem::current_path(oldDirectory);
        std::filesystem::remove_all(directory);
        std::cout << "checks=" << checks << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::filesystem::current_path(oldDirectory);
        std::cerr << error.what() << "\nevidence=" << directory.string() << '\n';
        return 1;
    }
}
