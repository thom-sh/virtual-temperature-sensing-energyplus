from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from vts.data import load_energyplus_csv
from vts.reference import generate_synthetic_reference


ROOT = Path(__file__).resolve().parents[1]


def test_direct_generator_reproduces_archived_data3():
    cfg = yaml.safe_load((ROOT / "configs" / "project.yaml").read_text(encoding="utf-8"))
    r = cfg["reference"]
    generated = generate_synthetic_reference(
        ROOT / "tests" / "fixtures" / "model.csv",
        zone_order=r["zone_order"],
        seed=r["seed"],
        bias_range=r["bias_range"],
        drift_std=r["drift_std"],
        sinusoid_amplitude=r["sinusoid_amplitude"],
        sinusoid_period_hours=r["sinusoid_period_hours"],
        deviation_threshold=r["deviation_threshold"],
        reduction_strength=r["reduction_strength"],
    )
    expected = load_energyplus_csv(ROOT / "tests" / "fixtures" / "data3.csv", strip_time=False)
    zones = r["zone_order"]
    max_abs = np.max(np.abs(generated[zones].to_numpy(float) - expected[zones].to_numpy(float)))
    assert max_abs < 1e-12
