#include "Scoring/TrajectoryRecorder.hh"

#include "G4ParticleDefinition.hh"
#include "G4Step.hh"
#include "G4StepPoint.hh"
#include "G4SystemOfUnits.hh"
#include "G4Track.hh"
#include "G4VPhysicalVolume.hh"
#include "G4VProcess.hh"

#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace {

std::string Quote(const std::string& text)
{
    std::string out = "\"";
    for (const char c : text) {
        if (c == '"' || c == '\\') out += '\\';
        if (static_cast<unsigned char>(c) < 0x20) continue;
        out += c;
    }
    return out + "\"";
}

std::string VolumeName(const G4StepPoint* point)
{
    const G4VPhysicalVolume* volume = point ? point->GetPhysicalVolume() : nullptr;
    // G4String and std::string have no common ternary type under GCC.
    return volume ? std::string(volume->GetName()) : std::string("OutOfWorld");
}

}  // namespace

TrajectoryRecorder::TrajectoryRecorder(TrajectorySettings settings)
    : settings_(settings)
{
}

const TrajectorySettings& TrajectoryRecorder::GetSettings() const
{
    return settings_;
}

bool TrajectoryRecorder::IsEnabled() const
{
    return settings_.events > 0;
}

bool TrajectoryRecorder::IsRecording() const
{
    return recording_;
}

void TrajectoryRecorder::BeginRun(const std::string& path, int runID, int threadID)
{
    path_ = path;
    file_.open(path, std::ios::out | std::ios::trunc);
    if (!file_) throw std::runtime_error("Cannot open trajectory file: " + path);
    file_ << "{\"schema\": \"g4usim_trajectories_v1\", \"length_unit\": \"mm\", \"energy_unit\": \"MeV\", "
          << "\"run\": " << runID << ", \"thread\": " << threadID << ", \"events\": [";
    firstEvent_ = true;
    fileTruncated_ = false;
    pointsInFile_ = 0;
    recording_ = false;
}

void TrajectoryRecorder::BeginEvent(int eventID)
{
    eventID_ = eventID;
    recording_ = file_.is_open() && eventID >= 0 && eventID < settings_.events;
    eventTruncated_ = false;
    tracks_.clear();
    skipped_.clear();
    volumes_.clear();
    volumeIndex_.clear();
}

int TrajectoryRecorder::VolumeIndex(const std::string& name)
{
    const auto found = volumeIndex_.find(name);
    if (found != volumeIndex_.end()) return found->second;
    const int index = static_cast<int>(volumes_.size());
    volumes_.push_back(name);
    volumeIndex_.emplace(name, index);
    return index;
}

void TrajectoryRecorder::RecordStep(const G4Step* step)
{
    if (!recording_ || !step) return;
    const G4Track* track = step->GetTrack();
    const G4StepPoint* pre = step->GetPreStepPoint();
    const G4StepPoint* post = step->GetPostStepPoint();
    if (!track || !pre || !post) return;
    const int id = track->GetTrackID();
    if (skipped_.count(id)) return;

    auto found = tracks_.find(id);
    if (found == tracks_.end()) {
        // first step of this track: decide and record its start
        if (track->GetParentID() != 0 && pre->GetKineticEnergy() < settings_.minEnergy) {
            skipped_[id] = true;
            return;
        }
        Track entry;
        entry.parent = track->GetParentID();
        const G4ParticleDefinition* definition = track->GetParticleDefinition();
        entry.particle = definition ? definition->GetParticleName() : "";
        entry.pdg = definition ? definition->GetPDGEncoding() : 0;
        const G4VProcess* creator = track->GetCreatorProcess();
        entry.creator = creator ? creator->GetProcessName() : "primary";
        entry.initialEnergy = pre->GetKineticEnergy();
        const G4ThreeVector start = pre->GetPosition();
        if (pointsInFile_ < settings_.maxPoints) {
            entry.points.push_back({start.x(), start.y(), start.z(), pre->GetKineticEnergy(), VolumeIndex(VolumeName(pre))});
            ++pointsInFile_;
        } else {
            eventTruncated_ = fileTruncated_ = true;
        }
        found = tracks_.emplace(id, std::move(entry)).first;
    }
    Track& entry = found->second;
    entry.length += step->GetStepLength();
    if (const G4VProcess* process = post->GetProcessDefinedStep()) entry.endProcess = process->GetProcessName();
    if (pointsInFile_ >= settings_.maxPoints) {
        eventTruncated_ = fileTruncated_ = true;
        return;
    }
    const G4ThreeVector end = post->GetPosition();
    entry.points.push_back({end.x(), end.y(), end.z(), post->GetKineticEnergy(), VolumeIndex(VolumeName(pre))});
    ++pointsInFile_;
}

void TrajectoryRecorder::EndEvent()
{
    if (recording_) WriteEvent();
    recording_ = false;
    tracks_.clear();
    skipped_.clear();
}

void TrajectoryRecorder::WriteEvent()
{
    std::ostringstream out;
    out << std::setprecision(8);
    out << (firstEvent_ ? "\n" : ",\n") << "{\"event\": " << eventID_ << ", \"truncated\": "
        << (eventTruncated_ ? "true" : "false") << ", \"volumes\": [";
    for (std::size_t i = 0; i < volumes_.size(); ++i) out << (i ? ", " : "") << Quote(volumes_[i]);
    out << "], \"tracks\": [";
    bool firstTrack = true;
    for (const auto& [id, track] : tracks_) {
        out << (firstTrack ? "\n" : ",\n") << " {\"track\": " << id << ", \"parent\": " << track.parent
            << ", \"particle\": " << Quote(track.particle) << ", \"pdg\": " << track.pdg
            << ", \"creator\": " << Quote(track.creator) << ", \"initial_energy\": " << track.initialEnergy / MeV
            << ", \"end_process\": " << Quote(track.endProcess) << ", \"length\": " << track.length / mm
            << ", \"points\": [";
        for (std::size_t i = 0; i < track.points.size(); ++i) {
            const Point& p = track.points[i];
            out << (i ? ", " : "") << "[" << p.x / mm << ", " << p.y / mm << ", " << p.z / mm << ", "
                << p.energy / MeV << ", " << p.volume << "]";
        }
        out << "]}";
        firstTrack = false;
    }
    out << "]}";
    file_ << out.str();
    if (!file_) throw std::runtime_error("Cannot write trajectory file: " + path_);
    firstEvent_ = false;
}

std::string TrajectoryRecorder::EndRun()
{
    if (!file_.is_open()) return "";
    file_ << "\n], \"truncated\": " << (fileTruncated_ ? "true" : "false") << "}\n";
    file_.close();
    if (file_.fail()) throw std::runtime_error("Cannot close trajectory file: " + path_);
    recording_ = false;
    return path_;
}
