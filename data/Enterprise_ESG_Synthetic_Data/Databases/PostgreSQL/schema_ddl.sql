-- SYNTHETIC PostgreSQL schema export generated for testing

CREATE TABLE suppliers (
  supplier_id TEXT,
  erp_vendor_no TEXT,
  srm_supplier_ref TEXT,
  supplier_name TEXT,
  country_id TEXT,
  supplier_category TEXT,
  tier BIGINT,
  onboarding_date TIMESTAMP,
  termination_date TIMESTAMP,
  payment_terms TEXT,
  currency TEXT,
  risk_rating TEXT,
  data_maturity TEXT,
  synthetic_id_tax TEXT,
  synthetic_flag BOOLEAN,
  status TEXT,
  CONSTRAINT pk_suppliers PRIMARY KEY (supplier_id)
);
ALTER TABLE suppliers ADD CONSTRAINT fk_suppliers_country_id FOREIGN KEY (country_id) REFERENCES countries(country_id);

CREATE TABLE materials (
  material_id TEXT,
  sap_matnr TEXT,
  material_family TEXT,
  material_group TEXT,
  base_unit TEXT,
  description TEXT,
  standard_price_usd NUMERIC(20,6),
  recycled_content_pct NUMERIC(20,6),
  hazardous_flag BOOLEAN,
  weight_kg_per_unit NUMERIC(20,6),
  synthetic_flag BOOLEAN,
  primary_supplier_id TEXT,
  secondary_supplier_id TEXT,
  CONSTRAINT pk_materials PRIMARY KEY (material_id)
);
ALTER TABLE materials ADD CONSTRAINT fk_materials_primary_supplier_id FOREIGN KEY (primary_supplier_id) REFERENCES suppliers(supplier_id);
ALTER TABLE materials ADD CONSTRAINT fk_materials_secondary_supplier_id FOREIGN KEY (secondary_supplier_id) REFERENCES suppliers(supplier_id);

CREATE TABLE purchase_orders (
  po_id TEXT,
  sap_ebeln TEXT,
  po_date TIMESTAMP,
  supplier_id TEXT,
  facility_id TEXT,
  legal_entity_id TEXT,
  po_type TEXT,
  currency TEXT,
  payment_terms TEXT,
  incoterm TEXT,
  plant_id TEXT,
  contract_id TEXT,
  pr_id TEXT,
  approval_status TEXT,
  approval_date TIMESTAMP,
  approved_by_role TEXT,
  delivery_terms_days BIGINT,
  total_net_amount NUMERIC(20,6),
  source_system TEXT,
  source_application TEXT,
  source_database TEXT,
  source_table TEXT,
  source_record_id TEXT,
  data_owner TEXT,
  source_record_timestamp TIMESTAMP,
  ingestion_timestamp TIMESTAMP,
  processing_timestamp TIMESTAMP,
  schema_version TEXT,
  transformation_version TEXT,
  CONSTRAINT pk_purchase_orders PRIMARY KEY (po_id)
);
ALTER TABLE purchase_orders ADD CONSTRAINT fk_purchase_orders_supplier_id FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id);
ALTER TABLE purchase_orders ADD CONSTRAINT fk_purchase_orders_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE purchase_orders ADD CONSTRAINT fk_purchase_orders_contract_id FOREIGN KEY (contract_id) REFERENCES supplier_contracts(contract_id);
CREATE INDEX ix_purchase_orders_src ON purchase_orders (source_record_id);
CREATE TABLE po_lines (
  po_line_id TEXT,
  po_id TEXT,
  line_no BIGINT,
  material_id TEXT,
  service_category TEXT,
  order_qty NUMERIC(20,6),
  unit TEXT,
  unit_price NUMERIC(20,6),
  currency TEXT,
  discount_pct BIGINT,
  net_amount NUMERIC(20,6),
  tax_rate_pct BIGINT,
  requested_delivery_date TIMESTAMP,
  gl_account TEXT,
  cost_centre_id TEXT,
  CONSTRAINT pk_po_lines PRIMARY KEY (po_line_id)
);
ALTER TABLE po_lines ADD CONSTRAINT fk_po_lines_po_id FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id);
ALTER TABLE po_lines ADD CONSTRAINT fk_po_lines_material_id FOREIGN KEY (material_id) REFERENCES materials(material_id);
ALTER TABLE po_lines ADD CONSTRAINT fk_po_lines_cost_centre_id FOREIGN KEY (cost_centre_id) REFERENCES cost_centres(cost_centre_id);

CREATE TABLE goods_receipts (
  grn_id TEXT,
  sap_mblnr TEXT,
  po_id TEXT,
  po_line_id TEXT,
  receipt_date TIMESTAMP,
  posting_date TIMESTAMP,
  facility_id TEXT,
  material_id TEXT,
  received_qty NUMERIC(20,6),
  rejected_qty NUMERIC(20,6),
  unit TEXT,
  movement_type TEXT,
  storage_location TEXT,
  batch_no TEXT,
  accepted_qty NUMERIC(20,6),
  source_system TEXT,
  source_application TEXT,
  source_database TEXT,
  source_table TEXT,
  source_record_id TEXT,
  data_owner TEXT,
  source_record_timestamp TIMESTAMP,
  ingestion_timestamp TIMESTAMP,
  processing_timestamp TIMESTAMP,
  schema_version TEXT,
  transformation_version TEXT,
  CONSTRAINT pk_goods_receipts PRIMARY KEY (grn_id)
);
ALTER TABLE goods_receipts ADD CONSTRAINT fk_goods_receipts_po_line_id FOREIGN KEY (po_line_id) REFERENCES po_lines(po_line_id);
ALTER TABLE goods_receipts ADD CONSTRAINT fk_goods_receipts_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE goods_receipts ADD CONSTRAINT fk_goods_receipts_material_id FOREIGN KEY (material_id) REFERENCES materials(material_id);
CREATE INDEX ix_goods_receipts_src ON goods_receipts (source_record_id);
CREATE TABLE ap_invoices (
  invoice_id TEXT,
  sap_belnr TEXT,
  supplier_invoice_no TEXT,
  supplier_id TEXT,
  po_id TEXT,
  facility_id TEXT,
  legal_entity_id TEXT,
  currency TEXT,
  payment_terms TEXT,
  invoice_date TIMESTAMP,
  posting_date TIMESTAMP,
  net_amount NUMERIC(20,6),
  tax_amount NUMERIC(20,6),
  document_type TEXT,
  gross_amount NUMERIC(20,6),
  invoice_status TEXT,
  approval_date TIMESTAMP,
  service_category TEXT,
  fiscal_year BIGINT,
  fiscal_period BIGINT,
  company_code TEXT,
  source_system TEXT,
  source_application TEXT,
  source_database TEXT,
  source_table TEXT,
  source_record_id TEXT,
  data_owner TEXT,
  source_record_timestamp TIMESTAMP,
  ingestion_timestamp TIMESTAMP,
  processing_timestamp TIMESTAMP,
  schema_version TEXT,
  transformation_version TEXT,
  CONSTRAINT pk_ap_invoices PRIMARY KEY (invoice_id)
);
ALTER TABLE ap_invoices ADD CONSTRAINT fk_ap_invoices_supplier_id FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id);
ALTER TABLE ap_invoices ADD CONSTRAINT fk_ap_invoices_po_id FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id);
ALTER TABLE ap_invoices ADD CONSTRAINT fk_ap_invoices_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
CREATE INDEX ix_ap_invoices_src ON ap_invoices (source_record_id);
CREATE TABLE utility_invoices (
  utility_invoice_id TEXT,
  invoice_number TEXT,
  utility_supplier_id TEXT,
  customer_account_no TEXT,
  facility_id TEXT,
  meter_id TEXT,
  utility_type TEXT,
  billing_period_start TIMESTAMP,
  billing_period_end TIMESTAMP,
  invoice_date TIMESTAMP,
  consumption NUMERIC(20,6),
  unit TEXT,
  tariff_per_unit NUMERIC(20,6),
  currency TEXT,
  previous_reading NUMERIC(20,6),
  current_reading NUMERIC(20,6),
  energy_charge NUMERIC(20,6),
  network_charge NUMERIC(20,6),
  taxes NUMERIC(20,6),
  total_payable NUMERIC(20,6),
  green_tariff BOOLEAN,
  supplier_disclosed_ef_kg_per_kwh NUMERIC(20,6),
  source_system TEXT,
  source_application TEXT,
  source_database TEXT,
  source_table TEXT,
  source_record_id TEXT,
  data_owner TEXT,
  source_record_timestamp TIMESTAMP,
  ingestion_timestamp TIMESTAMP,
  processing_timestamp TIMESTAMP,
  schema_version TEXT,
  transformation_version TEXT,
  CONSTRAINT pk_utility_invoices PRIMARY KEY (utility_invoice_id)
);
ALTER TABLE utility_invoices ADD CONSTRAINT fk_utility_invoices_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE utility_invoices ADD CONSTRAINT fk_utility_invoices_meter_id FOREIGN KEY (meter_id) REFERENCES meters(meter_id);
ALTER TABLE utility_invoices ADD CONSTRAINT fk_utility_invoices_utility_supplier_id FOREIGN KEY (utility_supplier_id) REFERENCES suppliers(supplier_id);
CREATE INDEX ix_utility_invoices_src ON utility_invoices (source_record_id);
CREATE TABLE meters (
  meter_id TEXT,
  facility_id TEXT,
  utility_type TEXT,
  meter_level TEXT,
  linked_entity_id TEXT,
  unit TEXT,
  serial_no TEXT,
  utility_account_no TEXT,
  protocol TEXT,
  install_date TIMESTAMP,
  last_calibration_date TIMESTAMP,
  CONSTRAINT pk_meters PRIMARY KEY (meter_id)
);
ALTER TABLE meters ADD CONSTRAINT fk_meters_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);

CREATE TABLE facilities (
  facility_id TEXT,
  facility_name TEXT,
  facility_type TEXT,
  country_id TEXT,
  city TEXT,
  address TEXT,
  latitude NUMERIC(20,6),
  longitude NUMERIC(20,6),
  division_id TEXT,
  business_unit_id TEXT,
  legal_entity_id TEXT,
  time_zone TEXT,
  floor_area_m2 BIGINT,
  tenure TEXT,
  leased_out_portion_pct NUMERIC(20,6),
  commissioning_date TIMESTAMP,
  temporary_shutdown_start TIMESTAMP,
  temporary_shutdown_end TIMESTAMP,
  divestment_date TIMESTAMP,
  energy_intensity_index NUMERIC(20,6),
  climate_zone TEXT,
  grid_region TEXT,
  operational_control BOOLEAN,
  enterprise_id TEXT,
  synthetic_flag BOOLEAN,
  CONSTRAINT pk_facilities PRIMARY KEY (facility_id)
);
ALTER TABLE facilities ADD CONSTRAINT fk_facilities_country_id FOREIGN KEY (country_id) REFERENCES countries(country_id);
ALTER TABLE facilities ADD CONSTRAINT fk_facilities_legal_entity_id FOREIGN KEY (legal_entity_id) REFERENCES legal_entities(legal_entity_id);
ALTER TABLE facilities ADD CONSTRAINT fk_facilities_business_unit_id FOREIGN KEY (business_unit_id) REFERENCES business_units(business_unit_id);

CREATE TABLE emission_factors (
  emission_factor_id TEXT,
  activity_type TEXT,
  lookup_key TEXT,
  fuel_type TEXT,
  material_type TEXT,
  product_type TEXT,
  geography TEXT,
  industry_applicability TEXT,
  factor_value NUMERIC(20,6),
  factor_unit TEXT,
  activity_unit TEXT,
  gas_type TEXT,
  co2_factor NUMERIC(20,6),
  ch4_factor NUMERIC(20,6),
  n2o_factor NUMERIC(20,6),
  gwp_basis TEXT,
  gwp_time_horizon TEXT,
  publication_year BIGINT,
  effective_date TIMESTAMP,
  expiry_date TIMESTAMP,
  version TEXT,
  source_organisation TEXT,
  source_document TEXT,
  methodology TEXT,
  uncertainty_low_pct BIGINT,
  uncertainty_high_pct NUMERIC(20,6),
  data_quality_rating BIGINT,
  synthetic_flag BOOLEAN,
  CONSTRAINT pk_emission_factors PRIMARY KEY (emission_factor_id)
);

CREATE TABLE ghg_activities (
  ghg_activity_id TEXT,
  facility_id TEXT,
  equipment_id TEXT,
  activity_type TEXT,
  activity_quantity NUMERIC(20,6),
  activity_unit TEXT,
  original_quantity NUMERIC(20,6),
  original_unit TEXT,
  period_start TIMESTAMP,
  period_end TIMESTAMP,
  calculation_method TEXT,
  source_dataset TEXT,
  source_record_id TEXT,
  source_system TEXT,
  scope TEXT,
  category_id TEXT,
  category_name TEXT,
  vehicle_id TEXT,
  assumptions TEXT,
  scope2_method TEXT,
  supplier_id TEXT,
  customer_id TEXT,
  product_id TEXT,
  reporting_year TEXT,
  reporting_period TEXT,
  emission_factor_id TEXT,
  emission_factor_value NUMERIC(20,6),
  emission_factor_unit TEXT,
  gwp_basis TEXT,
  co2e_kg NUMERIC(20,6),
  reporting_boundary TEXT,
  included_in_inventory BOOLEAN,
  data_quality_rating BIGINT,
  uncertainty_pct BIGINT,
  gas_type TEXT,
  gwp_time_horizon TEXT,
  source_document_id TEXT,
  co2e_t NUMERIC(20,6),
  source_application TEXT,
  source_database TEXT,
  source_table TEXT,
  data_owner TEXT,
  schema_version TEXT,
  transformation_version TEXT,
  CONSTRAINT pk_ghg_activities PRIMARY KEY (ghg_activity_id)
);
ALTER TABLE ghg_activities ADD CONSTRAINT fk_ghg_activities_emission_factor_id FOREIGN KEY (emission_factor_id) REFERENCES emission_factors(emission_factor_id);
ALTER TABLE ghg_activities ADD CONSTRAINT fk_ghg_activities_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
CREATE INDEX ix_ghg_activities_src ON ghg_activities (source_record_id);
CREATE TABLE customers (
  customer_id TEXT,
  crm_account_id TEXT,
  erp_sold_to TEXT,
  customer_name TEXT,
  country_id TEXT,
  segment TEXT,
  sales_territory TEXT,
  credit_limit_usd NUMERIC(20,6),
  acquisition_date TIMESTAMP,
  churn_date TIMESTAMP,
  incoterm TEXT,
  synthetic_flag BOOLEAN,
  latitude NUMERIC(20,6),
  longitude NUMERIC(20,6),
  CONSTRAINT pk_customers PRIMARY KEY (customer_id)
);
ALTER TABLE customers ADD CONSTRAINT fk_customers_country_id FOREIGN KEY (country_id) REFERENCES countries(country_id);

CREATE TABLE sales_orders (
  sales_order_id TEXT,
  crm_order_ref TEXT,
  sap_vbeln TEXT,
  customer_id TEXT,
  order_date TIMESTAMP,
  sales_territory TEXT,
  incoterm TEXT,
  currency TEXT,
  channel TEXT,
  net_value NUMERIC(20,6),
  source_system TEXT,
  source_application TEXT,
  source_database TEXT,
  source_table TEXT,
  source_record_id TEXT,
  data_owner TEXT,
  source_record_timestamp TIMESTAMP,
  ingestion_timestamp TIMESTAMP,
  processing_timestamp TIMESTAMP,
  schema_version TEXT,
  transformation_version TEXT,
  CONSTRAINT pk_sales_orders PRIMARY KEY (sales_order_id)
);
ALTER TABLE sales_orders ADD CONSTRAINT fk_sales_orders_customer_id FOREIGN KEY (customer_id) REFERENCES customers(customer_id);
CREATE INDEX ix_sales_orders_src ON sales_orders (source_record_id);
CREATE TABLE shipments (
  shipment_id TEXT,
  direction TEXT,
  ref_doc TEXT,
  po_id TEXT,
  delivery_id TEXT,
  supplier_id TEXT,
  customer_id TEXT,
  origin TEXT,
  destination TEXT,
  ship_date TIMESTAMP,
  weight_kg NUMERIC(20,6),
  incoterm TEXT,
  tms_ref TEXT,
  mode TEXT,
  distance_km NUMERIC(20,6),
  distance_unit TEXT,
  carrier_id TEXT,
  load_factor_pct NUMERIC(20,6),
  freight_paid_by TEXT,
  empty_return_km NUMERIC(20,6),
  consolidation_id TEXT,
  tkm NUMERIC(20,6),
  source_system TEXT,
  source_application TEXT,
  source_database TEXT,
  source_table TEXT,
  source_record_id TEXT,
  data_owner TEXT,
  source_record_timestamp TIMESTAMP,
  ingestion_timestamp TIMESTAMP,
  processing_timestamp TIMESTAMP,
  schema_version TEXT,
  transformation_version TEXT,
  CONSTRAINT pk_shipments PRIMARY KEY (shipment_id)
);
ALTER TABLE shipments ADD CONSTRAINT fk_shipments_carrier_id FOREIGN KEY (carrier_id) REFERENCES suppliers(supplier_id);
CREATE INDEX ix_shipments_src ON shipments (source_record_id);