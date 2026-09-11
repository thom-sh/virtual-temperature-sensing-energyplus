from pathlib import Path

from eppy.modeleditor import IDF

from vts.idf_parameters import CalibrationParameters, IDFParameterModifier


IDD = Path(r"C:\EnergyPlusV25-1-0\Energy+.idd")
BASE_IDF = Path(r"models\base\model.idf")
CHECK_ROOT = Path(r"outputs\parameter_checks")


try:
    IDF.setiddname(str(IDD))
except Exception:
    pass


def get_attr(obj, *names):
    for name in names:
        if hasattr(obj, name):
            return name, getattr(obj, name)
    return None, None


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def build_test(name, params):
    output = CHECK_ROOT / name / "model.idf"

    modifier = IDFParameterModifier(
        IDD,
        BASE_IDF,
        mode="corrected",
    )

    audit = modifier.build(output, params)

    print(f"\n{'=' * 70}")
    print(name.upper())
    print("=" * 70)
    print("Audit:", audit)

    return IDF(str(output))


base = IDF(str(BASE_IDF))


# ============================================================
# 1. INTERNAL GAINS — ELECTRIC EQUIPMENT
# ============================================================

test = build_test(
    "internal_gains",
    CalibrationParameters(
        0.8,
        1.0,
        1.0,
        1.0,
        1.0,
        0.0,
    ),
)

passed = 0
checked = 0

for b, t in zip(
    base.idfobjects["ELECTRICEQUIPMENT"],
    test.idfobjects["ELECTRICEQUIPMENT"],
):
    method = str(b.Design_Level_Calculation_Method).strip().lower()

    if method == "equipmentlevel":
        field = "Design_Level"
    elif method == "watts/area":
        field, _ = get_attr(
            b,
            "Watts_per_Zone_Floor_Area",
            "Watts_per_Floor_Area",
        )
    elif method == "watts/person":
        field = "Watts_per_Person"
    else:
        continue

    bval = number(getattr(b, field))
    tval = number(getattr(t, field))

    if bval is None or tval is None:
        continue

    expected = bval * 0.8
    ok = close(tval, expected)

    checked += 1
    passed += int(ok)

    if not ok:
        print(
            f"FAIL {b.Name}: "
            f"{bval} -> {tval}, expected {expected}"
        )

print(f"Electric equipment: {passed}/{checked} PASS")


# ============================================================
# 2. INFILTRATION
# ============================================================

test = build_test(
    "infiltration",
    CalibrationParameters(
        1.0,
        1.2,
        1.0,
        1.0,
        1.0,
        0.0,
    ),
)

passed = 0
checked = 0

for b, t in zip(
    base.idfobjects["ZONEINFILTRATION:DESIGNFLOWRATE"],
    test.idfobjects["ZONEINFILTRATION:DESIGNFLOWRATE"],
):
    method = (
        str(b.Design_Flow_Rate_Calculation_Method)
        .replace(" ", "")
        .lower()
    )

    fields = {
        "flow/zone": (
            "Design_Flow_Rate",
        ),
        "flow/area": (
            "Flow_Rate_per_Zone_Floor_Area",
            "Flow_Rate_per_Floor_Area",
        ),
        "flow/exteriorarea": (
            "Flow_Rate_per_Exterior_Surface_Area",
        ),
        "flow/exteriorwallarea": (
            "Flow_Rate_per_Exterior_Surface_Area",
        ),
        "airchanges/hour": (
            "Air_Changes_per_Hour",
        ),
    }

    candidates = fields.get(method)

    if not candidates:
        print(f"UNKNOWN infiltration method: {b.Name}: {method}")
        continue

    field, braw = get_attr(b, *candidates)
    _, traw = get_attr(t, *candidates)

    bval = number(braw)
    tval = number(traw)

    if bval is None or tval is None:
        continue

    expected = bval * 1.2
    ok = close(tval, expected)

    checked += 1
    passed += int(ok)

    if not ok:
        print(
            f"FAIL {b.Name}: "
            f"{field}: {bval} -> {tval}, "
            f"expected {expected}"
        )

print(f"Infiltration: {passed}/{checked} PASS")


# ============================================================
# 3. VAV MINIMUM FLOW
# ============================================================

test = build_test(
    "vav_min_flow",
    CalibrationParameters(
        1.0,
        1.0,
        0.5,
        1.0,
        1.0,
        0.0,
    ),
)

passed = 0
checked = 0
scheduled = []

for b, t in zip(
    base.idfobjects["AIRTERMINAL:SINGLEDUCT:VAV:REHEAT"],
    test.idfobjects["AIRTERMINAL:SINGLEDUCT:VAV:REHEAT"],
):
    method = (
        str(b.Zone_Minimum_Air_Flow_Input_Method)
        .replace(" ", "")
        .lower()
    )

    if method == "constant":
        bval = number(b.Constant_Minimum_Air_Flow_Fraction)
        tval = number(t.Constant_Minimum_Air_Flow_Fraction)

        expected = max(
            0.1,
            min(
                0.8,
                bval * 0.5,
            ),
        )

        ok = close(tval, expected)

        checked += 1
        passed += int(ok)

        if not ok:
            print(
                f"FAIL {b.Name}: "
                f"{bval} -> {tval}, "
                f"expected {expected}"
            )

    elif method == "fixedflowrate":
        bval = number(b.Fixed_Minimum_Air_Flow_Rate)
        tval = number(t.Fixed_Minimum_Air_Flow_Rate)

        expected = bval * 0.5

        ok = close(tval, expected)

        checked += 1
        passed += int(ok)

    elif method == "scheduled":
        scheduled.append(
            (
                b.Name,
                b.Minimum_Air_Flow_Fraction_Schedule_Name,
            )
        )


print(f"VAV directly modified: {passed}/{checked} PASS")

if scheduled:
    print("\nVAV scheduled cases NOT currently modified:")

    for name, schedule in scheduled:
        print(f"  {name}")
        print(f"    schedule = {schedule}")


# ============================================================
# 4. REHEAT CAPACITY
# ============================================================

test = build_test(
    "reheat_capacity",
    CalibrationParameters(
        1.0,
        1.0,
        1.0,
        1.1,
        1.0,
        0.0,
    ),
)

passed = 0
checked = 0

for b, t in zip(
    base.idfobjects["SIZING:ZONE"],
    test.idfobjects["SIZING:ZONE"],
):
    _, braw = get_attr(
        b,
        "Zone_Heating_Sizing_Factor",
    )

    _, traw = get_attr(
        t,
        "Zone_Heating_Sizing_Factor",
    )

    bval = number(braw)
    tval = number(traw)

    base_factor = (
        1.0
        if bval is None or bval <= 0
        else bval
    )

    expected = base_factor * 1.1

    ok = (
        tval is not None
        and close(tval, expected)
    )

    checked += 1
    passed += int(ok)

    if not ok:
        print(
            f"FAIL {b.Zone_or_ZoneList_Name}: "
            f"{braw} -> {traw}, "
            f"expected {expected}"
        )

print(
    f"Reheat sizing factor: "
    f"{passed}/{checked} PASS"
)


# ============================================================
# 5. OUTDOOR AIR
# ============================================================

test = build_test(
    "outdoor_air",
    CalibrationParameters(
        1.0,
        1.0,
        1.0,
        1.0,
        1.2,
        0.0,
    ),
)

passed = 0
checked = 0
sum_objects = 0

for b, t in zip(
    base.idfobjects["DESIGNSPECIFICATION:OUTDOORAIR"],
    test.idfobjects["DESIGNSPECIFICATION:OUTDOORAIR"],
):
    method = (
        str(b.Outdoor_Air_Method)
        .replace(" ", "")
        .lower()
    )

    field, braw = get_attr(
        b,
        "Outdoor_Air_Flow_per_Zone_Floor_Area",
        "Outdoor_Air_Flow_per_Floor_Area",
    )

    _, traw = get_attr(
        t,
        "Outdoor_Air_Flow_per_Zone_Floor_Area",
        "Outdoor_Air_Flow_per_Floor_Area",
    )

    bval = number(braw)
    tval = number(traw)

    if bval is not None and tval is not None:
        expected = bval * 1.2

        ok = close(
            tval,
            expected,
        )

        checked += 1
        passed += int(ok)

        if not ok:
            print(
                f"FAIL {b.Name}: "
                f"{bval} -> {tval}, "
                f"expected {expected}"
            )

    if method == "sum":
        sum_objects += 1


print(
    f"Outdoor-air area component: "
    f"{passed}/{checked} PASS"
)

print(
    f"Outdoor-air objects using Sum method: "
    f"{sum_objects}"
)


# ============================================================
# 6. SUPPLY AIR TEMPERATURE OFFSET
# ============================================================

test = build_test(
    "sat_offset",
    CalibrationParameters(
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
    ),
)

passed = 0
checked = 0

for b, t in zip(
    base.idfobjects["SETPOINTMANAGER:OUTDOORAIRRESET"],
    test.idfobjects["SETPOINTMANAGER:OUTDOORAIRRESET"],
):
    for field in (
        "Setpoint_at_Outdoor_Low_Temperature",
        "Setpoint_at_Outdoor_High_Temperature",
    ):
        bval = number(getattr(b, field))
        tval = number(getattr(t, field))

        expected = bval + 1.0

        ok = close(
            tval,
            expected,
        )

        checked += 1
        passed += int(ok)

        if not ok:
            print(
                f"FAIL {b.Name} / {field}: "
                f"{bval} -> {tval}, "
                f"expected {expected}"
            )

print(
    f"SAT setpoints: "
    f"{passed}/{checked} PASS"
)


print("\n" + "=" * 70)
print("PARAMETER-MAPPING CHECK COMPLETE")
print("=" * 70)