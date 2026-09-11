# Calibration parameter mapping

The original notebooks optimized six variables, but several notebook field mappings did not target active fields in the supplied IDF. The repository keeps both behaviors explicitly.

| Calibration variable | Legacy notebook mapping | Active field used in corrected mode |
|---|---|---|
| Internal gains | `People.Number_of_People`, `Lights.Watts_per_Zone_Floor_Area`, `ElectricEquipment.Design_Level` | Method-aware People/Lights/Equipment active design field; `Area/Person` is inversely scaled |
| Infiltration | `ZoneInfiltration:DesignFlowRate.Design_Flow_Rate` | Method-aware active field; supplied model uses `Flow_Rate_per_Exterior_Surface_Area` |
| VAV minimum flow | `Zone_Minimum_Air_Flow_Fraction` | `Constant_Minimum_Air_Flow_Fraction` for the supplied VAV terminals |
| Reheat capacity | numeric `Coil:Heating:* .Nominal_Capacity` only | numeric capacity if available; otherwise `Sizing:Zone.Zone_Heating_Sizing_Factor` for autosized reheat |
| Outdoor air | `Controller:OutdoorAir.Minimum_Outdoor_Air_Flow_Rate` | method-aware `DesignSpecification:OutdoorAir` field; supplied model uses flow per zone floor area |
| SAT offset | passed to function but not applied | added to low/high setpoints in `SetpointManager:OutdoorAirReset` |

`corrected` is the recommended mode for new experiments. `legacy` exists only so the historical implementation can be inspected without being confused with the corrected model behavior.
