from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .data import load_energyplus_csv, temperature_columns
from .metrics import per_zone_rmse, percent_change
from .plotting import plot_zone_comparison


def _comparison(reference: pd.DataFrame, full: pd.DataFrame, sparse: pd.DataFrame, zones: list[str]) -> pd.DataFrame:
    a = per_zone_rmse(reference, full, zones).rename(columns={"RMSE_C": "Full_RMSE_C"})
    b = per_zone_rmse(reference, sparse, zones).rename(columns={"RMSE_C": "Sparse_RMSE_C"})
    out = a.merge(b, on="Zone")
    out["Sparse_vs_Full_pct"] = [percent_change(n, o) for n, o in zip(out["Sparse_RMSE_C"], out["Full_RMSE_C"])]
    return out


def evaluate_project(
    *,
    baseline_csv: str | Path,
    reference_csv: str | Path,
    full_csv: str | Path,
    sparse_csv: str | Path,
    primary_zones: list[str],
    sparse_anchors: list[str],
    output_dir: str | Path,
    secondary_reference: str = "baseline",
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    baseline = load_energyplus_csv(baseline_csv)
    reference = load_energyplus_csv(reference_csv)
    full = load_energyplus_csv(full_csv)
    sparse = load_energyplus_csv(sparse_csv)

    all_zones = temperature_columns(baseline)
    secondary_zones = [z for z in all_zones if z not in primary_zones]
    virtual_primary = [z for z in primary_zones if z not in sparse_anchors]

    primary = _comparison(reference, full, sparse, primary_zones)
    anchors = _comparison(reference, full, sparse, sparse_anchors)
    virtual = _comparison(reference, full, sparse, virtual_primary)

    if secondary_reference == "baseline":
        secondary_ref_df = baseline
    elif secondary_reference == "synthetic_reference":
        secondary_ref_df = reference
    else:
        raise ValueError("secondary_reference must be 'baseline' or 'synthetic_reference'")
    secondary = _comparison(secondary_ref_df, full, sparse, secondary_zones)

    primary.to_csv(tables_dir / "primary_zones.csv", index=False)
    anchors.to_csv(tables_dir / "sparse_anchor_zones.csv", index=False)
    virtual.to_csv(tables_dir / "virtual_primary_zones.csv", index=False)
    secondary.to_csv(tables_dir / "secondary_zones.csv", index=False)

    full_primary_avg = float(primary["Full_RMSE_C"].mean())
    sparse_primary_avg = float(primary["Sparse_RMSE_C"].mean())
    full_secondary_avg = float(secondary["Full_RMSE_C"].mean())
    sparse_secondary_avg = float(secondary["Sparse_RMSE_C"].mean())
    sparse_anchor_avg = float(anchors["Sparse_RMSE_C"].mean())

    summary = {
        "sensor_counts": {"full": len(primary_zones), "sparse": len(sparse_anchors)},
        "sensor_reduction_pct": (1.0 - len(sparse_anchors) / len(primary_zones)) * 100.0,
        "primary": {
            "full_average_rmse_c": full_primary_avg,
            "sparse_average_rmse_c": sparse_primary_avg,
            "sparse_vs_full_pct": percent_change(sparse_primary_avg, full_primary_avg),
        },
        "sparse_anchors": {"average_rmse_c": sparse_anchor_avg},
        "virtual_primary_zone_count": len(virtual_primary),
        "secondary": {
            "reference": secondary_reference,
            "full_average_rmse_c": full_secondary_avg,
            "sparse_average_rmse_c": sparse_secondary_avg,
            "sparse_vs_full_pct": percent_change(sparse_secondary_avg, full_secondary_avg),
        },
    }
    with (output_dir / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    plot_zone_comparison({"Baseline": baseline, "Reference": reference, "Full calibration": full}, primary_zones, figures_dir / "full_primary.png", "Full calibration — primary zones", columns=3)
    plot_zone_comparison({"Baseline": baseline, "Reference": reference, "Sparse calibration": sparse}, sparse_anchors, figures_dir / "sparse_anchors.png", "Sparse calibration — anchor zones", columns=3)
    plot_zone_comparison({"Reference": reference, "Full calibration": full, "Sparse calibration": sparse}, virtual_primary, figures_dir / "virtual_primary.png", "Virtual temperatures — seven non-anchor primary zones", columns=3)
    plot_zone_comparison({"Baseline": baseline, "Full calibration": full, "Sparse calibration": sparse}, secondary_zones, figures_dir / "secondary_zones.png", "Secondary zones", columns=4)
    return summary
