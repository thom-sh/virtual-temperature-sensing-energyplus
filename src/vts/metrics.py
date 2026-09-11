from __future__ import annotations

import numpy as np
import pandas as pd

from .data import DATE_TIME, aligned_pair


def rmse(y_true, y_pred) -> float:
    a = np.asarray(y_true, dtype=float)
    b = np.asarray(y_pred, dtype=float)
    mask = np.isfinite(a) & np.isfinite(b)
    if not mask.any():
        return float("nan")
    return float(np.sqrt(np.mean((a[mask] - b[mask]) ** 2)))


def per_zone_rmse(reference: pd.DataFrame, simulation: pd.DataFrame, zones: list[str]) -> pd.DataFrame:
    merged = aligned_pair(reference, simulation, zones, "_ref", "_sim")
    rows = []
    for zone in zones:
        rows.append({"Zone": zone, "RMSE_C": rmse(merged[f"{zone}_ref"], merged[f"{zone}_sim"])})
    return pd.DataFrame(rows)


def mean_zone_rmse(reference: pd.DataFrame, simulation: pd.DataFrame, zones: list[str]) -> float:
    values = per_zone_rmse(reference, simulation, zones)["RMSE_C"]
    return float(values.mean())


def percent_change(new: float, old: float) -> float:
    if old == 0:
        return float("nan")
    return float((new - old) / old * 100.0)
