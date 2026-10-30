-- SYNTHETIC SQL_Server schema export generated for testing

CREATE TABLE suppliers (
  supplier_id NVARCHAR(255),
  erp_vendor_no NVARCHAR(255),
  srm_supplier_ref NVARCHAR(255),
  supplier_name NVARCHAR(255),
  country_id NVARCHAR(255),
  supplier_category NVARCHAR(255),
  tier BIGINT,
  onboarding_date DATETIME2,
  termination_date DATETIME2,
  payment_terms NVARCHAR(255),
  currency NVARCHAR(255),
  risk_rating NVARCHAR(255),
  data_maturity NVARCHAR(255),
  synthetic_id_tax NVARCHAR(255),
  synthetic_flag BIT,
  status NVARCHAR(255),
  CONSTRAINT pk_suppliers PRIMARY KEY (supplier_id)
);
ALTER TABLE suppliers ADD CONSTRAINT fk_suppliers_country_id FOREIGN KEY (country_id) REFERENCES countries(country_id);

CREATE TABLE materials (
  material_id NVARCHAR(255),
  sap_matnr NVARCHAR(255),
  material_family NVARCHAR(255),
  material_group NVARCHAR(255),
  base_unit NVARCHAR(255),
  description NVARCHAR(255),
  standard_price_usd DECIMAL(20,6),
  recycled_content_pct DECIMAL(20,6),
  hazardous_flag BIT,
  weight_kg_per_unit DECIMAL(20,6),
  synthetic_flag BIT,
  primary_supplier_id NVARCHAR(255),
  secondary_supplier_id NVARCHAR(255),
  CONSTRAINT pk_materials PRIMARY KEY (material_id)
);
ALTER TABLE materials ADD CONSTRAINT fk_materials_primary_supplier_id FOREIGN KEY (primary_supplier_id) REFERENCES suppliers(supplier_id);
ALTER TABLE materials ADD CONSTRAINT fk_materials_secondary_supplier_id FOREIGN KEY (secondary_supplier_id) REFERENCES suppliers(supplier_id);

CREATE TABLE purchase_orders (
  po_id NVARCHAR(255),
  sap_ebeln NVARCHAR(255),
  po_date DATETIME2,
  supplier_id NVARCHAR(255),
  facility_id NVARCHAR(255),
  legal_entity_id NVARCHAR(255),
  po_type NVARCHAR(255),
  currency NVARCHAR(255),
  payment_terms NVARCHAR(255),
  incoterm NVARCHAR(255),
  plant_id NVARCHAR(255),
  contract_id NVARCHAR(255),
  pr_id NVARCHAR(255),
  approval_status NVARCHAR(255),
  approval_date DATETIME2,
  approved_by_role NVARCHAR(255),
  delivery_terms_days BIGINT,
  total_net_amount DECIMAL(20,6),
  source_system NVARCHAR(255),
  source_application NVARCHAR(255),
  source_database NVARCHAR(255),
  source_table NVARCHAR(255),
  source_record_id NVARCHAR(255),
  data_owner NVARCHAR(255),
  source_record_timestamp DATETIME2,
  ingestion_timestamp DATETIME2,
  processing_timestamp DATETIME2,
  schema_version NVARCHAR(255),
  transformation_version NVARCHAR(255),
  CONSTRAINT pk_purchase_orders PRIMARY KEY (po_id)
);
ALTER TABLE purchase_orders ADD CONSTRAINT fk_purchase_orders_supplier_id FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id);
ALTER TABLE purchase_orders ADD CONSTRAINT fk_purchase_orders_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE purchase_orders ADD CONSTRAINT fk_purchase_orders_contract_id FOREIGN KEY (contract_id) REFERENCES supplier_contracts(contract_id);
CREATE INDEX ix_purchase_orders_src ON purchase_orders (source_record_id);
CREATE TABLE po_lines (
  po_line_id NVARCHAR(255),
  po_id NVARCHAR(255),
  line_no BIGINT,
  material_id NVARCHAR(255),
  service_category NVARCHAR(255),
  order_qty DECIMAL(20,6),
  unit NVARCHAR(255),
  unit_price DECIMAL(20,6),
  currency NVARCHAR(255),
  discount_pct BIGINT,
  net_amount DECIMAL(20,6),
  tax_rate_pct BIGINT,
  requested_delivery_date DATETIME2,
  gl_account NVARCHAR(255),
  cost_centre_id NVARCHAR(255),
  CONSTRAINT pk_po_lines PRIMARY KEY (po_line_id)
);
ALTER TABLE po_lines ADD CONSTRAINT fk_po_lines_po_id FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id);
ALTER TABLE po_lines ADD CONSTRAINT fk_po_lines_material_id FOREIGN KEY (material_id) REFERENCES materials(material_id);
ALTER TABLE po_lines ADD CONSTRAINT fk_po_lines_cost_centre_id FOREIGN KEY (cost_centre_id) REFERENCES cost_centres(cost_centre_id);

CREATE TABLE goods_receipts (
  grn_id NVARCHAR(255),
  sap_mblnr NVARCHAR(255),
  po_id NVARCHAR(255),
  po_line_id NVARCHAR(255),
  receipt_date DATETIME2,
  posting_date DATETIME2,
  facility_id NVARCHAR(255),
  material_id NVARCHAR(255),
  received_qty DECIMAL(20,6),
  rejected_qty DECIMAL(20,6),
  unit NVARCHAR(255),
  movement_type NVARCHAR(255),
  storage_location NVARCHAR(255),
  batch_no NVARCHAR(255),
  accepted_qty DECIMAL(20,6),
  source_system NVARCHAR(255),
  source_application NVARCHAR(255),
  source_database NVARCHAR(255),
  source_table NVARCHAR(255),
  source_record_id NVARCHAR(255),
  data_owner NVARCHAR(255),
  source_record_timestamp DATETIME2,
  ingestion_timestamp DATETIME2,
  processing_timestamp DATETIME2,
  schema_version NVARCHAR(255),
  transformation_version NVARCHAR(255),
  CONSTRAINT pk_goods_receipts PRIMARY KEY (grn_id)
);
ALTER TABLE goods_receipts ADD CONSTRAINT fk_goods_receipts_po_line_id FOREIGN KEY (po_line_id) REFERENCES po_lines(po_line_id);
ALTER TABLE goods_receipts ADD CONSTRAINT fk_goods_receipts_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE goods_receipts ADD CONSTRAINT fk_goods_receipts_material_id FOREIGN KEY (material_id) REFERENCES materials(material_id);
CREATE INDEX ix_goods_receipts_src ON goods_receipts (source_record_id);
CREATE TABLE ap_invoices (
  invoice_id NVARCHAR(255),
  sap_belnr NVARCHAR(255),
  supplier_invoice_no NVARCHAR(255),
  supplier_id NVARCHAR(255),
  po_id NVARCHAR(255),
  facility_id NVARCHAR(255),
  legal_entity_id NVARCHAR(255),
  currency NVARCHAR(255),
  payment_terms NVARCHAR(255),
  invoice_date DATETIME2,
  posting_date DATETIME2,
  net_amount DECIMAL(20,6),
  tax_amount DECIMAL(20,6),
  document_type NVARCHAR(255),
  gross_amount DECIMAL(20,6),
  invoice_status NVARCHAR(255),
  approval_date DATETIME2,
  service_category NVARCHAR(255),
  fiscal_year BIGINT,
  fiscal_period BIGINT,
  company_code NVARCHAR(255),
  source_system NVARCHAR(255),
  source_application NVARCHAR(255),
  source_database NVARCHAR(255),
  source_table NVARCHAR(255),
  source_record_id NVARCHAR(255),
  data_owner NVARCHAR(255),
  source_record_timestamp DATETIME2,
  ingestion_timestamp DATETIME2,
  processing_timestamp DATETIME2,
  schema_version NVARCHAR(255),
  transformation_version NVARCHAR(255),
  CONSTRAINT pk_ap_invoices PRIMARY KEY (invoice_id)
);
ALTER TABLE ap_invoices ADD CONSTRAINT fk_ap_invoices_supplier_id FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id);
ALTER TABLE ap_invoices ADD CONSTRAINT fk_ap_invoices_po_id FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id);
ALTER TABLE ap_invoices ADD CONSTRAINT fk_ap_invoices_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
CREATE INDEX ix_ap_invoices_src ON ap_invoices (source_record_id);
CREATE TABLE utility_invoices (
  utility_invoice_id NVARCHAR(255),
  invoice_number NVARCHAR(255),
  utility_supplier_id NVARCHAR(255),
  customer_account_no NVARCHAR(255),
  facility_id NVARCHAR(255),
  meter_id NVARCHAR(255),
  utility_type NVARCHAR(255),
  billing_period_start DATETIME2,
  billing_period_end DATETIME2,
  invoice_date DATETIME2,
  consumption DECIMAL(20,6),
  unit NVARCHAR(255),
  tariff_per_unit DECIMAL(20,6),
  currency NVARCHAR(255),
  previous_reading DECIMAL(20,6),
  current_reading DECIMAL(20,6),
  energy_charge DECIMAL(20,6),
  network_charge DECIMAL(20,6),
  taxes DECIMAL(20,6),
  total_payable DECIMAL(20,6),
  green_tariff BIT,
  supplier_disclosed_ef_kg_per_kwh DECIMAL(20,6),
  source_system NVARCHAR(255),
  source_application NVARCHAR(255),
  source_database NVARCHAR(255),
  source_table NVARCHAR(255),
  source_record_id NVARCHAR(255),
  data_owner NVARCHAR(255),
  source_record_timestamp DATETIME2,
  ingestion_timestamp DATETIME2,
  processing_timestamp DATETIME2,
  schema_version NVARCHAR(255),
  transformation_version NVARCHAR(255),
  CONSTRAINT pk_utility_invoices PRIMARY KEY (utility_invoice_id)
);
ALTER TABLE utility_invoices ADD CONSTRAINT fk_utility_invoices_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE utility_invoices ADD CONSTRAINT fk_utility_invoices_meter_id FOREIGN KEY (meter_id) REFERENCES meters(meter_id);
ALTER TABLE utility_invoices ADD CONSTRAINT fk_utility_invoices_utility_supplier_id FOREIGN KEY (utility_supplier_id) REFERENCES suppliers(supplier_id);
CREATE INDEX ix_utility_invoices_src ON utility_invoices (source_record_id);
CREATE TABLE meters (
  meter_id NVARCHAR(255),
  facility_id NVARCHAR(255),
  utility_type NVARCHAR(255),
  meter_level NVARCHAR(255),
  linked_entity_id NVARCHAR(255),
  unit NVARCHAR(255),
  serial_no NVARCHAR(255),
  utility_account_no NVARCHAR(255),
  protocol NVARCHAR(255),
  install_date DATETIME2,
  last_calibration_date DATETIME2,
  CONSTRAINT pk_meters PRIMARY KEY (meter_id)
);
ALTER TABLE meters ADD CONSTRAINT fk_meters_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);

CREATE TABLE facilities (
  facility_id NVARCHAR(255),
  facility_name NVARCHAR(255),
  facility_type NVARCHAR(255),
  country_id NVARCHAR(255),
  city NVARCHAR(255),
  address NVARCHAR(255),
  latitude DECIMAL(20,6),
  longitude DECIMAL(20,6),
  division_id NVARCHAR(255),
  business_unit_id NVARCHAR(255),
  legal_entity_id NVARCHAR(255),
  time_zone NVARCHAR(255),
  floor_area_m2 BIGINT,
  tenure NVARCHAR(255),
  leased_out_portion_pct DECIMAL(20,6),
  commissioning_date DATETIME2,
  temporary_shutdown_start DATETIME2,
  temporary_shutdown_end DATETIME2,
  divestment_date DATETIME2,
  energy_intensity_index DECIMAL(20,6),
  climate_zone NVARCHAR(255),
  grid_region NVARCHAR(255),
  operational_control BIT,
  enterprise_id NVARCHAR(255),
  synthetic_flag BIT,
  CONSTRAINT pk_facilities PRIMARY KEY (facility_id)
);
ALTER TABLE facilities ADD CONSTRAINT fk_facilities_country_id FOREIGN KEY (country_id) REFERENCES countries(country_id);
ALTER TABLE facilities ADD CONSTRAINT fk_facilities_legal_entity_id FOREIGN KEY (legal_entity_id) REFERENCES legal_entities(legal_entity_id);
ALTER TABLE facilities ADD CONSTRAINT fk_facilities_business_unit_id FOREIGN KEY (business_unit_id) REFERENCES business_units(business_unit_id);

CREATE TABLE emission_factors (
  emission_factor_id NVARCHAR(255),
  activity_type NVARCHAR(255),
  lookup_key NVARCHAR(255),
  fuel_type NVARCHAR(255),
  material_type NVARCHAR(255),
  product_type NVARCHAR(255),
  geography NVARCHAR(255),
  industry_applicability NVARCHAR(255),
  factor_value DECIMAL(20,6),
  factor_unit NVARCHAR(255),
  activity_unit NVARCHAR(255),
  gas_type NVARCHAR(255),
  co2_factor DECIMAL(20,6),
  ch4_factor DECIMAL(20,6),
  n2o_factor DECIMAL(20,6),
  gwp_basis NVARCHAR(255),
  gwp_time_horizon NVARCHAR(255),
  publication_year BIGINT,
  effective_date DATETIME2,
  expiry_date DATETIME2,
  version NVARCHAR(255),
  source_organisation NVARCHAR(255),
  source_document NVARCHAR(255),
  methodology NVARCHAR(255),
  uncertainty_low_pct BIGINT,
  uncertainty_high_pct DECIMAL(20,6),
  data_quality_rating BIGINT,
  synthetic_flag BIT,
  CONSTRAINT pk_emission_factors PRIMARY KEY (emission_factor_id)
);

CREATE TABLE ghg_activities (
  ghg_activity_id NVARCHAR(255),
  facility_id NVARCHAR(255),
  equipment_id NVARCHAR(255),
  activity_type NVARCHAR(255),
  activity_quantity DECIMAL(20,6),
  activity_unit NVARCHAR(255),
  original_quantity DECIMAL(20,6),
  original_unit NVARCHAR(255),
  period_start DATETIME2,
  period_end DATETIME2,
  calculation_method NVARCHAR(255),
  source_dataset NVARCHAR(255),
  source_record_id NVARCHAR(255),
  source_system NVARCHAR(255),
  scope NVARCHAR(255),
  category_id NVARCHAR(255),
  category_name NVARCHAR(255),
  vehicle_id NVARCHAR(255),
  assumptions NVARCHAR(255),
  scope2_method NVARCHAR(255),
  supplier_id NVARCHAR(255),
  customer_id NVARCHAR(255),
  product_id NVARCHAR(255),
  reporting_year NVARCHAR(255),
  reporting_period NVARCHAR(255),
  emission_factor_id NVARCHAR(255),
  emission_factor_value DECIMAL(20,6),
  emission_factor_unit NVARCHAR(255),
  gwp_basis NVARCHAR(255),
  co2e_kg DECIMAL(20,6),
  reporting_boundary NVARCHAR(255),
  included_in_inventory BIT,
  data_quality_rating BIGINT,
  uncertainty_pct BIGINT,
  gas_type NVARCHAR(255),
  gwp_time_horizon NVARCHAR(255),
  source_document_id NVARCHAR(255),
  co2e_t DECIMAL(20,6),
  source_application NVARCHAR(255),
  source_database NVARCHAR(255),
  source_table NVARCHAR(255),
  data_owner NVARCHAR(255),
  schema_version NVARCHAR(255),
  transformation_version NVARCHAR(255),
  CONSTRAINT pk_ghg_activities PRIMARY KEY (ghg_activity_id)
);
ALTER TABLE ghg_activities ADD CONSTRAINT fk_ghg_activities_emission_factor_id FOREIGN KEY (emission_factor_id) REFERENCES emission_factors(emission_factor_id);
ALTER TABLE ghg_activities ADD CONSTRAINT fk_ghg_activities_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
CREATE INDEX ix_ghg_activities_src ON ghg_activities (source_record_id);
CREATE TABLE customers (
  customer_id NVARCHAR(255),
  crm_account_id NVARCHAR(255),
  erp_sold_to NVARCHAR(255),
  customer_name NVARCHAR(255),
  country_id NVARCHAR(255),
  segment NVARCHAR(255),
  sales_territory NVARCHAR(255),
  credit_limit_usd DECIMAL(20,6),
  acquisition_date DATETIME2,
  churn_date DATETIME2,
  incoterm NVARCHAR(255),
  synthetic_flag BIT,
  latitude DECIMAL(20,6),
  longitude DECIMAL(20,6),
  CONSTRAINT pk_customers PRIMARY KEY (customer_id)
);
ALTER TABLE customers ADD CONSTRAINT fk_customers_country_id FOREIGN KEY (country_id) REFERENCES countries(country_id);

CREATE TABLE sales_orders (
  sales_order_id NVARCHAR(255),
  crm_order_ref NVARCHAR(255),
  sap_vbeln NVARCHAR(255),
  customer_id NVARCHAR(255),
  order_date DATETIME2,
  sales_territory NVARCHAR(255),
  incoterm NVARCHAR(255),
  currency NVARCHAR(255),
  channel NVARCHAR(255),
  net_value DECIMAL(20,6),
  source_system NVARCHAR(255),
  source_application NVARCHAR(255),
  source_database NVARCHAR(255),
  source_table NVARCHAR(255),
  source_record_id NVARCHAR(255),
  data_owner NVARCHAR(255),
  source_record_timestamp DATETIME2,
  ingestion_timestamp DATETIME2,
  processing_timestamp DATETIME2,
  schema_version NVARCHAR(255),
  transformation_version NVARCHAR(255),
  CONSTRAINT pk_sales_orders PRIMARY KEY (sales_order_id)
);
ALTER TABLE sales_orders ADD CONSTRAINT fk_sales_orders_customer_id FOREIGN KEY (customer_id) REFERENCES customers(customer_id);
CREATE INDEX ix_sales_orders_src ON sales_orders (source_record_id);
CREATE TABLE shipments (
  shipment_id NVARCHAR(255),
  direction NVARCHAR(255),
  ref_doc NVARCHAR(255),
  po_id NVARCHAR(255),
  delivery_id NVARCHAR(255),
  supplier_id NVARCHAR(255),
  customer_id NVARCHAR(255),
  origin NVARCHAR(255),
  destination NVARCHAR(255),
  ship_date DATETIME2,
  weight_kg DECIMAL(20,6),
  incoterm NVARCHAR(255),
  tms_ref NVARCHAR(255),
  mode NVARCHAR(255),
  distance_km DECIMAL(20,6),
  distance_unit NVARCHAR(255),
  carrier_id NVARCHAR(255),
  load_factor_pct DECIMAL(20,6),
  freight_paid_by NVARCHAR(255),
  empty_return_km DECIMAL(20,6),
  consolidation_id NVARCHAR(255),
  tkm DECIMAL(20,6),
  source_system NVARCHAR(255),
  source_application NVARCHAR(255),
  source_database NVARCHAR(255),
  source_table NVARCHAR(255),
  source_record_id NVARCHAR(255),
  data_owner NVARCHAR(255),
  source_record_timestamp DATETIME2,
  ingestion_timestamp DATETIME2,
  processing_timestamp DATETIME2,
  schema_version NVARCHAR(255),
  transformation_version NVARCHAR(255),
  CONSTRAINT pk_shipments PRIMARY KEY (shipment_id)
);
ALTER TABLE shipments ADD CONSTRAINT fk_shipments_carrier_id FOREIGN KEY (carrier_id) REFERENCES suppliers(supplier_id);
CREATE INDEX ix_shipments_src ON shipments (source_record_id);