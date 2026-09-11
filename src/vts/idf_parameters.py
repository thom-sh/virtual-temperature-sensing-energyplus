from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CalibrationParameters:
    internal_gains: float
    infiltration: float
    vav_min_flow: float
    reheat_capacity: float
    outdoor_air: float
    sat_offset_c: float

    @classmethod
    def from_vector(cls, values) -> "CalibrationParameters":
        return cls(*map(float, values))

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _blank_or_autosize(value: Any) -> bool:
    if value is None:
        return True
    return str(value).strip().lower() in {"", "autosize", "autocalculate"}


def _get_attr(obj: Any, *names: str) -> tuple[str | None, Any]:
    for name in names:
        if hasattr(obj, name):
            return name, getattr(obj, name)
    return None, None


def _scale_attr(obj: Any, names: tuple[str, ...], multiplier: float, minimum: float | None = None, maximum: float | None = None) -> bool:
    name, value = _get_attr(obj, *names)
    if name is None or _blank_or_autosize(value):
        return False
    number = _safe_float(value)
    if number is None:
        return False
    number *= multiplier
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    setattr(obj, name, number)
    return True


def _objects(idf: Any, key: str):
    try:
        return idf.idfobjects[key] if key in idf.idfobjects else []
    except Exception:
        return []


class IDFParameterModifier:
    """Apply calibration parameters to an EnergyPlus IDF.

    ``legacy`` reproduces the parameter-field mappings in the surviving notebooks,
    including their inactive/no-op mappings. ``corrected`` maps parameters to the
    active fields present in the supplied model.idf and applies SAT offset.
    """

    def __init__(self, idd_path: str | Path, base_idf: str | Path, mode: str = "corrected"):
        self.idd_path = Path(idd_path)
        self.base_idf = Path(base_idf)
        self.mode = mode
        if mode not in {"legacy", "corrected"}:
            raise ValueError("mode must be 'legacy' or 'corrected'")

    def _load(self):
        try:
            from eppy.modeleditor import IDF
        except ImportError as exc:
            raise RuntimeError("eppy is required for IDF modification. Install the project dependencies first.") from exc
        try:
            IDF.setiddname(str(self.idd_path))
        except Exception as exc:
            # eppy permits one IDD per process. Reusing the same IDD is fine.
            if "IDD file is set to" not in str(exc):
                raise
        return IDF(str(self.base_idf))

    def build(self, output_idf: str | Path, params: CalibrationParameters) -> dict[str, Any]:
        idf = self._load()
        audit = {"mode": self.mode, "changes": {}, "notes": []}
        if self.mode == "legacy":
            self._apply_legacy(idf, params, audit)
        else:
            self._apply_corrected(idf, params, audit)
        output_idf = Path(output_idf)
        output_idf.parent.mkdir(parents=True, exist_ok=True)
        idf.saveas(str(output_idf))
        return audit

    def _bump(self, audit: dict[str, Any], key: str, count: int = 1) -> None:
        audit["changes"][key] = audit["changes"].get(key, 0) + count

    def _apply_legacy(self, idf, p: CalibrationParameters, audit: dict[str, Any]) -> None:
        # Exact intent of the notebook code. Several fields are inactive in model.idf.
        for obj in _objects(idf, "PEOPLE"):
            if _scale_attr(obj, ("Number_of_People",), p.internal_gains): self._bump(audit, "people")
        for obj in _objects(idf, "LIGHTS"):
            if _scale_attr(obj, ("Watts_per_Zone_Floor_Area",), p.internal_gains): self._bump(audit, "lights")
        for obj in _objects(idf, "ELECTRICEQUIPMENT"):
            if _scale_attr(obj, ("Design_Level",), p.internal_gains): self._bump(audit, "electric_equipment")
        for obj in _objects(idf, "ZONEINFILTRATION:DESIGNFLOWRATE"):
            if _scale_attr(obj, ("Design_Flow_Rate",), p.infiltration, minimum=0.0): self._bump(audit, "infiltration")
        for obj in _objects(idf, "AIRTERMINAL:SINGLEDUCT:VAV:REHEAT"):
            if _scale_attr(obj, ("Zone_Minimum_Air_Flow_Fraction",), p.vav_min_flow, 0.1, 0.8): self._bump(audit, "vav_min_flow")
        for coil_type in ("COIL:HEATING:ELECTRIC", "COIL:HEATING:FUEL"):
            for obj in _objects(idf, coil_type):
                if _scale_attr(obj, ("Nominal_Capacity",), p.reheat_capacity, minimum=0.0): self._bump(audit, "reheat_capacity")
        for obj in _objects(idf, "CONTROLLER:OUTDOORAIR"):
            if _scale_attr(obj, ("Minimum_Outdoor_Air_Flow_Rate",), p.outdoor_air, minimum=0.0): self._bump(audit, "outdoor_air")
        audit["notes"].append("Legacy notebook accepted sat_offset_c but did not apply it to the IDF.")

    def _apply_corrected(self, idf, p: CalibrationParameters, audit: dict[str, Any]) -> None:
        # Internal gains: scale whichever field is active for the calculation method.
        for obj in _objects(idf, "PEOPLE"):
            method = str(getattr(obj, "Number_of_People_Calculation_Method", "")).strip().lower()
            changed = False
            if method == "people":
                changed = _scale_attr(obj, ("Number_of_People",), p.internal_gains)
            elif method in {"people/area", "peopleperarea"}:
                changed = _scale_attr(obj, ("People_per_Zone_Floor_Area", "People_per_Floor_Area"), p.internal_gains)
            elif method in {"area/person", "areaperperson"}:
                name, value = _get_attr(obj, "Zone_Floor_Area_per_Person", "Floor_Area_per_Person")
                number = _safe_float(value)
                if name and number is not None and number > 0 and p.internal_gains > 0:
                    setattr(obj, name, number / p.internal_gains)
                    changed = True
            if changed: self._bump(audit, "people")

        for obj in _objects(idf, "LIGHTS"):
            method = str(getattr(obj, "Design_Level_Calculation_Method", "")).strip().lower()
            candidates = {
                "lightinglevel": ("Lighting_Level",),
                "watts/area": ("Watts_per_Zone_Floor_Area", "Watts_per_Floor_Area"),
                "watts/person": ("Watts_per_Person",),
            }.get(method, ("Lighting_Level", "Watts_per_Zone_Floor_Area", "Watts_per_Floor_Area", "Watts_per_Person"))
            if _scale_attr(obj, candidates, p.internal_gains): self._bump(audit, "lights")

        for obj in _objects(idf, "ELECTRICEQUIPMENT"):
            method = str(getattr(obj, "Design_Level_Calculation_Method", "")).strip().lower()
            candidates = {
                "equipmentlevel": ("Design_Level",),
                "watts/area": ("Watts_per_Zone_Floor_Area", "Watts_per_Floor_Area"),
                "watts/person": ("Watts_per_Person",),
            }.get(method, ("Design_Level", "Watts_per_Zone_Floor_Area", "Watts_per_Floor_Area", "Watts_per_Person"))
            if _scale_attr(obj, candidates, p.internal_gains): self._bump(audit, "electric_equipment")

        for obj in _objects(idf, "ZONEINFILTRATION:DESIGNFLOWRATE"):
            method = str(getattr(obj, "Design_Flow_Rate_Calculation_Method", "")).replace(" ", "").lower()
            candidates = {
                "flow/zone": ("Design_Flow_Rate",),
                "flow/area": ("Flow_Rate_per_Zone_Floor_Area", "Flow_Rate_per_Floor_Area"),
                "flow/exteriorarea": ("Flow_Rate_per_Exterior_Surface_Area",),
                "flow/exteriorwallarea": ("Flow_Rate_per_Exterior_Surface_Area",),
                "airchanges/hour": ("Air_Changes_per_Hour",),
            }.get(method, ("Design_Flow_Rate", "Flow_Rate_per_Zone_Floor_Area", "Flow_Rate_per_Floor_Area", "Flow_Rate_per_Exterior_Surface_Area", "Air_Changes_per_Hour"))
            if _scale_attr(obj, candidates, p.infiltration, minimum=0.0): self._bump(audit, "infiltration")

        for obj in _objects(idf, "AIRTERMINAL:SINGLEDUCT:VAV:REHEAT"):
            method = str(getattr(obj, "Zone_Minimum_Air_Flow_Input_Method", "")).replace(" ", "").lower()
            if method == "constant":
                changed = _scale_attr(obj, ("Constant_Minimum_Air_Flow_Fraction",), p.vav_min_flow, 0.1, 0.8)
            elif method == "fixedflowrate":
                changed = _scale_attr(obj, ("Fixed_Minimum_Air_Flow_Rate",), p.vav_min_flow, 0.0, None)
            else:
                changed = False
            if changed: self._bump(audit, "vav_min_flow")

        # Numeric reheat capacities can be scaled directly. For this supplied model the
        # electric reheat coils are AUTOSIZE, so corrected mode uses each zone's heating
        # sizing factor to scale the autosized design load/capacity.
        direct_reheat_changes = 0
        for coil_type in ("COIL:HEATING:ELECTRIC", "COIL:HEATING:FUEL"):
            for obj in _objects(idf, coil_type):
                if _scale_attr(obj, ("Nominal_Capacity",), p.reheat_capacity, minimum=0.0):
                    direct_reheat_changes += 1
        if direct_reheat_changes:
            self._bump(audit, "reheat_capacity", direct_reheat_changes)
        else:
            sizing_changes = 0
            for obj in _objects(idf, "SIZING:ZONE"):
                name, value = _get_attr(obj, "Zone_Heating_Sizing_Factor")
                if name:
                    base_factor = _safe_float(value)
                    if base_factor is None or base_factor <= 0:
                        base_factor = 1.0
                    setattr(obj, name, base_factor * p.reheat_capacity)
                    sizing_changes += 1
            if sizing_changes:
                self._bump(audit, "reheat_capacity_via_zone_heating_sizing_factor", sizing_changes)
                audit["notes"].append("Autosized reheat capacity is represented through Zone Heating Sizing Factor in corrected mode.")

        for obj in _objects(idf, "DESIGNSPECIFICATION:OUTDOORAIR"):
            method = str(getattr(obj, "Outdoor_Air_Method", "")).replace(" ", "").lower()
            if method in {"flow/area", "sum", "maximum"}:
                candidates = ("Outdoor_Air_Flow_per_Zone_Floor_Area", "Outdoor_Air_Flow_per_Floor_Area")
            elif method == "flow/person":
                candidates = ("Outdoor_Air_Flow_per_Person",)
            elif method == "flow/zone":
                candidates = ("Outdoor_Air_Flow_per_Zone",)
            elif method == "airchanges/hour":
                candidates = ("Outdoor_Air_Flow_Air_Changes_per_Hour",)
            else:
                candidates = ("Outdoor_Air_Flow_per_Person", "Outdoor_Air_Flow_per_Zone_Floor_Area", "Outdoor_Air_Flow_per_Floor_Area", "Outdoor_Air_Flow_per_Zone", "Outdoor_Air_Flow_Air_Changes_per_Hour")
            if _scale_attr(obj, candidates, p.outdoor_air, minimum=0.0): self._bump(audit, "outdoor_air")

        sat_changes = 0
        for obj in _objects(idf, "SETPOINTMANAGER:OUTDOORAIRRESET"):
            for field in ("Setpoint_at_Outdoor_Low_Temperature", "Setpoint_at_Outdoor_High_Temperature"):
                if hasattr(obj, field):
                    value = _safe_float(getattr(obj, field))
                    if value is not None:
                        setattr(obj, field, value + p.sat_offset_c)
                        sat_changes += 1
        if sat_changes:
            self._bump(audit, "sat_setpoints", sat_changes)
