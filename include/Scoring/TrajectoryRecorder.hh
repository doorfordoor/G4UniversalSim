#pragma once

// Particle trajectories of the first events of a run (roadmap H1), for display and
// checks: [output] trajectories = <N> records every track of events 0..N-1.
//
// Written per worker as trajectories_tN[_rR].json, schema g4usim_trajectories_v1,
// one event object appended after each recorded event:
//   {"schema", "length_unit": "mm", "energy_unit": "MeV", "run", "thread",
//    "events": [{"event", "volumes": [physical volume names], "truncated",
//                "tracks": [{"track", "parent", "particle", "pdg", "creator",
//                            "initial_energy", "end_process", "length",
//                            "points": [[x, y, z, kinetic_energy, volume], ...]}]}],
//    "truncated"}
// Point 0 is the track's start (its volume: where it starts); point i > 0 is the
// end of step i, and "volume" is the index of the volume that step travelled in
// (the pre-step volume), so the segment from point i-1 to point i lies in it.
// kinetic_energy is the value at that point. Tracks starting below
// trajectory_min_energy are left out except primaries (parent 0); after
// trajectory_max_points points in a file no further points are kept and the event
// and file are marked truncated.

#include <cstddef>
#include <fstream>
#include <map>
#include <string>
#include <vector>

class G4Step;

struct TrajectorySettings {
    int events = 0;                    // 0 = off
    double minEnergy = 0.0;            // Geant4 internal energy units
    std::size_t maxPoints = 2000000;
};

class TrajectoryRecorder {
public:
    explicit TrajectoryRecorder(TrajectorySettings settings = {});

    const TrajectorySettings& GetSettings() const;
    bool IsEnabled() const;
    bool IsRecording() const;            // the current event is recorded

    void BeginRun(const std::string& path, int runID, int threadID);
    void BeginEvent(int eventID);
    void RecordStep(const G4Step* step);
    void EndEvent();
    // Closes the file; returns its path ("" when nothing was opened).
    std::string EndRun();

private:
    struct Point {
        double x, y, z, energy;
        int volume;
    };
    struct Track {
        int parent = 0;
        std::string particle;
        int pdg = 0;
        std::string creator;
        double initialEnergy = 0.0;
        std::string endProcess;
        double length = 0.0;
        std::vector<Point> points;
    };

    int VolumeIndex(const std::string& name);
    void WriteEvent();

    TrajectorySettings settings_;
    std::ofstream file_;
    std::string path_;
    bool firstEvent_ = true;
    bool recording_ = false;
    bool eventTruncated_ = false;
    bool fileTruncated_ = false;
    int eventID_ = -1;
    std::size_t pointsInFile_ = 0;
    std::map<int, Track> tracks_;
    std::map<int, bool> skipped_;      // tracks left out (below the energy threshold)
    std::vector<std::string> volumes_;
    std::map<std::string, int> volumeIndex_;
};
