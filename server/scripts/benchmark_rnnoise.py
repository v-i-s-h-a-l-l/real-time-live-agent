#!/usr/bin/env python3
"""Benchmark RNNoise preprocessing latency (local dev tool — not CI).

Usage (from server/):
  python scripts/benchmark_rnnoise.py
  python scripts/benchmark_rnnoise.py --compare
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audio.rnnoise_processor import RNNoiseProcessor


def _chunk_pcm16(n_samples: int = 512) -> np.ndarray:
    t = np.linspace(0, 1, n_samples, endpoint=False)
    wave = (0.3 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    noise = np.random.randint(-500, 500, size=n_samples, dtype=np.int16)
    return np.clip(wave + noise, -32768, 32767).astype(np.int16)


def benchmark_passthrough(iterations: int = 2000) -> dict:
    pcm = _chunk_pcm16()
    times_us: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        _ = pcm.copy()
        times_us.append((time.perf_counter() - t0) * 1_000_000)
    return _stats(times_us)


def benchmark_rnnoise(iterations: int = 2000) -> dict:
    from audio.rnnoise_native import library_available

    if not library_available():
        print("RNNoise library not installed — install pyrnnoise wheel first.")
        sys.exit(1)

    proc = RNNoiseProcessor(enabled=True, session_id="bench")
    if not proc.initialize():
        print("RNNoise failed to initialize.")
        sys.exit(1)

    pcm = _chunk_pcm16()
    times_us: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        proc.process(pcm)
        times_us.append((time.perf_counter() - t0) * 1_000_000)

    proc.close()
    return _stats(times_us)


def _stats(times_us: list[float]) -> dict:
    sorted_t = sorted(times_us)
    p95_idx = int(len(sorted_t) * 0.95) - 1
    return {
        "avg_us": statistics.mean(times_us),
        "p95_us": sorted_t[max(0, p95_idx)],
        "max_us": max(times_us),
        "iterations": len(times_us),
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark RNNoise frame latency")
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare passthrough vs RNNoise enabled",
    )
    args = parser.parse_args()

    if args.compare:
        base = benchmark_passthrough(args.iterations)
        rn = benchmark_rnnoise(args.iterations)
        print("Passthrough (copy only):")
        print(f"  avg={base['avg_us']:.1f}µs  p95={base['p95_us']:.1f}µs  max={base['max_us']:.1f}µs")
        print("RNNoise enabled:")
        print(f"  avg={rn['avg_us']:.1f}µs  p95={rn['p95_us']:.1f}µs  max={rn['max_us']:.1f}µs")
        delta = rn["avg_us"] - base["avg_us"]
        print(f"RNNoise overhead (avg): +{delta:.1f}µs per 512-sample frame (~32ms audio)")
        print(
            "Note: end-to-end turn latency also includes STT/LLM/TTS — "
            "compare voice sessions with RNNOISE_ENABLED=false vs true."
        )
    else:
        rn = benchmark_rnnoise(args.iterations)
        print(f"RNNoise: avg={rn['avg_us']:.1f}µs p95={rn['p95_us']:.1f}µs max={rn['max_us']:.1f}µs")


if __name__ == "__main__":
    main()
