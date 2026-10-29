"""Particle tracks for the 3D view (roadmap G6), without Qt or VTK.

Reads the backend's trajectory files (roadmap H1, schema g4usim_trajectories_v1:
trajectories_tN[_rR].json, one per worker) of one run, merges the workers' events in
event order and selects what to draw: one event or all, the particles shown and a
minimum starting energy (primaries are always kept). Each particle gets a fixed colour
so tracks look the same from event to event.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from g4usim_gui.output.provenance import output_files, output_evidence

SCHEMA = "g4usim_trajectories_v1"
FILE = re.compile(r"trajectories_t(\d+)(?:_r(\d+))?\.json$")
# common particles keep their colour (others take the palette in name order)
PARTICLE_COLOURS = {
    "proton": "#e15759", "e-": "#f28e2b", "e+": "#59a14f", "gamma": "#4e79a7", "neutron": "#9aa6b2",
    "alpha": "#b07aa1", "mu-": "#76b7b2", "mu+": "#76b7b2", "pi+": "#ff9da7", "pi-": "#ff9da7",
    "deuteron": "#d37295", "triton": "#d37295", "He3": "#b07aa1", "opticalphoton": "#a0cbe8",
}
PALETTE = ("#edc948", "#86bcb6", "#9c755f", "#8cd17d", "#bab0ac", "#d4a6c8", "#79706e")


@dataclass
class Track:
    track: int
    parent: int
    particle: str
    creator: str
    initial_energy: float          # MeV
    end_process: str
    length: float                  # mm
    points: list[tuple[float, float, float]]
    energies: list[float]
    volumes: list[str]             # per point (point 0: start volume; point i: the step's volume)

    @property
    def primary(self) -> bool:
        return self.parent == 0

    def describe(self) -> str:
        return (f"{self.particle} #{self.track} ({self.creator}), {self.initial_energy:.4g} MeV, "
                f"{self.length:.4g} mm, ends: {self.end_process or '?'}")


@dataclass
class TrajectoryEvent:
    event: int
    tracks: list[Track] = field(default_factory=list)
    truncated: bool = False


@dataclass
class TrajectorySet:
    source: str = ""
    run: int = 0
    events: list[TrajectoryEvent] = field(default_factory=list)
    truncated: bool = False

    def particles(self) -> dict[str, int]:
        """Particle -> number of tracks, over all events."""
        counts: dict[str, int] = {}
        for event in self.events:
            for track in event.tracks:
                counts[track.particle] = counts.get(track.particle, 0) + 1
        return dict(sorted(counts.items()))

    def colours(self) -> dict[str, str]:
        result: dict[str, str] = {}
        others = []
        for particle in self.particles():
            if particle in PARTICLE_COLOURS:
                result[particle] = PARTICLE_COLOURS[particle]
            else:
                others.append(particle)
        for index, particle in enumerate(others):
            result[particle] = PALETTE[index % len(PALETTE)]
        return result


@dataclass
class TrackFilter:
    event_index: int | None = 0          # index into TrajectorySet.events; None = all events
    hidden_particles: set[str] = field(default_factory=set)
    min_energy: float = 0.0              # MeV, secondaries starting below are hidden
    primaries_only: bool = False

    def tracks(self, trajectories: TrajectorySet) -> list[Track]:
        if not trajectories.events:
            return []
        if self.event_index is None:
            events = trajectories.events
        else:
            events = [trajectories.events[max(0, min(self.event_index, len(trajectories.events) - 1))]]
        selected = []
        for event in events:
            for track in event.tracks:
                if track.particle in self.hidden_particles:
                    continue
                if not track.primary and (self.primaries_only or track.initial_energy < self.min_energy):
                    continue
                selected.append(track)
        return selected


def trajectory_files(output_dir: str | Path, run: int = 0) -> list[Path]:
    """The worker files of one run (run 0: trajectories_tN.json; run R: trajectories_tN_rR.json)."""
    files = []
    for path in output_files(output_dir, "trajectories_t*.json"):
        match = FILE.fullmatch(path.name)
        if match and int(match.group(2) or 0) == run:
            files.append(path)
    return sorted(files, key=lambda p: int(FILE.fullmatch(p.name).group(1)))


def available_runs(output_dir: str | Path) -> list[int]:
    runs = set()
    for path in output_files(output_dir, "trajectories_t*.json"):
        match = FILE.fullmatch(path.name)
        if match:
            runs.add(int(match.group(2) or 0))
    return sorted(runs)


def load_trajectories(output_dir: str | Path, run: int | None = None) -> TrajectorySet:
    """All events of a run (default: the last run that has trajectories). Raises ValueError on a bad file."""
    runs = available_runs(output_dir)
    if not runs:
        raise ValueError(f"no trajectory files (trajectories_tN.json) in {output_dir}")
    run = runs[-1] if run is None else run
    result = TrajectorySet(source=str(output_dir) + " [" + output_evidence(output_dir).status + "]", run=run)
    seen: set[int] = set()
    for path in trajectory_files(output_dir, run):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"cannot read {path.name}: {error}") from error
        if data.get("schema") != SCHEMA or data.get("length_unit") != "mm" or data.get("energy_unit") != "MeV":
            raise ValueError(f"{path.name} is not a {SCHEMA} file")
        result.truncated |= bool(data.get("truncated"))
        for item in data.get("events", []):
            event_id = int(item["event"])
            if event_id in seen:
                raise ValueError(f"event {event_id} appears in more than one file")
            seen.add(event_id)
            names = [str(name) for name in item.get("volumes", [])]
            event = TrajectoryEvent(event_id, truncated=bool(item.get("truncated")))
            for track in item.get("tracks", []):
                points = track.get("points", [])
                if any(len(p) != 5 or not 0 <= int(p[4]) < len(names) for p in points):
                    raise ValueError(f"{path.name}: event {event_id} track {track.get('track')} has a bad point")
                event.tracks.append(Track(
                    track=int(track["track"]), parent=int(track["parent"]), particle=str(track["particle"]),
                    creator=str(track.get("creator", "")), initial_energy=float(track["initial_energy"]),
                    end_process=str(track.get("end_process", "")), length=float(track.get("length", 0.0)),
                    points=[(float(p[0]), float(p[1]), float(p[2])) for p in points],
                    energies=[float(p[3]) for p in points], volumes=[names[int(p[4])] for p in points]))
            result.events.append(event)
    result.events.sort(key=lambda e: e.event)
    return result
