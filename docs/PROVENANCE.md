# Project provenance and reconstruction notes

## Source material

The streamlined repository was reconstructed from the submitted Project Module report, the supplied EnergyPlus `model.idf`, baseline and calibration CSV outputs, and the surviving Jupyter notebooks. The three most important historical notebooks retained under `legacy/notebooks/` are:

- `Test2_10_newdata.ipynb` — final full (10-zone) calibration development and historical results.
- `Sharon_Project_Module.ipynb` — contains the sparse (3-zone) differential-evolution calibration code missing from the later consolidated notebook.
- `Test4_quick_dirty.ipynb` — final full-vs-sparse evaluation used for the report tables.

## Synthetic reference reconstruction

The original development created `data1.csv`, experimented with `data2.csv`, and ultimately used `data3.csv`. The new operational pipeline intentionally does **not** generate data1 or data2.

The final `data3.csv` rule was reconstructed from the archived files. It combines:

1. a zone-specific random bias sampled from `[-1.5, 1.5]` using the legacy NumPy RNG with seed 42;
2. cumulative Gaussian drift with standard deviation `0.02` per timestep;
3. a daily sinusoid of amplitude `0.3 °C` and period 24 h;
4. a progressive reduction for absolute deviations greater than `0.5 °C`, with reduction strength `0.5` scaled by each zone's maximum absolute raw deviation.

Applying the combined direct rule to the archived `model.csv` reproduces the archived final `data3.csv` to floating-point precision. This is regression-tested in `tests/test_reference.py`.

The submitted report describes the synthetic reference as a “noise-free benchmark”. The surviving code and archived data, however, show deliberate bias, cumulative drift, and sinusoidal perturbation. The repository follows the recovered code/data behavior and records this wording inconsistency rather than silently reconciling it.

## Historical calibration setup

The report compared ten primary calibration zones against a three-zone sparse strategy. The optimizer was SciPy differential evolution with six parameters and the bounds preserved in `configs/project.yaml`.

The notebooks used average **per-zone RMSE** as the objective function rather than one pooled RMSE across all temperature values. The streamlined pipeline preserves that definition.

## Legacy code issues discovered during reconstruction

The supplied model and surviving notebook code revealed several field-mapping issues:

- `People` objects use `Area/Person`, while the notebook attempted to scale the blank `Number_of_People` field.
- infiltration uses `Flow/ExteriorArea`, while the notebook scaled the zero `Design_Flow_Rate` field.
- VAV terminals use `Constant Minimum Air Flow Fraction`, while the notebook targeted `Zone_Minimum_Air_Flow_Fraction`.
- electric reheat coils are `AUTOSIZE`, so multiplying numeric nominal capacity had no effect.
- controller minimum outdoor-air flow is zero while zone OA is defined by `DesignSpecification:OutdoorAir` using `Flow/Area`.
- the SAT offset was an optimizer variable but was never applied to the IDF.

The original optimizer also reused one output directory for every candidate. After optimization it did not rerun the best parameter vector, so `eplusout.csv` could correspond to the last evaluated candidate rather than the optimizer's best candidate. This explains why later archived full-calibration CSV output no longer matched the report's final full-calibration table.

## Two parameter-mapping modes

`configs/project.yaml` uses `parameter_mapping: corrected` and maps parameters to active model fields. For autosized electric reheat, the corrected mode represents the multiplier via `Sizing:Zone -> Zone Heating Sizing Factor`.

`configs/legacy_mapping.yaml` uses `parameter_mapping: legacy` and preserves the field mappings of the surviving notebooks for historical comparison. It intentionally retains the legacy SAT no-op.

The corrected mode is the recommended operational pipeline. Results from corrected mode should be treated as a new reproducible experiment, not as the numerical results submitted in the historical report.

## Secondary-zone evaluation

The final report evaluated the eight secondary zones relative to the uncalibrated base model. That behavior is the default (`secondary_reference: baseline`) because it reproduces the reported analysis logic. The pipeline also supports `secondary_reference: synthetic_reference` for a controlled alternative evaluation.
