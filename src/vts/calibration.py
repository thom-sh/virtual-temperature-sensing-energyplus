from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pandas as pd
from scipy.optimize import differential_evolution

from .data import load_energyplus_csv
from .energyplus import EnergyPlusRunner
from .idf_parameters import CalibrationParameters, IDFParameterModifier
from .metrics import mean_zone_rmse

PARAMETER_NAMES = [
    "internal_gains",
    "infiltration",
    "vav_min_flow",
    "reheat_capacity",
    "outdoor_air",
    "sat_offset_c",
]


class CalibrationEngine:
    def __init__(
        self,
        *,
        runner: EnergyPlusRunner,
        modifier: IDFParameterModifier,
        reference_csv: str | Path,
        calibration_zones: list[str],
        output_dir: str | Path,
        optimizer_config: dict[str, Any],
        bounds_config: dict[str, list[float]],
    ):
        self.runner = runner
        self.modifier = modifier
        self.reference_csv = Path(reference_csv)
        self.reference = load_energyplus_csv(self.reference_csv)
        self.calibration_zones = calibration_zones
        self.output_dir = Path(output_dir)
        self.trials_dir = self.output_dir / "trials"
        self.best_dir = self.output_dir / "best"
        self.optimizer_config = optimizer_config
        self.bounds = [tuple(map(float, bounds_config[name])) for name in PARAMETER_NAMES]
        self.history: list[dict[str, Any]] = []
        self.cache: dict[str, float] = {}
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.trials_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, params: CalibrationParameters) -> str:
        raw = json.dumps(params.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    def _write_history(self) -> None:
        path = self.output_dir / "optimization_history.csv"
        if not self.history:
            return
        keys = list(self.history[0].keys())
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.history)

    def objective(self, vector) -> float:
        params = CalibrationParameters.from_vector(vector)
        key = self._key(params)
        if key in self.cache:
            return self.cache[key]

        trial_index = len(self.history) + 1
        trial_dir = self.trials_dir / f"trial_{trial_index:04d}_{key}"
        trial_dir.mkdir(parents=True, exist_ok=True)
        idf_path = trial_dir / "model_trial.idf"
        row = {"trial": trial_index, **params.to_dict(), "rmse_c": "", "status": "ok", "error": "", "audit_changes": ""}

        try:
            audit = self.modifier.build(idf_path, params)
            with (trial_dir / "parameter_audit.json").open("w", encoding="utf-8") as f:
                json.dump(audit, f, indent=2)
            sim_csv = self.runner.run(idf_path, trial_dir)
            sim = load_energyplus_csv(sim_csv)
            value = mean_zone_rmse(self.reference, sim, self.calibration_zones)
            row["rmse_c"] = value
            row["audit_changes"] = json.dumps(audit.get("changes", {}), sort_keys=True)
        except Exception as exc:
            value = float(self.optimizer_config.get("failure_penalty", 1e6))
            row["rmse_c"] = value
            row["status"] = "failed"
            row["error"] = str(exc)

        self.history.append(row)
        self.cache[key] = value
        self._write_history()
        keep_all = bool(self.optimizer_config.get("keep_trial_files", False))
        keep_failed = bool(self.optimizer_config.get("keep_failed_trials", True))
        if trial_dir.exists() and not keep_all and not (row["status"] == "failed" and keep_failed):
            shutil.rmtree(trial_dir)
        print(f"Trial {trial_index:04d}: RMSE={value:.6f} °C | {params.to_dict()}")
        return value

    def run(self) -> dict[str, Any]:
        cfg = self.optimizer_config
        result = differential_evolution(
            self.objective,
            self.bounds,
            maxiter=int(cfg.get("maxiter", 5)),
            popsize=int(cfg.get("popsize", 15)),
            tol=float(cfg.get("tol", 1e-2)),
            polish=bool(cfg.get("polish", False)),
            seed=cfg.get("seed", 42),
            disp=bool(cfg.get("disp", True)),
            workers=1,
            updating="immediate",
        )

        best = CalibrationParameters.from_vector(result.x)
        # Critical fix over the notebooks: explicitly rerun the best parameter vector.
        if self.best_dir.exists():
            shutil.rmtree(self.best_dir)
        self.best_dir.mkdir(parents=True, exist_ok=True)
        best_idf = self.best_dir / "best_model.idf"
        audit = self.modifier.build(best_idf, best)
        with (self.best_dir / "parameter_audit.json").open("w", encoding="utf-8") as f:
            json.dump(audit, f, indent=2)
        best_csv = self.runner.run(best_idf, self.best_dir)
        best_sim = load_energyplus_csv(best_csv)
        verified_rmse = mean_zone_rmse(self.reference, best_sim, self.calibration_zones)

        summary = {
            "success": bool(result.success),
            "message": str(result.message),
            "objective_rmse_c": float(result.fun),
            "verified_best_rmse_c": float(verified_rmse),
            "nfev": int(result.nfev),
            "nit": int(result.nit),
            "calibration_zones": self.calibration_zones,
            "best_parameters": best.to_dict(),
            "best_csv": str(best_csv),
            "best_idf": str(best_idf),
            "parameter_mapping_mode": self.modifier.mode,
        }
        with (self.output_dir / "result.json").open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        with (self.output_dir / "best_parameters.json").open("w", encoding="utf-8") as f:
            json.dump(best.to_dict(), f, indent=2)
        return summary
