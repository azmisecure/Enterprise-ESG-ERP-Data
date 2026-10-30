import numpy as np
import pandas as pd
from .core import ids, MONTHS, YEARS
from .ef import apply_ef, GWP, REGIONS
from .master import COUNTRIES, CO_IDX, PRODUCT_FAMILIES

CAT = {1: "Purchased goods and services", 2: "Capital goods", 3: "Fuel- and energy-related activities", 4: "Upstream transportation and distribution",
       5: "Waste generated in operations", 6: "Business travel", 7: "Employee commuting", 8: "Upstream leased assets", 9: "Downstream transportation and distribution",
       10: "Processing of sold products", 11: "Use of sold products", 12: "End-of-life treatment of sold products", 13: "Downstream leased assets", 14: "Franchises", 15: "Investments"}
REG = {c[0]: REGIONS[c[2]] for c in COUNTRIES}
MODE_EF = {"Road": "road_hgv", "Rail": "rail_freight", "Sea": "sea_container", "Air": "air_freight_long", "Inland waterway": "inland_waterway", "Multimodal": "sea_container", "Last-mile": "last_mile_van"}


def A(scope, cat, n, **kw):
    d = pd.DataFrame(kw, index=range(n))
    d["scope"] = scope
    d["category_id"] = f"S3-C{cat:02d}" if scope == "Scope 3" else cat
    d["category_name"] = CAT[cat] if scope == "Scope 3" else cat
    return d


def gen_ghg(ctx):
    rng = ctx.rng("ghg")
    fac = ctx.get("facilities"); fi = fac.set_index("facility_id")
    yr = lambda s: pd.to_datetime(s).dt.year if hasattr(s, "dt") or isinstance(s, pd.Series) else pd.DatetimeIndex(s).year
    acts = []
    # --- Scope 1 stationary: natural gas from utility invoices
    ui = ctx.get("utility_invoices")
    g = ui[ui.utility_type == "natural_gas"]
    d = A("Scope 1", "Stationary combustion", len(g), facility_id=g.facility_id.values, equipment_id=g.meter_id.values, activity_type="natural_gas", activity_quantity=g.consumption.values,
          activity_unit="m3", original_quantity=g.consumption.values, original_unit=g.unit.values, period_start=g.billing_period_start.values, period_end=g.billing_period_end.values,
          calculation_method="Fuel-based", source_dataset="utility_invoices", source_record_id=g.utility_invoice_id.values, source_system="SAP_S4")
    d["ef_key"] = "stationary_combustion|natural_gas|m3|" + fi.loc[g.facility_id, "country_id"].values
    acts.append(d)
    fu = ctx.get("fuel_purchases")
    qty = np.where(fu.unit == "gal", fu.quantity * 3.78541, fu.quantity)
    unit = np.where(fu.unit == "gal", "L", fu.unit)
    ps = pd.PeriodIndex(fu.period, freq="M")
    d = A("Scope 1", "Stationary combustion", len(fu), facility_id=fu.facility_id.values, equipment_id=None, activity_type=fu.fuel_type.values, activity_quantity=np.round(qty, 3), activity_unit=unit,
          original_quantity=fu.quantity.values, original_unit=fu.unit.values, period_start=ps.start_time, period_end=ps.end_time.normalize(), calculation_method="Fuel-based",
          source_dataset="fuel_purchases", source_record_id=fu.fuel_purchase_id.values, source_system="SAP_S4")
    d["ef_key"] = "stationary_combustion|" + fu.fuel_type.values + "|" + unit + "|" + fi.loc[fu.facility_id, "country_id"].values
    acts.append(d)
    # mobile
    ff = ctx.get("fleet_fuel"); ff = ff[ff.fuel_qty > 0]
    ft = ff.fuel_type.replace({"hybrid": "petrol"}).values
    ps = pd.PeriodIndex(ff.period, freq="M")
    d = A("Scope 1", "Mobile combustion", len(ff), facility_id=ff.facility_id.values, vehicle_id=ff.vehicle_id.values, activity_type=ft, activity_quantity=ff.fuel_qty.values, activity_unit=ff.fuel_unit.values,
          original_quantity=ff.fuel_qty.values, original_unit=ff.fuel_unit.values, period_start=ps.start_time, period_end=ps.end_time.normalize(), calculation_method="Fuel-based",
          source_dataset="fleet_fuel", source_record_id=ff.fleet_fuel_id.values, source_system="FLEET_MGMT")
    d["ef_key"] = "mobile_combustion|" + ft + "|" + ff.fuel_unit.values + "|" + fi.loc[ff.facility_id, "country_id"].values
    acts.append(d)
    # process emissions
    po = ctx.get("production_orders"); prod = ctx.get("products").set_index("product_id")
    pfam = prod.product_family.reindex(po.product_id).values
    pmap = {"Portland Cement CEM I": ("cement_clinker_calcination", 0.92), "Blended Cement CEM II": ("cement_clinker_calcination", 0.68), "Steel Section": ("steel_eaf", 1), "Aluminium Extrusion": ("aluminium_anode", 0.35),
            "Specialty Resin": ("titanium_dioxide_chloride", 0.0004), "Industrial Coating": ("titanium_dioxide_chloride", 0.00025)}
    sel = np.isin(pfam, list(pmap))
    pp = po[sel].assign(proc=[pmap[f][0] for f in pfam[sel]], t=[pmap[f][1] for f in pfam[sel]] * po[sel].actual_qty.values, period=pd.to_datetime(po[sel].planned_start).dt.to_period("M"))
    pg = pp.groupby(["facility_id", "proc", "period"]).agg(t=("t", "sum"), ref=("production_order_id", "first")).reset_index()
    d = A("Scope 1", "Process emissions", len(pg), facility_id=pg.facility_id.values, activity_type=pg.proc.values, activity_quantity=np.round(pg.t.values, 3), activity_unit="t", original_quantity=np.round(pg.t.values, 3),
          original_unit="t", period_start=pg.period.dt.start_time.values, period_end=pg.period.dt.end_time.dt.normalize().values, calculation_method="Mass balance (clinker / product output)",
          source_dataset="production_orders", source_record_id=pg.ref.values, source_system="SAP_S4", assumptions="Clinker/feedstock ratio from synthetic product spec")
    d["ef_key"] = "process_emissions|" + pg.proc.values + "|t|GLOBAL"
    acts.append(d)
    # --- Scope 2
    for ut, key, unit_ in [("electricity", "grid_location|electricity|kWh|", "kWh"), ("steam", "purchased_steam|steam|MWh|", "MWh"), ("chilled_water", "purchased_cooling|chilled_water|kWh|", "kWh")]:
        e = ui[ui.utility_type == ut]
        q = np.where((e.unit == "MWh") & (unit_ == "kWh"), e.consumption * 1000, e.consumption)
        d = A("Scope 2", {"electricity": "Purchased electricity", "steam": "Purchased steam", "chilled_water": "Purchased cooling"}[ut], len(e), facility_id=e.facility_id.values, equipment_id=e.meter_id.values,
              activity_type=ut, activity_quantity=np.round(q, 3), activity_unit=unit_, original_quantity=e.consumption.values, original_unit=e.unit.values,
              period_start=e.billing_period_start.values, period_end=e.billing_period_end.values, calculation_method="Location-based", scope2_method="location-based",
              source_dataset="utility_invoices", source_record_id=e.utility_invoice_id.values, source_system="SAP_S4", supplier_id=e.utility_supplier_id.values)
        d["ef_key"] = key + fi.loc[e.facility_id, "country_id"].values
        acts.append(d)
    # --- Scope 3
    # Cat 1: GRN-based materials + spend-based services
    pol = ctx.get("po_lines"); pos = ctx.get("purchase_orders").drop_duplicates("po_id").set_index("po_id")
    grn = ctx.get("goods_receipts"); mat = ctx.get("materials").set_index("material_id"); sup = ctx.get("suppliers").set_index("supplier_id")
    acc = grn.groupby("po_line_id").agg(q=("accepted_qty", "sum"), dt=("receipt_date", "max"))
    ml = pol[pol.material_id.notna()].join(acc, on="po_line_id").dropna(subset=["q"])
    sid = pos.supplier_id.reindex(ml.po_id).values
    reg = pd.Series(sup.country_id.reindex(sid).values).map(REG).fillna("GLOBAL").values
    fam = mat.material_family.reindex(ml.material_id).values; mu = mat.base_unit.reindex(ml.material_id).values
    y = pd.DatetimeIndex(ml.dt).year.values
    maturity = sup.data_maturity.reindex(sid).values
    sup_spec = np.isin(maturity, ["Leading", "Established"]) & (rng.random(len(ml)) < 0.15 + 0.12 * (y - 2022))
    spend = (rng.random(len(ml)) < np.clip(0.45 - 0.09 * (y - 2022), 0.05, 1)) & ~sup_spec
    from .erp import fx_lookup
    usd = ml.q.values * ml.unit_price.values * fx_lookup(ctx, pd.DatetimeIndex(ml.dt).to_period("M").astype(str), ml.currency.values)
    grp = mat.material_group.reindex(ml.material_id).values
    from .master import GROUP_TO_CAT
    d = A("Scope 3", 1, len(ml), facility_id=pos.facility_id.reindex(ml.po_id).values, supplier_id=sid, activity_type=fam,
          activity_quantity=np.where(spend, np.round(usd, 2), ml.q.values), activity_unit=np.where(spend, "USD", mu), original_quantity=ml.q.values, original_unit=mu,
          period_start=pd.DatetimeIndex(ml.dt).to_period("M").start_time, period_end=pd.DatetimeIndex(ml.dt).to_period("M").end_time.normalize(),
          calculation_method=np.where(sup_spec, "Supplier-specific", np.where(spend, "Spend-based", "Average-data")), source_dataset="po_lines", source_record_id=ml.po_line_id.values, source_system="SAP_S4")
    d["ef_key"] = np.where(sup_spec, "supplier_specific_material|" + fam + "|" + pd.Series(sid).fillna("").values, np.where(spend, "spend_eeio|" + pd.Series(grp).map(GROUP_TO_CAT).fillna("Components").values + "|USD|" + reg, "purchased_material|" + fam + "|" + mu + "|" + reg))
    acts.append(d)
    sl = pol[pol.material_id.isna()]
    sid = pos.supplier_id.reindex(sl.po_id).values
    dt = pos.po_date.reindex(sl.po_id).values
    usd = sl.net_amount.values * fx_lookup(ctx, pd.DatetimeIndex(dt).to_period("M").astype(str), sl.currency.values)
    capex = sl.service_category.values == "Capital Equipment"
    reg = pd.Series(sup.country_id.reindex(sid).values).map(REG).fillna("GLOBAL").values
    d = A("Scope 3", 1, len(sl), facility_id=pos.facility_id.reindex(sl.po_id).values, supplier_id=sid, activity_type=sl.service_category.values, activity_quantity=np.round(usd, 2), activity_unit="USD",
          original_quantity=sl.net_amount.values, original_unit=sl.currency.values, period_start=pd.DatetimeIndex(dt).to_period("M").start_time, period_end=pd.DatetimeIndex(dt).to_period("M").end_time.normalize(),
          calculation_method="Spend-based", source_dataset="po_lines", source_record_id=sl.po_line_id.values, source_system="SAP_S4")
    d.loc[capex, ["category_id", "category_name"]] = ["S3-C02", CAT[2]]
    d["ef_key"] = "spend_eeio|" + sl.service_category.values + "|USD|" + reg
    acts.append(d)
    ast = ctx.get("assets"); na = ast[(ast.acquisition_date >= "2022-01-01") & (ast.acquisition_date <= "2026-12-31")]
    ps = pd.DatetimeIndex(na.acquisition_date).to_period("M")
    d = A("Scope 3", 2, len(na), facility_id=na.facility_id.values, equipment_id=na.asset_id.values, activity_type=na.asset_type.values, activity_quantity=na.acquisition_cost_usd.values, activity_unit="USD",
          original_quantity=na.acquisition_cost_usd.values, original_unit="USD", period_start=ps.start_time, period_end=ps.end_time.normalize(), calculation_method="Spend-based",
          source_dataset="assets", source_record_id=na.asset_id.values, source_system="SAP_S4", assumptions="Capitalised in year of acquisition; not depreciated")
    d["ef_key"] = "spend_eeio|Machinery|USD|" + pd.Series(fi.loc[na.facility_id, "country_id"].values).map(REG).values
    acts.append(d)
    s12 = pd.concat(acts, ignore_index=True)
    # Cat 3: WTT for fuels & T&D for electricity
    s1 = s12[s12.scope == "Scope 1"]
    s1 = s1[~s1.category_id.eq("Process emissions")]
    d = s1[["facility_id", "activity_type", "activity_quantity", "activity_unit", "period_start", "period_end", "source_dataset", "source_record_id", "source_system"]].copy()
    d["ef_key"] = "wtt_fuel|" + d.activity_type + "|" + d.activity_unit + "|GLOBAL"
    d["scope"], d["category_id"], d["category_name"], d["calculation_method"] = "Scope 3", "S3-C03", CAT[3], "Average-data (WTT)"
    el = s12[(s12.scope == "Scope 2") & (s12.activity_type == "electricity")]
    d2 = el[["facility_id", "activity_type", "activity_quantity", "activity_unit", "period_start", "period_end", "source_dataset", "source_record_id", "source_system"]].copy()
    d2["ef_key"] = "wtt_td_electricity|electricity|kWh|" + fi.loc[d2.facility_id, "country_id"].values
    d2["scope"], d2["category_id"], d2["category_name"], d2["calculation_method"] = "Scope 3", "S3-C03", CAT[3], "Average-data (WTT + T&D losses)"
    acts.extend([d, d2])
    # Cat 4 / 9 transport
    sh = ctx.get("shipments")
    lf = np.where(sh.load_factor_pct > 85, "full", np.where(sh.load_factor_pct < 50, "partial", "avg_laden"))
    cat = np.where(sh.freight_paid_by == "Company", 4, np.where(sh.freight_paid_by == "Customer", 9, 0))
    for c in (4, 9):
        s = sh[cat == c]; l_ = lf[cat == c]
        ps = pd.DatetimeIndex(s.ship_date).to_period("M")
        dd = A("Scope 3", c, len(s), facility_id=np.where(s.origin.str.startswith("FAC"), s.origin, s.destination), supplier_id=s.supplier_id.values, customer_id=s.customer_id.values,
               activity_type=s["mode"].values, activity_quantity=s.tkm.values, activity_unit="tkm", original_quantity=s.distance_km.values, original_unit=s.distance_unit.values,
               period_start=ps.start_time, period_end=ps.end_time.normalize(), calculation_method="Distance-based", source_dataset="shipments", source_record_id=s.shipment_id.values, source_system="TMS")
        dd["ef_key"] = "freight_transport|" + s["mode"].map(MODE_EF).values + "|" + l_ + "|GLOBAL"
        acts.append(dd)
    # Cat 5 waste
    w = ctx.get("waste_records")
    ps = pd.PeriodIndex(w.period, freq="M")
    d = A("Scope 3", 5, len(w), facility_id=w.facility_id.values, supplier_id=w.waste_contractor_id.values, activity_type=w.waste_type.values, activity_quantity=w.quantity.values, activity_unit="t",
          original_quantity=w.quantity.values, original_unit=w.unit.values, period_start=ps.start_time, period_end=ps.end_time.normalize(), calculation_method="Waste-type-specific",
          source_dataset="waste_records", source_record_id=w.waste_record_id.values, source_system="EHS")
    d["ef_key"] = "waste_treatment|" + w.waste_type.values + "|" + w.disposal_method.values + "|GLOBAL"
    acts.append(d)
    # Cat 6 travel
    bt = ctx.get("business_travel")
    ps = pd.DatetimeIndex(bt.travel_date).to_period("M")
    nod = bt.distance_km.isna().values
    d = A("Scope 3", 6, len(bt), facility_id=bt.origin_facility_id.values, activity_type=bt.travel_mode.values, activity_quantity=np.where(nod, bt.cost_usd, bt.distance_km), activity_unit=np.where(nod, "USD", "pkm"),
          original_quantity=np.where(nod, bt.cost_usd, bt.distance_km), original_unit=np.where(nod, "USD", "km"), period_start=ps.start_time, period_end=ps.end_time.normalize(),
          calculation_method=np.where(nod, "Spend-based", "Distance-based"), source_dataset="business_travel", source_record_id=bt.trip_id.values, source_system="CONCUR_LIKE")
    d["ef_key"] = np.where(nod, "spend_eeio|Travel Services|USD|GLOBAL", "business_travel|" + bt.travel_mode.values + "|pkm|GLOBAL")
    h = bt[bt.hotel_nights > 0]; ph = pd.DatetimeIndex(h.travel_date).to_period("M")
    d2 = A("Scope 3", 6, len(h), facility_id=h.origin_facility_id.values, activity_type="hotel_stay", activity_quantity=h.hotel_nights.values.astype(float), activity_unit="night",
           original_quantity=h.hotel_nights.values.astype(float), original_unit="night", period_start=ph.start_time, period_end=ph.end_time.normalize(), calculation_method="Average-data",
           source_dataset="business_travel", source_record_id=h.trip_id.values, source_system="CONCUR_LIKE")
    d2["ef_key"] = "hotel_stay|night|" + h.destination_country_id.values
    acts.extend([d, d2])
    # Cat 7 commuting
    cs = ctx.get("commuting_survey")
    rows = []
    for m in ["car_petrol", "car_diesel", "car_ev", "bus", "rail", "motorbike", "bike_walk"]:
        pkm = cs.headcount * cs.working_days * (1 - cs.avg_remote_days_per_week / 5) * 2 * cs.avg_one_way_km * cs[f"share_{m}"]
        rows.append(A("Scope 3", 7, len(cs), facility_id=cs.facility_id.values, activity_type=m, activity_quantity=np.round(pkm.values, 1), activity_unit="pkm", original_quantity=np.round(pkm.values, 1), original_unit="pkm",
                      period_start=pd.to_datetime(cs.year.astype(str) + "-01-01").values, period_end=pd.to_datetime(cs.year.astype(str) + "-12-31").values, calculation_method="Distance-based (survey extrapolation)",
                      source_dataset="commuting_survey", source_record_id=(cs.facility_id + "-" + cs.year.astype(str)).values, source_system="HRMS", ef_key=f"employee_commute|{m}|pkm|GLOBAL",
                      assumptions="Survey response extrapolated to headcount; remote days deducted"))
    acts.extend(rows)
    # Cat 8 upstream leased (3PL-operated leased warehouse space, average-data)
    lw = fac[(fac.tenure == "Leased") & (fac.facility_type == "Warehouse/DC")].head(12)
    rows = []
    for y in YEARS:
        q = np.round(lw.floor_area_m2.values * 0.35 * 30 * rng.uniform(0.8, 1.2, len(lw)), 0)
        rows.append(A("Scope 3", 8, len(lw), facility_id=lw.facility_id.values, activity_type="leased_space_electricity_estimate", activity_quantity=q, activity_unit="kWh", original_quantity=lw.floor_area_m2.values.astype(float),
                      original_unit="m2", period_start=pd.Timestamp(f"{y}-01-01"), period_end=pd.Timestamp(f"{y}-12-31"), calculation_method="Average-data (area-based)", source_dataset="facilities",
                      source_record_id=lw.facility_id.values, source_system="MDG", ef_key="grid_location|electricity|kWh|" + lw.country_id.values,
                      assumptions="Annex space operated by landlord's 3PL; not metered by company"))
    acts.extend(rows)
    # Cat 10/11/12 from deliveries
    dl = ctx.get("deliveries")
    cu = ctx.get("customers").set_index("customer_id")
    dl = dl.assign(year=pd.to_datetime(dl.delivery_date).dt.year, ctry=cu.country_id.reindex(dl.customer_id).values)
    pr = prod
    agg = dl.groupby(["product_id", "ctry", "year"]).agg(qty=("delivered_qty", "sum"), kg=("gross_weight_kg", "sum"), ref=("delivery_id", "first")).reset_index()
    p = pr.reindex(agg.product_id)
    yS, yE = pd.to_datetime(agg.year.astype(str) + "-01-01").values, pd.to_datetime(agg.year.astype(str) + "-12-31").values
    inter = p.intermediate_product.values.astype(bool)
    procmap = {"DIV-MET": "metal_forming", "DIV-CHM": "chemical_formulation", "DIV-AUT": "automotive_assembly", "DIV-CON": "cement_to_concrete"}
    a10 = agg[inter]; p10 = p[inter]
    pk = p10.division_id.map(procmap).values
    q10 = np.where(pk == "automotive_assembly", a10.qty, a10.kg / 1000)
    d = A("Scope 3", 10, len(a10), activity_type=p10.product_family.values, activity_quantity=np.round(q10.astype(float), 3), activity_unit=np.where(pk == "automotive_assembly", "pcs", "t"), original_quantity=a10.qty.values,
          original_unit=p10.sales_unit.values, period_start=yS[inter], period_end=yE[inter], calculation_method="Average-data downstream processing", source_dataset="deliveries", source_record_id=a10.ref.values,
          source_system="SAP_S4", product_id=a10.product_id.values, assumptions="Customer processing energy not disclosed; industry-average used")
    d["ef_key"] = "processing_sold|" + pk + "|t|GLOBAL"
    acts.append(d)
    use = p.use_phase_kwh_per_year.values > 0
    a11 = agg[use]; p11 = p[use]
    d = A("Scope 3", 11, len(a11), activity_type=p11.product_family.values, activity_quantity=np.round(a11.qty.values * p11.lifetime_years.values * p11.use_phase_kwh_per_year.values, 1), activity_unit="kWh",
          original_quantity=a11.qty.values, original_unit="pcs", period_start=yS[use], period_end=yE[use], calculation_method="Product-specific (lifetime direct use-phase energy)", source_dataset="deliveries",
          source_record_id=a11.ref.values, source_system="SAP_S4", product_id=a11.product_id.values, assumptions="Lifetime energy x grid factor of customer country in year of sale (no grid decarbonisation)")
    d["ef_key"] = "grid_location|electricity|kWh|" + a11.ctry.values
    acts.append(d)
    grpm = {"DIV-IMC": "Metals", "DIV-AUT": "Metals", "DIV-MET": "Metals", "DIV-CHM": "Chemicals", "DIV-ELE": "Electronics", "DIV-PKG": "Packaging", "DIV-CON": "Minerals"}
    d = A("Scope 3", 12, len(agg), activity_type=p.division_id.map(grpm).values, activity_quantity=np.round(agg.kg.values / 1000, 3), activity_unit="t", original_quantity=agg.kg.values, original_unit="kg",
          period_start=yS, period_end=yE, calculation_method="Average-data EoL", source_dataset="deliveries", source_record_id=agg.ref.values, source_system="SAP_S4", product_id=agg.product_id.values)
    d["ef_key"] = "end_of_life|" + p.division_id.map(grpm).values + "|mixed_eol|GLOBAL"
    acts.append(d)
    lo = fac[fac.leased_out_portion_pct > 0]
    el_y = ui[ui.utility_type == "electricity"].assign(y=pd.to_datetime(ui.billing_period_start).dt.year).groupby(["facility_id", "y"]).consumption.sum()
    rows = []
    for y in YEARS:
        q = el_y.reindex(pd.MultiIndex.from_arrays([lo.facility_id, np.full(len(lo), y)])).fillna(0).values * lo.leased_out_portion_pct.values / 100
        rows.append(A("Scope 3", 13, len(lo), facility_id=lo.facility_id.values, activity_type="tenant_electricity", activity_quantity=np.round(q, 1), activity_unit="kWh", original_quantity=np.round(q, 1), original_unit="kWh",
                      period_start=pd.Timestamp(f"{y}-01-01"), period_end=pd.Timestamp(f"{y}-12-31"), calculation_method="Asset-specific (floor-area allocation)", source_dataset="utility_invoices",
                      source_record_id=lo.facility_id.values, source_system="SAP_S4", ef_key="grid_location|electricity|kWh|" + lo.country_id.values,
                      assumptions="Tenant share of metered electricity removed from Scope 2 (see adjustments)"))
    acts.extend(rows)
    fr_ = [(f"FRN-{i:03d}", COUNTRIES[i % 22][0]) for i in range(1, 13)]
    rows = []
    for y in YEARS:
        rev = np.round(rng.lognormal(16, 0.4, len(fr_)), 0)
        rows.append(A("Scope 3", 14, len(fr_), activity_type="franchise_distributor_operations", activity_quantity=rev, activity_unit="USD", original_quantity=rev, original_unit="USD",
                      period_start=pd.Timestamp(f"{y}-01-01"), period_end=pd.Timestamp(f"{y}-12-31"), calculation_method="Spend-based (franchise revenue)", source_dataset="franchise_register",
                      source_record_id=[f[0] for f in fr_], source_system="CRM_PARTNER", ef_key="spend_eeio|Franchise Operations|USD|GLOBAL", assumptions="Franchisee energy not reported"))
    acts.extend(rows)
    inv = pd.DataFrame(dict(investment_id=[f"INV-{i:03d}" for i in range(1, 9)], investee=[f"Synthetic Investee {c} Holdings (SYNTHETIC)" for c in "ABCDEFGH"],
                            equity_share_pct=[15, 22, 35, 8, 49, 12, 30, 40], investee_scope12_tco2e=np.round(rng.lognormal(11, 0.8, 8), 0)))
    rows = []
    for y in YEARS:
        rows.append(A("Scope 3", 15, len(inv), activity_type="equity_investment", activity_quantity=np.round(inv.investee_scope12_tco2e.values * 1000 * inv.equity_share_pct.values / 100 * (1 - 0.03 * (y - 2022)), 0), activity_unit="kgCO2e",
                      original_quantity=inv.investee_scope12_tco2e.values, original_unit="tCO2e (investee)", period_start=pd.Timestamp(f"{y}-01-01"), period_end=pd.Timestamp(f"{y}-12-31"),
                      calculation_method="Investment-specific (equity share)", source_dataset="investment_register", source_record_id=inv.investment_id.values, source_system="TREASURY", ef_key=None,
                      assumptions="Investee-reported emissions x equity share"))
    acts.extend(rows)
    ctx.save(inv, "GHG_Accounting/Scope_3/investment_register.csv", "investment_register", pk="investment_id", system="TREASURY")
    ctx.save(pd.DataFrame(dict(franchise_id=[f[0] for f in fr_], country_id=[f[1] for f in fr_], name=[f"Synthetic Franchise Distributor {f[0]} (SYNTHETIC)" for f in fr_])), "GHG_Accounting/Scope_3/franchise_register.csv", "franchise_register", pk="franchise_id", system="CRM_PARTNER")
    ga = pd.concat(acts, ignore_index=True)
    ga["period_start"] = pd.to_datetime(ga.period_start); ga["period_end"] = pd.to_datetime(ga.period_end)
    ga["reporting_year"] = ga.period_start.dt.year
    ga["reporting_period"] = ga.period_start.dt.to_period("M").astype(str)
    ga = ga[ga.reporting_year.between(2022, 2026)].reset_index(drop=True)
    ga = apply_ef(ctx, ga, "ef_key", "reporting_year")
    miss_ef = ga.emission_factor_value.isna() & ga.ef_key.notna()
    ss = miss_ef & ga.ef_key.str.startswith("supplier_specific_material")
    ga.loc[ss, "ef_key"] = "purchased_material|" + ga.loc[ss, "activity_type"] + "|" + ga.loc[ss, "activity_unit"] + "|GLOBAL"
    ga.loc[ss, "calculation_method"] = "Average-data"
    oth = miss_ef & ~ss
    ga.loc[oth, "ef_key"] = ga.loc[oth, "ef_key"].str.rsplit("|", n=1).str[0] + "|GLOBAL"
    ga = apply_ef(ctx, ga, "ef_key", "reporting_year")
    inv_rows = ga.activity_type == "equity_investment"
    ga.loc[inv_rows, ["emission_factor_value", "emission_factor_unit", "gwp_basis"]] = [1.0, "kgCO2e/kgCO2e", "AR6"]
    # fugitive emissions (GWP table)
    mr = ctx.get("maintenance"); mr = mr[mr.refrigerant_added_kg > 0]
    gw = ctx.get("emission_factors"); gw = gw[gw.activity_type == "fugitive_gwp"].set_index("lookup_key")
    yy = pd.to_datetime(mr.work_date).dt.year.values
    basis = np.where(yy <= 2023, "AR5", "AR6")
    keys = "fugitive_gwp|" + mr.refrigerant_type.values + "|kg|" + basis
    ps = pd.DatetimeIndex(mr.work_date).to_period("M")
    fg = A("Scope 1", "Fugitive emissions (refrigerants)", len(mr), facility_id=mr.facility_id.values, equipment_id=mr.asset_id.values, activity_type=mr.refrigerant_type.values,
           activity_quantity=np.round(mr.refrigerant_added_kg.values - mr.refrigerant_recovered_kg.values, 3), activity_unit="kg", original_quantity=mr.refrigerant_added_kg.values, original_unit="kg",
           period_start=ps.start_time, period_end=ps.end_time.normalize(), calculation_method="Mass-balance (top-up minus recovered)", source_dataset="maintenance", source_record_id=mr.maintenance_id.values,
           source_system="CMMS", ef_key=keys, reporting_year=yy, reporting_period=ps.astype(str))
    fg["emission_factor_id"] = gw.emission_factor_id.reindex(keys).values; fg["emission_factor_value"] = gw.factor_value.reindex(keys).values
    fg["emission_factor_unit"] = "kgCO2e/kg"; fg["gwp_basis"] = basis
    ga = pd.concat([ga, fg], ignore_index=True)
    ga["activity_quantity"] = ga.activity_quantity.astype(float)
    ga["co2e_kg"] = np.round(ga.activity_quantity * ga.emission_factor_value, 3)
    # JV facilities (no operational control) -> excluded from S1/S2, reported under Cat 15
    jv = ga.facility_id.isin(fac[~fac.operational_control].facility_id) & ga.scope.isin(["Scope 1", "Scope 2"])
    ga["reporting_boundary"] = np.where(jv, "Excluded - no operational control (reported in S3 Cat 15 at equity share)", "Operational control")
    ga["included_in_inventory"] = ~jv
    yrs = ga.reporting_year.values
    ga["data_quality_rating"] = np.clip(np.where(ga.calculation_method.astype(str).str.contains("Spend"), 5, np.where(ga.calculation_method.astype(str).str.contains("Supplier|Fuel|Mass"), 2, 3)) + (yrs < 2024).astype(int), 1, 5)
    ga["uncertainty_pct"] = ga.data_quality_rating.map({1: 3, 2: 7, 3: 15, 4: 30, 5: 50})
    ga["gas_type"] = np.where(ga.category_id.astype(str).str.startswith("Fugitive"), ga.activity_type, "CO2e")
    ga["gwp_time_horizon"] = "GWP100"
    ga["source_document_id"] = None
    ga["assumptions"] = ga.get("assumptions")
    # ---- anomalies
    n = len(ga)
    loc = np.where((ga.scope == "Scope 2") & (ga.activity_type == "electricity"))[0]
    t = ctx.get("emission_factors").assign(year=lambda e: pd.to_datetime(e.effective_date).dt.year).drop_duplicates(["lookup_key", "year"]).set_index(["lookup_key", "year"])
    k = rng.choice(loc, int(len(loc) * 0.01), replace=False)
    wrong_c = rng.choice([c[0] for c in COUNTRIES], len(k))
    wk = pd.MultiIndex.from_arrays(["grid_location|electricity|kWh|" + wrong_c, ga.reporting_year.values[k]])
    e_ef = ga.emission_factor_value.values[k].copy(); e_co = ga.co2e_kg.values[k].copy()
    ga.loc[k, "emission_factor_id"] = t.emission_factor_id.reindex(wk).values; ga.loc[k, "emission_factor_value"] = t.factor_value.reindex(wk).values
    ga.loc[k, "co2e_kg"] = np.round(ga.activity_quantity.values[k] * ga.emission_factor_value.values[k], 3)
    ok = ga.emission_factor_value.values[k] != e_ef; k = k[ok]
    ctx.anom("ghg_activities", ga.ghg_activity_id.values[k] if "ghg_activity_id" in ga else k, "GHG calculation", "Incorrect geographic factors", "High", e_ef[ok], ga.emission_factor_value.values[k],
             "Grid factor selected for wrong country", "Factor geography vs facility country", "Apply facility-country grid factor", corrected=e_co[ok], ghg="Scope 2", impact=ga.co2e_kg.values[k] - e_co[ok], family="Calculation_Errors")
    pool = np.setdiff1d(np.where(ga.scope.isin(["Scope 1", "Scope 2"]) & (ga.reporting_year >= 2024) & ~ga.category_id.astype(str).str.startswith("Fugitive"))[0], k)
    k2 = rng.choice(pool, int(len(pool) * 0.006), replace=False)
    ok_ = pd.MultiIndex.from_arrays([ga.ef_key.values[k2], ga.reporting_year.values[k2] - 2])
    e_ef = ga.emission_factor_value.values[k2].copy(); e_id = ga.emission_factor_id.values[k2].copy(); e_co = ga.co2e_kg.values[k2].copy()
    ga.loc[k2, "emission_factor_id"] = t.emission_factor_id.reindex(ok_).values; ga.loc[k2, "emission_factor_value"] = t.factor_value.reindex(ok_).values
    ga.loc[k2, "co2e_kg"] = np.round(ga.activity_quantity.values[k2] * ga.emission_factor_value.values[k2], 3)
    ctx.anom("ghg_activities", k2, "GHG calculation", "Outdated emission factors / factor applied outside validity period", "Medium", e_id, ga.emission_factor_id.values[k2], "Factor library not refreshed",
             "EF effective/expiry vs activity date", "Apply current-year factor version", corrected=e_co, ghg="Scope 1/2", impact=ga.co2e_kg.values[k2] - e_co, family="Calculation_Errors")
    fgi = np.where(ga.category_id.astype(str).str.startswith("Fugitive"))[0]
    k3 = rng.choice(fgi, max(1, int(len(fgi) * 0.04)), replace=False)
    ar4 = np.array([GWP.get(g, (1, 1, 1))[0] for g in ga.activity_type.values[k3]], dtype=float)
    e_ef = ga.emission_factor_value.values[k3].copy(); e_co = ga.co2e_kg.values[k3].copy()
    ga.loc[k3, "emission_factor_value"] = ar4; ga.loc[k3, "gwp_basis"] = "AR4"; ga.loc[k3, "co2e_kg"] = np.round(ga.activity_quantity.values[k3] * ar4, 3)
    ctx.anom("ghg_activities", k3, "GHG calculation", "Wrong GWP values", "Medium", e_ef, ar4, "Legacy spreadsheet GWP table (AR4)", "GWP basis consistency check", "Apply inventory GWP basis",
             corrected=e_co, ghg="Scope 1 Fugitive", impact=ga.co2e_kg.values[k3] - e_co, family="Calculation_Errors")
    k4 = rng.choice(np.setdiff1d(loc, k), int(len(loc) * 0.004), replace=False)
    ga.loc[k4, "scope"] = "Scope 1"; ga.loc[k4, "category_id"] = "Stationary combustion"
    ctx.anom("ghg_activities", k4, "GHG calculation", "Incorrect Scope classification", "High", "Scope 2", "Scope 1", "Mapping table error for utility account", "Activity type vs scope rule", "Reclassify to Scope 2", ghg="Scope 1/2", family="Calculation_Errors")
    small = np.where(ga.co2e_kg.values < np.nanmedian(ga.co2e_kg.values))[0]
    k5 = rng.choice(np.setdiff1d(small, np.r_[k, k2, k3, k4]), int(n * 0.0015), replace=False)
    e_co = ga.co2e_kg.values[k5].copy(); ga.loc[k5, "co2e_kg"] = np.round(e_co * rng.choice([10, 0.1], len(k5)), 3)
    ctx.anom("ghg_activities", k5, "GHG calculation", "Incorrect calculation (arithmetic / conversion factor)", "High", e_co, ga.co2e_kg.values[k5], "Decimal shift in manual calculation", "Recompute qty x EF", "Recalculate",
             ghg="Multiple", impact=ga.co2e_kg.values[k5] - e_co, family="Calculation_Errors")
    dec = np.where((ga.period_start.dt.month == 12) & (ga.scope != "Scope 3"))[0]
    k6 = rng.choice(np.setdiff1d(dec, np.r_[k, k2, k3, k4, k5]), int(len(dec) * 0.01), replace=False)
    e_p = ga.reporting_year.values[k6].copy(); ga.loc[k6, "reporting_year"] = e_p + 1; ga.loc[k6, "reporting_period"] = np.char.add((e_p + 1).astype(str), "-01")
    ctx.anom("ghg_activities", k6, "Temporal", "Incorrect reporting-year assignments / calculation periods", "Medium", e_p, e_p + 1, "Activity bucketed by invoice date not consumption period", "Period vs consumption dates",
             "Assign to consumption period", ghg="Scope 1/2", family="Calculation_Errors")
    jvi = np.where(~ga.included_in_inventory.values & (ga.reporting_year.values == 2025))[0]
    k7 = jvi[:max(1, len(jvi) // 3)]
    ga.loc[k7, "included_in_inventory"] = True; ga.loc[k7, "reporting_boundary"] = "Operational control"
    ctx.anom("ghg_activities", k7, "Boundary", "Incorrect organisational boundaries", "High", "Excluded (JV, no operational control)", "Included at 100%", "JV facility added to inventory in 2025 roll-out",
             "Facility control flag vs inventory inclusion", "Exclude; report under Cat 15 at equity share", ghg="Scope 1/2", impact=ga.co2e_kg.values[k7], family="Governance_Anomalies")
    dpi = rng.choice(np.where(ga.scope != "Scope 3")[0], int(n * 0.002), replace=False)
    ga.insert(0, "ghg_activity_id", ids("GHG-", n, 8))
    dup = ga.iloc[dpi].copy(); dup["ghg_activity_id"] = ids("GHG-", len(dup), 8, start=n + 1)
    gas_inv = np.setdiff1d(ga[(ga.activity_type == "natural_gas")].index.values, np.r_[k, k2, k3, k4, k5, k6, k7, dpi])
    miss = rng.choice(gas_inv, max(1, int(len(gas_inv) * 0.01)), replace=False)
    missing = ga.loc[miss]
    ctx.anom("utility_invoices", missing.source_record_id.values, "Completeness", "Missing emission sources", "High", missing.co2e_kg.values, "Not in GHG inventory", "Gas invoice not mapped to GHG activity",
             "Invoice-to-activity completeness reconciliation", "Create activity from invoice", ghg="Scope 1 Stationary", impact=-missing.co2e_kg.values, family="Calculation_Errors", system="GHG_PLATFORM")
    ga = pd.concat([ga.drop(index=miss), dup], ignore_index=True)
    ctx.anom("ghg_activities", dup.ghg_activity_id.values, "Duplicate record", "Double-counted emissions", "High", "single activity", "duplicate", "Same invoice ingested from ERP and from document upload",
             "Duplicate on source_record_id + period", "Remove duplicate", related=dup.source_record_id.values, ghg="Scope 1/2", impact=dup.co2e_kg.values, family="Calculation_Errors")
    # remap index-based GT ids to activity ids
    idmap = ga.ghg_activity_id
    fixed = []
    for a in ctx.anoms:
        if (a.source_dataset == "ghg_activities").all() and np.issubdtype(np.asarray(a.source_record_id.tolist()).dtype, np.integer):
            orig_ids = ids("GHG-", n, 8)
            a = a.assign(source_record_id=orig_ids[a.source_record_id.astype(int).values])
        fixed.append(a)
    ctx.anoms = fixed
    # propagated source anomalies
    import glob
    prev = pd.concat([pd.read_parquet(f) for f in glob.glob(str(ctx.root / "Anomaly_Ground_Truth/_batches/B0[4-9].parquet"))], ignore_index=True)
    hit = ga[ga.source_record_id.isin(prev.source_record_id)]
    pm = prev.drop_duplicates("source_record_id").set_index("source_record_id")
    ctx.anom("ghg_activities", hit.ghg_activity_id.values, "Propagated", "Source-system error propagated to GHG activity", pm.severity.reindex(hit.source_record_id).values, "see related source anomaly",
             hit.activity_quantity.values, "Upstream data defect", "Cross-system lineage trace", "Correct source record and recalculate", related=hit.source_record_id.values, ghg=hit.scope.values, family="Calculation_Errors")
    ga["co2e_t"] = np.round(ga.co2e_kg / 1000, 6)
    ga["scope2_method"] = np.where(ga.scope == "Scope 2", "location-based", None)
    ga = ga.drop(columns=["ef_key"])
    ctx.lineage(ga, "GHG_PLATFORM", "Canonical GHG Engine", "GHGDB", "GHG_ACTIVITY", "EHS & Sustainability", ga.source_record_id.values)
    for sc, rel in [("Scope 1", "GHG_Accounting/Scope_1/scope1_activities.parquet"), ("Scope 2", "GHG_Accounting/Scope_2/scope2_location_based_activities.parquet"), ("Scope 3", "GHG_Accounting/Scope_3/scope3_activities.parquet")]:
        ga[ga.scope == sc].to_parquet(ctx.path(rel), index=False)
    ctx.save(ga, "GHG_Accounting/Calculation_Results/ghg_activities_all.parquet", "ghg_activities", pk="ghg_activity_id", fks={"emission_factor_id": "emission_factors.emission_factor_id", "facility_id": "facilities.facility_id"}, target=3000000, system="GHG_PLATFORM")
    gen_scope2_market(ctx, ga, rng)


def gen_scope2_market(ctx, ga, rng):
    fac = ctx.get("facilities").set_index("facility_id")
    ui = ctx.get("utility_invoices").set_index("utility_invoice_id")
    el = ga[(ga.activity_type == "electricity") & (ga.source_dataset == "utility_invoices")].copy()
    fy = el.groupby(["facility_id", "reporting_year"]).activity_quantity.sum().reset_index()
    fy = fy[fy.reporting_year >= 2023]
    pick = fy[rng.random(len(fy)) < fy.reporting_year.map({2023: 0.2, 2024: 0.32, 2025: 0.45, 2026: 0.58}).values].reset_index(drop=True)
    cov = np.round(rng.uniform(0.3, 1.0, len(pick)), 2)
    ctry = fac.country_id.reindex(pick.facility_id).values
    reg = np.where(np.isin(ctry, ["DE", "FR", "IT", "ES", "PL", "NL", "SE", "GB"]), "AIB-GO (synthetic)", np.where(np.isin(ctry, ["US", "CA"]), "M-RETS-like (synthetic)", "I-REC-like (synthetic)"))
    ins = pd.DataFrame(dict(instrument_id=ids("EAC-", len(pick), 5), instrument_type=np.where(reg == "AIB-GO (synthetic)", "Guarantee of Origin", np.where(rng.random(len(pick)) < 0.3, "Physical PPA", "REC/I-REC")),
                            registry=reg, serial_number=[f"SYN-{c}-{y}-{rng.integers(10 ** 9, 10 ** 10)}" for c, y in zip(ctry, pick.reporting_year)], vintage_year=pick.reporting_year.values,
                            technology=rng.choice(["Wind", "Solar PV", "Hydro"], len(pick)), mwh=np.round(pick.activity_quantity.values * cov / 1000, 3), market_boundary=ctry,
                            allocated_facility_id=pick.facility_id.values, allocation_year=pick.reporting_year.values, retirement_date=pd.to_datetime(pick.reporting_year.astype(str) + "-12-15") + pd.DateOffset(months=3),
                            retired_on_behalf_of="Halvorsen-Kaito Industrial Holdings plc (SYNTHETIC)", price_usd_per_mwh=np.round(rng.uniform(1.5, 18, len(pick)), 2), synthetic_flag=True))
    dd = ins.sample(8, random_state=1).copy(); dd["instrument_id"] = ids("EAC-", 8, 5, start=len(ins) + 1)
    dd["allocated_facility_id"] = fac.index[fac.facility_type == "Manufacturing"][:8]
    ins = pd.concat([ins, dd], ignore_index=True)
    vm = rng.choice(len(pick), 6, replace=False); ins.loc[vm, "vintage_year"] = ins.loc[vm, "allocation_year"] - 3
    xb = rng.choice(np.setdiff1d(np.arange(len(pick)), vm), 5, replace=False); e_b = ins.loc[xb, "market_boundary"].values.copy(); ins.loc[xb, "market_boundary"] = "CN"
    ctx.save(ins, "GHG_Accounting/Scope_2/contractual_instruments_eac.csv", "contractual_instruments", pk="instrument_id", fks={"allocated_facility_id": "facilities.facility_id"}, system="EAC_REGISTRY")
    ctx.anom("contractual_instruments", dd.instrument_id.values, "Governance", "Double-counted renewable energy certificates / duplicate certificate serial numbers", "Critical", "unique serial", dd.serial_number.values,
             "Same certificate allocated to two facilities", "Serial-number uniqueness", "De-allocate duplicate", ghg="Scope 2 market-based", family="Governance_Anomalies")
    ctx.anom("contractual_instruments", ins.instrument_id.values[vm], "Scope 2 quality criteria", "Vintage outside reporting period", "High", ins.allocation_year.values[vm], ins.vintage_year.values[vm],
             "Old-vintage certificates bought cheaply", "Vintage vs reporting year (quality criteria)", "Exclude from market-based", ghg="Scope 2 market-based", family="Governance_Anomalies")
    ctx.anom("contractual_instruments", ins.instrument_id.values[xb], "Scope 2 quality criteria", "Certificate outside market boundary", "High", e_b, "CN", "I-REC from other grid allocated",
             "Market-boundary check", "Exclude from market-based", ghg="Scope 2 market-based", family="Governance_Anomalies")
    valid = ins.drop(index=np.r_[vm, xb]).drop_duplicates("serial_number")
    cov_map = valid.groupby(["allocated_facility_id", "allocation_year"]).mwh.sum() * 1000
    tot = el.groupby(["facility_id", "reporting_year"]).activity_quantity.transform("sum")
    covered = cov_map.reindex(pd.MultiIndex.from_arrays([el.facility_id, el.reporting_year])).fillna(0).values
    share = np.clip(covered / tot.values.clip(min=1), 0, 1)
    sup_ef = ui.supplier_disclosed_ef_kg_per_kwh.reindex(el.source_record_id).values
    green = ui.green_tariff.reindex(el.source_record_id).fillna(False).values.astype(bool)
    from .ef import ef_table
    t = ef_table(ctx); t = t[~t.index.duplicated()]
    rk = pd.MultiIndex.from_arrays(["grid_residual_mix|electricity|kWh|" + fac.country_id.reindex(el.facility_id).values, el.reporting_year.values])
    resid = t.factor_value.reindex(rk).values
    use_sup = ~np.isnan(sup_ef) & (rng.random(len(el)) < 0.5)
    ef_unc = np.where(green, 0.0, np.where(use_sup, sup_ef, resid))
    mb = pd.DataFrame(dict(market_calc_id=ids("S2MB-", len(el), 7), ghg_activity_id=el.ghg_activity_id.values, facility_id=el.facility_id.values, reporting_period=el.reporting_period.values,
                           reporting_year=el.reporting_year.values, activity_quantity_kwh=el.activity_quantity.values, eac_covered_share=np.round(np.where(green, 1, share), 4),
                           instrument_basis=np.where(green, "Green tariff (supplier-specific)", np.where(share > 0, "EAC allocation", np.where(use_sup, "Supplier-specific EF", "Residual mix"))),
                           uncovered_ef_kg_per_kwh=np.round(ef_unc, 5), residual_mix_ef_id=t.emission_factor_id.reindex(rk).values, location_based_co2e_kg=el.co2e_kg.values,
                           included_in_inventory=el.included_in_inventory.values))
    mb["market_based_co2e_kg"] = np.round(mb.activity_quantity_kwh * (1 - mb.eac_covered_share) * mb.uncovered_ef_kg_per_kwh, 3)
    k = rng.choice(np.where(mb.eac_covered_share == 0)[0], int(len(mb) * 0.008), replace=False)
    e = mb.market_based_co2e_kg.values[k].copy(); mb.loc[k, "market_based_co2e_kg"] = 0.0; mb.loc[k, "instrument_basis"] = "EAC allocation"
    ctx.save(mb, "GHG_Accounting/Scope_2/scope2_market_based_calculations.parquet", "scope2_market", pk="market_calc_id", fks={"ghg_activity_id": "ghg_activities.ghg_activity_id"}, system="GHG_PLATFORM")
    ctx.anom("scope2_market", mb.market_calc_id.values[k], "GHG calculation", "Incorrect Scope 2 market-based calculations", "High", e, 0.0, "Facility assumed covered by corporate PPA without allocation",
             "Certificate allocation vs claimed coverage", "Apply residual mix", ghg="Scope 2 market-based", impact=-e, family="Calculation_Errors")
    # inventory summaries
    inc = ga[ga.included_in_inventory & ga.reporting_year.between(2022, 2026)]
    inv = inc.groupby(["reporting_year", "scope", "category_id"]).co2e_kg.sum().div(1000).round(2).rename("tco2e").reset_index()
    inv["scope2_method"] = np.where(inv.scope == "Scope 2", "location-based", None)
    m = mb[mb.included_in_inventory & mb.reporting_year.between(2022, 2026)].groupby("reporting_year").market_based_co2e_kg.sum().div(1000).round(2)
    inv = pd.concat([inv, pd.DataFrame(dict(reporting_year=m.index, scope="Scope 2", category_id="Purchased electricity", tco2e=m.values, scope2_method="market-based"))], ignore_index=True)
    ctx.save(inv, "GHG_Accounting/Calculation_Results/annual_ghg_inventory.csv", "ghg_inventory", system="GHG_PLATFORM")
    fy = inc.groupby(["facility_id", "reporting_year", "scope"]).co2e_kg.sum().div(1000).round(3).rename("tco2e").reset_index()
    ctx.save(fy, "GHG_Accounting/Calculation_Results/facility_year_emissions.csv", "facility_emissions", system="GHG_PLATFORM")
    base = inv[(inv.reporting_year == 2022)].groupby("scope").tco2e.sum()
    rb = pd.DataFrame([dict(baseline_year=2022, scope=s, original_baseline_tco2e=round(v, 2), recalculated_baseline_tco2e=round(v * (1.034 if s != "Scope 3" else 1.012), 2),
                            recalculation_trigger="Structural change: facilities commissioned 2023-2025 exceed 5% significance threshold (synthetic policy)",
                            approval_status="Approved", approved_by="Group Sustainability Committee (synthetic)", approval_date="2025-02-18") for s, v in base.items()])
    ctx.save(rb, "GHG_Accounting/Calculation_Results/baseline_recalculations.csv", "baseline_recalculations", system="GHG_PLATFORM")
