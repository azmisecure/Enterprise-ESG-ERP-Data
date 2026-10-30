import numpy as np
import pandas as pd
from .core import ids, zipf, ENTERPRISE_ID, START, YEARS, MONTHS

# code, name, region, ccy, tz, lang, measure, fy_start, synthetic grid kgCO2e/kWh, usd_per_ccy, cities
COUNTRIES = [
    ("US", "United States", "North America", "USD", "America/Chicago", "en-US", "imperial", 1, 0.385, 1.0, [("Houston", 29.76, -95.37), ("Detroit", 42.33, -83.05), ("Charlotte", 35.23, -80.84), ("Columbus", 39.96, -83.0)]),
    ("CA", "Canada", "North America", "CAD", "America/Toronto", "en-CA", "metric", 1, 0.125, 0.74, [("Hamilton", 43.26, -79.87), ("Montreal", 45.5, -73.57)]),
    ("MX", "Mexico", "Latin America", "MXN", "America/Mexico_City", "es-MX", "metric", 1, 0.432, 0.055, [("Monterrey", 25.69, -100.32), ("Queretaro", 20.59, -100.39)]),
    ("BR", "Brazil", "Latin America", "BRL", "America/Sao_Paulo", "pt-BR", "metric", 1, 0.091, 0.19, [("Campinas", -22.91, -47.06), ("Curitiba", -25.43, -49.27)]),
    ("GB", "United Kingdom", "Europe", "GBP", "Europe/London", "en-GB", "imperial-mixed", 4, 0.207, 1.27, [("Sheffield", 53.38, -1.47), ("Birmingham", 52.49, -1.89)]),
    ("DE", "Germany", "Europe", "EUR", "Europe/Berlin", "de-DE", "metric", 1, 0.366, 1.08, [("Duisburg", 51.43, 6.76), ("Stuttgart", 48.78, 9.18), ("Leipzig", 51.34, 12.37)]),
    ("FR", "France", "Europe", "EUR", "Europe/Paris", "fr-FR", "metric", 1, 0.058, 1.08, [("Lyon", 45.76, 4.84), ("Lille", 50.63, 3.06)]),
    ("IT", "Italy", "Europe", "EUR", "Europe/Rome", "it-IT", "metric", 1, 0.281, 1.08, [("Brescia", 45.54, 10.21), ("Turin", 45.07, 7.69)]),
    ("ES", "Spain", "Europe", "EUR", "Europe/Madrid", "es-ES", "metric", 1, 0.168, 1.08, [("Bilbao", 43.26, -2.93), ("Valencia", 39.47, -0.38)]),
    ("PL", "Poland", "Europe", "PLN", "Europe/Warsaw", "pl-PL", "metric", 1, 0.682, 0.25, [("Katowice", 50.26, 19.02), ("Wroclaw", 51.11, 17.03)]),
    ("NL", "Netherlands", "Europe", "EUR", "Europe/Amsterdam", "nl-NL", "metric", 1, 0.328, 1.08, [("Rotterdam", 51.92, 4.48)]),
    ("SE", "Sweden", "Europe", "SEK", "Europe/Stockholm", "sv-SE", "metric", 1, 0.028, 0.095, [("Gothenburg", 57.71, 11.97)]),
    ("TR", "Turkiye", "Middle East & Africa", "TRY", "Europe/Istanbul", "tr-TR", "metric", 1, 0.441, 0.04, [("Bursa", 40.19, 29.06), ("Izmir", 38.42, 27.14)]),
    ("ZA", "South Africa", "Middle East & Africa", "ZAR", "Africa/Johannesburg", "en-ZA", "metric", 3, 0.921, 0.055, [("Johannesburg", -26.2, 28.05)]),
    ("AE", "United Arab Emirates", "Middle East & Africa", "AED", "Asia/Dubai", "ar-AE", "metric", 1, 0.412, 0.27, [("Jebel Ali", 25.01, 55.06)]),
    ("IN", "India", "Asia Pacific", "INR", "Asia/Kolkata", "en-IN", "metric", 4, 0.712, 0.012, [("Pune", 18.52, 73.86), ("Chennai", 13.08, 80.27), ("Ahmedabad", 23.02, 72.57)]),
    ("CN", "China", "Asia Pacific", "CNY", "Asia/Shanghai", "zh-CN", "metric", 1, 0.556, 0.14, [("Suzhou", 31.3, 120.59), ("Tianjin", 39.34, 117.36), ("Foshan", 23.02, 113.12)]),
    ("JP", "Japan", "Asia Pacific", "JPY", "Asia/Tokyo", "ja-JP", "metric", 4, 0.452, 0.0068, [("Nagoya", 35.18, 136.91)]),
    ("KR", "South Korea", "Asia Pacific", "KRW", "Asia/Seoul", "ko-KR", "metric", 1, 0.418, 0.00075, [("Ulsan", 35.54, 129.31)]),
    ("SG", "Singapore", "Asia Pacific", "SGD", "Asia/Singapore", "en-SG", "metric", 4, 0.402, 0.74, [("Tuas", 1.32, 103.65)]),
    ("TH", "Thailand", "Asia Pacific", "THB", "Asia/Bangkok", "th-TH", "metric", 10, 0.451, 0.028, [("Rayong", 12.68, 101.28)]),
    ("AU", "Australia", "Asia Pacific", "AUD", "Australia/Sydney", "en-AU", "metric", 7, 0.681, 0.66, [("Newcastle", -32.93, 151.78), ("Melbourne", -37.81, 144.96)]),
]
CO_IDX = {c[0]: i for i, c in enumerate(COUNTRIES)}
DIVISIONS = [
    ("DIV-IMC", "Industrial Machinery"), ("DIV-AUT", "Automotive Components"), ("DIV-MET", "Metals & Engineered Materials"),
    ("DIV-CHM", "Chemicals & Industrial Materials"), ("DIV-ELE", "Electrical & Energy Equipment"),
    ("DIV-PKG", "Industrial Packaging"), ("DIV-CON", "Construction Materials"),
]
# family, unit, usd price/unit, synthetic kgCO2e/unit, group
MATERIAL_FAMILIES = [
    ("hot_rolled_steel_coil", "kg", 0.85, 2.1, "Metals"), ("cold_rolled_steel", "kg", 1.05, 2.4, "Metals"),
    ("stainless_steel_sheet", "kg", 3.2, 6.1, "Metals"), ("aluminium_ingot_primary", "kg", 2.6, 11.5, "Metals"),
    ("aluminium_recycled", "kg", 2.3, 1.1, "Metals"), ("copper_cathode", "kg", 8.9, 3.8, "Metals"),
    ("zinc", "kg", 3.0, 3.6, "Metals"), ("cast_iron", "kg", 0.9, 1.9, "Metals"),
    ("polypropylene_resin", "kg", 1.4, 1.9, "Polymers"), ("hdpe_resin", "kg", 1.3, 1.8, "Polymers"),
    ("pa66_resin", "kg", 3.6, 7.9, "Polymers"), ("pvc_compound", "kg", 1.2, 2.3, "Polymers"),
    ("epoxy_resin", "kg", 4.5, 6.5, "Chemicals"), ("sulphuric_acid", "kg", 0.15, 0.12, "Chemicals"),
    ("caustic_soda", "kg", 0.45, 1.2, "Chemicals"), ("industrial_solvent", "L", 1.8, 2.9, "Chemicals"),
    ("titanium_dioxide", "kg", 3.4, 8.1, "Chemicals"), ("cement_clinker", "t", 65, 830, "Minerals"),
    ("limestone", "t", 18, 8, "Minerals"), ("fly_ash", "t", 25, 4, "Minerals"), ("gypsum", "t", 30, 20, "Minerals"),
    ("sand_aggregate", "t", 15, 5, "Minerals"), ("corrugated_cardboard", "kg", 0.9, 0.95, "Packaging"),
    ("recycled_cardboard", "kg", 0.7, 0.55, "Packaging"), ("wooden_pallet", "pcs", 9, 12, "Packaging"),
    ("stretch_film", "kg", 2.1, 2.5, "Packaging"), ("electronic_pcb", "pcs", 14, 9.5, "Electronics"),
    ("electric_motor_small", "pcs", 55, 38, "Components"), ("bearing_assembly", "pcs", 7, 3.2, "Components"),
    ("fasteners", "kg", 3.5, 3.0, "Components"), ("copper_wire", "kg", 10.2, 4.4, "Components"),
    ("rubber_seal", "kg", 4.0, 3.1, "Components"), ("glass_fibre", "kg", 1.9, 2.6, "Materials"),
    ("lubricant_oil", "L", 3.2, 1.4, "Consumables"), ("refractory_brick", "kg", 1.1, 1.3, "Materials"),
    ("lithium_cell", "pcs", 22, 18, "Electronics"), ("paint_coating", "L", 6.5, 4.2, "Chemicals"),
    ("insulation_mineral_wool", "kg", 1.0, 1.3, "Materials"), ("industrial_gas_argon", "m3", 0.6, 0.4, "Consumables"),
    ("welding_wire", "kg", 3.8, 3.3, "Consumables"),
]
MF_IDX = {m[0]: i for i, m in enumerate(MATERIAL_FAMILIES)}
DIV_MATS = {
    "DIV-IMC": ["hot_rolled_steel_coil", "cast_iron", "electric_motor_small", "bearing_assembly", "fasteners", "paint_coating", "electronic_pcb", "rubber_seal", "welding_wire", "wooden_pallet"],
    "DIV-AUT": ["cold_rolled_steel", "aluminium_ingot_primary", "aluminium_recycled", "pa66_resin", "copper_wire", "rubber_seal", "fasteners", "lithium_cell", "paint_coating", "corrugated_cardboard"],
    "DIV-MET": ["hot_rolled_steel_coil", "aluminium_ingot_primary", "aluminium_recycled", "copper_cathode", "zinc", "refractory_brick", "industrial_gas_argon", "lubricant_oil"],
    "DIV-CHM": ["sulphuric_acid", "caustic_soda", "industrial_solvent", "titanium_dioxide", "epoxy_resin", "hdpe_resin", "pvc_compound"],
    "DIV-ELE": ["copper_wire", "copper_cathode", "stainless_steel_sheet", "electronic_pcb", "insulation_mineral_wool", "epoxy_resin", "fasteners", "glass_fibre"],
    "DIV-PKG": ["corrugated_cardboard", "recycled_cardboard", "hdpe_resin", "polypropylene_resin", "stretch_film", "wooden_pallet"],
    "DIV-CON": ["cement_clinker", "limestone", "fly_ash", "gypsum", "sand_aggregate", "refractory_brick"],
}
# family, unit, kg/unit, usd price, lifetime yrs, use-phase kWh/yr, intermediate
PRODUCT_FAMILIES = {
    "DIV-IMC": [("Hydraulic Press", "pcs", 6800, 185000, 20, 42000, False), ("CNC Machining Centre", "pcs", 9200, 240000, 15, 38000, False), ("Industrial Pump", "pcs", 320, 8200, 12, 21000, False), ("Screw Compressor", "pcs", 1100, 26000, 12, 95000, False)],
    "DIV-AUT": [("Brake Assembly", "pcs", 9.5, 140, 10, 0, True), ("Steering Column", "pcs", 7.2, 210, 12, 0, True), ("Alloy Wheel", "pcs", 11, 165, 12, 0, True), ("Wiring Harness", "pcs", 4.1, 120, 12, 0, True), ("EV Battery Housing", "pcs", 38, 950, 12, 0, True)],
    "DIV-MET": [("Steel Section", "t", 1000, 980, 50, 0, True), ("Aluminium Extrusion", "t", 1000, 3900, 40, 0, True), ("Copper Busbar", "t", 1000, 10800, 40, 0, True), ("Specialty Alloy Bar", "t", 1000, 6200, 30, 0, True)],
    "DIV-CHM": [("Industrial Coating", "kg", 1, 7.5, 0, 0, True), ("Structural Adhesive", "kg", 1, 11, 0, 0, True), ("Specialty Resin", "kg", 1, 5.4, 0, 0, True), ("Process Solvent Blend", "kg", 1, 2.6, 0, 0, True)],
    "DIV-ELE": [("Distribution Transformer", "pcs", 1450, 21000, 30, 6500, False), ("MV Switchgear", "pcs", 820, 34000, 25, 900, False), ("Industrial Electric Motor", "pcs", 140, 3600, 15, 48000, False), ("Solar Inverter", "pcs", 62, 4200, 12, 350, False)],
    "DIV-PKG": [("Corrugated Shipping Box", "pcs", 0.6, 1.1, 0, 0, False), ("HDPE Drum 200L", "pcs", 9, 38, 5, 0, False), ("IBC Container", "pcs", 58, 260, 8, 0, False), ("Stretch Wrap Roll", "pcs", 16, 44, 0, 0, False)],
    "DIV-CON": [("Portland Cement CEM I", "t", 1000, 118, 60, 0, True), ("Blended Cement CEM II", "t", 1000, 104, 60, 0, True), ("Precast Concrete Block", "t", 1000, 72, 60, 0, False), ("Dry Mortar", "t", 1000, 96, 60, 0, False)],
}
SUP_CATEGORIES = ["Raw Metals", "Polymers & Resins", "Chemicals", "Minerals", "Packaging", "Components", "Electronics", "Consumables",
                  "Logistics", "Utilities", "Energy & Fuels", "Waste Management", "IT Services", "Professional Services", "Facility Services",
                  "Capital Equipment", "Travel Services", "Refrigeration Services"]
GROUP_TO_CAT = {"Metals": "Raw Metals", "Polymers": "Polymers & Resins", "Chemicals": "Chemicals", "Minerals": "Minerals", "Packaging": "Packaging",
                "Components": "Components", "Electronics": "Electronics", "Consumables": "Consumables", "Materials": "Components"}
P1 = ["Arden", "Bryn", "Calder", "Dovre", "Elgin", "Falk", "Garr", "Hollin", "Ivor", "Jarl", "Kestrel", "Lumen", "Marrow", "Norr", "Oster",
      "Pell", "Quill", "Rook", "Sable", "Tarn", "Ulm", "Vale", "Wren", "Yarrow", "Zeph", "Corvin", "Brask", "Halden", "Merin", "Tovik"]
P2 = ["stone", "field", "forge", "wick", "mont", "bridge", "haven", "croft", "gate", "ridge", "vale", "brook", "line", "point", "worth"]
SUFFIX = {"US": "Inc.", "CA": "Ltd.", "MX": "S.A. de C.V.", "BR": "Ltda.", "GB": "Ltd", "DE": "GmbH", "FR": "SAS", "IT": "S.p.A.", "ES": "S.L.",
          "PL": "Sp. z o.o.", "NL": "B.V.", "SE": "AB", "TR": "A.S.", "ZA": "(Pty) Ltd", "AE": "FZE", "IN": "Pvt Ltd", "CN": "Co., Ltd.",
          "JP": "K.K.", "KR": "Co., Ltd.", "SG": "Pte Ltd", "TH": "Co., Ltd.", "AU": "Pty Ltd"}
DEPTS = ["Finance", "Procurement", "Operations", "EHS & Sustainability", "Human Resources", "IT", "Sales", "Logistics", "Maintenance", "Quality", "Engineering", "Legal & Compliance"]
REFRIGERANTS = ["R-410A", "R-134a", "R-404A", "R-32", "R-407C", "R-1234ze", "R-744", "R-22"]


def names(rng, n, countries, kind):
    a = rng.choice(P1, n); b = rng.choice(P2, n); c = rng.choice(kind, n)
    suf = np.array([SUFFIX[x] for x in countries])
    nm = np.char.add(np.char.add(np.char.add(np.char.add(np.char.add(a, b), " "), c), " "), suf)
    return np.char.add(nm, np.char.add(" #", np.arange(1, n + 1).astype(str)))


def gen_enterprise(ctx):
    rng = ctx.rng("enterprise")
    ent = pd.DataFrame([dict(enterprise_id=ENTERPRISE_ID, enterprise_name="Halvorsen-Kaito Industrial Holdings plc (SYNTHETIC)",
                             legal_form="plc", hq_country_id="GB", hq_city="Sheffield", reporting_currency="USD", consolidation_approach="Operational control",
                             ghg_base_year=2022, fiscal_year_convention="Calendar year (group); local FY varies by legal entity", employees_target=75000,
                             annual_revenue_usd_bn=18.6, industry="Diversified industrial manufacturing", synthetic_flag=True)])
    ctx.save(ent, "Enterprise_Master/Enterprise/enterprise.json", "enterprise", pk="enterprise_id", desc="Fictional enterprise identity", system="MDG", domain="Enterprise_Master")
    co = pd.DataFrame([dict(country_id=c[0], country_name=c[1], region=c[2], currency=c[3], time_zone=c[4], language=c[5], measurement_system=c[6],
                            local_fiscal_year_start_month=c[7], grid_region=f"GRID-{c[0]}", regulatory_jurisdiction=f"{c[1]} environmental authority (synthetic)",
                            reporting_requirements=("CSRD/ESRS" if c[2] == "Europe" else "SEC/State" if c[0] == "US" else "BRSR" if c[0] == "IN" else "ISSB-aligned local"),
                            enterprise_id=ENTERPRISE_ID) for c in COUNTRIES])
    ctx.save(co, "Enterprise_Master/Countries/countries.csv", "countries", pk="country_id", system="MDG")
    le_rows = []
    for i, c in enumerate(COUNTRIES):
        for k in range(2 if c[0] in ("US", "DE", "CN", "IN") else 1):
            le_rows.append(dict(legal_entity_id=f"LE-{c[0]}{k + 1:02d}", company_code=f"{1000 + len(le_rows) * 10}",
                                legal_entity_name=f"Halvorsen-Kaito {c[1]} {'Manufacturing' if k == 0 else 'Trading'} {SUFFIX[c[0]]} (SYNTHETIC)",
                                country_id=c[0], functional_currency=c[3], fiscal_year_start_month=c[7], ownership_pct=(100.0 if k == 0 or c[0] != "CN" else 60.0),
                                consolidation_method=("Full" if k == 0 or c[0] != "CN" else "JV-equity share"), enterprise_id=ENTERPRISE_ID, synthetic_flag=True))
    le = pd.DataFrame(le_rows)
    ctx.save(le, "Enterprise_Master/Legal_Entities/legal_entities.csv", "legal_entities", pk="legal_entity_id", fks={"country_id": "countries.country_id"}, system="SAP_S4")
    div = pd.DataFrame([dict(division_id=d, division_name=n, enterprise_id=ENTERPRISE_ID) for d, n in DIVISIONS])
    bu = pd.DataFrame([dict(business_unit_id=f"BU-{d[4:]}-{r}", division_id=d, business_unit_name=f"{n} - {rg}", region=rg, enterprise_id=ENTERPRISE_ID)
                       for d, n in DIVISIONS for r, rg in [("AM", "Americas"), ("EU", "Europe & MEA"), ("AP", "Asia Pacific")]])
    ctx.save(div, "Enterprise_Master/Business_Units/divisions.csv", "divisions", pk="division_id", system="MDG")
    ctx.save(bu, "Enterprise_Master/Business_Units/business_units.csv", "business_units", pk="business_unit_id", fks={"division_id": "divisions.division_id"}, system="MDG")
    # facilities
    rows = []
    reg_bu = {"North America": "AM", "Latin America": "AM", "Europe": "EU", "Middle East & Africa": "EU", "Asia Pacific": "AP"}
    cweights = np.array([5, 1.5, 2, 1.5, 2, 4, 2, 2, 1.5, 2, 1, 1, 1.5, 1, 1, 3.5, 4, 1.5, 1, 1, 1, 1.5]); cweights /= cweights.sum()
    for ftype, n in [("Manufacturing", 42), ("Warehouse/DC", 72), ("Office", 38)]:
        cs = rng.choice(len(COUNTRIES), n, p=cweights)
        for j, ci in enumerate(cs):
            c = COUNTRIES[ci]; city, clat, clon = c[10][rng.integers(len(c[10]))]
            d = DIVISIONS[(j + rng.integers(3)) % 7][0] if ftype != "Office" else DIVISIONS[j % 7][0]
            fid = f"FAC-{ftype[:3].upper()}-{len(rows) + 1:03d}"
            comm = pd.Timestamp("2015-01-01") if rng.random() > 0.12 else pd.Timestamp(rng.choice(pd.date_range("2022-03-01", "2025-09-01", freq="MS")))
            rows.append(dict(facility_id=fid, facility_name=f"{city} {['North', 'Riverside', 'East', 'Park', 'Harbour', 'Valley'][j % 6]} {ftype.split('/')[0]} (SYNTHETIC)",
                             facility_type=ftype, country_id=c[0], city=city, address=f"{rng.integers(1, 400)} Synthetic Industrial Way, {city}",
                             latitude=round(clat + rng.normal(0, .08), 4), longitude=round(clon + rng.normal(0, .08), 4),
                             division_id=d, business_unit_id=f"BU-{d[4:]}-{reg_bu[c[2]]}", legal_entity_id=f"LE-{c[0]}01",
                             time_zone=c[4], floor_area_m2=int(rng.lognormal(10.3 if ftype == "Manufacturing" else 9.6 if ftype[0] == "W" else 8.4, 0.4)),
                             tenure=("Leased" if (ftype != "Manufacturing" and rng.random() < 0.45) else "Owned"),
                             leased_out_portion_pct=(round(rng.uniform(10, 40), 1) if ftype == "Office" and rng.random() < 0.15 else 0.0),
                             commissioning_date=comm, temporary_shutdown_start=pd.NaT, temporary_shutdown_end=pd.NaT,
                             divestment_date=pd.NaT, energy_intensity_index=round(rng.lognormal(0, 0.35), 3),
                             climate_zone=("Hot" if abs(clat) < 26 else "Cold" if abs(clat) > 50 else "Temperate"),
                             grid_region=f"GRID-{c[0]}", operational_control=True, enterprise_id=ENTERPRISE_ID, synthetic_flag=True))
    fac = pd.DataFrame(rows)
    mfg = fac.index[fac.facility_type == "Manufacturing"]
    sd = rng.choice(mfg, 4, replace=False)
    fac.loc[sd, "temporary_shutdown_start"] = pd.to_datetime(["2022-06-01", "2023-08-01", "2024-02-01", "2025-07-01"])
    fac.loc[sd, "temporary_shutdown_end"] = pd.to_datetime(["2022-07-15", "2023-09-30", "2024-03-10", "2025-08-20"])
    dv = rng.choice(fac.index[fac.facility_type == "Warehouse/DC"], 2, replace=False)
    fac.loc[dv, "divestment_date"] = pd.to_datetime(["2024-06-30", "2025-12-31"])
    cn_le = fac.country_id == "CN"
    fac.loc[cn_le & (fac.facility_type == "Manufacturing"), "legal_entity_id"] = np.where(rng.random((cn_le & (fac.facility_type == "Manufacturing")).sum()) < 0.4, "LE-CN02", "LE-CN01")
    fac.loc[fac.legal_entity_id == "LE-CN02", "operational_control"] = False
    ctx.save(fac, "Enterprise_Master/Facilities/facilities.csv", "facilities", pk="facility_id",
             fks={"country_id": "countries.country_id", "legal_entity_id": "legal_entities.legal_entity_id", "business_unit_id": "business_units.business_unit_id"}, system="MDG")
    # plants and lines
    pl, ln = [], []
    for _, f in fac[fac.facility_type == "Manufacturing"].iterrows():
        for p in range(1 + int(rng.random() < 0.4)):
            pid = f"PLT-{len(pl) + 1:03d}"
            pl.append(dict(plant_id=pid, sap_plant_code=f"{f.country_id}{len(pl) + 1:02d}", facility_id=f.facility_id, plant_name=f"{f.city} Plant {p + 1}",
                           division_id=f.division_id, capacity_index=round(rng.lognormal(0, 0.3), 3)))
            for k in range(rng.integers(3, 8)):
                ln.append(dict(production_line_id=f"LIN-{len(ln) + 1:04d}", plant_id=pid, facility_id=f.facility_id, division_id=f.division_id,
                               line_name=f"Line {chr(65 + k)}", line_type=rng.choice(["Machining", "Assembly", "Forming", "Casting", "Mixing", "Coating", "Kiln", "Extrusion", "Packing"]),
                               rated_capacity_units_per_hr=round(rng.lognormal(3, 0.6), 1), commissioning_year=int(rng.integers(2005, 2024)),
                               oee_baseline=round(rng.uniform(0.58, 0.86), 3)))
    plants = pd.DataFrame(pl); lines = pd.DataFrame(ln)
    ctx.save(plants, "Enterprise_Master/Plants/plants.csv", "plants", pk="plant_id", fks={"facility_id": "facilities.facility_id"}, system="SAP_S4")
    ctx.save(lines, "Enterprise_Master/Plants/production_lines.csv", "production_lines", pk="production_line_id", fks={"plant_id": "plants.plant_id"}, system="MES")
    dep = pd.DataFrame([dict(department_id=f"DEP-{le_id[3:]}-{k:02d}", legal_entity_id=le_id, department_name=d, enterprise_id=ENTERPRISE_ID)
                        for le_id in le.legal_entity_id for k, d in enumerate(DEPTS)])
    ctx.save(dep, "Enterprise_Master/Departments/departments.csv", "departments", pk="department_id", fks={"legal_entity_id": "legal_entities.legal_entity_id"}, system="HRMS")
    cc = []
    for _, f in fac.iterrows():
        for k, d in enumerate(DEPTS[:8] if f.facility_type == "Manufacturing" else DEPTS[:5]):
            cc.append(dict(cost_centre_id=f"CC-{f.facility_id[4:]}-{k:02d}", sap_kostl=f"{4000000 + len(cc)}", facility_id=f.facility_id, department_name=d,
                           legal_entity_id=f.legal_entity_id, profit_centre_id=f"PC-{f.business_unit_id[3:]}-{f.country_id}", business_unit_id=f.business_unit_id,
                           team_name=f"{d} Team {f.city}"))
    ccd = pd.DataFrame(cc)
    pc = ccd[["profit_centre_id", "business_unit_id"]].drop_duplicates("profit_centre_id").reset_index(drop=True)
    pc["profit_centre_name"] = pc.profit_centre_id.str.replace("PC-", "Profit Centre ")
    ctx.save(ccd, "Enterprise_Master/Cost_Centres/cost_centres.csv", "cost_centres", pk="cost_centre_id", fks={"facility_id": "facilities.facility_id", "profit_centre_id": "profit_centres.profit_centre_id"}, system="SAP_S4")
    ctx.save(pc, "Enterprise_Master/Cost_Centres/profit_centres.csv", "profit_centres", pk="profit_centre_id", fks={"business_unit_id": "business_units.business_unit_id"}, system="SAP_S4")
    # fx rates monthly
    fx = []
    for c in COUNTRIES:
        walk = np.cumprod(1 + rng.normal(0.0 if c[3] not in ("TRY", "ZAR") else -0.025 if c[3] == "TRY" else -0.004, 0.015, len(MONTHS)))
        for m, w in zip(MONTHS, walk):
            fx.append(dict(period=str(m), currency=c[3], usd_per_unit=round(c[9] * w, 6) if c[3] != "USD" else 1.0))
    fxd = pd.DataFrame(fx).drop_duplicates(["period", "currency"])
    ctx.save(fxd, "Enterprise_Master/Countries/fx_rates_monthly.csv", "fx_rates", system="TREASURY")
    cal = pd.DataFrame(dict(period=[str(m) for m in MONTHS], period_start=[m.start_time.date() for m in MONTHS], period_end=[m.end_time.date() for m in MONTHS],
                            calendar_year=[m.year for m in MONTHS], quarter=[f"{m.year}-Q{m.quarter}" for m in MONTHS]))
    ctx.save(cal, "Enterprise_Master/Enterprise/reporting_calendar.csv", "reporting_calendar", pk="period", system="MDG")


def gen_source_master(ctx):
    rng = ctx.rng("source_master")
    fac = ctx.get("facilities"); lines = ctx.get("production_lines")
    cc = [c[0] for c in COUNTRIES]
    # suppliers
    n_s = 10000
    cat_p = np.array([10, 7, 7, 4, 6, 10, 6, 5, 6, 3, 3, 2, 4, 6, 6, 4, 1.5, 1.5]); cat_p /= cat_p.sum()
    scats = rng.choice(SUP_CATEGORIES, n_s, p=cat_p)
    sc = rng.choice(cc, n_s, p=np.array([18, 3, 4, 3, 5, 12, 5, 5, 4, 4, 2, 2, 3, 1.5, 1, 10, 14, 3, 2, 1.5, 1.5, 2]) / 106.5)
    onboard = pd.to_datetime(rng.choice(pd.date_range("2008-01-01", "2026-06-01", freq="D"), n_s))
    sup = pd.DataFrame(dict(supplier_id=ids("SUP-", n_s, 5), erp_vendor_no=np.char.add("V", (1000000 + rng.choice(9000000, n_s, replace=False)).astype(str)),
                            srm_supplier_ref=np.char.add("SRM-", rng.choice(900000, n_s, replace=False).astype(str)),
                            supplier_name=names(rng, n_s, sc, ["Metals", "Polymers", "Components", "Logistics", "Chemicals", "Fabrication", "Packaging", "Electrics", "Industrial Services", "Castings"]),
                            country_id=sc, supplier_category=scats, tier=rng.choice([1, 1, 1, 2, 2, 3], n_s), onboarding_date=onboard,
                            termination_date=pd.NaT, payment_terms=rng.choice(["NET30", "NET45", "NET60", "NET90", "2/10NET30"], n_s, p=[.3, .2, .3, .15, .05]),
                            currency=[COUNTRIES[CO_IDX[x]][3] for x in sc], risk_rating=rng.choice(["Low", "Medium", "High"], n_s, p=[.6, .3, .1]),
                            data_maturity=rng.choice(["Leading", "Established", "Developing", "Basic"], n_s, p=[.1, .3, .35, .25]),
                            synthetic_id_tax=np.char.add("TAX-SYN-", rng.choice(10 ** 8, n_s, replace=False).astype(str)), synthetic_flag=True))
    term = rng.random(n_s) < 0.07
    sup.loc[term, "termination_date"] = pd.to_datetime(rng.choice(pd.date_range("2022-03-01", "2026-10-01"), term.sum()))
    sup["status"] = np.where(sup.termination_date.notna(), "Terminated", "Active")
    miss_c = rng.choice(n_s, 60, replace=False)
    orig_c = sup.loc[miss_c, "country_id"].values
    sup.loc[miss_c, "country_id"] = None
    ctx.save(sup, "Procurement/Suppliers/supplier_master.parquet", "suppliers", pk="supplier_id", fks={"country_id": "countries.country_id"}, target=10000, system="SAP_Ariba")
    ctx.anom("suppliers", sup.supplier_id.values[miss_c], "Missing data", "Missing country information", "Medium", orig_c, "NULL",
             "Supplier onboarding form country field left blank", "Rule: required-field check", "Populate country from supplier location master",
             process="Supplier master data", family="Data_Inconsistencies")
    sl = sup[["supplier_id", "country_id"]].loc[sup.index.repeat(rng.choice([1, 1, 2, 3], n_s))].reset_index(drop=True)
    sl["country_id"] = sl.country_id.fillna(sl.supplier_id.map(dict(zip(sup.supplier_id.values[miss_c], orig_c))))
    sl["supplier_location_id"] = ids("SLOC-", len(sl), 6)
    cities = [COUNTRIES[CO_IDX[x]][10][0] for x in sl.country_id]
    sl["city"] = [c[0] for c in cities]
    sl["latitude"] = np.round([c[1] for c in cities] + rng.normal(0, 0.6, len(sl)), 4)
    sl["longitude"] = np.round([c[2] for c in cities] + rng.normal(0, 0.6, len(sl)), 4)
    sl["location_type"] = rng.choice(["Manufacturing", "Warehouse", "HQ"], len(sl), p=[.6, .25, .15])
    sl["grid_region"] = "GRID-" + sl.country_id
    ctx.save(sl, "Procurement/Suppliers/supplier_locations.parquet", "supplier_locations", pk="supplier_location_id", fks={"supplier_id": "suppliers.supplier_id"}, system="SAP_Ariba")
    # materials
    n_m = 5000
    mf = rng.choice(len(MATERIAL_FAMILIES), n_m, p=zipf(len(MATERIAL_FAMILIES), 0.4))
    fam = np.array([MATERIAL_FAMILIES[i] for i in mf], dtype=object)
    mat = pd.DataFrame(dict(material_id=ids("MAT-", n_m, 5), sap_matnr=np.char.zfill((10000000 + np.arange(n_m) * 7).astype(str), 18),
                            material_family=fam[:, 0], material_group=fam[:, 4], base_unit=fam[:, 1],
                            description=[f"{f[0].replace('_', ' ').title()} grade {chr(65 + g)}-{s}" for f, g, s in zip(fam, rng.integers(0, 8, n_m), rng.integers(100, 999, n_m))],
                            standard_price_usd=np.round(fam[:, 2].astype(float) * rng.lognormal(0, 0.18, n_m), 4),
                            recycled_content_pct=np.round(np.where(np.char.find(fam[:, 0].astype(str), "recycled") >= 0, rng.uniform(70, 98, n_m), rng.beta(1.2, 6, n_m) * 40), 1),
                            hazardous_flag=np.isin(fam[:, 4], ["Chemicals"]) & (rng.random(n_m) < 0.6), weight_kg_per_unit=np.where(fam[:, 1] == "t", 1000.0, np.where(fam[:, 1] == "pcs", np.round(rng.lognormal(0.5, 0.8, n_m), 3), np.where(fam[:, 1] == "L", 0.92, np.where(fam[:, 1] == "m3", 1.78, 1.0)))),
                            synthetic_flag=True))
    ok_sup = sup[sup.supplier_category.isin(list(GROUP_TO_CAT.values()))]
    mat["primary_supplier_id"] = [ok_sup.supplier_id.values[rng.integers(len(ok_sup))] for _ in range(n_m)]
    by_cat = ok_sup.groupby("supplier_category").supplier_id.apply(np.array).to_dict()
    mat["primary_supplier_id"] = [by_cat[GROUP_TO_CAT[g]][rng.integers(len(by_cat[GROUP_TO_CAT[g]]))] for g in mat.material_group]
    mat["secondary_supplier_id"] = [by_cat[GROUP_TO_CAT[g]][rng.integers(len(by_cat[GROUP_TO_CAT[g]]))] if r < 0.6 else None for g, r in zip(mat.material_group, rng.random(n_m))]
    bad = rng.choice(n_m, 45, replace=False); orig = mat.loc[bad, "material_group"].values.copy()
    mat.loc[bad, "material_group"] = rng.choice(["Packaging", "Consumables", "Electronics"], 45)
    ctx.save(mat, "ERP/Materials/material_master.parquet", "materials", pk="material_id", fks={"primary_supplier_id": "suppliers.supplier_id", "secondary_supplier_id": "suppliers.supplier_id"}, target=5000, system="SAP_S4")
    ctx.anom("materials", mat.material_id.values[bad], "Classification error", "Incorrect material classification", "Medium", orig, mat.loc[bad, "material_group"].values,
             "Material group changed during legacy migration", "Cross-check family vs group mapping", "Restore material group from family taxonomy", process="Material master", ghg="Scope 3 Cat 1")
    # products + BOM
    pr, bom = [], []
    div_ids = [d[0] for d in DIVISIONS]
    per_div = [400, 360, 200, 260, 330, 250, 200]
    for d, cnt in zip(div_ids, per_div):
        fams = PRODUCT_FAMILIES[d]; dm = [m for m in DIV_MATS[d]]
        dmats = mat[mat.material_family.isin(dm)]
        for k in range(cnt):
            f = fams[k % len(fams)]
            pid = f"PRD-{len(pr) + 1:04d}"
            launch = pd.Timestamp("2012-01-01") if rng.random() > 0.15 else pd.Timestamp(rng.choice(pd.date_range("2022-02-01", "2026-03-01", freq="MS")))
            disc = pd.Timestamp(rng.choice(pd.date_range("2023-01-01", "2026-09-01", freq="MS"))) if rng.random() < 0.08 else pd.NaT
            w = f[2] * rng.lognormal(0, 0.15)
            pr.append(dict(product_id=pid, sku=f"{d[4:]}-{rng.integers(10000, 99999)}-{chr(65 + k % 26)}", division_id=d, product_family=f[0],
                           product_name=f"{f[0]} {['Pro', 'Max', 'Eco', 'HD', 'Std', 'X'][k % 6]} {k % 40 + 1}", sales_unit=f[1], unit_weight_kg=round(w, 3),
                           list_price_usd=round(f[3] * rng.lognormal(0, 0.12), 2), lifetime_years=f[4], use_phase_kwh_per_year=round(f[5] * rng.lognormal(0, 0.2), 1),
                           intermediate_product=f[6], launch_date=launch, discontinuation_date=disc, recyclable_share_pct=round(rng.uniform(20, 95), 1), synthetic_flag=True))
            comp = rng.choice(len(dmats), min(len(dmats), int(rng.integers(4, 10))), replace=False)
            shares = rng.dirichlet(np.ones(len(comp)))
            for s, ci in zip(shares, comp):
                m = dmats.iloc[ci]
                qty_kg = w * s * 1.0
                qty = qty_kg / m.weight_kg_per_unit if m.base_unit != "pcs" else max(1, round(qty_kg / max(m.weight_kg_per_unit, 0.01) / 8))
                bom.append(dict(bom_id=f"BOM-{pid[4:]}", bom_item_id=f"BOMI-{len(bom) + 1:06d}", product_id=pid, material_id=m.material_id,
                                component_qty_per_unit=round(qty, 6), component_unit=m.base_unit, scrap_allowance_pct=round(rng.uniform(1, 6), 2), valid_from=START.date()))
    prod = pd.DataFrame(pr); bomd = pd.DataFrame(bom)
    ctx.save(prod, "ERP/Products/product_master.parquet", "products", pk="product_id", fks={"division_id": "divisions.division_id"}, target=2000, system="SAP_S4")
    ctx.save(bomd, "ERP/Products/bill_of_materials.parquet", "bom", pk="bom_item_id", fks={"product_id": "products.product_id", "material_id": "materials.material_id"}, system="SAP_S4")
    rt = lines.merge(prod[["product_id", "division_id"]], on="division_id").groupby("product_id").head(2).reset_index(drop=True)
    rt["routing_id"] = ids("RTG-", len(rt), 6); rt["cycle_time_min"] = np.round(rng.lognormal(2.5, 0.7, len(rt)), 2)
    rt["energy_kwh_per_unit"] = np.round(rng.lognormal(1.2, 1.1, len(rt)), 3)
    ctx.save(rt[["routing_id", "product_id", "production_line_id", "plant_id", "facility_id", "cycle_time_min", "energy_kwh_per_unit"]], "ERP/Products/routings.parquet", "routings",
             pk="routing_id", fks={"product_id": "products.product_id", "production_line_id": "production_lines.production_line_id"}, system="SAP_S4")
    # assets / machines
    n_a = 20000
    mfg_fac = fac[fac.facility_type == "Manufacturing"].facility_id.values
    li = rng.integers(0, len(lines), n_a)
    atype = rng.choice(["CNC Machine", "Press", "Furnace", "Boiler", "Air Compressor", "Chiller", "HVAC Unit", "Conveyor", "Robot Cell", "Kiln", "Mixer", "Extruder",
                        "Diesel Generator", "Forklift", "Pump", "Transformer", "IT Server Rack"], n_a, p=[.12, .08, .04, .03, .06, .04, .07, .1, .08, .02, .05, .05, .02, .07, .1, .03, .04])
    on_line = ~np.isin(atype, ["HVAC Unit", "IT Server Rack", "Boiler", "Diesel Generator", "Chiller", "Transformer"])
    afac = np.where(on_line, lines.facility_id.values[li], fac.facility_id.values[rng.integers(0, len(fac), n_a)])
    afac = np.where(np.isin(atype, ["Boiler", "Furnace", "Kiln"]), mfg_fac[rng.integers(0, len(mfg_fac), n_a)], afac)
    acq = pd.to_datetime(rng.choice(pd.date_range("2006-01-01", "2026-06-01", freq="D"), n_a))
    fuel = {"Boiler": "natural_gas", "Furnace": "natural_gas", "Kiln": "coal", "Diesel Generator": "diesel", "Forklift": "lpg"}
    assets = pd.DataFrame(dict(asset_id=ids("AST-", n_a, 6), machine_id=np.char.add("MCH-", np.char.zfill(np.arange(1, n_a + 1).astype(str), 6)),
                               sap_anln1=np.char.zfill((100000 + np.arange(n_a)).astype(str), 12), asset_type=atype, facility_id=afac,
                               production_line_id=np.where(on_line, lines.production_line_id.values[li], None), acquisition_date=acq,
                               acquisition_cost_usd=np.round(rng.lognormal(11, 1.1, n_a), 2), useful_life_years=rng.choice([5, 8, 10, 15, 20, 25], n_a),
                               rated_power_kw=np.round(rng.lognormal(3.4, 1.0, n_a), 1), fuel_type=[fuel.get(a, "electricity") for a in atype],
                               refrigerant_type=[rng.choice(REFRIGERANTS) if a in ("Chiller", "HVAC Unit") else None for a in atype],
                               refrigerant_charge_kg=np.where(np.isin(atype, ["Chiller", "HVAC Unit"]), np.round(rng.lognormal(3, 0.8, n_a), 1), 0.0),
                               manufacturer=np.char.add("SynthOEM-", rng.integers(1, 80, n_a).astype(str)), status="In service", retirement_date=pd.NaT, synthetic_flag=True))
    ret = rng.random(n_a) < 0.05
    assets.loc[ret, "retirement_date"] = pd.to_datetime(rng.choice(pd.date_range("2022-02-01", "2026-10-01"), ret.sum()))
    assets.loc[ret, "status"] = "Retired"
    assets.loc[assets.acquisition_date > assets.retirement_date, "retirement_date"] = pd.NaT
    ctx.save(assets, "ERP/Assets/fixed_asset_register.parquet", "assets", pk="asset_id", fks={"facility_id": "facilities.facility_id", "production_line_id": "production_lines.production_line_id"}, target=20000, system="SAP_S4")
    # meters
    mrows = []
    for _, f in fac.iterrows():
        mrows.append((f.facility_id, "electricity", "main", None, "kWh"))
        mrows.append((f.facility_id, "water", "main", None, "m3"))
        if f.facility_type == "Manufacturing":
            mrows.append((f.facility_id, "natural_gas", "main", None, "m3"))
            if rng.random() < 0.25:
                mrows.append((f.facility_id, "steam", "main", None, "MWh"))
            mrows.append((f.facility_id, "compressed_air", "sub", None, "Nm3"))
        elif f.facility_type == "Office" and rng.random() < 0.3:
            mrows.append((f.facility_id, "chilled_water", "main", None, "kWh"))
    for _, l in lines.iterrows():
        mrows.append((l.facility_id, "electricity", "sub", l.production_line_id, "kWh"))
    sub_assets = assets[assets.rated_power_kw > 60].sample(5000 - len(mrows), random_state=ctx.seed)
    for _, a in sub_assets.iterrows():
        mrows.append((a.facility_id, "electricity" if a.fuel_type == "electricity" else a.fuel_type, "asset", a.asset_id, "kWh" if a.fuel_type == "electricity" else "m3" if a.fuel_type == "natural_gas" else "L"))
    met = pd.DataFrame(mrows, columns=["facility_id", "utility_type", "meter_level", "linked_entity_id", "unit"])
    met.insert(0, "meter_id", ids("MTR-", len(met), 5))
    met["serial_no"] = np.char.add("SN", rng.choice(10 ** 9, len(met), replace=False).astype(str))
    met["utility_account_no"] = np.where(met.meter_level == "main", np.char.add("UA-", rng.integers(10 ** 7, 10 ** 8, len(met)).astype(str)), None)
    met["protocol"] = rng.choice(["Modbus TCP", "BACnet", "OPC-UA", "M-Bus", "Pulse", "Manual read"], len(met))
    met["install_date"] = pd.to_datetime(rng.choice(pd.date_range("2012-01-01", "2023-12-31"), len(met)))
    met["last_calibration_date"] = pd.to_datetime(rng.choice(pd.date_range("2024-01-01", "2026-06-01"), len(met)))
    met.loc[(met.utility_type == "electricity") & (met.meter_level == "main") & (rng.random(len(met)) < 0.08), "unit"] = "MWh"
    ctx.save(met, "Energy/energy_meters.csv", "meters", pk="meter_id", fks={"facility_id": "facilities.facility_id"}, target=5000, system="EMS")
    # fleet
    n_v = 3000
    vt = rng.choice(["HGV Rigid", "HGV Articulated", "LCV Van", "Company Car", "Pickup", "Yard Tractor"], n_v, p=[.2, .15, .3, .25, .06, .04])
    ft = np.where(np.isin(vt, ["Company Car", "LCV Van"]), rng.choice(["diesel", "petrol", "bev", "hybrid"], n_v, p=[.4, .3, .18, .12]), rng.choice(["diesel", "hvo", "cng", "bev"], n_v, p=[.82, .07, .06, .05]))
    eff = {"HGV Rigid": 28, "HGV Articulated": 34, "LCV Van": 10, "Company Car": 6.5, "Pickup": 11, "Yard Tractor": 22}
    veh = pd.DataFrame(dict(vehicle_id=ids("VEH-", n_v, 4), fleet_system_ref=np.char.add("FLT", rng.choice(10 ** 6, n_v, replace=False).astype(str)),
                            registration_synthetic=np.char.add("SYN-", rng.choice(10 ** 6, n_v, replace=False).astype(str)), vehicle_type=vt, fuel_type=ft,
                            facility_id=fac.facility_id.values[rng.integers(0, len(fac), n_v)], model_year=rng.integers(2014, 2026, n_v),
                            rated_consumption_per_100km=[round(eff[v] * rng.lognormal(0, 0.1) * (0 if f == "bev" else 1), 2) for v, f in zip(vt, ft)],
                            rated_kwh_per_100km=[round(eff[v] * 2.6 * rng.lognormal(0, 0.1), 1) if f == "bev" else 0 for v, f in zip(vt, ft)],
                            payload_t=np.round([{"HGV Rigid": 12, "HGV Articulated": 24, "LCV Van": 1.2, "Company Car": 0.3, "Pickup": 0.9, "Yard Tractor": 30}[v] for v in vt], 1),
                            in_service_date=pd.to_datetime(rng.choice(pd.date_range("2016-01-01", "2026-01-01"), n_v)), synthetic_flag=True))
    veh.loc[veh.fuel_type == "bev", "in_service_date"] = pd.to_datetime(rng.choice(pd.date_range("2023-01-01", "2026-03-01"), (veh.fuel_type == "bev").sum()))
    veh["disposal_date"] = pd.NaT
    dsp = (veh.fuel_type == "diesel") & (rng.random(n_v) < 0.12)
    veh.loc[dsp, "disposal_date"] = pd.to_datetime(rng.choice(pd.date_range("2023-01-01", "2026-06-01"), dsp.sum()))
    ctx.save(veh, "Logistics/fleet_master.csv", "vehicles", pk="vehicle_id", fks={"facility_id": "facilities.facility_id"}, target=3000, system="FLEET_MGMT")
    # customers
    n_c = 20000
    cc_w = np.array([20, 4, 4, 4, 6, 10, 5, 4, 3, 3, 2, 2, 2, 1.5, 1.5, 9, 9, 3, 2, 1.5, 1.5, 2.5]); cc_w /= cc_w.sum()
    ccn = rng.choice(cc, n_c, p=cc_w)
    seg = rng.choice(["Automotive OEM", "Industrial OEM", "Construction Contractor", "Utility", "Distributor", "Government", "Packaging Converter", "EPC Contractor"], n_c, p=[.12, .2, .16, .06, .26, .04, .08, .08])
    cust = pd.DataFrame(dict(customer_id=ids("CUST-", n_c, 6), crm_account_id=np.char.add("001SYN", np.char.zfill(rng.choice(10 ** 12, n_c, replace=False).astype(str), 12)),
                             erp_sold_to=np.char.add("C", (2000000 + rng.choice(7999999, n_c, replace=False)).astype(str)),
                             customer_name=names(rng, n_c, ccn, ["Industries", "Holdings", "Construction", "Motors", "Energy", "Trading", "Systems", "Works"]),
                             country_id=ccn, segment=seg, sales_territory=np.char.add("TER-", ccn), credit_limit_usd=np.round(rng.lognormal(12, 1.1, n_c), -3),
                             acquisition_date=pd.to_datetime(rng.choice(pd.date_range("2005-01-01", "2026-06-01"), n_c)), churn_date=pd.NaT,
                             incoterm=rng.choice(["DAP", "DDP", "FCA", "EXW", "CPT"], n_c, p=[.35, .2, .2, .15, .1]), synthetic_flag=True))
    ch = rng.random(n_c) < 0.08
    cust.loc[ch, "churn_date"] = pd.to_datetime(rng.choice(pd.date_range("2022-06-01", "2026-10-01"), ch.sum()))
    cust["latitude"] = [COUNTRIES[CO_IDX[c]][10][0][1] for c in ccn] + rng.normal(0, 1.2, n_c)
    cust["longitude"] = [COUNTRIES[CO_IDX[c]][10][0][2] for c in ccn] + rng.normal(0, 1.2, n_c)
    ctx.save(cust, "CRM/Customers/customer_master.parquet", "customers", pk="customer_id", fks={"country_id": "countries.country_id"}, target=20000, system="SALESFORCE")
    erp_c = cust[["customer_id", "erp_sold_to", "customer_name", "country_id", "credit_limit_usd"]].copy()
    cf = rng.choice(n_c, 120, replace=False)
    erp_c.loc[cf, "country_id"] = rng.choice(cc, 120)
    erp_c.loc[cf[:60], "customer_name"] = erp_c.loc[cf[:60], "customer_name"].str.upper().str.replace(" #", " NO.")
    ctx.save(erp_c.rename(columns={"customer_id": "customer_ref"}), "ERP/Finance/AR/erp_customer_master.parquet", "erp_customers", pk="erp_sold_to", system="SAP_S4")
    m = erp_c.loc[cf].country_id.values != cust.loc[cf].country_id.values
    ctx.anom("erp_customers", erp_c.erp_sold_to.values[cf][m], "Cross-system inconsistency", "Conflicting customer information", "Low",
             cust.country_id.values[cf][m], erp_c.country_id.values[cf][m], "CRM and ERP customer masters maintained separately", "Cross-system record matching", "Align ERP country to CRM golden record",
             related=cust.customer_id.values[cf][m], process="Customer master", family="Data_Inconsistencies")
    # employees
    n_e = 75000
    fw = fac.floor_area_m2.values * np.where(fac.facility_type == "Manufacturing", 1.0, np.where(fac.facility_type == "Office", 2.2, 0.35)); fw = fw / fw.sum()
    ef = fac.iloc[rng.choice(len(fac), n_e, p=fw)]
    jc = np.where(ef.facility_type.values == "Manufacturing", rng.choice(["Production Operator", "Technician", "Engineer", "Supervisor", "Administrative", "Manager"], n_e, p=[.55, .15, .1, .08, .07, .05]),
                  rng.choice(["Administrative", "Sales", "Engineer", "Manager", "Logistics Operative", "IT Specialist"], n_e, p=[.3, .2, .1, .12, .2, .08]))
    hire = pd.to_datetime(rng.choice(pd.date_range("1995-01-01", "2026-11-30"), n_e, p=None))
    emp = pd.DataFrame(dict(employee_synthetic_id=ids("EMP-", n_e, 6), hr_system_id=np.char.add("W", rng.choice(10 ** 7, n_e, replace=False).astype(str)),
                            facility_id=ef.facility_id.values, legal_entity_id=ef.legal_entity_id.values,
                            department_id=[f"DEP-{le[3:]}-{k:02d}" for le, k in zip(ef.legal_entity_id.values, rng.integers(0, 12, n_e))],
                            job_category=jc, employment_type=rng.choice(["Full-time", "Part-time", "Contractor"], n_e, p=[.86, .07, .07]),
                            hire_date=hire, termination_date=pd.NaT, remote_eligible=np.isin(jc, ["Administrative", "Sales", "Engineer", "Manager", "IT Specialist"]),
                            fte=np.where(rng.random(n_e) < 0.07, 0.6, 1.0), grade_band=rng.choice(["B1", "B2", "B3", "B4", "B5"], n_e, p=[.35, .3, .2, .1, .05]), synthetic_flag=True))
    t = rng.random(n_e) < 0.22
    emp.loc[t, "termination_date"] = pd.to_datetime(rng.choice(pd.date_range("2022-01-15", "2026-12-15"), t.sum()))
    emp.loc[emp.termination_date < emp.hire_date, "termination_date"] = pd.NaT
    emp["employment_status"] = np.where(emp.termination_date.notna(), "Terminated", "Active")
    ctx.save(emp, "HRMS/employee_master.parquet", "employees", pk="employee_synthetic_id", fks={"facility_id": "facilities.facility_id", "department_id": "departments.department_id"}, target=75000, system="WORKDAY_LIKE")
    coa = []
    for code, nm, typ in [("100100", "Cash at bank", "Asset"), ("110000", "Trade receivables", "Asset"), ("120000", "Raw material inventory", "Asset"), ("121000", "WIP inventory", "Asset"),
                          ("122000", "Finished goods", "Asset"), ("150000", "Plant & machinery", "Asset"), ("159000", "Accumulated depreciation", "Asset"), ("165000", "Intercompany receivable", "Asset"),
                          ("175000", "Input VAT", "Asset"), ("200000", "Trade payables", "Liability"), ("205000", "GR/IR clearing", "Liability"), ("210000", "Accrued expenses", "Liability"),
                          ("215000", "Output VAT", "Liability"), ("220000", "Payroll liabilities", "Liability"), ("225000", "Provisions - environmental", "Liability"), ("265000", "Intercompany payable", "Liability"),
                          ("300000", "Share capital", "Equity"), ("310000", "Retained earnings", "Equity"), ("400000", "Product revenue", "Revenue"), ("401000", "Service revenue", "Revenue"),
                          ("410000", "Sales returns", "Revenue"), ("500000", "Cost of materials", "Expense"), ("510000", "Production variance", "Expense"), ("520000", "Scrap & obsolescence", "Expense"),
                          ("600100", "Electricity expense", "Expense"), ("600200", "Natural gas expense", "Expense"), ("600300", "Fuel - diesel", "Expense"), ("600400", "Steam & heat", "Expense"),
                          ("600500", "Water & wastewater", "Expense"), ("600600", "Waste disposal", "Expense"), ("600700", "Refrigerant & gases", "Expense"), ("600800", "Coal & solid fuels", "Expense"),
                          ("610000", "Freight & logistics", "Expense"), ("620000", "Travel & accommodation", "Expense"), ("630000", "Salaries & wages", "Expense"), ("640000", "Depreciation", "Expense"),
                          ("650000", "Maintenance & repairs", "Expense"), ("660000", "Professional services", "Expense"), ("670000", "IT services", "Expense"), ("680000", "Environmental fines", "Expense"),
                          ("690000", "Carbon credits & certificates", "Expense"), ("700000", "FX gains/losses", "Expense")]:
        coa.append(dict(gl_account=code, gl_account_name=nm, account_type=typ, chart_of_accounts="SYN-COA-01"))
    ctx.save(pd.DataFrame(coa), "ERP/Finance/GL/chart_of_accounts.csv", "chart_of_accounts", pk="gl_account", system="SAP_S4")
