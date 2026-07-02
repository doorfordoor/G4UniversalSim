from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SourceSettings:
    preset: str = "proton_beam"
    particle: str = "proton"
    energy: str = "10 MeV"
    position: str = "0,0,-1 mm"
    direction: str = "0,0,1"
