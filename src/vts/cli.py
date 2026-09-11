from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_config, project_path
from .pipeline import run_all, run_baseline, run_calibration, run_evaluation, run_reference
from .reference import generate_synthetic_reference


def _print(obj) -> None:
    if isinstance(obj, Path):
        print(obj)
    else:
        print(json.dumps(obj, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Virtual Temperature Sensing EnergyPlus pipeline")
    parser.add_argument("--config", default="configs/project.yaml", help="Path to YAML configuration")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("baseline", help="Run the baseline EnergyPlus model")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("reference", help="Generate the synthetic reference directly from baseline output")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("calibrate", help="Run differential-evolution calibration")
    p.add_argument("--strategy", choices=["full", "sparse"], required=True)

    sub.add_parser("evaluate", help="Evaluate full and sparse calibration results")

    p = sub.add_parser("all", help="Run baseline → reference → full → sparse → evaluation")
    p.add_argument("--force-baseline", action="store_true")
    p.add_argument("--force-reference", action="store_true")

    sub.add_parser("verify-reference", help="Verify recovered direct reference generator against archived data3")

    args = parser.parse_args()
    cfg = load_config(args.config)

    if args.command == "baseline":
        _print(run_baseline(cfg, args.force))
    elif args.command == "reference":
        _print(run_reference(cfg, args.force))
    elif args.command == "calibrate":
        _print(run_calibration(cfg, args.strategy))
    elif args.command == "evaluate":
        _print(run_evaluation(cfg))
    elif args.command == "all":
        _print(run_all(cfg, args.force_baseline, args.force_reference))
    elif args.command == "verify-reference":
        import numpy as np
        from .data import load_energyplus_csv
        archived_base = project_path(cfg, "data/archive/model_baseline_original.csv")
        archived_ref = project_path(cfg, "data/archive/data3_original.csv")
        generated = generate_synthetic_reference(archived_base, zone_order=cfg["reference"].get("zone_order"), **{k: cfg["reference"][k] for k in ["seed", "bias_range", "drift_std", "sinusoid_amplitude", "sinusoid_period_hours", "deviation_threshold", "reduction_strength"]})
        expected = load_energyplus_csv(archived_ref, strip_time=False)
        zones = cfg["reference"]["zone_order"]
        max_abs = float(np.max(np.abs(generated[zones].to_numpy(float) - expected[zones].to_numpy(float))))
        _print({"max_absolute_difference_c": max_abs, "matches_machine_precision": max_abs < 1e-12})


if __name__ == "__main__":
    main()
