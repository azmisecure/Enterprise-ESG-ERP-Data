import numpy as np
import pandas as pd
from .core import ids, rand_dates, YEARS, END
from .master import COUNTRIES


def gen_esg(ctx):
    rng = ctx.rng("esg")
    sup, fac, cust = ctx.get("suppliers"), ctx.get("facilities"), ctx.get("customers")
    ef = ctx.get("emission_factors")
    ns = len(sup)
    mat_lvl = sup.data_maturity.map({"Leading": 4, "Established": 3, "Developing": 2, "Basic": 1}).values
    # supplier ESG assessments
    adate = pd.to_datetime(rng.choice(pd.date_range("2022-01-01", "2026-12-31", freq="QS"), ns))
    sa = pd.DataFrame(dict(assessment_id=ids("SESG-", ns, 5), supplier_id=sup.supplier_id.values, assessment_date=adate, framework="SynthRate ESG v3 (FICTIONAL)",
                           overall_score=np.clip(np.round(rng.normal(30 + 9 * mat_lvl, 8), 0), 5, 98), environment_score=np.clip(np.round(rng.normal(28 + 10 * mat_lvl, 9)), 0, 100),
                           labour_human_rights_score=np.clip(np.round(rng.normal(35 + 8 * mat_lvl, 9)), 0, 100), ethics_score=np.clip(np.round(rng.normal(35 + 8 * mat_lvl, 10)), 0, 100),
                           sustainable_procurement_score=np.clip(np.round(rng.normal(25 + 9 * mat_lvl, 10)), 0, 100),
                           sbti_status=np.where(mat_lvl >= 3, rng.choice(["Targets validated", "Committed", "None"], ns, p=[.35, .35, .3]), rng.choice(["Committed", "None"], ns, p=[.1, .9])),
                           has_ghg_inventory=(mat_lvl >= 2) & (rng.random(ns) < 0.4 + 0.15 * mat_lvl), labour_audit_result=rng.choice(["No findings", "Minor findings", "Major findings", "Not audited"], ns, p=[.4, .3, .05, .25]),
                           verification_status=np.where(mat_lvl >= 3, rng.choice(["Third-party verified", "Self-declared"], ns), "Self-declared")))
    ctx.save(sa, "Procurement/Supplier_Assessments/supplier_esg_assessments.parquet", "supplier_esg_assessments", pk="assessment_id", fks={"supplier_id": "suppliers.supplier_id"}, target=10000, system="SAP_Ariba")
    # supplier emissions disclosures
    top = sup[mat_lvl >= 2].head(2500)
    rows = []
    for y in [2022, 2023, 2024, 2025]:
        part = top[rng.random(len(top)) < 0.35 + 0.12 * (y - 2022)]
        n = len(part)
        rev = rng.lognormal(18, 1.2, n)
        s1 = rev / 1e6 * rng.lognormal(3.2, 0.8, n)
        rows.append(pd.DataFrame(dict(supplier_id=part.supplier_id.values, reporting_year=y, reporting_period=np.where(rng.random(n) < 0.3, f"FY{y} (Apr-Mar)", f"CY{y}"),
                                      methodology=rng.choice(["GHG Protocol Corporate Standard", "ISO 14064-1", "Spend-based estimate", "Undisclosed"], n, p=[.55, .2, .15, .1]),
                                      reporting_boundary=rng.choice(["Operational control", "Financial control", "Single site", "Unclear"], n, p=[.55, .15, .2, .1]),
                                      scope1_tco2e=np.round(s1, 1), scope2_tco2e=np.round(s1 * rng.uniform(0.4, 2.5, n), 1), scope3_tco2e=np.where(rng.random(n) < 0.4, np.round(s1 * rng.uniform(3, 15, n), 1), np.nan),
                                      revenue_usd=np.round(rev, -3), energy_mwh=np.round(s1 * rng.uniform(2, 6, n), 0), water_m3=np.round(s1 * rng.uniform(5, 40, n)), waste_t=np.round(s1 * rng.uniform(0.05, 0.4, n), 1),
                                      renewable_electricity_pct=np.round(np.clip(rng.beta(1.5, 4, n) * 100 + 5 * (y - 2022), 0, 100), 1), emission_factor_source=rng.choice(["National inventory", "IEA-like (synthetic)", "Supplier utility", "Unknown"], n),
                                      verification_status=rng.choice(["Limited assurance", "Reasonable assurance", "Unverified"], n, p=[.35, .1, .55]), uncertainty_pct=rng.choice([5, 10, 20, 40], n),
                                      reported_unit="tCO2e", submission_date=pd.to_datetime(f"{y + 1}-04-30") + pd.to_timedelta(rng.gamma(2, 25, n), "D"),
                                      evidence_document_id=np.where(rng.random(n) < 0.7, np.char.add("DOC-SD-", rng.integers(10 ** 6, 10 ** 7, n).astype(str)), None))))
    sd = pd.concat(rows, ignore_index=True)
    sd.insert(0, "disclosure_id", ids("SDISC-", len(sd), 6))
    sd["intensity_tco2e_per_musd"] = np.round((sd.scope1_tco2e + sd.scope2_tco2e) / (sd.revenue_usd / 1e6), 3)
    k = rng.choice(len(sd), int(len(sd) * 0.02), replace=False); e = sd.scope1_tco2e.values[k].copy(); sd.loc[k, "scope1_tco2e"] = np.round(e / 1000, 4); sd.loc[k, "reported_unit"] = "tCO2e"
    ctx.anom("supplier_disclosures", sd.disclosure_id.values[k], "Unit conversion", "Kilograms versus metric tonnes (ktCO2e reported as tCO2e)", "Medium", e, sd.scope1_tco2e.values[k], "Supplier reported in kt",
             "Intensity outlier vs sector", "Multiply by 1000", ghg="Scope 3 Cat 1", family="Unit_Errors", system="SUPPLIER_PORTAL")
    late = np.where(sd.submission_date > pd.to_datetime(sd.reporting_year.astype(str) + "-12-31") + pd.DateOffset(months=9))[0]
    ctx.anom("supplier_disclosures", sd.disclosure_id.values[late], "Temporal", "Delayed supplier disclosures", "Low", "<= 9 months after year end", sd.submission_date.dt.date.values[late], "Supplier resource constraints",
             "Submission vs deadline", "Use prior-year with extrapolation flag", family="Document_Anomalies", system="SUPPLIER_PORTAL")
    cr = rng.choice(np.where(sd.renewable_electricity_pct > 60)[0], min(40, (sd.renewable_electricity_pct > 60).sum()), replace=False)
    e = sd.scope2_tco2e.values[cr].copy(); sd.loc[cr, "scope2_tco2e"] = np.round(sd.scope1_tco2e.values[cr] * 2.4, 1)
    ctx.anom("supplier_disclosures", sd.disclosure_id.values[cr], "Disclosure quality", "Contradictory supplier disclosures (high renewable % but high Scope 2)", "Medium", e, sd.scope2_tco2e.values[cr],
             "Location-based figure reported alongside market-based RE claim", "Consistency rule RE% vs Scope 2 intensity", "Request market-based Scope 2", ghg="Scope 3 Cat 1", family="Document_Anomalies", system="SUPPLIER_PORTAL")
    ctx.save(sd, "Procurement/Supplier_Disclosures/supplier_emissions_disclosures.parquet", "supplier_disclosures", pk="disclosure_id", fks={"supplier_id": "suppliers.supplier_id"}, system="SUPPLIER_PORTAL")
    ss = ef[ef.activity_type == "supplier_specific_material"]
    pcf = pd.DataFrame(dict(pcf_id=ids("PCF-", len(ss), 5), supplier_id=ss.geography.values, material_family=ss.material_type.values, emission_factor_id=ss.emission_factor_id.values,
                            declared_kgco2e_per_unit=ss.factor_value.values, declared_unit=ss.activity_unit.values, system_boundary="Cradle-to-gate", standard=rng.choice(["ISO 14067", "PACT Pathfinder-like", "Internal LCA"], len(ss)),
                            reference_year=ss.effective_date.dt.year.values - 1, valid_until=ss.expiry_date.values + pd.Timedelta(days=365), verification=rng.choice(["Third-party verified", "Self-declared"], len(ss)),
                            primary_data_share_pct=np.round(rng.uniform(10, 90, len(ss)), 0), synthetic_flag=True))
    k = rng.choice(len(pcf), int(len(pcf) * 0.03), replace=False); e = pcf.declared_kgco2e_per_unit.values[k].copy()
    pcf.loc[k, "declared_kgco2e_per_unit"] = np.round(e * rng.uniform(0.3, 0.6, len(k)), 4)
    ctx.save(pcf, "Supply_Chain/Supplier_Emissions/supplier_product_carbon_footprints.parquet", "supplier_pcfs", pk="pcf_id", fks={"supplier_id": "suppliers.supplier_id", "emission_factor_id": "emission_factors.emission_factor_id"}, system="SUPPLIER_PORTAL")
    ctx.anom("supplier_pcfs", pcf.pcf_id.values[k], "Disclosure quality", "Contradictory supplier disclosures (PCF vs factor library)", "Medium", e, pcf.declared_kgco2e_per_unit.values[k], "Updated PCF excludes upstream aluminium",
             "PCF vs EF library comparison", "Request boundary clarification", ghg="Scope 3 Cat 1", family="Document_Anomalies", system="SUPPLIER_PORTAL")
    nc = 6000
    csup = sup.iloc[rng.choice(ns, nc)]
    vf = pd.to_datetime(rng.choice(pd.date_range("2019-01-01", "2026-06-01"), nc))
    sc = pd.DataFrame(dict(certificate_id=ids("SCERT-", nc, 5), supplier_id=csup.supplier_id.values, standard=rng.choice(["ISO 14001", "ISO 50001", "ISO 45001", "ISO 9001", "FSC CoC", "Responsible Metals (synthetic)", "SA8000"], nc),
                           certificate_serial=np.char.add("CB-SYN-", rng.choice(10 ** 7, nc, replace=False).astype(str)), certification_body="SynthCert Assurance Ltd (FICTIONAL)", valid_from=vf, valid_to=vf + pd.DateOffset(years=3)))
    sc["presented_status"] = np.where(sc.valid_to < END, "Expired", "Valid")
    ex = rng.choice(np.where(sc.presented_status == "Expired")[0], 80, replace=False); sc.loc[ex, "presented_status"] = "Valid"
    dpl = rng.choice(nc, 25, replace=False); src = rng.choice(nc, 25, replace=False); sc.loc[dpl, "certificate_serial"] = sc.certificate_serial.values[src]
    ctx.save(sc, "Procurement/Supplier_Certifications/supplier_certifications.csv", "supplier_certifications", pk="certificate_id", fks={"supplier_id": "suppliers.supplier_id"}, system="SAP_Ariba")
    ctx.anom("supplier_certifications", sc.certificate_id.values[ex], "Governance", "Expired certifications presented as valid", "High", "Expired", "Valid", "Supplier portal not refreshed", "valid_to < as-of date", "Request renewed certificate", family="Governance_Anomalies")
    ctx.anom("supplier_certifications", sc.certificate_id.values[dpl], "Governance", "Duplicate certificate serial numbers", "High", "unique", sc.certificate_serial.values[dpl], "Copied certificate", "Serial uniqueness", "Verify with certification body", related=sc.certificate_id.values[src], family="Governance_Anomalies")
    # questionnaires (supplier + customer)
    nq = 3000
    qs = sup.iloc[rng.choice(ns, nq, replace=False)]
    sq = pd.DataFrame(dict(questionnaire_id=ids("SQ-", nq, 5), supplier_id=qs.supplier_id.values, sent_date=rand_dates(rng, nq), q_has_climate_policy=rng.choice(["Yes", "No", None], nq, p=[.55, .25, .2]),
                           q_scope1_disclosed=rng.choice(["Yes", "No", None], nq, p=[.4, .4, .2]), q_renewable_pct=np.where(rng.random(nq) < 0.75, np.round(rng.uniform(0, 100, nq)), np.nan),
                           q_iso14001=rng.choice(["Yes", "No", None], nq, p=[.45, .4, .15]), q_child_labour_policy=rng.choice(["Yes", None], nq, p=[.85, .15]),
                           q_material_origin_country=np.where(rng.random(nq) < 0.7, rng.choice([c[0] for c in COUNTRIES], nq), None)))
    sq["completion_pct"] = np.round(100 * sq.notna().mean(axis=1), 1)
    sq["status"] = np.where(sq.completion_pct < 100, "Incomplete", "Complete")
    ctx.save(sq, "Procurement/Supplier_Assessments/supplier_esg_questionnaires.csv", "supplier_questionnaires", pk="questionnaire_id", fks={"supplier_id": "suppliers.supplier_id"}, system="SUPPLIER_PORTAL")
    ncr = 3000
    cc = cust.iloc[:ncr]
    creq = pd.DataFrame(dict(requirement_id=ids("CREQ-", ncr, 5), customer_id=cc.customer_id.values, requirement_type=rng.choice(["Product carbon footprint", "Recycled content minimum", "Renewable electricity usage", "Supplier sustainability programme",
                                                                                                                     "Environmental certification", "Packaging sustainability", "SBTi-aligned targets", "Product lifecycle (LCA) data"], ncr),
                             threshold=rng.choice(["<= 2.0 kgCO2e/kg", ">= 30% recycled", ">= 50% RE by 2027", "ISO 14001 at all sites", "100% recyclable packaging", "-42% by 2030 vs 2022", "EPD available", None], ncr),
                             effective_date=pd.to_datetime(rng.choice(pd.date_range("2022-01-01", "2026-06-01"), ncr)), compliance_status=rng.choice(["Compliant", "Partially compliant", "Non-compliant", "Unknown"], ncr, p=[.4, .3, .1, .2])))
    ctx.save(creq, "CRM/Sustainability_Requirements/customer_sustainability_requirements.csv", "customer_requirements", pk="requirement_id", fks={"customer_id": "customers.customer_id"}, system="SALESFORCE")
    ncq = 1500
    cq = pd.DataFrame(dict(customer_questionnaire_id=ids("CQ-", ncq, 5), customer_id=cust.customer_id.values[rng.integers(0, 3000, ncq)], received_date=rand_dates(rng, ncq),
                           answered_scope12_tco2e=np.where(rng.random(ncq) < 0.8, np.round(rng.uniform(5e5, 9e5, ncq), -3), np.nan), answered_renewable_pct=np.where(rng.random(ncq) < 0.85, np.round(rng.uniform(15, 60, ncq), 1), np.nan),
                           product_pcf_reference_year=rng.choice([2019, 2020, 2022, 2024, 2025], ncq), status=rng.choice(["Submitted", "Draft", "Overdue"], ncq, p=[.7, .2, .1])))
    od = np.where(cq.product_pcf_reference_year <= 2020)[0]
    ctx.save(cq, "CRM/Sustainability_Requirements/customer_esg_questionnaires.csv", "customer_questionnaires", pk="customer_questionnaire_id", system="SALESFORCE")
    ctx.anom("customer_questionnaires", cq.customer_questionnaire_id.values[od], "Disclosure quality", "Outdated product sustainability information", "Low", ">= 2022 reference year", cq.product_pcf_reference_year.values[od],
             "PCF library not refreshed", "Reference-year staleness check", "Update PCF", family="Document_Anomalies", system="SALESFORCE")
    # environmental
    ga = ctx.get("ghg_activities")
    fuel = ga[(ga.scope == "Scope 1") & ga.category_id.isin(["Stationary combustion", "Mobile combustion"])].groupby(["facility_id", "reporting_year"]).co2e_kg.sum().reset_index()
    fuel["nox_t"] = np.round(fuel.co2e_kg / 1e6 * rng.uniform(1.2, 2.4, len(fuel)), 3); fuel["sox_t"] = np.round(fuel.co2e_kg / 1e6 * rng.uniform(0.05, 1.5, len(fuel)), 3)
    fuel["pm10_t"] = np.round(fuel.co2e_kg / 1e6 * rng.uniform(0.05, 0.3, len(fuel)), 3); fuel["voc_t"] = np.round(rng.lognormal(0, 1, len(fuel)), 3)
    ctx.save(fuel.drop(columns=["co2e_kg"]), "ESG_Reporting/air_pollutant_emissions.csv", "air_pollutants", fks={"facility_id": "facilities.facility_id"}, system="EHS")
    mfg = fac[fac.facility_type == "Manufacturing"]
    ni = 320
    ei = pd.DataFrame(dict(incident_id=ids("ENVINC-", ni, 4), facility_id=mfg.facility_id.values[rng.integers(0, len(mfg), ni)], incident_date=rand_dates(rng, ni, business=False),
                           incident_type=rng.choice(["Spill (oil)", "Permit exceedance (wastewater)", "Air emission exceedance", "Refrigerant release", "Odour complaint", "Hazardous waste mislabelling"], ni),
                           severity=rng.choice(["Minor", "Moderate", "Major"], ni, p=[.7, .25, .05]), reported_to_regulator=rng.random(ni) < 0.3, fine_usd=np.where(rng.random(ni) < 0.12, np.round(rng.lognormal(9.5, 1, ni), -2), 0),
                           corrective_action_id=np.char.add("CAPA-", rng.integers(10 ** 4, 10 ** 5, ni).astype(str)), status=rng.choice(["Closed", "Open"], ni, p=[.85, .15])))
    ctx.save(ei, "ESG_Reporting/environmental_incidents.csv", "environmental_incidents", pk="incident_id", fks={"facility_id": "facilities.facility_id"}, system="EHS")
    pm = mfg.loc[mfg.index.repeat(rng.integers(2, 6, len(mfg)))]
    iss = pd.to_datetime(rng.choice(pd.date_range("2017-01-01", "2025-06-01"), len(pm)))
    perm = pd.DataFrame(dict(permit_id=ids("PERM-", len(pm), 4), facility_id=pm.facility_id.values, permit_type=rng.choice(["Air emissions", "Wastewater discharge", "Water abstraction", "Hazardous waste storage", "GHG emissions (ETS-like)"], len(pm)),
                             issuing_authority=pm.country_id.values + " Environmental Agency (synthetic)", issue_date=iss, expiry_date=iss + pd.DateOffset(years=5), compliance_status=rng.choice(["Compliant", "Compliant", "Compliant", "Minor deviation", "Non-compliant"], len(pm))))
    ctx.save(perm, "ESG_Reporting/environmental_permits.csv", "environmental_permits", pk="permit_id", fks={"facility_id": "facilities.facility_id"}, system="EHS")
    bio = fac[["facility_id", "floor_area_m2"]].copy(); bio["site_area_ha"] = np.round(bio.floor_area_m2 / 10000 * rng.uniform(1.5, 4, len(bio)), 2)
    bio["distance_to_protected_area_km"] = np.round(rng.lognormal(2.5, 1, len(bio)), 1); bio["impervious_surface_pct"] = np.round(rng.uniform(40, 95, len(bio)), 1)
    bio["biodiversity_action_plan"] = bio.distance_to_protected_area_km < 5
    ctx.save(bio, "ESG_Reporting/biodiversity_land_use.csv", "biodiversity", fks={"facility_id": "facilities.facility_id"}, system="EHS")
    # social & governance
    sm = ctx.get("safety_monthly").assign(year=lambda d: d.period.str[:4].astype(int)).groupby(["facility_id", "year"]).sum(numeric_only=True).reset_index()
    sm["ltifr"] = np.round(sm.lost_time_injuries / sm.hours_worked.clip(lower=1) * 1e6, 2); sm["trir"] = np.round(sm.recordable_incidents / sm.hours_worked.clip(lower=1) * 2e5, 2)
    sm["voluntary_turnover_pct"] = np.round(rng.uniform(4, 16, len(sm)), 1); sm["engagement_score"] = np.round(rng.normal(68, 7, len(sm)), 0)
    sm["training_hours_per_fte"] = np.round(rng.uniform(8, 40, len(sm)), 1); sm["community_investment_usd"] = np.round(rng.lognormal(10, 0.8, len(sm)), -2)
    ctx.save(sm, "ESG_Reporting/social_performance_facility_year.csv", "social_kpis", fks={"facility_id": "facilities.facility_id"}, system="HRMS")
    nr = 260
    rr = pd.DataFrame(dict(risk_id=ids("RSK-", nr, 4), risk_category=rng.choice(["Climate transition", "Climate physical", "Regulatory (ESG reporting)", "Supply chain human rights", "Data quality / greenwashing", "Anti-corruption", "Water stress"], nr),
                           description="Synthetic risk statement", owner_department=rng.choice(["EHS & Sustainability", "Finance", "Procurement", "Legal & Compliance", "Operations"], nr),
                           likelihood=rng.integers(1, 6, nr), impact=rng.integers(1, 6, nr), mitigation_plan_id=np.char.add("MIT-", rng.integers(1000, 9999, nr).astype(str)),
                           review_date=rand_dates(rng, nr), status=rng.choice(["Open", "Mitigating", "Closed"], nr, p=[.35, .45, .2])))
    rr["risk_score"] = rr.likelihood * rr.impact
    ctx.save(rr, "ESG_Reporting/governance_risk_register.csv", "risk_register", pk="risk_id", system="GRC")
    na = 420
    ia = pd.DataFrame(dict(audit_observation_id=ids("IAO-", na, 4), audit_type=rng.choice(["Internal audit", "External audit (financial)", "External assurance (ESG)", "Compliance assessment", "Business ethics review"], na, p=[.5, .15, .15, .12, .08]),
                           facility_id=fac.facility_id.values[rng.integers(0, len(fac), na)], observation_date=rand_dates(rng, na),
                           finding=rng.choice(["Utility invoices not reconciled to meter data", "Missing evidence for refrigerant top-ups", "Emission factor library outdated", "Manual spreadsheet without review",
                                               "Supplier certificate expired", "Segregation of duties in AP", "Anti-corruption training overdue", "Waste certificate missing"], na),
                           rating=rng.choice(["Low", "Medium", "High"], na, p=[.45, .4, .15]), responsible_department=rng.choice(["Finance", "EHS & Sustainability", "Procurement", "Operations"], na),
                           corrective_action_due=lambda: None, closure_status=rng.choice(["Closed", "Open", "Overdue"], na, p=[.6, .3, .1]), evidence_document_id=np.where(rng.random(na) < 0.85, np.char.add("DOC-AUD-", np.arange(na).astype(str)), None)))
    ia["corrective_action_due"] = ia.observation_date + pd.to_timedelta(rng.integers(30, 180, na), "D")
    ctx.save(ia, "ESG_Reporting/audit_and_compliance_observations.csv", "audit_observations", pk="audit_observation_id", system="GRC")
    gov = pd.DataFrame([dict(record_id=f"BRD-{y}-Q{q}", meeting_date=f"{y}-{q * 3:02d}-20", body="Board of Directors", esg_agenda_items=int(rng.integers(1, 5)), climate_risk_reviewed=bool(rng.random() < 0.6 + 0.08 * (y - 2022)),
                              independent_directors_pct=round(float(rng.uniform(55, 75)), 1), women_on_board_pct=round(float(rng.uniform(25, 42)), 1)) for y in YEARS for q in range(1, 5)])
    ctx.save(gov, "ESG_Reporting/board_governance_records.csv", "board_governance", pk="record_id", system="GRC")
    pol = pd.DataFrame([dict(policy_id=f"POL-{i:02d}", title=t, version=f"{1 + i % 3}.{i % 4}", approved_date=f"{2021 + i % 5}-0{1 + i % 9}-15", owner="Group Sustainability (synthetic)")
                        for i, t in enumerate(["Climate & Energy Policy", "Environmental Claims Policy", "Supplier Code of Conduct", "Anti-Bribery & Corruption Policy", "Human Rights Policy", "Water Stewardship Policy",
                                               "Carbon Credit Procurement Policy", "Data Quality & ESG Controls Policy", "Biodiversity Policy", "Health & Safety Policy"])])
    ctx.save(pol, "ESG_Reporting/esg_governance_policies.csv", "esg_policies", pk="policy_id", system="DMS")
    gen_decarb_credits(ctx, ga, rng)


def gen_decarb_credits(ctx, ga, rng):
    fac = ctx.get("facilities").set_index("facility_id")
    inc = ga[ga.included_in_inventory & (ga.reporting_year == 2024)]
    base = inc.groupby(["facility_id", "scope", "category_id", "activity_type"]).co2e_kg.sum().div(1000).rename("t").reset_index()
    OPP = [("Renewable electricity procurement (PPA)", "Scope 2", "Purchased electricity", None, "Substitute", (0.5, 0.9), 0.0, -2.0, "Grid electricity", "Wind/solar PPA"),
           ("Coal to renewable electricity / electric kiln assist", "Scope 1", "Stationary combustion", "coal", "Substitute", (0.2, 0.45), 420.0, 30.0, "Coal-fired kiln", "Electric kiln + biomass"),
           ("Fossil-fuel boilers to electrified heating (heat pumps)", "Scope 1", "Stationary combustion", "natural_gas", "Directly reduce", (0.4, 0.75), 180.0, 12.0, "Gas boiler", "Industrial heat pump"),
           ("Heat recovery from process exhaust", "Scope 1", "Stationary combustion", "natural_gas", "Directly reduce", (0.08, 0.2), 60.0, -25.0, "No heat recovery", "Waste-heat recovery"),
           ("Compressed-air optimisation & leak repair", "Scope 2", "Purchased electricity", None, "Avoid", (0.03, 0.08), 15.0, -40.0, "Leaking compressed-air network", "VSD compressors + leak programme"),
           ("High-efficiency motors (IE4) & VSDs", "Scope 2", "Purchased electricity", None, "Directly reduce", (0.04, 0.1), 45.0, -35.0, "IE2 motors", "IE4 motors"),
           ("Production scheduling optimisation", "Scope 2", "Purchased electricity", None, "Avoid", (0.02, 0.05), 5.0, -20.0, "Static scheduling", "AI scheduling"),
           ("Diesel to electric vehicles", "Scope 1", "Mobile combustion", "diesel", "Substitute", (0.3, 0.7), 260.0, -15.0, "Diesel fleet", "BEV fleet + charging"),
           ("High-GWP refrigerants to lower-GWP alternatives", "Scope 1", "Fugitive emissions (refrigerants)", None, "Substitute", (0.6, 0.95), 90.0, 2.0, "R-404A/R-410A", "R-1234ze/R-744"),
           ("Conventional steel to low-carbon steel", "Scope 3", "S3-C01", "hot_rolled_steel_coil", "Substitute", (0.25, 0.55), 0.0, 35.0, "BF-BOF steel", "EAF low-carbon steel"),
           ("Primary to recycled aluminium", "Scope 3", "S3-C01", "aluminium_ingot_primary", "Substitute", (0.5, 0.8), 0.0, 5.0, "Primary aluminium", "Recycled aluminium"),
           ("Conventional cement to lower-carbon cement (clinker substitution)", "Scope 1", "Process emissions", "cement_clinker_calcination", "Substitute", (0.1, 0.3), 120.0, -5.0, "CEM I", "CEM II/C-M (LC3)"),
           ("Material yield improvement / circular manufacturing", "Scope 3", "S3-C05", None, "Avoid", (0.15, 0.4), 30.0, -30.0, "High-scrap process", "Closed-loop scrap"),
           ("Air freight to sea or rail", "Scope 3", "S3-C04", "Air", "Avoid", (0.6, 0.9), 0.0, -50.0, "Air freight", "Sea/rail freight")]
    rows = []
    for name, sc, cat, act, hier, (lo, hi), capex_per_t, opex_per_t, ex, alt in OPP:
        b = base[(base.scope == sc) & (base.category_id == cat)]
        if act:
            b = b[b.activity_type == act]
        b = b.groupby("facility_id").t.sum()
        b = b[b > 1].sort_values(ascending=False).head(25)
        for fid, bt in b.items():
            for scen, f in [("Conservative", 0.6), ("Base", 1.0), ("Ambitious", 1.3)]:
                pct = min(0.98, rng.uniform(lo, hi) * f)
                red = bt * pct
                capex = red * (capex_per_t if capex_per_t else 5) * rng.uniform(0.7, 1.4) * (1 / f ** 0.3)
                sav = -red * opex_per_t * rng.uniform(0.8, 1.2)
                rows.append(dict(opportunity_group=f"{name[:24]}|{fid}", opportunity_name=name, scenario=scen, enterprise_id="ENT-0001", facility_id=fid, business_unit_id=fac.business_unit_id.get(fid),
                                 decarbonisation_hierarchy=hier, scope=sc, category_id=cat, existing_technology=ex, proposed_alternative=alt, baseline_year=2024, baseline_emissions_tco2e=round(bt, 2),
                                 expected_emissions_tco2e=round(bt - red, 2), absolute_reduction_tco2e=round(red, 2), percentage_reduction=round(100 * pct, 2), implementation_cost_usd=round(capex, -2),
                                 annual_cost_savings_usd=round(sav, -1), operating_cost_impact_usd=round(-sav, -1), payback_years=(round(capex / sav, 1) if sav > 0 else None),
                                 implementation_timeline_months=int(rng.integers(3, 36)), technical_feasibility=rng.choice(["High", "Medium", "Low"], p=[.45, .4, .15]),
                                 supplier_availability=rng.choice(["Available", "Limited", "Constrained"], p=[.6, .3, .1]), confidence_score=round(float(rng.uniform(0.4, 0.9) * (1.1 - 0.2 * (f - 1))), 2),
                                 operational_constraints=rng.choice(["Requires shutdown window", "Grid connection upgrade", "Customer qualification", "None identified"]),
                                 evidence_reference=f"DOC-EA-{fid}", lifecycle_emissions_note="Embodied emissions of equipment excluded (synthetic)"))
    op = pd.DataFrame(rows)
    op.insert(0, "opportunity_id", ids("OPP-DC-", len(op), 5))
    op["interaction_adjusted_reduction_tco2e"] = op.absolute_reduction_tco2e
    order = {"Avoid": 0, "Directly reduce": 1, "Substitute": 2}
    bs = op[op.scenario == "Base"].assign(o=lambda d: d.decarbonisation_hierarchy.map(order)).sort_values(["facility_id", "scope", "category_id", "o"])
    for (f, s, c), g in bs.groupby(["facility_id", "scope", "category_id"]):
        rem = g.baseline_emissions_tco2e.iloc[0]
        for i, r in g.iterrows():
            adj = rem * r.percentage_reduction / 100
            op.loc[i, "interaction_adjusted_reduction_tco2e"] = round(adj, 2); rem -= adj
    op["overlap_note"] = "Adjusted sequentially in hierarchy order within facility/scope/category (Base scenario) to avoid double counting"
    ctx.save(op, "Decarbonisation/decarbonisation_opportunities.csv", "decarbonisation", pk="opportunity_id", fks={"facility_id": "facilities.facility_id"}, system="SUSTAINABILITY_PLANNING")
    # carbon credits
    ptypes = [("Afforestation", "Removal", 0.25), ("Reforestation", "Removal", 0.2), ("Mangrove Restoration", "Removal", 0.3), ("Direct Air Capture", "Removal", 0.02), ("Biochar", "Removal", 0.05),
              ("Methane Capture", "Avoidance", 0.05), ("Improved Forest Management", "Avoidance/Removal", 0.35), ("Verified Industrial Carbon Removal", "Removal", 0.03)]
    npj = 48
    pt = [ptypes[i % 8] for i in range(npj)]
    pj = pd.DataFrame(dict(project_id=ids("CCP-", npj, 3), project_name=[f"{p[0]} Project {i + 1} (SYNTHETIC)" for i, p in enumerate(pt)], project_type=[p[0] for p in pt], credit_class=[p[1] for p in pt],
                           project_location=rng.choice(["BR", "IN", "ID-synthetic", "KE-synthetic", "US", "SE", "AU", "CO-synthetic"], npj), registry=rng.choice(["SynthVerra-like Registry", "SynthGold Registry", "SynthPuro-like Registry"], npj),
                           methodology=[f"SYN-METH-{p[0][:4].upper()}-0{i % 4 + 1}" for i, p in enumerate(pt)], vintage_year=rng.choice([2019, 2020, 2021, 2022, 2023, 2024, 2025], npj),
                           credits_issued=rng.integers(20000, 900000, npj), verification_status=rng.choice(["Verified", "Verified", "Pending verification", "Verification lapsed"], npj),
                           additionality_assessment=rng.choice(["Robust", "Moderate", "Questionable"], npj, p=[.4, .4, .2]), permanence_risk=[("Low" if p[0] in ("Direct Air Capture", "Biochar", "Verified Industrial Carbon Removal") else "Medium-High") for p in pt],
                           reversal_risk_buffer_pct=[p[2] * 100 for p in pt], leakage_risk=rng.choice(["Low", "Medium", "High"], npj), corresponding_adjustment=rng.choice(["Applied", "Not applied", "Unknown"], npj, p=[.25, .6, .15]),
                           price_usd_per_t=[round(float(rng.uniform(300, 700) if p[0] == "Direct Air Capture" else rng.uniform(90, 180) if p[1] == "Removal" and p[0] in ("Biochar", "Verified Industrial Carbon Removal") else rng.uniform(4, 35)), 2) for p in pt], synthetic_flag=True))
    pj["credits_available"] = (pj.credits_issued * rng.uniform(0.1, 0.7, npj)).astype(int)
    ctx.save(pj, "Carbon_Credits/carbon_credit_projects.csv", "credit_projects", pk="project_id", system="CARBON_REGISTRY")
    inv = ctx.get("ghg_inventory")
    s12 = inv[(inv.scope == "Scope 1") | ((inv.scope == "Scope 2") & (inv.scope2_method == "market-based"))].groupby("reporting_year").tco2e.sum()
    tx = []
    for y in YEARS:
        target = s12[y] * {2022: 0.0, 2023: 0.02, 2024: 0.05, 2025: 0.12, 2026: 0.2}[y]
        while target >= 1:
            p = pj.iloc[rng.integers(npj)]
            q = int(min(target, rng.integers(2000, 40000)))
            tx.append(dict(project_id=p.project_id, purchase_year=y, credits_purchased=q, price_usd_per_t=p.price_usd_per_t, vintage_year=p.vintage_year, credit_class=p.credit_class))
            target -= q
    cp = pd.DataFrame(tx)
    cp.insert(0, "credit_transaction_id", ids("CCT-", len(cp), 5))
    cp["serial_number_block"] = [f"SYN-{pid}-{v}-{rng.integers(10 ** 8, 10 ** 9)}-{q}" for pid, v, q in zip(cp.project_id, cp.vintage_year, cp.credits_purchased)]
    cp["credits_retired"] = np.where(rng.random(len(cp)) < 0.85, cp.credits_purchased, (cp.credits_purchased * 0.5).astype(int))
    cp["retirement_date"] = pd.to_datetime(cp.purchase_year.astype(str) + "-12-20")
    cp["retirement_certificate_ref"] = np.char.add("RETCERT-", np.arange(len(cp)).astype(str))
    cp["retirement_beneficiary"] = "Halvorsen-Kaito Industrial Holdings plc (SYNTHETIC)"
    cp["evidence_document_id"] = np.where(rng.random(len(cp)) < 0.9, np.char.add("DOC-CC-", np.arange(len(cp)).astype(str)), None)
    dd = cp.sample(min(4, len(cp)), random_state=2).copy(); dd["credit_transaction_id"] = ids("CCT-", len(dd), 5, start=len(cp) + 1); dd["purchase_year"] = dd.purchase_year.clip(upper=2025) + 1
    cp = pd.concat([cp, dd], ignore_index=True)
    lapsed = cp.project_id.isin(pj[pj.verification_status != "Verified"].project_id)
    ctx.save(cp, "Carbon_Credits/carbon_credit_transactions.csv", "credit_transactions", pk="credit_transaction_id", fks={"project_id": "credit_projects.project_id"}, system="CARBON_REGISTRY")
    ctx.anom("credit_transactions", dd.credit_transaction_id.values, "Governance", "Double-counted credits (same serial retired in two years)", "Critical", "unique serial block", dd.serial_number_block.values,
             "Retirement re-claimed in following year report", "Serial uniqueness across years", "Remove second claim", family="Governance_Anomalies", system="CARBON_REGISTRY")
    ctx.anom("credit_transactions", cp.credit_transaction_id.values[lapsed], "Governance", "Unverified carbon offsets counted", "High", "Verified", "Unverified / lapsed", "Pending or lapsed verification", "Project verification status",
             "Exclude from neutralisation claims", family="Governance_Anomalies", system="CARBON_REGISTRY")
    # neutralisation ledger
    gross = inv.groupby(["reporting_year", "scope", "scope2_method"], dropna=False).tco2e.sum().reset_index()
    led = []
    b22 = None
    for y in YEARS:
        g = gross[gross.reporting_year == y]
        s1 = g[g.scope == "Scope 1"].tco2e.sum(); s2m = g[(g.scope == "Scope 2") & (g.scope2_method == "market-based")].tco2e.sum(); s3 = g[g.scope == "Scope 3"].tco2e.sum()
        tot = s1 + s2m
        b22 = b22 or tot
        c = cp[cp.purchase_year == y].drop_duplicates("serial_number_block") if False else cp[cp.purchase_year == y]
        valid = c[~c.project_id.isin(pj[pj.verification_status != "Verified"].project_id)]
        led.append(dict(reporting_year=y, gross_scope1_tco2e=round(s1, 1), gross_scope2_market_tco2e=round(s2m, 1), gross_scope3_tco2e=round(s3, 1),
                        actual_inventory_reduction_vs_2022_tco2e=round(b22 - tot, 1), avoided_emissions_tco2e_not_deducted=round(s3 * 0.004, 1), residual_scope12_tco2e=round(tot, 1),
                        credits_purchased_t=int(c.credits_purchased.sum()), credits_retired_t=int(c.credits_retired.sum()), credits_retired_valid_t=int(valid.credits_retired.sum()),
                        removal_credits_retired_t=int(valid[valid.credit_class == "Removal"].credits_retired.sum()), avoidance_credits_retired_t=int(valid[valid.credit_class != "Removal"].credits_retired.sum()),
                        remaining_neutralisation_requirement_tco2e=round(max(0, tot - valid[valid.credit_class == "Removal"].credits_retired.sum()), 1),
                        neutrality_status="Not carbon neutral (credits do not reduce inventory; residual removal requirement remains)"))
    ld = pd.DataFrame(led)
    ctx.save(ld, "Carbon_Credits/neutralisation_ledger.csv", "neutralisation_ledger", pk="reporting_year", system="SUSTAINABILITY_PLANNING")
    cl = pd.DataFrame([dict(claim_id="CLM-001", channel="Corporate ESG report 2025", claim_text="Our operations were carbon neutral in 2025.", reporting_year=2025, approval_status="Approved by marketing only", supported=False),
                       dict(claim_id="CLM-002", channel="Product brochure", claim_text="Eco-line motors cut emissions 40% vs 2022.", reporting_year=2025, approval_status="Pending legal", supported=False),
                       dict(claim_id="CLM-003", channel="Corporate ESG report 2024", claim_text="Scope 1+2 market-based emissions reduced vs 2022 baseline.", reporting_year=2024, approval_status="Approved", supported=True),
                       dict(claim_id="CLM-004", channel="Investor presentation", claim_text="100% renewable electricity at all European sites.", reporting_year=2026, approval_status="Approved", supported=False),
                       dict(claim_id="CLM-005", channel="Customer questionnaire", claim_text="Net-zero across value chain by 2026 via offsets.", reporting_year=2026, approval_status="Not reviewed", supported=False)])
    ctx.save(cl, "ESG_Reporting/environmental_claims_register.csv", "environmental_claims", pk="claim_id", system="DMS")
    for cid, sub, exp, act in [("CLM-001", "Unsupported carbon-neutral claims", f"Residual {ld.loc[ld.reporting_year == 2025, 'residual_scope12_tco2e'].iloc[0]} tCO2e; valid removals {ld.loc[ld.reporting_year == 2025, 'removal_credits_retired_t'].iloc[0]} t", "Carbon neutral"),
                               ("CLM-002", "Unsupported emission-reduction claims", "No product LCA evidence", "-40%"), ("CLM-004", "Incomplete environmental disclosures", "EAC coverage < 100% at EU sites", "100% RE"),
                               ("CLM-005", "Incorrect carbon credit retirement claims / net-zero via offsets", "Net-zero requires deep reduction; credits only for residual", "Net-zero 2026")]:
        ctx.anom("environmental_claims", [cid], "Governance", sub, "Critical", exp, act, "Claim not reconciled with inventory", "Claim vs ledger reconciliation", "Withdraw or qualify claim", family="Governance_Anomalies", system="DMS")
    k = pd.DataFrame(dict(reporting_year=YEARS))
    rev = ctx.get("profit_and_loss").query("gl_account == '400000'").groupby("year").line_amount_usd.sum()
    k["revenue_usd_sample_scale"] = rev.reindex(YEARS).values
    k["scope1_tco2e"] = ld.gross_scope1_tco2e.values; k["scope2_market_tco2e"] = ld.gross_scope2_market_tco2e.values
    k["scope2_location_tco2e"] = inv[(inv.scope == "Scope 2") & (inv.scope2_method == "location-based")].groupby("reporting_year").tco2e.sum().reindex(YEARS).round(1).values
    k["scope3_tco2e"] = ld.gross_scope3_tco2e.values
    k["intensity_s12_t_per_musd"] = np.round((k.scope1_tco2e + k.scope2_market_tco2e) / (k.revenue_usd_sample_scale / 1e6), 3)
    w = ctx.get("water_monthly").assign(y=lambda d: d.period.str[:4].astype(int)).groupby("y").withdrawal_m3.sum()
    ws = ctx.get("waste_records").assign(y=lambda d: d.period.str[:4].astype(int))
    k["water_withdrawal_m3"] = w.reindex(YEARS).round(0).values
    k["waste_total_t"] = ws.groupby("y").quantity.sum().reindex(YEARS).round(1).values
    k["waste_diversion_pct"] = (100 * ws[ws.disposal_method == "recycling"].groupby("y").quantity.sum() / ws.groupby("y").quantity.sum()).reindex(YEARS).round(1).values
    ins = ctx.get("contractual_instruments")
    el = inv[(inv.scope == "Scope 2")]
    k["eac_mwh_allocated"] = ins.groupby("allocation_year").mwh.sum().reindex(YEARS).fillna(0).round(0).values
    ctx.save(k, "ESG_Reporting/esg_kpi_summary.csv", "esg_kpis", pk="reporting_year", system="ESG_REPORTING")
