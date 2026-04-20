-- Create Read-Only Database User for Admin Chatbot
-- This script creates a PostgreSQL user with SELECT-only permissions
-- Run this as a PostgreSQL superuser (e.g., postgres)
--
-- Usage: psql -U postgres -d tank_depot -f scripts/create_readonly_user.sql

-- Create the user (change the password to a strong value)
CREATE USER chatbot_readonly WITH PASSWORD 'CHANGE_THIS_PASSWORD';

-- Grant connection to the database
GRANT CONNECT ON DATABASE tank_depot TO chatbot_readonly;

-- Grant usage on the public schema
GRANT USAGE ON SCHEMA public TO chatbot_readonly;

-- Grant SELECT on all existing tables in the public schema
GRANT SELECT ON ALL TABLES IN SCHEMA public TO chatbot_readonly;

-- Grant SELECT on all existing sequences (for reading auto-increment values)
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO chatbot_readonly;

-- Grant SELECT on future tables (so new tables are automatically accessible)
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO chatbot_readonly;

-- Grant SELECT on future sequences
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO chatbot_readonly;

-- Explicitly revoke all write permissions (defense in depth)
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM chatbot_readonly;
REVOKE CREATE ON SCHEMA public FROM chatbot_readonly;
REVOKE ALL ON DATABASE tank_depot FROM chatbot_readonly;
GRANT CONNECT ON DATABASE tank_depot TO chatbot_readonly;

-- Verify the user was created
\du chatbot_readonly

-- Show granted permissions
\dp
