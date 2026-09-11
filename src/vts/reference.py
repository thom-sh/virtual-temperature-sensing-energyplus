from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .data import DATE_TIME, load_energyplus_csv, temperature_columns


def generate_synthetic_reference(
    baseline_csv: str | Path,
    output_csv: str | Path | None = None,
    *,
    zone_order: list[str] | None = None,
    seed: int = 42,
    bias_range: float = 1.5,
    drift_std: float = 0.02,
    sinusoid_amplitude: float = 0.3,
    sinusoid_period_hours: float = 24.0,
    deviation_threshold: float = 0.5,
    reduction_strength: float = 0.5,
) -> pd.DataFrame:
    """Create the final synthetic reference directly from baseline EnergyPlus output.

    This combines the original synthetic perturbation used to create ``data1.csv``
    with the recovered progressive-deviation transformation that produced the final
    ``data3.csv``. It therefore does not create or depend on intermediate data1/data2
    files.

    With the archived model.csv, the default settings reproduce the archived
    data3.csv to floating-point precision.
    """
    # Keep raw Date/Time formatting because the historical CSV retained it.
    df_base = load_energyplus_csv(baseline_csv, strip_time=False)
    available = temperature_columns(df_base)
    zones = zone_order or available
    missing = [z for z in zones if z not in available]
    if missing:
        raise ValueError(f"Configured reference zone order contains missing columns: {missing}")

    df_ref = df_base.copy()
    rng = np.random.RandomState(seed)  # reproduces legacy np.random.seed/np.random calls
    time = np.arange(len(df_base), dtype=float)
    sinusoid = sinusoid_amplitude * np.sin(2 * np.pi * time / sinusoid_period_hours)

    for zone in zones:
        base = df_base[zone].astype(float).to_numpy()
        bias = rng.uniform(-bias_range, bias_range)
        drift = np.cumsum(rng.normal(0.0, drift_std, size=len(base)))
        deviation = bias + drift + sinusoid

        abs_deviation = np.abs(deviation)
        max_abs_deviation = float(abs_deviation.max()) if len(abs_deviation) else 0.0
        adjusted = deviation.copy()

        if max_abs_deviation > 0.0:
            mask = abs_deviation > deviation_threshold
            reduction_factor = 1.0 - reduction_strength * (abs_deviation / max_abs_deviation)
            adjusted_large = np.sign(deviation) * (
                deviation_threshold
                + (abs_deviation - deviation_threshold) * reduction_factor
            )
            adjusted[mask] = adjusted_large[mask]

        df_ref[zone] = base + adjusted

    if output_csv is not None:
        output_csv = Path(output_csv)
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        df_ref.to_csv(output_csv, index=False)
    return df_ref
