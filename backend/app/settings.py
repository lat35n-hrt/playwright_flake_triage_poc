# backend/app/settings.py
from __future__ import annotations

import os
from dataclasses import dataclass


def _get_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return int(v)


def _get_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return float(v)


def _get_str(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None or v == "" else v


@dataclass(frozen=True)
class Settings:
    # Flake injection
    flake_seed: int = _get_int("FLAKE_SEED", 42)
    delay_min_ms: int = _get_int("DELAY_MIN_MS", 0)
    delay_max_ms: int = _get_int("DELAY_MAX_MS", 1200)
    delay_prob: float = _get_float("DELAY_PROB", 1.0)  # 1.0 = always inject

    # Logging
    log_filename: str = _get_str("BACKEND_JSONL_LOG", "backend_latency_samples.jsonl")

    # UI flake overlay
    ui_overlay_ms: int = _get_int("UI_OVERLAY_MS", 0)   # e.g. 300


settings = Settings()



