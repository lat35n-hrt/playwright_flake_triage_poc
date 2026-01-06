# backend/app/flake.py
from __future__ import annotations

import asyncio
import random
import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class DelayConfig:
    seed: int
    min_ms: int
    max_ms: int
    prob: float


class DelayInjector:
    """
    Random delay injector with reproducibility (seeded RNG).
    Thread-safe RNG access (important if uvicorn uses multiple workers/threads).
    """

    def __init__(self, cfg: DelayConfig) -> None:
        if cfg.min_ms < 0 or cfg.max_ms < 0:
            raise ValueError("min_ms/max_ms must be >= 0")
        if cfg.min_ms > cfg.max_ms:
            raise ValueError("min_ms must be <= max_ms")
        if not (0.0 <= cfg.prob <= 1.0):
            raise ValueError("prob must be within [0.0, 1.0]")

        self._cfg = cfg
        self._rng = random.Random(cfg.seed)
        self._lock = threading.Lock()

    def pick_delay_ms(self) -> int:
        with self._lock:
            roll = self._rng.random()
            if roll > self._cfg.prob:
                return 0
            return self._rng.randint(self._cfg.min_ms, self._cfg.max_ms)

    async def inject(self) -> int:
        delay_ms = self.pick_delay_ms()
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)
        return delay_ms
