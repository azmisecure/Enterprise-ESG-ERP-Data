-- SYNTHETIC MySQL schema export generated for testing

CREATE TABLE suppliers (
  supplier_id VARCHAR(255),
  erp_vendor_no VARCHAR(255),
  srm_supplier_ref VARCHAR(255),
  supplier_name VARCHAR(255),
  country_id VARCHAR(255),
  supplier_category VARCHAR(255),
  tier BIGINT,
  onboarding_date DATETIME,
  termination_date DATETIME,
  payment_terms VARCHAR(255),
  currency VARCHAR(255),
  risk_rating VARCHAR(255),
  data_maturity VARCHAR(255),
  synthetic_id_tax VARCHAR(255),
  synthetic_flag TINYINT(1),
  status VARCHAR(255),
  CONSTRAINT pk_suppliers PRIMARY KEY (supplier_id)
);
ALTER TABLE suppliers ADD CONSTRAINT fk_suppliers_country_id FOREIGN KEY (country_id) REFERENCES countries(country_id);

CREATE TABLE materials (
  material_id VARCHAR(255),
  sap_matnr VARCHAR(255),
  material_family VARCHAR(255),
  material_group VARCHAR(255),
  base_unit VARCHAR(255),
  description VARCHAR(255),
  standard_price_usd DECIMAL(20,6),
  recycled_content_pct DECIMAL(20,6),
  hazardous_flag TINYINT(1),
  weight_kg_per_unit DECIMAL(20,6),
  synthetic_flag TINYINT(1),
  primary_supplier_id VARCHAR(255),
  secondary_supplier_id VARCHAR(255),
  CONSTRAINT pk_materials PRIMARY KEY (material_id)
);
ALTER TABLE materials ADD CONSTRAINT fk_materials_primary_supplier_id FOREIGN KEY (primary_supplier_id) REFERENCES suppliers(supplier_id);
ALTER TABLE materials ADD CONSTRAINT fk_materials_secondary_supplier_id FOREIGN KEY (secondary_supplier_id) REFERENCES suppliers(supplier_id);

CREATE TABLE purchase_orders (
  po_id VARCHAR(255),
  sap_ebeln VARCHAR(255),
  po_date DATETIME,
  supplier_id VARCHAR(255),
  facility_id VARCHAR(255),
  legal_entity_id VARCHAR(255),
  po_type VARCHAR(255),
  currency VARCHAR(255),
  payment_terms VARCHAR(255),
  incoterm VARCHAR(255),
  plant_id VARCHAR(255),
  contract_id VARCHAR(255),
  pr_id VARCHAR(255),
  approval_status VARCHAR(255),
  approval_date DATETIME,
  approved_by_role VARCHAR(255),
  delivery_terms_days BIGINT,
  total_net_amount DECIMAL(20,6),
  source_system VARCHAR(255),
  source_application VARCHAR(255),
  source_database VARCHAR(255),
  source_table VARCHAR(255),
  source_record_id VARCHAR(255),
  data_owner VARCHAR(255),
  source_record_timestamp DATETIME,
  ingestion_timestamp DATETIME,
  processing_timestamp DATETIME,
  schema_version VARCHAR(255),
  transformation_version VARCHAR(255),
  CONSTRAINT pk_purchase_orders PRIMARY KEY (po_id)
);
ALTER TABLE purchase_orders ADD CONSTRAINT fk_purchase_orders_supplier_id FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id);
ALTER TABLE purchase_orders ADD CONSTRAINT fk_purchase_orders_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE purchase_orders ADD CONSTRAINT fk_purchase_orders_contract_id FOREIGN KEY (contract_id) REFERENCES supplier_contracts(contract_id);
CREATE INDEX ix_purchase_orders_src ON purchase_orders (source_record_id);
CREATE TABLE po_lines (
  po_line_id VARCHAR(255),
  po_id VARCHAR(255),
  line_no BIGINT,
  material_id VARCHAR(255),
  service_category VARCHAR(255),
  order_qty DECIMAL(20,6),
  unit VARCHAR(255),
  unit_price DECIMAL(20,6),
  currency VARCHAR(255),
  discount_pct BIGINT,
  net_amount DECIMAL(20,6),
  tax_rate_pct BIGINT,
  requested_delivery_date DATETIME,
  gl_account VARCHAR(255),
  cost_centre_id VARCHAR(255),
  CONSTRAINT pk_po_lines PRIMARY KEY (po_line_id)
);
ALTER TABLE po_lines ADD CONSTRAINT fk_po_lines_po_id FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id);
ALTER TABLE po_lines ADD CONSTRAINT fk_po_lines_material_id FOREIGN KEY (material_id) REFERENCES materials(material_id);
ALTER TABLE po_lines ADD CONSTRAINT fk_po_lines_cost_centre_id FOREIGN KEY (cost_centre_id) REFERENCES cost_centres(cost_centre_id);

CREATE TABLE goods_receipts (
  grn_id VARCHAR(255),
  sap_mblnr VARCHAR(255),
  po_id VARCHAR(255),
  po_line_id VARCHAR(255),
  receipt_date DATETIME,
  posting_date DATETIME,
  facility_id VARCHAR(255),
  material_id VARCHAR(255),
  received_qty DECIMAL(20,6),
  rejected_qty DECIMAL(20,6),
  unit VARCHAR(255),
  movement_type VARCHAR(255),
  storage_location VARCHAR(255),
  batch_no VARCHAR(255),
  accepted_qty DECIMAL(20,6),
  source_system VARCHAR(255),
  source_application VARCHAR(255),
  source_database VARCHAR(255),
  source_table VARCHAR(255),
  source_record_id VARCHAR(255),
  data_owner VARCHAR(255),
  source_record_timestamp DATETIME,
  ingestion_timestamp DATETIME,
  processing_timestamp DATETIME,
  schema_version VARCHAR(255),
  transformation_version VARCHAR(255),
  CONSTRAINT pk_goods_receipts PRIMARY KEY (grn_id)
);
ALTER TABLE goods_receipts ADD CONSTRAINT fk_goods_receipts_po_line_id FOREIGN KEY (po_line_id) REFERENCES po_lines(po_line_id);
ALTER TABLE goods_receipts ADD CONSTRAINT fk_goods_receipts_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE goods_receipts ADD CONSTRAINT fk_goods_receipts_material_id FOREIGN KEY (material_id) REFERENCES materials(material_id);
CREATE INDEX ix_goods_receipts_src ON goods_receipts (source_record_id);
CREATE TABLE ap_invoices (
  invoice_id VARCHAR(255),
  sap_belnr VARCHAR(255),
  supplier_invoice_no VARCHAR(255),
  supplier_id VARCHAR(255),
  po_id VARCHAR(255),
  facility_id VARCHAR(255),
  legal_entity_id VARCHAR(255),
  currency VARCHAR(255),
  payment_terms VARCHAR(255),
  invoice_date DATETIME,
  posting_date DATETIME,
  net_amount DECIMAL(20,6),
  tax_amount DECIMAL(20,6),
  document_type VARCHAR(255),
  gross_amount DECIMAL(20,6),
  invoice_status VARCHAR(255),
  approval_date DATETIME,
  service_category VARCHAR(255),
  fiscal_year BIGINT,
  fiscal_period BIGINT,
  company_code VARCHAR(255),
  source_system VARCHAR(255),
  source_application VARCHAR(255),
  source_database VARCHAR(255),
  source_table VARCHAR(255),
  source_record_id VARCHAR(255),
  data_owner VARCHAR(255),
  source_record_timestamp DATETIME,
  ingestion_timestamp DATETIME,
  processing_timestamp DATETIME,
  schema_version VARCHAR(255),
  transformation_version VARCHAR(255),
  CONSTRAINT pk_ap_invoices PRIMARY KEY (invoice_id)
);
ALTER TABLE ap_invoices ADD CONSTRAINT fk_ap_invoices_supplier_id FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id);
ALTER TABLE ap_invoices ADD CONSTRAINT fk_ap_invoices_po_id FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id);
ALTER TABLE ap_invoices ADD CONSTRAINT fk_ap_invoices_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
CREATE INDEX ix_ap_invoices_src ON ap_invoices (source_record_id);
CREATE TABLE utility_invoices (
  utility_invoice_id VARCHAR(255),
  invoice_number VARCHAR(255),
  utility_supplier_id VARCHAR(255),
  customer_account_no VARCHAR(255),
  facility_id VARCHAR(255),
  meter_id VARCHAR(255),
  utility_type VARCHAR(255),
  billing_period_start DATETIME,
  billing_period_end DATETIME,
  invoice_date DATETIME,
  consumption DECIMAL(20,6),
  unit VARCHAR(255),
  tariff_per_unit DECIMAL(20,6),
  currency VARCHAR(255),
  previous_reading DECIMAL(20,6),
  current_reading DECIMAL(20,6),
  energy_charge DECIMAL(20,6),
  network_charge DECIMAL(20,6),
  taxes DECIMAL(20,6),
  total_payable DECIMAL(20,6),
  green_tariff TINYINT(1),
  supplier_disclosed_ef_kg_per_kwh DECIMAL(20,6),
  source_system VARCHAR(255),
  source_application VARCHAR(255),
  source_database VARCHAR(255),
  source_table VARCHAR(255),
  source_record_id VARCHAR(255),
  data_owner VARCHAR(255),
  source_record_timestamp DATETIME,
  ingestion_timestamp DATETIME,
  processing_timestamp DATETIME,
  schema_version VARCHAR(255),
  transformation_version VARCHAR(255),
  CONSTRAINT pk_utility_invoices PRIMARY KEY (utility_invoice_id)
);
ALTER TABLE utility_invoices ADD CONSTRAINT fk_utility_invoices_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE utility_invoices ADD CONSTRAINT fk_utility_invoices_meter_id FOREIGN KEY (meter_id) REFERENCES meters(meter_id);
ALTER TABLE utility_invoices ADD CONSTRAINT fk_utility_invoices_utility_supplier_id FOREIGN KEY (utility_supplier_id) REFERENCES suppliers(supplier_id);
CREATE INDEX ix_utility_invoices_src ON utility_invoices (source_record_id);
CREATE TABLE meters (
  meter_id VARCHAR(255),
  facility_id VARCHAR(255),
  utility_type VARCHAR(255),
  meter_level VARCHAR(255),
  linked_entity_id VARCHAR(255),
  unit VARCHAR(255),
  serial_no VARCHAR(255),
  utility_account_no VARCHAR(255),
  protocol VARCHAR(255),
  install_date DATETIME,
  last_calibration_date DATETIME,
  CONSTRAINT pk_meters PRIMARY KEY (meter_id)
);
ALTER TABLE meters ADD CONSTRAINT fk_meters_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);

CREATE TABLE facilities (
  facility_id VARCHAR(255),
  facility_name VARCHAR(255),
  facility_type VARCHAR(255),
  country_id VARCHAR(255),
  city VARCHAR(255),
  address VARCHAR(255),
  latitude DECIMAL(20,6),
  longitude DECIMAL(20,6),
  division_id VARCHAR(255),
  business_unit_id VARCHAR(255),
  legal_entity_id VARCHAR(255),
  time_zone VARCHAR(255),
  floor_area_m2 BIGINT,
  tenure VARCHAR(255),
  leased_out_portion_pct DECIMAL(20,6),
  commissioning_date DATETIME,
  temporary_shutdown_start DATETIME,
  temporary_shutdown_end DATETIME,
  divestment_date DATETIME,
  energy_intensity_index DECIMAL(20,6),
  climate_zone VARCHAR(255),
  grid_region VARCHAR(255),
  operational_control TINYINT(1),
  enterprise_id VARCHAR(255),
  synthetic_flag TINYINT(1),
  CONSTRAINT pk_facilities PRIMARY KEY (facility_id)
);
ALTER TABLE facilities ADD CONSTRAINT fk_facilities_country_id FOREIGN KEY (country_id) REFERENCES countries(country_id);
ALTER TABLE facilities ADD CONSTRAINT fk_facilities_legal_entity_id FOREIGN KEY (legal_entity_id) REFERENCES legal_entities(legal_entity_id);
ALTER TABLE facilities ADD CONSTRAINT fk_facilities_business_unit_id FOREIGN KEY (business_unit_id) REFERENCES business_units(business_unit_id);

CREATE TABLE emission_factors (
  emission_factor_id VARCHAR(255),
  activity_type VARCHAR(255),
  lookup_key VARCHAR(255),
  fuel_type VARCHAR(255),
  material_type VARCHAR(255),
  product_type VARCHAR(255),
  geography VARCHAR(255),
  industry_applicability VARCHAR(255),
  factor_value DECIMAL(20,6),
  factor_unit VARCHAR(255),
  activity_unit VARCHAR(255),
  gas_type VARCHAR(255),
  co2_factor DECIMAL(20,6),
  ch4_factor DECIMAL(20,6),
  n2o_factor DECIMAL(20,6),
  gwp_basis VARCHAR(255),
  gwp_time_horizon VARCHAR(255),
  publication_year BIGINT,
  effective_date DATETIME,
  expiry_date DATETIME,
  version VARCHAR(255),
  source_organisation VARCHAR(255),
  source_document VARCHAR(255),
  methodology VARCHAR(255),
  uncertainty_low_pct BIGINT,
  uncertainty_high_pct DECIMAL(20,6),
  data_quality_rating BIGINT,
  synthetic_flag TINYINT(1),
  CONSTRAINT pk_emission_factors PRIMARY KEY (emission_factor_id)
);

CREATE TABLE ghg_activities (
  ghg_activity_id VARCHAR(255),
  facility_id VARCHAR(255),
  equipment_id VARCHAR(255),
  activity_type VARCHAR(255),
  activity_quantity DECIMAL(20,6),
  activity_unit VARCHAR(255),
  original_quantity DECIMAL(20,6),
  original_unit VARCHAR(255),
  period_start DATETIME,
  period_end DATETIME,
  calculation_method VARCHAR(255),
  source_dataset VARCHAR(255),
  source_record_id VARCHAR(255),
  source_system VARCHAR(255),
  scope VARCHAR(255),
  category_id VARCHAR(255),
  category_name VARCHAR(255),
  vehicle_id VARCHAR(255),
  assumptions VARCHAR(255),
  scope2_method VARCHAR(255),
  supplier_id VARCHAR(255),
  customer_id VARCHAR(255),
  product_id VARCHAR(255),
  reporting_year VARCHAR(255),
  reporting_period VARCHAR(255),
  emission_factor_id VARCHAR(255),
  emission_factor_value DECIMAL(20,6),
  emission_factor_unit VARCHAR(255),
  gwp_basis VARCHAR(255),
  co2e_kg DECIMAL(20,6),
  reporting_boundary VARCHAR(255),
  included_in_inventory TINYINT(1),
  data_quality_rating BIGINT,
  uncertainty_pct BIGINT,
  gas_type VARCHAR(255),
  gwp_time_horizon VARCHAR(255),
  source_document_id VARCHAR(255),
  co2e_t DECIMAL(20,6),
  source_application VARCHAR(255),
  source_database VARCHAR(255),
  source_table VARCHAR(255),
  data_owner VARCHAR(255),
  schema_version VARCHAR(255),
  transformation_version VARCHAR(255),
  CONSTRAINT pk_ghg_activities PRIMARY KEY (ghg_activity_id)
);
ALTER TABLE ghg_activities ADD CONSTRAINT fk_ghg_activities_emission_factor_id FOREIGN KEY (emission_factor_id) REFERENCES emission_factors(emission_factor_id);
ALTER TABLE ghg_activities ADD CONSTRAINT fk_ghg_activities_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
CREATE INDEX ix_ghg_activities_src ON ghg_activities (source_record_id);
CREATE TABLE customers (
  customer_id VARCHAR(255),
  crm_account_id VARCHAR(255),
  erp_sold_to VARCHAR(255),
  customer_name VARCHAR(255),
  country_id VARCHAR(255),
  segment VARCHAR(255),
  sales_territory VARCHAR(255),
  credit_limit_usd DECIMAL(20,6),
  acquisition_date DATETIME,
  churn_date DATETIME,
  incoterm VARCHAR(255),
  synthetic_flag TINYINT(1),
  latitude DECIMAL(20,6),
  longitude DECIMAL(20,6),
  CONSTRAINT pk_customers PRIMARY KEY (customer_id)
);
ALTER TABLE customers ADD CONSTRAINT fk_customers_country_id FOREIGN KEY (country_id) REFERENCES countries(country_id);

CREATE TABLE sales_orders (
  sales_order_id VARCHAR(255),
  crm_order_ref VARCHAR(255),
  sap_vbeln VARCHAR(255),
  customer_id VARCHAR(255),
  order_date DATETIME,
  sales_territory VARCHAR(255),
  incoterm VARCHAR(255),
  currency VARCHAR(255),
  channel VARCHAR(255),
  net_value DECIMAL(20,6),
  source_system VARCHAR(255),
  source_application VARCHAR(255),
  source_database VARCHAR(255),
  source_table VARCHAR(255),
  source_record_id VARCHAR(255),
  data_owner VARCHAR(255),
  source_record_timestamp DATETIME,
  ingestion_timestamp DATETIME,
  processing_timestamp DATETIME,
  schema_version VARCHAR(255),
  transformation_version VARCHAR(255),
  CONSTRAINT pk_sales_orders PRIMARY KEY (sales_order_id)
);
ALTER TABLE sales_orders ADD CONSTRAINT fk_sales_orders_customer_id FOREIGN KEY (customer_id) REFERENCES customers(customer_id);
CREATE INDEX ix_sales_orders_src ON sales_orders (source_record_id);
CREATE TABLE shipments (
  shipment_id VARCHAR(255),
  direction VARCHAR(255),
  ref_doc VARCHAR(255),
  po_id VARCHAR(255),
  delivery_id VARCHAR(255),
  supplier_id VARCHAR(255),
  customer_id VARCHAR(255),
  origin VARCHAR(255),
  destination VARCHAR(255),
  ship_date DATETIME,
  weight_kg DECIMAL(20,6),
  incoterm VARCHAR(255),
  tms_ref VARCHAR(255),
  mode VARCHAR(255),
  distance_km DECIMAL(20,6),
  distance_unit VARCHAR(255),
  carrier_id VARCHAR(255),
  load_factor_pct DECIMAL(20,6),
  freight_paid_by VARCHAR(255),
  empty_return_km DECIMAL(20,6),
  consolidation_id VARCHAR(255),
  tkm DECIMAL(20,6),
  source_system VARCHAR(255),
  source_application VARCHAR(255),
  source_database VARCHAR(255),
  source_table VARCHAR(255),
  source_record_id VARCHAR(255),
  data_owner VARCHAR(255),
  source_record_timestamp DATETIME,
  ingestion_timestamp DATETIME,
  processing_timestamp DATETIME,
  schema_version VARCHAR(255),
  transformation_version VARCHAR(255),
  CONSTRAINT pk_shipments PRIMARY KEY (shipment_id)
);
ALTER TABLE shipments ADD CONSTRAINT fk_shipments_carrier_id FOREIGN KEY (carrier_id) REFERENCES suppliers(supplier_id);
CREATE INDEX ix_shipments_src ON shipments (source_record_id);