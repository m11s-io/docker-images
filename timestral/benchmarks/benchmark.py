#!/usr/bin/env python3
"""Measure cold load, warm latency and peak memory for upstream Timestral checkpoints."""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time

import numpy as np
import torch
from timestral import TimestralForecaster


CHECKPOINTS = {
    "28M": ("mistralai/Timestral-28M", "49b26409ac87b5935539a5d8ffe7f397b720db47"),
    "209M": ("mistralai/Timestral-209M", "9874d252ab0aae16f7f7c999f98f98d6ad7d8365"),
}


def sync(device: str) -> None:
    if device.startswith("cuda"):
        torch.cuda.synchronize(device)


def peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def percentile(values: list[float], p: float) -> float:
    return float(np.percentile(values, p))


def benchmark_case(
    forecaster: TimestralForecaster,
    checkpoint: str,
    device: str,
    context_steps: int,
    horizon: int,
    variates: int,
    covariates: str,
    repeats: int,
) -> dict[str, object]:
    rng = np.random.default_rng(41)
    context = rng.normal(size=(1, variates, context_steps)).astype(np.float32)
    kwargs: dict[str, object] = {}
    if covariates == "numeric":
        past = rng.normal(size=(1, 1, context_steps)).astype(np.float32)
        known = rng.normal(size=(1, 1, context_steps + horizon)).astype(np.float32)
        kwargs.update(past_covariates=past, known_covariates=known)

    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats(device)
    forecaster.forecast(context, prediction_length=horizon, **kwargs)
    sync(device)
    timings = []
    for _ in range(repeats):
        start = time.perf_counter()
        forecaster.forecast(context, prediction_length=horizon, **kwargs)
        sync(device)
        timings.append(time.perf_counter() - start)

    result: dict[str, object] = {
        "model": checkpoint,
        "device": device,
        "context_steps": context_steps,
        "horizon": horizon,
        "variates": variates,
        "covariates": covariates,
        "repeats": repeats,
        "warm_p50_seconds": percentile(timings, 50),
        "warm_p95_seconds": percentile(timings, 95),
        "process_peak_rss_bytes_cumulative": peak_rss_bytes(),
    }
    if device.startswith("cuda"):
        result["cuda_peak_allocated_bytes"] = torch.cuda.max_memory_allocated(device)
        result["cuda_peak_reserved_bytes"] = torch.cuda.max_memory_reserved(device)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", choices=CHECKPOINTS, default=["28M"])
    parser.add_argument("--device", default="cpu", help="cpu or a CUDA device such as cuda:0")
    parser.add_argument("--contexts", nargs="+", type=int, default=[512, 4096, 32768])
    parser.add_argument("--horizons", nargs="+", type=int, default=[96, 1024])
    parser.add_argument("--variates", nargs="+", type=int, default=[1, 4])
    parser.add_argument("--covariates", nargs="+", choices=["none", "numeric"], default=["none", "numeric"])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-context", type=int, default=32768)
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    if args.threads < 1:
        parser.error("--threads must be positive")
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        parser.error("CUDA requested but torch.cuda.is_available() is false")
    torch.set_num_threads(args.threads)

    for name in args.models:
        repo, revision = CHECKPOINTS[name]
        start = time.perf_counter()
        forecaster = TimestralForecaster.from_pretrained(
            repo, revision=revision, device=args.device, max_context=args.max_context
        )
        load_seconds = time.perf_counter() - start
        for context_steps in args.contexts:
            for horizon in args.horizons:
                for variates in args.variates:
                    for covariates in args.covariates:
                        result = benchmark_case(
                            forecaster, repo, args.device, context_steps, horizon,
                            variates, covariates, args.repeats,
                        )
                        result["revision"] = revision
                        result["cold_load_seconds"] = load_seconds
                        print(json.dumps(result, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
