import numpy as np
import pandas as pd
from .core import ids, zipf, rand_dates, DAYS, MONTHS, END, START
from .master import COUNTRIES, CO_IDX
from .erp import fx_lookup, CCY

TARIFF = {"electricity": 0.14, "natural_gas": 0.48, "steam": 62.0, "water": 2.1, "chilled_water": 0.09}  # USD per unit


def hav(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


def season_factor(dates, lat, kind):
    m = pd.DatetimeIndex(dates).month.values
    south = np.asarray(lat) < 0
    mm = np.where(south, (m + 5) % 12 + 1, m)
    heat = np.array([1.6, 1.5, 1.25, 1.0, .7, .45, .35, .38, .6, .95, 1.3, 1.55])[mm - 1]
    cool = np.array([.7, .72, .82, .95, 1.1, 1.3, 1.45, 1.42, 1.18, .95, .78, .7])[mm - 1]
    return heat if kind == "heat" else cool


def gen_energy(ctx):
    rng = ctx.rng("energy")
    fac, met, mes, sup = ctx.get("facilities"), ctx.get("meters"), ctx.get("mes_line_daily"), ctx.get("suppliers")
    fi = fac.set_index("facility_id")
    main = met[(met.meter_level == "main") & met.utility_type.isin(["electricity", "natural_gas", "steam", "chilled_water"])]
    subl = met[(met.meter_level == "sub") & (met.utility_type == "electricity") & met.linked_entity_id.notna()].head(60)
    line_day = mes.groupby(["facility_id", "production_date"]).energy_kwh.sum()
    recs = []
    for _, m in pd.concat([main, subl]).iterrows():
        f = fi.loc[m.facility_id]
        alive = (DAYS >= f.commissioning_date) & (pd.isna(f.divestment_date) | (DAYS <= f.divestment_date))
        d = DAYS[alive]
        n = len(d)
        wk = np.array([1, 1, 1, 1, .97, .6, .45])[d.dayofweek]
        if m.meter_level == "sub":
            v = mes[mes.production_line_id == m.linked_entity_id].set_index("production_date").energy_kwh.reindex(d).fillna(0).values * rng.normal(1.0, 0.01, n)
        elif f.facility_type == "Manufacturing":
            base = line_day.reindex(pd.MultiIndex.from_arrays([np.full(n, m.facility_id), d])).fillna(0).values
            hvac = f.floor_area_m2 * 0.05 * season_factor(d, f.latitude, "cool")
            elec = base * 1.22 + hvac
            v = {"electricity": elec, "natural_gas": elec * 0.075 * season_factor(d, f.latitude, "heat") * f.energy_intensity_index,
                 "steam": elec * 0.00035, "chilled_water": hvac}[m.utility_type] * rng.normal(1, 0.03, n)
        else:
            k = 0.32 if f.facility_type == "Office" else 0.14
            ren = 1 - 0.015 * (d.year - 2022)
            v = f.floor_area_m2 * k * wk * season_factor(d, f.latitude, "cool") * ren * rng.normal(1, 0.05, n)
            if m.utility_type == "chilled_water":
                v = v * 0.3
        shut = (d >= f.temporary_shutdown_start) & (d <= f.temporary_shutdown_end) if pd.notna(f.temporary_shutdown_start) else np.zeros(n, bool)
        v = np.where(shut, v * 0.08, v)
        if m.unit == "MWh":
            v = v / 1000
        recs.append(pd.DataFrame(dict(meter_id=m.meter_id, facility_id=m.facility_id, utility_type=m.utility_type, reading_date=d, consumption=np.round(np.clip(v, 0, None), 4 if m.unit == "MWh" else 2), unit=m.unit)))
    en = pd.concat(recs, ignore_index=True)
    en.insert(0, "reading_id", ids("ENR-", len(en), 8))
    en["reading_quality"] = np.where(rng.random(len(en)) < 0.03, "E", "A")
    en["cumulative_register"] = en.groupby("meter_id").consumption.cumsum().round(2) + 100000
    clean = en.copy()
    N = len(en)
    sp = rng.choice(N, int(N * 0.002), replace=False)
    e = en.consumption.values[sp].copy(); en.loc[sp, "consumption"] = np.round(e * rng.uniform(3, 8, len(sp)), 2)
    ctx.anom("energy_daily", en.reading_id.values[sp], "Operational", "Abnormal energy consumption spike", "Medium", e, en.consumption.values[sp], "Meter pulse error or genuine process upset",
             "Z-score vs 28-day rolling median", "Replace with interpolated value if metering fault confirmed", ghg="Scope 1/2", process="Energy management", family="Operational_Anomalies")
    # drift on 6 meters
    dm = rng.choice(en.meter_id.unique(), 6, replace=False)
    for k, mid in enumerate(dm):
        idx = en.index[(en.meter_id == mid) & (en.reading_date >= pd.Timestamp(f"{2023 + k % 3}-03-01")) & (en.reading_date < pd.Timestamp(f"{2023 + k % 3}-06-01"))]
        e = en.loc[idx, "consumption"].values.copy()
        en.loc[idx, "consumption"] = np.round(e * (1 + np.linspace(0, 0.35, len(idx))), 2)
        ctx.anom("energy_daily", en.reading_id.values[idx], "Sensor fault", "Sensor drift", "Medium", e, en.loc[idx, "consumption"].values, "CT clamp calibration drift",
                 "Divergence vs utility invoice and peer meters (temporal)", "Recalibrate; restate using invoice", related=mid, family="Operational_Anomalies", ghg="Scope 2")
    # unit error: kWh values on MWh meters
    um = en[en.unit == "MWh"].meter_id.unique()[:4]
    for mid in um:
        idx = en.index[(en.meter_id == mid) & (en.reading_date.dt.to_period("M") == pd.Period("2024-09"))]
        e = en.loc[idx, "consumption"].values.copy(); en.loc[idx, "consumption"] = np.round(e * 1000, 2)
        ctx.anom("energy_daily", en.reading_id.values[idx], "Unit conversion", "kWh versus MWh", "High", e, en.loc[idx, "consumption"].values, "Gateway firmware update changed register scaling",
                 "Magnitude check vs history (x1000)", "Divide by 1000", related=mid, family="Unit_Errors", ghg="Scope 2")
    taken = set(pd.concat(ctx.anoms).source_record_id)
    miss = rng.choice(np.where(~en.reading_id.isin(taken).values)[0], int(N * 0.004), replace=False)
    ctx.anom("meters", en.meter_id.values[miss], "Missing data", "Missing machine/meter readings", "Low", en.consumption.values[miss], "MISSING", "Gateway offline",
             "Gap detection in daily series", "Interpolate from neighbours / invoice", related=en.reading_date.dt.strftime("%Y-%m-%d").values[miss], family="Operational_Anomalies")
    dup = rng.choice(np.setdiff1d(np.arange(N), miss), int(N * 0.002), replace=False)
    en = pd.concat([en.drop(index=miss), en.iloc[dup]], ignore_index=True)
    ctx.anom("energy_daily", en.reading_id.values[-len(dup):], "Duplicate record", "Duplicated readings", "Low", "single reading", "duplicate row", "Re-sent batch from data logger",
             "PK duplicate check", "Drop duplicate", family="Operational_Anomalies")
    ctx.lineage(en, "EMS", "SynthEnergy EMS", "EMSDB", "METER_DAILY", "Energy Management", en.reading_id.str.replace("ENR-", "R").values, ts_col="reading_date")
    ctx.save(en, "Energy/meter_daily_consumption.parquet", "energy_daily", pk="reading_id", fks={"meter_id": "meters.meter_id", "facility_id": "facilities.facility_id"}, target=5000000, system="EMS")
    # utility invoices from clean monthly sums
    clean["period"] = clean.reading_date.dt.to_period("M")
    mon = clean.groupby(["meter_id", "facility_id", "utility_type", "unit", "period"]).agg(consumption=("consumption", "sum"), days=("consumption", "size")).reset_index()
    # water monthly (from MES process water + domestic)
    wm = met[(met.meter_level == "main") & (met.utility_type == "water")]
    pw = mes.assign(period=mes.production_date.dt.to_period("M")).groupby(["facility_id", "period"]).process_water_m3.sum()
    wrows = []
    for _, m in wm.iterrows():
        f = fi.loc[m.facility_id]
        ps = MONTHS[MONTHS >= f.commissioning_date.to_period("M")]
        if pd.notna(f.divestment_date):
            ps = ps[ps <= f.divestment_date.to_period("M")]
        dom = f.floor_area_m2 * (0.012 if f.facility_type == "Office" else 0.004) * rng.normal(1, 0.06, len(ps))
        proc = pw.reindex(pd.MultiIndex.from_arrays([np.full(len(ps), m.facility_id), ps])).fillna(0).values * 1.3
        wrows.append(pd.DataFrame(dict(meter_id=m.meter_id, facility_id=m.facility_id, utility_type="water", unit="m3", period=ps, consumption=np.round(dom + proc, 2), days=ps.days_in_month)))
    mon = pd.concat([mon, pd.concat(wrows)], ignore_index=True)
    util_sup = sup[sup.supplier_category == "Utilities"]
    us_by_c = util_sup.groupby("country_id").supplier_id.apply(np.array).to_dict()
    cty = fi.loc[mon.facility_id, "country_id"].values
    acct = met.set_index("meter_id").utility_account_no
    msup = {mid: (us_by_c.get(c, util_sup.supplier_id.values)[hash(mid) % len(us_by_c.get(c, util_sup.supplier_id.values))]) for mid, c in zip(mon.meter_id.unique(), pd.Series(cty).groupby(mon.meter_id.values).first().reindex(mon.meter_id.unique()).values)}
    nI = len(mon)
    ps = mon.period.dt.start_time; pe = mon.period.dt.end_time.dt.normalize()
    q = np.round(mon.consumption.values * rng.normal(1, 0.003, nI), 3 if False else 2)
    ccy = np.array([CCY[c] for c in cty])
    yr = mon.period.dt.year.values
    tf = np.array([TARIFF[u] for u in mon.utility_type]) * np.where(mon.unit.values == "MWh", 1000, 1) * np.where(yr == 2022, 1.35, 1 + 0.03 * (yr - 2023)) * rng.lognormal(0, 0.1, nI)
    rate = fx_lookup(ctx, mon.period.astype(str), ccy)
    ui = pd.DataFrame(dict(utility_invoice_id=ids("UINV-", nI, 7), invoice_number=np.char.add("BILL-", rng.choice(10 ** 9, nI, replace=False).astype(str)),
                           utility_supplier_id=[msup[m] for m in mon.meter_id], customer_account_no=acct.reindex(mon.meter_id).values, facility_id=mon.facility_id.values,
                           meter_id=mon.meter_id.values, utility_type=mon.utility_type.values, billing_period_start=ps.values, billing_period_end=pe.values,
                           invoice_date=(pe + pd.to_timedelta(rng.integers(3, 15, nI), "D")).values, consumption=q, unit=mon.unit.values,
                           tariff_per_unit=np.round(tf / rate, 5), currency=ccy))
    ui["previous_reading"] = np.round(ui.groupby("meter_id").consumption.cumsum() - ui.consumption + 250000, 2)
    ui["current_reading"] = np.round(ui.previous_reading + ui.consumption, 2)
    ui["energy_charge"] = np.round(ui.consumption * ui.tariff_per_unit, 2)
    ui["network_charge"] = np.round(ui.energy_charge * rng.uniform(0.12, 0.3, nI), 2)
    ui["taxes"] = np.round((ui.energy_charge + ui.network_charge) * rng.choice([0.05, 0.1, 0.19, 0.2], nI), 2)
    ui["total_payable"] = ui.energy_charge + ui.network_charge + ui.taxes
    ui["green_tariff"] = (ui.utility_type == "electricity") & (rng.random(nI) < np.clip(0.04 + 0.08 * (yr - 2022), 0, 0.5))
    ui["supplier_disclosed_ef_kg_per_kwh"] = np.where(ui.green_tariff, 0.0, np.where(ui.utility_type == "electricity", np.round(np.array([COUNTRIES[CO_IDX[c]][8] for c in cty]) * rng.uniform(0.75, 1.25, nI), 3), np.nan))
    ui["true_consumption"] = ui.consumption
    k = rng.choice(nI, int(nI * 0.03), replace=False)
    e = ui.consumption.values[k].copy(); ui.loc[k, "consumption"] = np.round(e * rng.choice([0.8, 1.12, 1.25, 1.3], len(k)), 2)
    ui.loc[k, "current_reading"] = ui.previous_reading.values[k] + ui.consumption.values[k]
    ctx.anom("utility_invoices", ui.utility_invoice_id.values[k], "Cross-system inconsistency", "IoT/meter electricity readings differ from utility invoice", "High", e, ui.consumption.values[k],
             "Estimated billing by utility", "Reconcile invoice vs meter monthly sum (>2%)", "Use metered actuals; request re-bill", related=ui.meter_id.values[k], ghg="Scope 2", family="Data_Inconsistencies")
    el = np.where((ui.utility_type == "electricity") & (ui.unit == "kWh"))[0]
    k2 = rng.choice(np.setdiff1d(el, k), int(nI * 0.008), replace=False)
    e = ui.consumption.values[k2].copy(); ui.loc[k2, "consumption"] = np.round(e / 1000, 3)
    ctx.anom("utility_invoices", ui.utility_invoice_id.values[k2], "Unit conversion", "kWh versus MWh", "High", e, ui.consumption.values[k2], "Invoice template shows MWh but unit field kWh",
             "Magnitude check vs prior months", "Multiply by 1000", ghg="Scope 2", impact=e * 0.4, family="Unit_Errors")
    k3 = rng.choice(np.setdiff1d(np.arange(nI), np.r_[k, k2]), int(nI * 0.008), replace=False)
    e = ui.billing_period_start.values[k3].copy(); ui.loc[k3, "billing_period_start"] = pd.to_datetime(e) - pd.Timedelta(days=12)
    ctx.anom("utility_invoices", ui.utility_invoice_id.values[k3], "Temporal", "Overlapping utility billing periods", "Medium", pd.to_datetime(e).date, pd.to_datetime(ui.billing_period_start.values[k3]).date,
             "Utility re-based meter read cycle", "Period overlap check per meter", "Pro-rate overlapping days", ghg="Scope 2", family="Data_Inconsistencies")
    k4 = rng.choice(np.setdiff1d(np.arange(nI), np.r_[k, k2, k3]), int(nI * 0.005), replace=False)
    ctx.anom("meters", ui.meter_id.values[k4], "Missing data", "Missing months of energy consumption", "High", ui.consumption.values[k4], "MISSING INVOICE", "Invoice never received / not posted",
             "Completeness check meter x month", "Accrue from meter data", related=ui.billing_period_start.astype(str).values[k4], ghg="Scope 2", impact=ui.consumption.values[k4] * 0.4, family="Calculation_Errors")
    dupi = rng.choice(np.setdiff1d(np.arange(nI), k4), int(nI * 0.004), replace=False)
    d = ui.iloc[dupi].copy(); d["utility_invoice_id"] = ids("UINV-", len(d), 7, start=nI + 1)
    ui = pd.concat([ui.drop(index=k4), d], ignore_index=True)
    ctx.anom("utility_invoices", d.utility_invoice_id.values, "Duplicate record", "Duplicate invoices", "High", "single", "duplicate", "Paper and e-bill both captured", "Duplicate invoice number check",
             "Remove duplicate", related=ui.utility_invoice_id.values[dupi] if False else d.invoice_number.values, ghg="Scope 2 (double counting)", family="Data_Inconsistencies")
    truth = ui.pop("true_consumption")
    ctx.lineage(ui, "SAP_S4", "IS-U Invoice Capture", "S4PRD", "UTIL_INV", "Energy Management", ui.invoice_number.values, ts_col="invoice_date")
    ctx.save(ui, "ERP/Utilities/utility_invoices.parquet", "utility_invoices", pk="utility_invoice_id", fks={"facility_id": "facilities.facility_id", "meter_id": "meters.meter_id", "utility_supplier_id": "suppliers.supplier_id"}, target=100000, system="SAP_S4")
    # fuel purchases (diesel, coal, lpg)
    assets = ctx.get("assets")
    fa = assets[assets.fuel_type.isin(["diesel", "coal", "lpg"])].groupby(["facility_id", "fuel_type"]).rated_power_kw.sum().reset_index()
    fr = fa.loc[fa.index.repeat(len(MONTHS))].reset_index(drop=True)
    fr["period"] = np.tile(MONTHS, len(fa))
    unit = fr.fuel_type.map({"diesel": "L", "coal": "t", "lpg": "kg"})
    kwh = fr.rated_power_kw * np.where(fr.fuel_type == "coal", 420, 22) * rng.lognormal(0, 0.25, len(fr))
    fr["quantity"] = np.round(kwh / np.where(fr.fuel_type == "coal", 7600, np.where(fr.fuel_type == "diesel", 10, 12.8)) * np.where(fr.fuel_type == "coal", 1, 1), 3)
    fr["unit"] = unit
    fr["facility_country"] = fi.loc[fr.facility_id, "country_id"].values
    us = np.where((fr.facility_country == "US") & (fr.fuel_type == "diesel"))[0]
    fr.loc[us, "unit"] = "gal"; fr.loc[us, "quantity"] = np.round(fr.quantity.values[us] / 3.78541, 3)
    fr.insert(0, "fuel_purchase_id", ids("FUEL-", len(fr), 6))
    fr["delivery_date"] = fr.period.dt.start_time + pd.to_timedelta(rng.integers(0, 27, len(fr)), "D")
    fr["supplier_id"] = sup[sup.supplier_category == "Energy & Fuels"].supplier_id.values[rng.integers(0, (sup.supplier_category == "Energy & Fuels").sum(), len(fr))]
    fr["amount_usd"] = np.round(fr.quantity * np.where(fr.unit == "gal", 3.9, np.where(fr.fuel_type == "coal", 160, np.where(fr.fuel_type == "lpg", 0.9, 1.1))), 2)
    k = rng.choice(us, max(1, len(us) // 20), replace=False)
    e = fr.quantity.values[k].copy(); fr.loc[k, "unit"] = "L"
    ctx.anom("fuel_purchases", fr.fuel_purchase_id.values[k], "Unit conversion", "Litres versus gallons", "High", f"{0} gal", "labelled L", "US supplier delivery note in gallons captured as litres",
             "Price-per-unit plausibility check", "Convert quantity x3.78541 L", corrected=np.round(e * 3.78541, 3), ghg="Scope 1 Stationary", impact=-e * 2.78 * 2.68, family="Unit_Errors")
    fr["period"] = fr.period.astype(str)
    ctx.save(fr.drop(columns=["rated_power_kw", "facility_country"]), "Energy/fuel_purchases.csv", "fuel_purchases", pk="fuel_purchase_id", fks={"facility_id": "facilities.facility_id"}, system="SAP_S4")
    # water daily for manufacturing water meters + monthly withdrawal/discharge
    wmon = mon[mon.utility_type == "water"]
    wd = wmon[wmon.facility_id.isin(fac[fac.facility_type == "Manufacturing"].facility_id)]
    wdd = wd.loc[wd.index.repeat(wd.days)].reset_index(drop=True)
    wdd["reading_date"] = wdd.period.dt.start_time + pd.to_timedelta(wdd.groupby(["meter_id", "period"]).cumcount(), "D")
    wdd["consumption"] = np.round(wdd.consumption / wdd.days * rng.normal(1, 0.08, len(wdd)), 2)
    wdd.insert(0, "water_reading_id", ids("WTR-", len(wdd), 7))
    hw = rng.choice(len(wdd), 150, replace=False)
    e = wdd.consumption.values[hw].copy(); wdd.loc[hw, "consumption"] = np.round(e * rng.uniform(4, 10, 150), 2)
    ctx.save(wdd[["water_reading_id", "meter_id", "facility_id", "reading_date", "consumption", "unit"]], "Water/water_meter_daily.parquet", "water_daily", pk="water_reading_id", fks={"meter_id": "meters.meter_id"}, target=500000, system="EMS")
    ctx.anom("water_daily", wdd.water_reading_id.values[hw], "Operational", "Abnormally high water consumption", "Medium", e, wdd.consumption.values[hw], "Pipe burst / cooling tower overflow",
             "Daily z-score vs facility baseline", "Leak investigation", family="Operational_Anomalies")
    wr = wmon[["facility_id", "period", "consumption"]].copy()
    src = np.where(rng.random(len(wr)) < 0.25, "Groundwater", "Third-party (municipal)")
    wr["withdrawal_source"] = src; wr["withdrawal_m3"] = wr.consumption
    wr["discharge_m3"] = np.round(wr.consumption * rng.uniform(0.55, 0.85, len(wr)), 2)
    wr["consumption_m3"] = np.round(wr.withdrawal_m3 - wr.discharge_m3, 2)
    wr["discharge_destination"] = rng.choice(["Municipal sewer", "Surface water (permitted)", "On-site treatment"], len(wr), p=[.7, .15, .15])
    wr["cod_mg_l"] = np.round(rng.lognormal(4.6, 0.4, len(wr)), 1); wr["bod_mg_l"] = np.round(wr.cod_mg_l * 0.45, 1); wr["tss_mg_l"] = np.round(rng.lognormal(3.3, 0.4, len(wr)), 1); wr["ph"] = np.round(rng.normal(7.2, 0.35, len(wr)), 2)
    wr["water_stress_area"] = fi.loc[wr.facility_id, "country_id"].isin(["IN", "ZA", "AE", "MX", "ES", "AU"]).values
    wr.insert(0, "water_record_id", ids("WREC-", len(wr), 6)); wr["period"] = wr.period.astype(str)
    ctx.save(wr.drop(columns=["consumption"]), "Water/water_withdrawal_discharge_monthly.csv", "water_monthly", pk="water_record_id", fks={"facility_id": "facilities.facility_id"}, system="EHS")
    # waste
    wt_m = ["general_mixed", "metal_scrap", "plastics", "cardboard_paper", "hazardous_solvents", "sludge", "e_waste", "used_oil", "wood"]
    meth = {"general_mixed": ["landfill", "incineration_energy_recovery"], "metal_scrap": ["recycling"], "plastics": ["recycling", "incineration", "landfill"], "cardboard_paper": ["recycling"],
            "hazardous_solvents": ["hazardous_treatment", "incineration"], "sludge": ["landfill", "hazardous_treatment"], "e_waste": ["recycling"], "used_oil": ["recycling", "hazardous_treatment"], "wood": ["recycling", "incineration_energy_recovery"]}
    rows = []
    for _, f in fac.iterrows():
        ws = wt_m if f.facility_type == "Manufacturing" else ["general_mixed", "cardboard_paper"]
        mps = MONTHS[MONTHS >= f.commissioning_date.to_period("M")]
        for w in ws:
            base = f.floor_area_m2 * (0.00035 if f.facility_type == "Manufacturing" else 0.00005) * {"metal_scrap": 3, "general_mixed": 1.5, "cardboard_paper": 1}.get(w, 0.4)
            rows.append(pd.DataFrame(dict(facility_id=f.facility_id, waste_type=w, period=mps, quantity=np.round(base * (1 - 0.02 * (mps.year - 2022)) * rng.lognormal(0, 0.2, len(mps)), 3),
                                          disposal_method=rng.choice(meth[w], len(mps)))))
    ws = pd.concat(rows, ignore_index=True)
    nW = len(ws)
    ws.insert(0, "waste_record_id", ids("WST-", nW, 6))
    ws["unit"] = "t"; ws["hazardous"] = ws.waste_type.isin(["hazardous_solvents", "sludge", "used_oil", "e_waste"])
    wc = sup[sup.supplier_category == "Waste Management"].supplier_id.values
    ws["waste_contractor_id"] = [wc[hash(f) % len(wc)] for f in ws.facility_id]
    ws["manifest_no"] = np.char.add("MAN-", rng.choice(10 ** 8, nW, replace=False).astype(str))
    ws["waste_invoice_id"] = "WINV-" + ws.facility_id.str[4:] + "-" + ws.period.astype(str)
    ws["waste_certificate_id"] = np.where(ws.hazardous | (rng.random(nW) < 0.3), np.char.add("WCERT-", np.arange(nW).astype(str)), None)
    ex = rng.choice(nW, int(nW * 0.005), replace=False)
    e = ws.quantity.values[ex].copy(); ws.loc[ex, "quantity"] = np.round(e * rng.uniform(3, 7, len(ex)), 3)
    ctx.anom("waste_records", ws.waste_record_id.values[ex], "Operational", "Excessive waste", "Medium", e, ws.quantity.values[ex], "Batch rejection disposal not segregated", "Monthly waste vs production ratio",
             "Verify with manifest", ghg="Scope 3 Cat 5", family="Operational_Anomalies")
    kg = rng.choice(np.setdiff1d(np.arange(nW), ex), int(nW * 0.004), replace=False)
    e = ws.quantity.values[kg].copy(); ws.loc[kg, "quantity"] = np.round(e * 1000, 1)
    ctx.anom("waste_records", ws.waste_record_id.values[kg], "Unit conversion", "Kilograms versus metric tonnes", "High", e, ws.quantity.values[kg], "Contractor portal reports kg", "Magnitude check",
             "Divide by 1000", ghg="Scope 3 Cat 5", family="Unit_Errors")
    ws["period"] = ws.period.astype(str)
    ctx.lineage(ws, "EHS", "SynthEHS Waste", "EHSDB", "WASTE_MANIFEST", "EHS & Sustainability", ws.manifest_no.values)
    ctx.save(ws, "Waste/waste_records.parquet", "waste_records", pk="waste_record_id", fks={"facility_id": "facilities.facility_id", "waste_contractor_id": "suppliers.supplier_id"}, target=250000, system="EHS")
    winv = ws.groupby(["waste_invoice_id", "facility_id", "period", "waste_contractor_id"]).quantity.sum().reset_index()
    winv["amount_usd"] = np.round(winv.quantity * rng.uniform(80, 260, len(winv)), 2)
    ctx.save(winv, "Waste/waste_invoices.csv", "waste_invoices", pk="waste_invoice_id", system="SAP_S4")
    cert = ws[ws.waste_certificate_id.notna()][["waste_certificate_id", "waste_record_id", "facility_id", "waste_type", "quantity", "disposal_method", "period"]].copy()
    mm = rng.choice(len(cert), int(len(cert) * 0.01), replace=False)
    e = cert.disposal_method.values[mm].copy(); cert.iloc[mm, cert.columns.get_loc("disposal_method")] = "recycling"
    mm = mm[e != "recycling"]
    ctx.save(cert, "Waste/waste_disposal_certificates.csv", "waste_certificates", pk="waste_certificate_id", fks={"waste_record_id": "waste_records.waste_record_id"}, system="EHS")
    ctx.anom("waste_certificates", cert.waste_certificate_id.values[mm], "Document inconsistency", "Certificate disposal method contradicts waste record", "Medium", e[np.isin(np.arange(len(e)), np.where(e != "recycling")[0])], "recycling",
             "Contractor certificate template default", "Cross-check certificate vs manifest", "Use manifest disposal method", ghg="Scope 3 Cat 5", family="Document_Anomalies")
    # IoT / SCADA telemetry
    sens = met[met.meter_level != "main"].sample(60, random_state=ctx.seed).reset_index(drop=True)
    t15 = pd.date_range("2025-11-01", "2025-11-14 23:45", freq="15min")
    si = np.repeat(np.arange(60), len(t15)); ti = np.tile(np.arange(len(t15)), 60)
    tt = t15[ti]
    lt = tt
    kind = np.where(np.arange(60) % 4 == 0, "temperature", np.where(np.arange(60) % 4 == 1, "pressure", "power"))[si]
    base = np.where(kind == "temperature", 62, np.where(kind == "pressure", 6.5, 120))
    day = ((lt.hour >= 6) & (lt.hour < 22) & (lt.dayofweek < 5)).astype(float)
    val = base * (0.55 + 0.45 * day) * rng.normal(1, 0.03, len(tt))
    iot = pd.DataFrame(dict(sensor_id=np.char.add("SNS-", sens.meter_id.str[4:].values[si]), meter_id=sens.meter_id.values[si], facility_id=sens.facility_id.values[si], timestamp_utc=tt,
                            measurement_type=kind, value=np.round(val, 3), unit=np.where(kind == "temperature", "degC", np.where(kind == "pressure", "bar", "kW")),
                            device_status="OK", comm_status="ONLINE", calibration_date=sens.last_calibration_date.values[si]))
    iot["ingest_timestamp_utc"] = iot.timestamp_utc + pd.to_timedelta(rng.integers(5, 90, len(iot)), "s")
    iot.insert(0, "telemetry_id", ids("TEL-", len(iot), 8))
    n = len(iot)
    s = rng.choice(n, 120, replace=False); e = iot.value.values[s].copy(); iot.loc[s, "value"] = np.round(e * rng.uniform(4, 12, 120), 3)
    ctx.anom("iot_telemetry", iot.telemetry_id.values[s], "Sensor fault", "Abnormal spikes", "Low", e, iot.value.values[s], "Electrical noise on analogue input", "Spike filter (Hampel)", "Discard reading", family="Operational_Anomalies")
    tf_ = np.where(kind == "temperature")[0]; f2 = tf_[(tt[tf_] >= pd.Timestamp("2025-11-08")) & (iot.sensor_id.values[tf_] == iot.sensor_id.values[tf_][0])]
    e = iot.value.values[f2].copy(); iot.loc[f2, "value"] = np.round(e * 9 / 5 + 32, 2)
    ctx.anom("iot_telemetry", iot.telemetry_id.values[f2], "Unit conversion", "Celsius versus Fahrenheit", "Medium", e, iot.value.values[f2], "PLC replaced with US-configured unit", "Step-change detection", "Convert (F-32)*5/9", family="Unit_Errors")
    dl = rng.choice(n, 400, replace=False); iot.loc[dl, "ingest_timestamp_utc"] = iot.timestamp_utc.values[dl] + pd.to_timedelta(rng.integers(6, 48, 400), "h"); iot.loc[dl, "comm_status"] = "DELAYED"
    ctx.anom("iot_telemetry", iot.telemetry_id.values[dl], "Temporal", "Delayed transmission", "Low", "<5 min latency", "6-48h latency", "Cellular backhaul outage", "Ingest lag check", "Accept with flag", family="Operational_Anomalies")
    off = rng.choice(n, 900, replace=False); iot.loc[off, "comm_status"] = "OFFLINE"; iot.loc[off, "value"] = np.nan; iot.loc[off, "device_status"] = "FAULT"
    ctx.anom("iot_telemetry", iot.telemetry_id.values[off], "Sensor fault", "Faulty sensors / intermittent connectivity", "Low", "value", "NULL", "Intermittent connectivity", "Null + status check", "Interpolate", family="Operational_Anomalies")
    dd = rng.choice(n, 300, replace=False)
    iot = pd.concat([iot, iot.iloc[dd]], ignore_index=True)
    ctx.anom("iot_telemetry", iot.telemetry_id.values[-300:], "Duplicate record", "Duplicated readings", "Low", "single", "duplicate", "MQTT QoS1 redelivery", "PK duplicate", "Drop", family="Operational_Anomalies")
    ctx.save(iot, "Manufacturing/SCADA/scada_telemetry_15min_2025-11.parquet", "iot_telemetry", pk="telemetry_id", fks={"meter_id": "meters.meter_id"}, system="SCADA")
    t5 = pd.date_range("2025-11-03", "2025-11-05 23:55", freq="5min")
    s5 = sens.head(10)
    i5 = pd.DataFrame(dict(sensor_id=np.repeat(np.char.add("SNS-", s5.meter_id.str[4:].values), len(t5)), timestamp_utc=np.tile(t5, 10), value=np.round(rng.normal(100, 8, 10 * len(t5)), 2), unit="kW"))
    ctx.save(i5, "Manufacturing/IoT/iot_power_5min_2025-11.csv", "iot_5min", system="IOT_PLATFORM")


def gen_logistics_hr(ctx):
    rng = ctx.rng("logistics")
    fac, sup, cust, sl = ctx.get("facilities"), ctx.get("suppliers"), ctx.get("customers"), ctx.get("supplier_locations")
    grn, po, mat, dl, prod = ctx.get("goods_receipts"), ctx.get("purchase_orders"), ctx.get("materials"), ctx.get("deliveries"), ctx.get("products")
    fi = fac.set_index("facility_id")
    carriers = sup[sup.supplier_category == "Logistics"].supplier_id.values
    g = grn[grn.material_id.notna()].copy()
    g["kg"] = g.accepted_qty * g.material_id.map(mat.set_index("material_id").weight_kg_per_unit)
    ib = g.groupby(["po_id", "receipt_date", "facility_id"]).agg(kg=("kg", "sum"), grn_id=("grn_id", "first")).reset_index()
    ib["supplier_id"] = ib.po_id.map(po.drop_duplicates("po_id").set_index("po_id").supplier_id)
    ib["incoterm"] = ib.po_id.map(po.drop_duplicates("po_id").set_index("po_id").incoterm)
    loc = sl.drop_duplicates("supplier_id").set_index("supplier_id")
    ib = ib[ib.supplier_id.isin(loc.index)]
    o_lat, o_lon = loc.loc[ib.supplier_id, "latitude"].values, loc.loc[ib.supplier_id, "longitude"].values
    d_lat, d_lon = fi.loc[ib.facility_id, "latitude"].values, fi.loc[ib.facility_id, "longitude"].values
    ob = dl.copy()
    ci = cust.set_index("customer_id")
    ship = pd.concat([
        pd.DataFrame(dict(direction="Inbound", ref_doc=ib.grn_id.values, po_id=ib.po_id.values, delivery_id=None, supplier_id=ib.supplier_id.values, customer_id=None,
                          origin=ib.supplier_id.values, destination=ib.facility_id.values, ship_date=pd.to_datetime(ib.receipt_date.values) - pd.to_timedelta(rng.integers(2, 20, len(ib)), "D"),
                          weight_kg=ib.kg.values, o_lat=o_lat, o_lon=o_lon, d_lat=d_lat, d_lon=d_lon, incoterm=ib.incoterm.values)),
        pd.DataFrame(dict(direction="Outbound", ref_doc=ob.delivery_id.values, po_id=None, delivery_id=ob.delivery_id.values, supplier_id=None, customer_id=ob.customer_id.values,
                          origin=ob.ship_from_facility_id.values, destination=ob.customer_id.values, ship_date=pd.to_datetime(ob.delivery_date.values) - pd.to_timedelta(rng.integers(1, 10, len(ob)), "D"),
                          weight_kg=ob.gross_weight_kg.values, o_lat=fi.loc[ob.ship_from_facility_id, "latitude"].values, o_lon=fi.loc[ob.ship_from_facility_id, "longitude"].values,
                          d_lat=ci.loc[ob.customer_id, "latitude"].values, d_lon=ci.loc[ob.customer_id, "longitude"].values, incoterm=ci.loc[ob.customer_id, "incoterm"].values))], ignore_index=True)
    nS = len(ship)
    gc = hav(ship.o_lat.values, ship.o_lon.values, ship.d_lat.values, ship.d_lon.values)
    mode = np.where(gc < 1200, np.where(rng.random(nS) < 0.1, "Rail", "Road"), np.where(gc < 3500, np.where(rng.random(nS) < 0.25, "Rail", "Road"), np.where(rng.random(nS) < 0.07, "Air", "Sea")))
    mode = np.where((mode == "Road") & (rng.random(nS) < 0.04), "Inland waterway", mode)
    mode = np.where((mode == "Sea") & (rng.random(nS) < 0.15), "Multimodal", mode)
    mode = np.where((mode == "Road") & (ship.weight_kg.values < 300), "Last-mile", mode)
    circ = {"Road": 1.22, "Rail": 1.3, "Sea": 1.55, "Air": 1.08, "Inland waterway": 1.4, "Multimodal": 1.45, "Last-mile": 1.35}
    dist = np.round(np.maximum(gc, 15) * np.array([circ[m] for m in mode]), 1)
    ship.insert(0, "shipment_id", ids("SHP-", nS, 7))
    ship["tms_ref"] = np.char.add("TMS", rng.choice(10 ** 9, nS, replace=False).astype(str))
    ship["mode"] = mode; ship["distance_km"] = dist; ship["distance_unit"] = "km"
    ship["carrier_id"] = carriers[rng.integers(0, len(carriers), nS)]
    ship["load_factor_pct"] = np.round(np.clip(rng.beta(5, 2.2, nS) * 100, 10, 100), 1)
    ship["freight_paid_by"] = np.where(ship.direction == "Inbound", np.where(ship.incoterm.isin(["EXW", "FCA", "FOB"]), "Company", "Supplier"), np.where(ship.incoterm.isin(["EXW", "FCA"]), "Customer", "Company"))
    ship["empty_return_km"] = np.where((ship["mode"] == "Last-mile") | ((ship["mode"] == "Road") & (rng.random(nS) < 0.15)), np.round(dist * rng.uniform(0.5, 1, nS), 1), 0.0)
    ship["ship_date"] = ship.ship_date.clip(lower=START)
    ship["consolidation_id"] = np.where(rng.random(nS) < 0.12, np.char.add("CONS-", rng.integers(1, nS // 6, nS).astype(str)), None)
    dev = rng.choice(nS, int(nS * 0.006), replace=False)
    e = ship.distance_km.values[dev].copy(); ship.loc[dev, "distance_km"] = np.round(e * rng.uniform(1.6, 2.5, len(dev)), 1)
    ctx.anom("shipments", ship.shipment_id.values[dev], "Operational", "Route deviations / unusually high freight emissions", "Medium", e, ship.distance_km.values[dev], "Re-routing via distant hub",
             "Actual vs great-circle distance ratio > 2", "Validate with telematics", ghg="Scope 3 Cat 4/9", family="Operational_Anomalies")
    usm = np.where((ship.carrier_id.str[-1].isin(["3", "7"])) & (ship["mode"] == "Road"))[0][:int(nS * 0.004)]
    e = ship.distance_km.values[usm].copy(); ship.loc[usm, "distance_km"] = np.round(e / 1.60934, 1)
    ctx.anom("shipments", ship.shipment_id.values[usm], "Unit conversion", "Miles versus kilometres", "Medium", e, ship.distance_km.values[usm], "US carrier API returns miles", "Distance vs geodesic check",
             "Multiply by 1.60934", ghg="Scope 3 Cat 4/9", impact=-(e - e / 1.60934) * 0.105, family="Unit_Errors")
    ship["tkm"] = np.round(ship.weight_kg / 1000 * ship.distance_km, 3)
    ctx.lineage(ship, "TMS", "SynthTMS", "TMSDB", "SHIPMENT", "Logistics", ship.tms_ref.values, ts_col="ship_date")
    ctx.save(ship.drop(columns=["o_lat", "o_lon", "d_lat", "d_lon"]), "Logistics/shipments.parquet", "shipments", pk="shipment_id", fks={"carrier_id": "suppliers.carrier_id" if False else "suppliers.supplier_id"}, target=1000000, system="TMS")
    pay = ship[ship.freight_paid_by == "Company"]
    rate = {"Road": 0.11, "Rail": 0.05, "Sea": 0.012, "Air": 2.6, "Inland waterway": 0.04, "Multimodal": 0.03, "Last-mile": 0.9}
    amt = np.round(pay.tkm.values * np.array([rate[m] for m in pay["mode"]]) * rng.lognormal(0, 0.12, len(pay)) + 60, 2)
    fi_ = pd.DataFrame(dict(freight_invoice_id=ids("FINV-", len(pay), 7), shipment_id=pay.shipment_id.values, carrier_id=pay.carrier_id.values,
                            invoice_date=(pay.ship_date + pd.to_timedelta(rng.integers(5, 30, len(pay)), "D")).clip(upper=END).values, amount_usd=amt, billed_distance_km=pay.distance_km.values,
                            billed_weight_kg=np.round(pay.weight_kg.values, 1), mode=pay["mode"].values))
    k = rng.choice(len(fi_), int(len(fi_) * 0.02), replace=False)
    e = fi_.amount_usd.values[k].copy(); fi_.loc[k, "amount_usd"] = np.round(e * rng.uniform(1.15, 1.6, len(k)), 2)
    ctx.save(fi_, "Logistics/freight_invoices.parquet", "freight_invoices", pk="freight_invoice_id", fks={"shipment_id": "shipments.shipment_id", "carrier_id": "suppliers.supplier_id"}, system="SAP_S4")
    ctx.anom("freight_invoices", fi_.freight_invoice_id.values[k], "Amount mismatch", "Freight invoice discrepancies", "Medium", e, fi_.amount_usd.values[k], "Carrier applied surcharge outside rate card",
             "Rate-card audit", "Dispute surcharge", related=fi_.shipment_id.values[k], family="Data_Inconsistencies")
    # fleet fuel monthly
    veh = ctx.get("vehicles")
    vv = veh.loc[veh.index.repeat(len(MONTHS))].reset_index(drop=True); vv["period"] = np.tile(MONTHS, len(veh))
    ps = vv.period.dt.start_time
    vv = vv[(ps >= vv.in_service_date.dt.to_period("M").dt.start_time) & (vv.disposal_date.isna() | (ps <= vv.disposal_date))].reset_index(drop=True)
    km_base = vv.vehicle_type.map({"HGV Rigid": 7000, "HGV Articulated": 10500, "LCV Van": 2600, "Company Car": 1800, "Pickup": 1500, "Yard Tractor": 600})
    vv["distance_km"] = np.round(km_base * np.array([0.9, .93, 1.02, 1.0, 1.04, 1.03, .92, .85, 1.03, 1.06, 1.05, .9])[vv.period.dt.month - 1] * rng.lognormal(0, 0.15, len(vv)), 1)
    vv["fuel_qty"] = np.round(vv.distance_km * vv.rated_consumption_per_100km / 100 * rng.lognormal(0, 0.06, len(vv)), 2)
    vv["fuel_unit"] = np.where(vv.fuel_type == "cng", "kg", "L")
    vv["electricity_kwh"] = np.round(vv.distance_km * vv.rated_kwh_per_100km / 100, 1)
    vv.insert(0, "fleet_fuel_id", ids("FF-", len(vv), 7))
    k = rng.choice(np.where(vv.fuel_qty > 0)[0], int(len(vv) * 0.002), replace=False)
    e = vv.fuel_qty.values[k].copy(); vv.loc[k, "fuel_qty"] = np.round(e * rng.uniform(1.8, 3, len(k)), 2)
    ctx.anom("fleet_fuel", vv.fleet_fuel_id.values[k], "Operational", "Sudden fuel increases", "High", e, vv.fuel_qty.values[k], "Fuel card misuse / siphoning", "L/100km vs rated consumption",
             "Investigate fuel card; restate", ghg="Scope 1 Mobile", impact=(vv.fuel_qty.values[k] - e) * 2.68, family="Operational_Anomalies")
    vv["period"] = vv.period.astype(str)
    out = vv[["fleet_fuel_id", "vehicle_id", "facility_id", "period", "fuel_type", "distance_km", "fuel_qty", "fuel_unit", "electricity_kwh"]]
    ctx.lineage(out, "FLEET_MGMT", "SynthFleet Telematics", "FLEETDB", "FUEL_MONTHLY", "Logistics", out.fleet_fuel_id.str.replace("FF-", "TEL").values)
    ctx.save(out, "Logistics/fleet_fuel_mileage_monthly.parquet", "fleet_fuel", pk="fleet_fuel_id", fks={"vehicle_id": "vehicles.vehicle_id"}, system="FLEET_MGMT")
    # business travel
    emp = ctx.get("employees")
    trav = emp[emp.remote_eligible]
    nT = ctx.n(250000)
    te = trav.iloc[rng.choice(len(trav), nT)]
    dest = fac.iloc[rng.integers(0, len(fac), nT)]
    o = fi.loc[te.facility_id]
    gc = hav(o.latitude.values, o.longitude.values, dest.latitude.values, dest.longitude.values)
    m = np.where(gc < 400, rng.choice(["rail", "car_rental", "taxi"], nT, p=[.5, .35, .15]), np.where(gc < 3700, "air_short_economy", np.where(rng.random(nT) < 0.18, "air_long_business", "air_long_economy")))
    tdate = rand_dates(rng, nT)
    covid = np.where(pd.DatetimeIndex(tdate).year == 2022, 0.7, 1.0)
    bt = pd.DataFrame(dict(trip_id=ids("TRP-", nT, 6), expense_report_id=np.char.add("EXP-", rng.integers(10 ** 6, 10 ** 7, nT).astype(str)), employee_synthetic_id=te.employee_synthetic_id.values,
                           origin_facility_id=te.facility_id.values, destination_city=dest.city.values, destination_country_id=dest.country_id.values, travel_date=tdate,
                           travel_mode=m, distance_km=np.round(np.maximum(gc, 20) * 1.09 * 2, 1), hotel_nights=np.where(gc > 300, rng.integers(1, 6, nT), 0)))
    bt["cost_usd"] = np.round(bt.distance_km * np.where(bt.travel_mode.str.contains("business"), 0.42, 0.12) + bt.hotel_nights * rng.uniform(90, 260, nT), 2)
    bt = bt[rng.random(nT) < covid / 1.0].reset_index(drop=True)
    nd = rng.choice(len(bt), int(len(bt) * 0.05), replace=False); bt.loc[nd, "distance_km"] = np.nan
    ctx.save(bt, "HRMS/business_travel.parquet", "business_travel", pk="trip_id", fks={"employee_synthetic_id": "employees.employee_synthetic_id", "origin_facility_id": "facilities.facility_id"}, target=250000, system="CONCUR_LIKE")
    # commuting, occupancy, workforce, safety
    hc = emp.assign(y=0)
    rows = []
    for y in [2022, 2023, 2024, 2025, 2026]:
        ye = pd.Timestamp(f"{y}-12-31")
        act = emp[(emp.hire_date <= ye) & (emp.termination_date.isna() | (emp.termination_date > ye))]
        g = act.groupby("facility_id").agg(headcount=("employee_synthetic_id", "count"), remote_eligible=("remote_eligible", "sum"), fte=("fte", "sum")).reset_index()
        g["year"] = y
        rows.append(g)
    wf = pd.concat(rows, ignore_index=True)
    wf["female_share_pct"] = np.round(rng.uniform(18, 45, len(wf)), 1)
    wf["survey_response_rate_pct"] = np.round(np.clip(rng.normal(32 + 6 * (wf.year - 2022), 8), 5, 90), 1)
    for mm_, p in [("car_petrol", .32), ("car_diesel", .18), ("car_ev", .04), ("bus", .14), ("rail", .12), ("motorbike", .08), ("bike_walk", .12)]:
        adj = (0.012 * (wf.year - 2022)) if mm_ == "car_ev" else -(0.004 * (wf.year - 2022)) if mm_.startswith("car_") else 0
        wf[f"share_{mm_}"] = np.round(np.clip(p + adj + rng.normal(0, 0.02, len(wf)), 0, 1), 3)
    wf["avg_one_way_km"] = np.round(rng.lognormal(2.6, 0.35, len(wf)), 1)
    wf["avg_remote_days_per_week"] = np.round(np.where(wf.remote_eligible > 0, rng.uniform(0.8, 2.2, len(wf)), 0.1), 2)
    wf["working_days"] = 225
    ctx.save(wf, "HRMS/workforce_and_commuting_survey_annual.csv", "commuting_survey", fks={"facility_id": "facilities.facility_id"}, system="HRMS")
    offs = fac[fac.facility_type == "Office"]
    oc = offs.loc[offs.index.repeat(len(MONTHS)), ["facility_id"]].reset_index(drop=True); oc["period"] = np.tile(MONTHS.astype(str), len(offs))
    oc["avg_occupancy_pct"] = np.round(np.clip(rng.normal(55, 12, len(oc)) + np.where(oc.period.str[:4] == "2022", -15, 0), 5, 100), 1)
    ctx.save(oc, "HRMS/office_occupancy_monthly.csv", "office_occupancy", fks={"facility_id": "facilities.facility_id"}, system="FACILITIES")
    sf = fac.loc[fac.index.repeat(len(MONTHS)), ["facility_id", "facility_type"]].reset_index(drop=True); sf["period"] = np.tile(MONTHS.astype(str), len(fac))
    hcm = wf.set_index(["facility_id", "year"]).headcount
    sf["hours_worked"] = np.round(hcm.reindex(pd.MultiIndex.from_arrays([sf.facility_id, sf.period.str[:4].astype(int)])).fillna(0).values * 150, 0)
    rate = np.where(sf.facility_type == "Manufacturing", 4e-6, 1e-6) * (1 - 0.08 * (sf.period.str[:4].astype(int) - 2022))
    sf["recordable_incidents"] = rng.poisson(sf.hours_worked * rate)
    sf["lost_time_injuries"] = rng.binomial(sf.recordable_incidents, 0.3)
    sf["safety_training_hours"] = np.round(sf.hours_worked * rng.uniform(0.004, 0.01, len(sf)), 0)
    ctx.save(sf.drop(columns=["facility_type"]), "HRMS/safety_monthly.csv", "safety_monthly", fks={"facility_id": "facilities.facility_id"}, system="EHS")
    nt = 4000
    ctx.save(pd.DataFrame(dict(training_record_id=ids("TRN-", nt, 5), facility_id=fac.facility_id.values[rng.integers(0, len(fac), nt)],
                               programme=rng.choice(["Sustainability Fundamentals", "GHG Accounting 101", "Energy Champions", "Anti-Corruption", "Lockout/Tagout", "Ethics & Compliance", "Hazmat Handling"], nt),
                               session_date=rand_dates(rng, nt), participants=rng.integers(5, 120, nt), hours_per_participant=rng.choice([1, 2, 4, 8], nt))),
             "HRMS/training_programmes.csv", "training", pk="training_record_id", system="LMS")
