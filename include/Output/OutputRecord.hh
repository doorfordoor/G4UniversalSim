#pragma once

#include <string>

struct HitRecord {
    int eventID = -1;
    int trackID = -1;
    int parentID = -1;
    std::string particleName;
    double edep = 0.0;
    double ndep = 0.0;
    double stepLength = 0.0;
    double x0 = 0.0;
    double y0 = 0.0;
    double z0 = 0.0;
    double x1 = 0.0;
    double y1 = 0.0;
    double z1 = 0.0;
    double px = 0.0;
    double py = 0.0;
    double pz = 0.0;
    double kineticEnergy = 0.0;
    std::string processName;
    std::string volumeName;
    double weight = 1.0;
    double LETcalc = 0.0;
    double LETstep = 0.0;
};

struct EventEdepRecord {
    int eventID = -1;
    double rawEdep = 0.0;
    double weightedEdep = 0.0;
};
