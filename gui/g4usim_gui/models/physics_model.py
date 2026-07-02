from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PhysicsSettings:
    reference: str = "FTFP_BERT_EMZ"
    default_cut: str = "1 mm"
    enable_biasing: bool = False
