-- SYNTHETIC Oracle schema export generated for testing

CREATE TABLE suppliers (
  supplier_id VARCHAR2(255),
  erp_vendor_no VARCHAR2(255),
  srm_supplier_ref VARCHAR2(255),
  supplier_name VARCHAR2(255),
  country_id VARCHAR2(255),
  supplier_category VARCHAR2(255),
  tier NUMBER(19),
  onboarding_date TIMESTAMP,
  termination_date TIMESTAMP,
  payment_terms VARCHAR2(255),
  currency VARCHAR2(255),
  risk_rating VARCHAR2(255),
  data_maturity VARCHAR2(255),
  synthetic_id_tax VARCHAR2(255),
  synthetic_flag NUMBER(1),
  status VARCHAR2(255),
  CONSTRAINT pk_suppliers PRIMARY KEY (supplier_id)
);
ALTER TABLE suppliers ADD CONSTRAINT fk_suppliers_country_id FOREIGN KEY (country_id) REFERENCES countries(country_id);

CREATE TABLE materials (
  material_id VARCHAR2(255),
  sap_matnr VARCHAR2(255),
  material_family VARCHAR2(255),
  material_group VARCHAR2(255),
  base_unit VARCHAR2(255),
  description VARCHAR2(255),
  standard_price_usd NUMBER(20,6),
  recycled_content_pct NUMBER(20,6),
  hazardous_flag NUMBER(1),
  weight_kg_per_unit NUMBER(20,6),
  synthetic_flag NUMBER(1),
  primary_supplier_id VARCHAR2(255),
  secondary_supplier_id VARCHAR2(255),
  CONSTRAINT pk_materials PRIMARY KEY (material_id)
);
ALTER TABLE materials ADD CONSTRAINT fk_materials_primary_supplier_id FOREIGN KEY (primary_supplier_id) REFERENCES suppliers(supplier_id);
ALTER TABLE materials ADD CONSTRAINT fk_materials_secondary_supplier_id FOREIGN KEY (secondary_supplier_id) REFERENCES suppliers(supplier_id);

CREATE TABLE purchase_orders (
  po_id VARCHAR2(255),
  sap_ebeln VARCHAR2(255),
  po_date TIMESTAMP,
  supplier_id VARCHAR2(255),
  facility_id VARCHAR2(255),
  legal_entity_id VARCHAR2(255),
  po_type VARCHAR2(255),
  currency VARCHAR2(255),
  payment_terms VARCHAR2(255),
  incoterm VARCHAR2(255),
  plant_id VARCHAR2(255),
  contract_id VARCHAR2(255),
  pr_id VARCHAR2(255),
  approval_status VARCHAR2(255),
  approval_date TIMESTAMP,
  approved_by_role VARCHAR2(255),
  delivery_terms_days NUMBER(19),
  total_net_amount NUMBER(20,6),
  source_system VARCHAR2(255),
  source_application VARCHAR2(255),
  source_database VARCHAR2(255),
  source_table VARCHAR2(255),
  source_record_id VARCHAR2(255),
  data_owner VARCHAR2(255),
  source_record_timestamp TIMESTAMP,
  ingestion_timestamp TIMESTAMP,
  processing_timestamp TIMESTAMP,
  schema_version VARCHAR2(255),
  transformation_version VARCHAR2(255),
  CONSTRAINT pk_purchase_orders PRIMARY KEY (po_id)
);
ALTER TABLE purchase_orders ADD CONSTRAINT fk_purchase_orders_supplier_id FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id);
ALTER TABLE purchase_orders ADD CONSTRAINT fk_purchase_orders_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE purchase_orders ADD CONSTRAINT fk_purchase_orders_contract_id FOREIGN KEY (contract_id) REFERENCES supplier_contracts(contract_id);
CREATE INDEX ix_purchase_orders_src ON purchase_orders (source_record_id);
CREATE TABLE po_lines (
  po_line_id VARCHAR2(255),
  po_id VARCHAR2(255),
  line_no NUMBER(19),
  material_id VARCHAR2(255),
  service_category VARCHAR2(255),
  order_qty NUMBER(20,6),
  unit VARCHAR2(255),
  unit_price NUMBER(20,6),
  currency VARCHAR2(255),
  discount_pct NUMBER(19),
  net_amount NUMBER(20,6),
  tax_rate_pct NUMBER(19),
  requested_delivery_date TIMESTAMP,
  gl_account VARCHAR2(255),
  cost_centre_id VARCHAR2(255),
  CONSTRAINT pk_po_lines PRIMARY KEY (po_line_id)
);
ALTER TABLE po_lines ADD CONSTRAINT fk_po_lines_po_id FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id);
ALTER TABLE po_lines ADD CONSTRAINT fk_po_lines_material_id FOREIGN KEY (material_id) REFERENCES materials(material_id);
ALTER TABLE po_lines ADD CONSTRAINT fk_po_lines_cost_centre_id FOREIGN KEY (cost_centre_id) REFERENCES cost_centres(cost_centre_id);

CREATE TABLE goods_receipts (
  grn_id VARCHAR2(255),
  sap_mblnr VARCHAR2(255),
  po_id VARCHAR2(255),
  po_line_id VARCHAR2(255),
  receipt_date TIMESTAMP,
  posting_date TIMESTAMP,
  facility_id VARCHAR2(255),
  material_id VARCHAR2(255),
  received_qty NUMBER(20,6),
  rejected_qty NUMBER(20,6),
  unit VARCHAR2(255),
  movement_type VARCHAR2(255),
  storage_location VARCHAR2(255),
  batch_no VARCHAR2(255),
  accepted_qty NUMBER(20,6),
  source_system VARCHAR2(255),
  source_application VARCHAR2(255),
  source_database VARCHAR2(255),
  source_table VARCHAR2(255),
  source_record_id VARCHAR2(255),
  data_owner VARCHAR2(255),
  source_record_timestamp TIMESTAMP,
  ingestion_timestamp TIMESTAMP,
  processing_timestamp TIMESTAMP,
  schema_version VARCHAR2(255),
  transformation_version VARCHAR2(255),
  CONSTRAINT pk_goods_receipts PRIMARY KEY (grn_id)
);
ALTER TABLE goods_receipts ADD CONSTRAINT fk_goods_receipts_po_line_id FOREIGN KEY (po_line_id) REFERENCES po_lines(po_line_id);
ALTER TABLE goods_receipts ADD CONSTRAINT fk_goods_receipts_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE goods_receipts ADD CONSTRAINT fk_goods_receipts_material_id FOREIGN KEY (material_id) REFERENCES materials(material_id);
CREATE INDEX ix_goods_receipts_src ON goods_receipts (source_record_id);
CREATE TABLE ap_invoices (
  invoice_id VARCHAR2(255),
  sap_belnr VARCHAR2(255),
  supplier_invoice_no VARCHAR2(255),
  supplier_id VARCHAR2(255),
  po_id VARCHAR2(255),
  facility_id VARCHAR2(255),
  legal_entity_id VARCHAR2(255),
  currency VARCHAR2(255),
  payment_terms VARCHAR2(255),
  invoice_date TIMESTAMP,
  posting_date TIMESTAMP,
  net_amount NUMBER(20,6),
  tax_amount NUMBER(20,6),
  document_type VARCHAR2(255),
  gross_amount NUMBER(20,6),
  invoice_status VARCHAR2(255),
  approval_date TIMESTAMP,
  service_category VARCHAR2(255),
  fiscal_year NUMBER(19),
  fiscal_period NUMBER(19),
  company_code VARCHAR2(255),
  source_system VARCHAR2(255),
  source_application VARCHAR2(255),
  source_database VARCHAR2(255),
  source_table VARCHAR2(255),
  source_record_id VARCHAR2(255),
  data_owner VARCHAR2(255),
  source_record_timestamp TIMESTAMP,
  ingestion_timestamp TIMESTAMP,
  processing_timestamp TIMESTAMP,
  schema_version VARCHAR2(255),
  transformation_version VARCHAR2(255),
  CONSTRAINT pk_ap_invoices PRIMARY KEY (invoice_id)
);
ALTER TABLE ap_invoices ADD CONSTRAINT fk_ap_invoices_supplier_id FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id);
ALTER TABLE ap_invoices ADD CONSTRAINT fk_ap_invoices_po_id FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id);
ALTER TABLE ap_invoices ADD CONSTRAINT fk_ap_invoices_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
CREATE INDEX ix_ap_invoices_src ON ap_invoices (source_record_id);
CREATE TABLE utility_invoices (
  utility_invoice_id VARCHAR2(255),
  invoice_number VARCHAR2(255),
  utility_supplier_id VARCHAR2(255),
  customer_account_no VARCHAR2(255),
  facility_id VARCHAR2(255),
  meter_id VARCHAR2(255),
  utility_type VARCHAR2(255),
  billing_period_start TIMESTAMP,
  billing_period_end TIMESTAMP,
  invoice_date TIMESTAMP,
  consumption NUMBER(20,6),
  unit VARCHAR2(255),
  tariff_per_unit NUMBER(20,6),
  currency VARCHAR2(255),
  previous_reading NUMBER(20,6),
  current_reading NUMBER(20,6),
  energy_charge NUMBER(20,6),
  network_charge NUMBER(20,6),
  taxes NUMBER(20,6),
  total_payable NUMBER(20,6),
  green_tariff NUMBER(1),
  supplier_disclosed_ef_kg_per_kwh NUMBER(20,6),
  source_system VARCHAR2(255),
  source_application VARCHAR2(255),
  source_database VARCHAR2(255),
  source_table VARCHAR2(255),
  source_record_id VARCHAR2(255),
  data_owner VARCHAR2(255),
  source_record_timestamp TIMESTAMP,
  ingestion_timestamp TIMESTAMP,
  processing_timestamp TIMESTAMP,
  schema_version VARCHAR2(255),
  transformation_version VARCHAR2(255),
  CONSTRAINT pk_utility_invoices PRIMARY KEY (utility_invoice_id)
);
ALTER TABLE utility_invoices ADD CONSTRAINT fk_utility_invoices_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE utility_invoices ADD CONSTRAINT fk_utility_invoices_meter_id FOREIGN KEY (meter_id) REFERENCES meters(meter_id);
ALTER TABLE utility_invoices ADD CONSTRAINT fk_utility_invoices_utility_supplier_id FOREIGN KEY (utility_supplier_id) REFERENCES suppliers(supplier_id);
CREATE INDEX ix_utility_invoices_src ON utility_invoices (source_record_id);
CREATE TABLE meters (
  meter_id VARCHAR2(255),
  facility_id VARCHAR2(255),
  utility_type VARCHAR2(255),
  meter_level VARCHAR2(255),
  linked_entity_id VARCHAR2(255),
  unit VARCHAR2(255),
  serial_no VARCHAR2(255),
  utility_account_no VARCHAR2(255),
  protocol VARCHAR2(255),
  install_date TIMESTAMP,
  last_calibration_date TIMESTAMP,
  CONSTRAINT pk_meters PRIMARY KEY (meter_id)
);
ALTER TABLE meters ADD CONSTRAINT fk_meters_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);

CREATE TABLE facilities (
  facility_id VARCHAR2(255),
  facility_name VARCHAR2(255),
  facility_type VARCHAR2(255),
  country_id VARCHAR2(255),
  city VARCHAR2(255),
  address VARCHAR2(255),
  latitude NUMBER(20,6),
  longitude NUMBER(20,6),
  division_id VARCHAR2(255),
  business_unit_id VARCHAR2(255),
  legal_entity_id VARCHAR2(255),
  time_zone VARCHAR2(255),
  floor_area_m2 NUMBER(19),
  tenure VARCHAR2(255),
  leased_out_portion_pct NUMBER(20,6),
  commissioning_date TIMESTAMP,
  temporary_shutdown_start TIMESTAMP,
  temporary_shutdown_end TIMESTAMP,
  divestment_date TIMESTAMP,
  energy_intensity_index NUMBER(20,6),
  climate_zone VARCHAR2(255),
  grid_region VARCHAR2(255),
  operational_control NUMBER(1),
  enterprise_id VARCHAR2(255),
  synthetic_flag NUMBER(1),
  CONSTRAINT pk_facilities PRIMARY KEY (facility_id)
);
ALTER TABLE facilities ADD CONSTRAINT fk_facilities_country_id FOREIGN KEY (country_id) REFERENCES countries(country_id);
ALTER TABLE facilities ADD CONSTRAINT fk_facilities_legal_entity_id FOREIGN KEY (legal_entity_id) REFERENCES legal_entities(legal_entity_id);
ALTER TABLE facilities ADD CONSTRAINT fk_facilities_business_unit_id FOREIGN KEY (business_unit_id) REFERENCES business_units(business_unit_id);

CREATE TABLE emission_factors (
  emission_factor_id VARCHAR2(255),
  activity_type VARCHAR2(255),
  lookup_key VARCHAR2(255),
  fuel_type VARCHAR2(255),
  material_type VARCHAR2(255),
  product_type VARCHAR2(255),
  geography VARCHAR2(255),
  industry_applicability VARCHAR2(255),
  factor_value NUMBER(20,6),
  factor_unit VARCHAR2(255),
  activity_unit VARCHAR2(255),
  gas_type VARCHAR2(255),
  co2_factor NUMBER(20,6),
  ch4_factor NUMBER(20,6),
  n2o_factor NUMBER(20,6),
  gwp_basis VARCHAR2(255),
  gwp_time_horizon VARCHAR2(255),
  publication_year NUMBER(19),
  effective_date TIMESTAMP,
  expiry_date TIMESTAMP,
  version VARCHAR2(255),
  source_organisation VARCHAR2(255),
  source_document VARCHAR2(255),
  methodology VARCHAR2(255),
  uncertainty_low_pct NUMBER(19),
  uncertainty_high_pct NUMBER(20,6),
  data_quality_rating NUMBER(19),
  synthetic_flag NUMBER(1),
  CONSTRAINT pk_emission_factors PRIMARY KEY (emission_factor_id)
);

CREATE TABLE ghg_activities (
  ghg_activity_id VARCHAR2(255),
  facility_id VARCHAR2(255),
  equipment_id VARCHAR2(255),
  activity_type VARCHAR2(255),
  activity_quantity NUMBER(20,6),
  activity_unit VARCHAR2(255),
  original_quantity NUMBER(20,6),
  original_unit VARCHAR2(255),
  period_start TIMESTAMP,
  period_end TIMESTAMP,
  calculation_method VARCHAR2(255),
  source_dataset VARCHAR2(255),
  source_record_id VARCHAR2(255),
  source_system VARCHAR2(255),
  scope VARCHAR2(255),
  category_id VARCHAR2(255),
  category_name VARCHAR2(255),
  vehicle_id VARCHAR2(255),
  assumptions VARCHAR2(255),
  scope2_method VARCHAR2(255),
  supplier_id VARCHAR2(255),
  customer_id VARCHAR2(255),
  product_id VARCHAR2(255),
  reporting_year VARCHAR2(255),
  reporting_period VARCHAR2(255),
  emission_factor_id VARCHAR2(255),
  emission_factor_value NUMBER(20,6),
  emission_factor_unit VARCHAR2(255),
  gwp_basis VARCHAR2(255),
  co2e_kg NUMBER(20,6),
  reporting_boundary VARCHAR2(255),
  included_in_inventory NUMBER(1),
  data_quality_rating NUMBER(19),
  uncertainty_pct NUMBER(19),
  gas_type VARCHAR2(255),
  gwp_time_horizon VARCHAR2(255),
  source_document_id VARCHAR2(255),
  co2e_t NUMBER(20,6),
  source_application VARCHAR2(255),
  source_database VARCHAR2(255),
  source_table VARCHAR2(255),
  data_owner VARCHAR2(255),
  schema_version VARCHAR2(255),
  transformation_version VARCHAR2(255),
  CONSTRAINT pk_ghg_activities PRIMARY KEY (ghg_activity_id)
);
ALTER TABLE ghg_activities ADD CONSTRAINT fk_ghg_activities_emission_factor_id FOREIGN KEY (emission_factor_id) REFERENCES emission_factors(emission_factor_id);
ALTER TABLE ghg_activities ADD CONSTRAINT fk_ghg_activities_facility_id FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
CREATE INDEX ix_ghg_activities_src ON ghg_activities (source_record_id);
CREATE TABLE customers (
  customer_id VARCHAR2(255),
  crm_account_id VARCHAR2(255),
  erp_sold_to VARCHAR2(255),
  customer_name VARCHAR2(255),
  country_id VARCHAR2(255),
  segment VARCHAR2(255),
  sales_territory VARCHAR2(255),
  credit_limit_usd NUMBER(20,6),
  acquisition_date TIMESTAMP,
  churn_date TIMESTAMP,
  incoterm VARCHAR2(255),
  synthetic_flag NUMBER(1),
  latitude NUMBER(20,6),
  longitude NUMBER(20,6),
  CONSTRAINT pk_customers PRIMARY KEY (customer_id)
);
ALTER TABLE customers ADD CONSTRAINT fk_customers_country_id FOREIGN KEY (country_id) REFERENCES countries(country_id);

CREATE TABLE sales_orders (
  sales_order_id VARCHAR2(255),
  crm_order_ref VARCHAR2(255),
  sap_vbeln VARCHAR2(255),
  customer_id VARCHAR2(255),
  order_date TIMESTAMP,
  sales_territory VARCHAR2(255),
  incoterm VARCHAR2(255),
  currency VARCHAR2(255),
  channel VARCHAR2(255),
  net_value NUMBER(20,6),
  source_system VARCHAR2(255),
  source_application VARCHAR2(255),
  source_database VARCHAR2(255),
  source_table VARCHAR2(255),
  source_record_id VARCHAR2(255),
  data_owner VARCHAR2(255),
  source_record_timestamp TIMESTAMP,
  ingestion_timestamp TIMESTAMP,
  processing_timestamp TIMESTAMP,
  schema_version VARCHAR2(255),
  transformation_version VARCHAR2(255),
  CONSTRAINT pk_sales_orders PRIMARY KEY (sales_order_id)
);
ALTER TABLE sales_orders ADD CONSTRAINT fk_sales_orders_customer_id FOREIGN KEY (customer_id) REFERENCES customers(customer_id);
CREATE INDEX ix_sales_orders_src ON sales_orders (source_record_id);
CREATE TABLE shipments (
  shipment_id VARCHAR2(255),
  direction VARCHAR2(255),
  ref_doc VARCHAR2(255),
  po_id VARCHAR2(255),
  delivery_id VARCHAR2(255),
  supplier_id VARCHAR2(255),
  customer_id VARCHAR2(255),
  origin VARCHAR2(255),
  destination VARCHAR2(255),
  ship_date TIMESTAMP,
  weight_kg NUMBER(20,6),
  incoterm VARCHAR2(255),
  tms_ref VARCHAR2(255),
  mode VARCHAR2(255),
  distance_km NUMBER(20,6),
  distance_unit VARCHAR2(255),
  carrier_id VARCHAR2(255),
  load_factor_pct NUMBER(20,6),
  freight_paid_by VARCHAR2(255),
  empty_return_km NUMBER(20,6),
  consolidation_id VARCHAR2(255),
  tkm NUMBER(20,6),
  source_system VARCHAR2(255),
  source_application VARCHAR2(255),
  source_database VARCHAR2(255),
  source_table VARCHAR2(255),
  source_record_id VARCHAR2(255),
  data_owner VARCHAR2(255),
  source_record_timestamp TIMESTAMP,
  ingestion_timestamp TIMESTAMP,
  processing_timestamp TIMESTAMP,
  schema_version VARCHAR2(255),
  transformation_version VARCHAR2(255),
  CONSTRAINT pk_shipments PRIMARY KEY (shipment_id)
);
ALTER TABLE shipments ADD CONSTRAINT fk_shipments_carrier_id FOREIGN KEY (carrier_id) REFERENCES suppliers(supplier_id);
CREATE INDEX ix_shipments_src ON shipments (source_record_id);