from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScoringSettings:
    enabled: bool = True
    hits: bool = True
    event_edep: bool = True
    edep: bool = True
    hist_bins: int = 100
    hist_min: str = "0 eV"
    hist_max: str = "10 MeV"
