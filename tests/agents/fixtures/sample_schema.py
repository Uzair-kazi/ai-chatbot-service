"""
Sample Schema Fixtures for Testing

This module provides sample database schemas for testing the Schema Intelligence
agent. The schemas are formatted to match the output from SchemaIntrospector.
"""

# Simple schema with no foreign keys
SCHEMA_NO_FKS = """Database Schema:
================================================================================

Table: users
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - name: varchar(255) (not null)
  - email: varchar(255) (not null)
  - created_at: timestamp (not null, default: CURRENT_TIMESTAMP)

Table: products
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - name: varchar(255) (not null)
  - price: decimal(10,2) (not null)
  - created_at: timestamp (not null, default: CURRENT_TIMESTAMP)
"""

# Schema with simple foreign keys
SCHEMA_WITH_FKS = """Database Schema:
================================================================================

Table: iso_tank
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - tank_number: varchar(50) (not null)
  - iso_tank_status: varchar(20) (not null)
  - vehicle_in_id: uuid (foreign key -> vehicle_in.id)
  - vehicle_out_id: uuid (foreign key -> vehicle_out.id)
  - survey_form_id: uuid (foreign key -> survey_form.id)
  - created_at: timestamp (not null, default: CURRENT_TIMESTAMP)

Table: vehicle_in
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - croyance_client_name: varchar(255) (not null)
  - in_date_time: timestamp (not null)
  - driver_mobile_number: varchar(20)
  - license_number: varchar(50)
  - created_at: timestamp (not null, default: CURRENT_TIMESTAMP)

Table: vehicle_out
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - out_date_time: timestamp (not null)
  - created_at: timestamp (not null, default: CURRENT_TIMESTAMP)

Table: survey_form
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - survey_date: timestamp (not null)
  - inspector_name: varchar(255) (not null)
  - created_at: timestamp (not null, default: CURRENT_TIMESTAMP)
"""

# Schema with self-referential foreign key
SCHEMA_SELF_REFERENTIAL = """Database Schema:
================================================================================

Table: employee
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - name: varchar(255) (not null)
  - manager_id: uuid (foreign key -> employee.id)
  - created_at: timestamp (not null, default: CURRENT_TIMESTAMP)
"""

# Schema with circular foreign keys
SCHEMA_CIRCULAR = """Database Schema:
================================================================================

Table: table_a
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - name: varchar(255) (not null)
  - b_id: uuid (foreign key -> table_b.id)

Table: table_b
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - name: varchar(255) (not null)
  - c_id: uuid (foreign key -> table_c.id)

Table: table_c
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - name: varchar(255) (not null)
  - a_id: uuid (foreign key -> table_a.id)
"""

# Complex schema with multiple FK paths
SCHEMA_COMPLEX = """Database Schema:
================================================================================

Table: iso_tank
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - tank_number: varchar(50) (not null)
  - iso_tank_status: varchar(20) (not null)
  - vehicle_in_id: uuid (foreign key -> vehicle_in.id)
  - vehicle_out_id: uuid (foreign key -> vehicle_out.id)
  - survey_form_id: uuid (foreign key -> survey_form.id)
  - created_at: timestamp (not null, default: CURRENT_TIMESTAMP)

Table: service_tank
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - tank_number: varchar(50) (not null)
  - service_tank_status: varchar(20) (not null)
  - vehicle_in_id: uuid (foreign key -> vehicle_in.id)
  - created_at: timestamp (not null, default: CURRENT_TIMESTAMP)

Table: vehicle_in
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - croyance_client_name: varchar(255) (not null)
  - in_date_time: timestamp (not null)
  - client_id: uuid (foreign key -> client_details.id)
  - created_at: timestamp (not null, default: CURRENT_TIMESTAMP)

Table: vehicle_out
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - out_date_time: timestamp (not null)
  - created_at: timestamp (not null, default: CURRENT_TIMESTAMP)

Table: survey_form
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - survey_date: timestamp (not null)
  - inspector_name: varchar(255) (not null)
  - created_at: timestamp (not null, default: CURRENT_TIMESTAMP)

Table: client_details
--------------------------------------------------------------------------------
  - id: uuid (primary key, not null)
  - company_name: varchar(255) (not null)
  - contact_email: varchar(255) (not null)
  - created_at: timestamp (not null, default: CURRENT_TIMESTAMP)
"""
