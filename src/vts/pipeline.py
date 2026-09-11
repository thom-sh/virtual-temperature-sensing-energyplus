from __future__ import annotations

from pathlib import Path
from typing import Any

from .calibration import CalibrationEngine
from .config import energyplus_path, project_path
from .energyplus import EnergyPlusRunner
from .evaluation import evaluate_project
from .idf_parameters import IDFParameterModifier
from .reference import generate_synthetic_reference


def _runner(cfg: dict[str, Any]) -> EnergyPlusRunner:
    ep = cfg["energyplus"]
    return EnergyPlusRunner(
        executable=energyplus_path(cfg, ep.get("executable", "energyplus.exe")),
        weather_file=energyplus_path(cfg, ep["weather_file"]),
    )


def baseline_path(cfg: dict[str, Any]) -> Path:
    return project_path(cfg, cfg["paths"]["baseline_output_dir"]) / "eplusout.csv"


def reference_path(cfg: dict[str, Any]) -> Path:
    return project_path(cfg, cfg["paths"]["reference_csv"])


def calibration_dir(cfg: dict[str, Any], strategy: str) -> Path:
    return project_path(cfg, cfg["paths"]["calibration_root"]) / strategy


def run_baseline(cfg: dict[str, Any], force: bool = False) -> Path:
    outdir = project_path(cfg, cfg["paths"]["baseline_output_dir"])
    csv_path = outdir / "eplusout.csv"
    if csv_path.exists() and not force:
        return csv_path
    model = project_path(cfg, cfg["model"]["idf"])
    return _runner(cfg).run(model, outdir)


def run_reference(cfg: dict[str, Any], force: bool = False) -> Path:
    out = reference_path(cfg)
    if out.exists() and not force:
        return out
    baseline = baseline_path(cfg)
    if not baseline.exists():
        raise FileNotFoundError("Baseline output is missing. Run the baseline stage first.")
    r = cfg["reference"]
    generate_synthetic_reference(
        baseline,
        out,
        zone_order=r.get("zone_order"),
        seed=int(r.get("seed", 42)),
        bias_range=float(r.get("bias_range", 1.5)),
        drift_std=float(r.get("drift_std", 0.02)),
        sinusoid_amplitude=float(r.get("sinusoid_amplitude", 0.3)),
        sinusoid_period_hours=float(r.get("sinusoid_period_hours", 24)),
        deviation_threshold=float(r.get("deviation_threshold", 0.5)),
        reduction_strength=float(r.get("reduction_strength", 0.5)),
    )
    return out


def run_calibration(cfg: dict[str, Any], strategy: str) -> dict[str, Any]:
    if strategy not in {"full", "sparse"}:
        raise ValueError("strategy must be 'full' or 'sparse'")
    ref = reference_path(cfg)
    if not ref.exists():
        raise FileNotFoundError("Synthetic reference is missing. Run the reference stage first.")

    ep = cfg["energyplus"]
    modifier = IDFParameterModifier(
        energyplus_path(cfg, ep.get("idd", "Energy+.idd")),
        project_path(cfg, cfg["model"]["idf"]),
        mode=cfg["calibration"].get("parameter_mapping", "corrected"),
    )
    zones = cfg["zones"]["primary"] if strategy == "full" else cfg["zones"]["sparse_anchors"]
    engine = CalibrationEngine(
        runner=_runner(cfg),
        modifier=modifier,
        reference_csv=ref,
        calibration_zones=zones,
        output_dir=calibration_dir(cfg, strategy),
        optimizer_config=cfg["calibration"]["optimizer"],
        bounds_config=cfg["calibration"]["bounds"],
    )
    return engine.run()


def run_evaluation(cfg: dict[str, Any]) -> dict[str, Any]:
    full_csv = calibration_dir(cfg, "full") / "best" / "eplusout.csv"
    sparse_csv = calibration_dir(cfg, "sparse") / "best" / "eplusout.csv"
    for p in [baseline_path(cfg), reference_path(cfg), full_csv, sparse_csv]:
        if not p.exists():
            raise FileNotFoundError(f"Required evaluation input is missing: {p}")
    return evaluate_project(
        baseline_csv=baseline_path(cfg),
        reference_csv=reference_path(cfg),
        full_csv=full_csv,
        sparse_csv=sparse_csv,
        primary_zones=cfg["zones"]["primary"],
        sparse_anchors=cfg["zones"]["sparse_anchors"],
        output_dir=project_path(cfg, cfg["paths"]["evaluation_dir"]),
        secondary_reference=cfg["evaluation"].get("secondary_reference", "baseline"),
    )


def run_all(cfg: dict[str, Any], force_baseline: bool = False, force_reference: bool = False) -> dict[str, Any]:
    run_baseline(cfg, force=force_baseline)
    run_reference(cfg, force=force_reference)
    full = run_calibration(cfg, "full")
    sparse = run_calibration(cfg, "sparse")
    evaluation = run_evaluation(cfg)
    return {"full": full, "sparse": sparse, "evaluation": evaluation}
