"""
app/pipeline/processors/base.py — Base Processor Protocol
===========================================================
"""
from __future__ import annotations
from typing import Any, Dict, Protocol
import numpy as np


class DetectionProcessor(Protocol):
    def process(self, frame: np.ndarray, camera: dict, timestamp: str, **kwargs) -> Any:
        ...