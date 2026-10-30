import numpy as np
import pandas as pd
from .master import COUNTRIES, MATERIAL_FAMILIES
from .core import YEARS

SRC = "Synthetic Emission Factor Authority (SEFA) - FICTIONAL"
FUELS = [("natural_gas", "m3", 2.02), ("natural_gas", "kWh", 0.1829), ("natural_gas", "GJ", 56.4), ("diesel", "L", 2.68), ("petrol", "L", 2.31),
         ("lpg", "L", 1.56), ("lpg", "kg", 2.94), ("coal", "t", 2420.0), ("fuel_oil", "L", 2.96), ("hvo", "L", 0.21), ("cng", "kg", 2.54),
         ("biomass_pellets", "t", 61.0), ("kerosene", "L", 2.54)]
GWP = {"R-410A": (2088, 1924, 2256), "R-134a": (1430, 1300, 1530), "R-404A": (3922, 3943, 4728), "R-32": (675, 677, 771), "R-407C": (1774, 1624, 1908),
       "R-1234ze": (7, 1, 1.4), "R-744": (1, 1, 1), "R-22": (1810, 1760, 1960), "SF6": (22800, 23500, 25200), "CH4": (25, 28, 29.8), "N2O": (298, 265, 273)}
REGIONS = {"North America": "NA", "Latin America": "LATAM", "Europe": "EU", "Middle East & Africa": "MEA", "Asia Pacific": "APAC"}
REG_MULT = {"GLOBAL": 1.0, "NA": 1.04, "EU": 0.9, "APAC": 1.18, "LATAM": 0.97, "MEA": 1.1}
EEIO = [("IT Services", 0.21), ("Professional Services", 0.17), ("Facility Services", 0.29), ("Capital Equipment", 0.46), ("Logistics", 0.88), ("Travel Services", 0.71),
        ("Refrigeration Services", 0.33), ("Waste Management", 0.94), ("Utilities", 1.4), ("Energy & Fuels", 1.9), ("Raw Metals", 1.35), ("Polymers & Resins", 1.1),
        ("Chemicals", 0.98), ("Minerals", 1.6), ("Packaging", 0.74), ("Components", 0.62), ("Electronics", 0.51), ("Consumables", 0.66), ("Construction", 0.58),
        ("Insurance", 0.09), ("Telecom", 0.15), ("Marketing", 0.19), ("Catering", 0.55), ("Security Services", 0.21), ("Machinery", 0.44), ("Vehicles", 0.52),
        ("Buildings", 0.39), ("Software", 0.08), ("Investments", 0.12), ("Franchise Operations", 0.36)]
TRANSPORT = [("road_hgv", 0.105), ("road_lcv", 0.58), ("rail_freight", 0.027), ("sea_container", 0.016), ("sea_bulk", 0.0045), ("air_freight_long", 0.6),
             ("air_freight_short", 1.13), ("inland_waterway", 0.031), ("last_mile_van", 0.92)]
TRAVEL = [("air_short_economy", 0.151), ("air_long_economy", 0.148), ("air_long_business", 0.429), ("rail", 0.035), ("car_rental", 0.17), ("taxi", 0.149), ("bus", 0.1), ("ferry", 0.113)]
COMMUTE = [("car_petrol", 0.165), ("car_diesel", 0.17), ("car_ev", 0.05), ("bus", 0.1), ("rail", 0.035), ("motorbike", 0.113), ("bike_walk", 0.0)]
WASTE_TYPES = ["general_mixed", "metal_scrap", "plastics", "cardboard_paper", "hazardous_solvents", "sludge", "e_waste", "used_oil", "wood"]
WASTE_METHODS = {"landfill": 1.0, "incineration": 0.6, "incineration_energy_recovery": 0.35, "recycling": 0.05, "hazardous_treatment": 1.4}
WASTE_BASE = {"general_mixed": 467, "metal_scrap": 21, "plastics": 360, "cardboard_paper": 300, "hazardous_solvents": 900, "sludge": 520, "e_waste": 210, "used_oil": 680, "wood": 330}
PROCESS = [("cement_clinker_calcination", 525.0), ("lime_calcination", 785.0), ("aluminium_anode", 1600.0), ("steel_eaf", 95.0), ("nitric_acid_n2o", 2100.0),
           ("glass_melting", 190.0), ("ammonia_feedstock", 1700.0), ("titanium_dioxide_chloride", 1300.0)]


def gen_emission_factors(ctx):
    rng = ctx.rng("ef")
    rows = []

    def add(atype, sub, geo, val, unit, gas="CO2e", ind="Cross-sector", meth="Average-data", fuel=None, mat=None, prod=None, years=YEARS, drift=0.0, noise=0.01, unc=10, dq=3, gwp=None, src_doc=None):
        for y in years:
            v = val * (1 + drift) ** (y - 2022) * (1 + rng.normal(0, noise))
            basis = gwp or ("AR5" if y <= 2023 else "AR6")
            co2 = v * (0.985 if gas == "CO2e" and atype in ("stationary_combustion", "mobile_combustion") else 1.0)
            rows.append(dict(activity_type=atype, lookup_key=f"{atype}|{sub}|{geo}", fuel_type=fuel, material_type=mat, product_type=prod, geography=geo,
                             industry_applicability=ind, factor_value=round(v, 6), factor_unit=f"kgCO2e/{unit}", activity_unit=unit, gas_type=gas,
                             co2_factor=round(co2, 6), ch4_factor=round((v - co2) * 0.6 / GWP["CH4"][1], 8), n2o_factor=round((v - co2) * 0.4 / GWP["N2O"][1], 8),
                             gwp_basis=basis, gwp_time_horizon="GWP100", publication_year=y - 1, effective_date=pd.Timestamp(f"{y}-01-01"),
                             expiry_date=pd.Timestamp(f"{y}-12-31"), version=f"v{y}.1", source_organisation=SRC,
                             source_document=src_doc or f"SEFA Synthetic Factor Compendium {y - 1} ed.", methodology=meth,
                             uncertainty_low_pct=-unc, uncertainty_high_pct=unc * 1.3, data_quality_rating=dq, synthetic_flag=True))

    geos = ["GLOBAL"] + [c[0] for c in COUNTRIES]
    for f, u, v in FUELS:
        for g in geos:
            add("stationary_combustion", f"{f}|{u}", g, v * (1 if g == "GLOBAL" else rng.uniform(0.98, 1.03)), u, fuel=f, meth="Fuel-based", unc=4, dq=2)
        if u in ("L", "kg") and f in ("diesel", "petrol", "lpg", "cng", "hvo"):
            for g in geos:
                add("mobile_combustion", f"{f}|{u}", g, v * 1.008 * (1 if g == "GLOBAL" else rng.uniform(0.98, 1.03)), u, fuel=f, meth="Fuel-based", unc=5, dq=2)
        add("wtt_fuel", f"{f}|{u}", "GLOBAL", v * rng.uniform(0.16, 0.24), u, fuel=f, meth="Average-data", unc=20, dq=3)
    for c in COUNTRIES:
        g = c[0]
        add("grid_location", "electricity|kWh", g, c[8], "kWh", meth="Location-based grid average", drift=-0.035, noise=0.015, unc=8, dq=2)
        add("grid_residual_mix", "electricity|kWh", g, c[8] * rng.uniform(1.08, 1.35), "kWh", meth="Market-based residual mix", drift=-0.02, noise=0.02, unc=15, dq=3)
        add("purchased_steam", "steam|MWh", g, rng.uniform(170, 290), "MWh", meth="Supplier average", drift=-0.01, unc=15, dq=3)
        add("purchased_cooling", "chilled_water|kWh", g, c[8] * 0.31, "kWh", meth="Average-data", drift=-0.03, unc=20, dq=3)
        add("wtt_td_electricity", "electricity|kWh", g, c[8] * rng.uniform(0.09, 0.16), "kWh", meth="Average-data", drift=-0.03, unc=20, dq=3)
        add("hotel_stay", "night", g, rng.uniform(12, 58), "night", meth="Average-data", unc=30, dq=4)
        add("water_supply", "m3", g, rng.uniform(0.15, 0.42), "m3", unc=25, dq=4)
        add("water_treatment", "m3", g, rng.uniform(0.18, 0.7), "m3", unc=25, dq=4)
    for gas, (ar4, ar5, ar6) in GWP.items():
        for basis, v in [("AR4", ar4), ("AR5", ar5), ("AR6", ar6)]:
            add("fugitive_gwp", f"{gas}|kg", basis, v, "kg", gas=gas, meth="Mass-balance / screening", years=[2022], noise=0, unc=1, dq=1, gwp=basis,
                src_doc="IPCC assessment-report GWP100 values (approximated, for synthetic testing)")
    regions = ["GLOBAL", "NA", "EU", "APAC", "LATAM", "MEA"]
    for f, u, p, v, grp in MATERIAL_FAMILIES:
        for r in regions:
            add("purchased_material", f"{f}|{u}", r, v * REG_MULT[r], u, mat=f, ind=grp, meth="Average-data (cradle-to-gate)", drift=-0.01, noise=0.02, unc=25, dq=3)
    for s, v in EEIO:
        for r in regions:
            add("spend_eeio", f"{s}|USD", r, v * REG_MULT[r], "USD", ind=s, meth="Spend-based EEIO", drift=-0.025, noise=0.02, unc=50, dq=5)
    for m, v in TRANSPORT:
        for lf in ["avg_laden", "full", "partial"]:
            add("freight_transport", f"{m}|{lf}", "GLOBAL", v * {"avg_laden": 1, "full": 0.82, "partial": 1.35}[lf], "tkm", meth="Distance-based", drift=-0.012, unc=20, dq=3)
    for m, v in TRAVEL:
        add("business_travel", f"{m}|pkm", "GLOBAL", v, "pkm", meth="Distance-based", drift=-0.01, unc=20, dq=3)
    for m, v in COMMUTE:
        add("employee_commute", f"{m}|pkm", "GLOBAL", v, "pkm", meth="Distance-based", drift=-0.015, unc=30, dq=4)
    for w in WASTE_TYPES:
        for meth, mult in WASTE_METHODS.items():
            add("waste_treatment", f"{w}|{meth}", "GLOBAL", WASTE_BASE[w] * mult, "t", meth="Waste-type-specific", unc=30, dq=3)
    for p, v in PROCESS:
        add("process_emissions", f"{p}|t", "GLOBAL", v, "t", meth="Stoichiometric / mass balance", unc=7, dq=2)
    for grp in ["Metals", "Polymers", "Packaging", "Electronics", "Minerals", "Chemicals", "Components", "Mixed"]:
        for meth, v in [("landfill", 25), ("incineration", 410 if grp == "Polymers" else 40), ("recycling", 10), ("mixed_eol", 60)]:
            add("end_of_life", f"{grp}|{meth}", "GLOBAL", v, "t", meth="Average-data EoL", unc=40, dq=4)
    for proc, v in [("metal_forming", 180), ("chemical_formulation", 120), ("automotive_assembly", 45), ("cement_to_concrete", 35)]:
        add("processing_sold", f"{proc}|t", "GLOBAL", v, "t" if proc != "automotive_assembly" else "pcs", meth="Average-data downstream processing", unc=40, dq=4)
    ef = pd.DataFrame(rows)
    # pad with supplier-specific factors to ~10,000 records
    sup = ctx.get("suppliers"); mat = ctx.get("materials")
    need = 10000 - len(ef) + 1500
    pairs = mat.sample(need, replace=True, random_state=ctx.seed)[["primary_supplier_id", "material_family", "base_unit"]].reset_index(drop=True)
    base = {m[0]: m[3] for m in MATERIAL_FAMILIES}
    yrs = rng.choice(YEARS, need)
    pad = pd.DataFrame(dict(activity_type="supplier_specific_material", lookup_key="supplier_specific_material|" + pairs.material_family + "|" + pairs.primary_supplier_id,
                            fuel_type=None, material_type=pairs.material_family, product_type=None, geography=pairs.primary_supplier_id, industry_applicability="Supplier-specific",
                            factor_value=np.round([base[f] for f in pairs.material_family] * rng.lognormal(-0.15, 0.3, need), 6), factor_unit="kgCO2e/" + pairs.base_unit,
                            activity_unit=pairs.base_unit, gas_type="CO2e", gwp_basis="AR6", gwp_time_horizon="GWP100", publication_year=yrs - 1,
                            effective_date=pd.to_datetime([f"{y}-01-01" for y in yrs]), expiry_date=pd.to_datetime([f"{y}-12-31" for y in yrs]),
                            version=[f"v{y}.s" for y in yrs], source_organisation="Supplier disclosure (SYNTHETIC)", source_document="Supplier PCF report (synthetic)",
                            methodology="Supplier-specific (ISO 14067-style, synthetic)", uncertainty_low_pct=-15, uncertainty_high_pct=20, data_quality_rating=2, synthetic_flag=True))
    pad["co2_factor"] = pad.factor_value; pad["ch4_factor"] = 0.0; pad["n2o_factor"] = 0.0
    ef = pd.concat([ef, pad], ignore_index=True).drop_duplicates(["lookup_key", "version"]).head(10000).reset_index(drop=True)
    ef.insert(0, "emission_factor_id", [f"EF-{i + 1:05d}" for i in range(len(ef))])
    ctx.save(ef, "GHG_Accounting/Emission_Factors/emission_factor_database.parquet", "emission_factors", pk="emission_factor_id", target=10000, system="EF_LIBRARY", desc="All factors are SYNTHETIC")
    ef.to_csv(ctx.path("GHG_Accounting/Emission_Factors/emission_factor_database.csv"), index=False)


def ef_table(ctx):
    ef = ctx.get("emission_factors")
    e = ef[ef.activity_type != "fugitive_gwp"].copy()
    e["year"] = pd.to_datetime(e.effective_date).dt.year
    return e.set_index(["lookup_key", "year"])[["emission_factor_id", "factor_value", "gwp_basis", "factor_unit"]]


def apply_ef(ctx, df, key_col, year_col):
    t = ef_table(ctx)
    t = t[~t.index.duplicated()]
    idx = pd.MultiIndex.from_arrays([df[key_col].values, df[year_col].values.astype(int)])
    r = t.reindex(idx)
    df["emission_factor_id"] = r.emission_factor_id.values
    df["emission_factor_value"] = r.factor_value.values
    df["emission_factor_unit"] = r.factor_unit.values
    df["gwp_basis"] = r.gwp_basis.values
    return df
