-- Test Read-Only Database User Permissions
-- This script verifies that chatbot_readonly can only read data, not modify it
-- Run this as the chatbot_readonly user
--
-- Usage: psql -U chatbot_readonly -d tank_depot -f scripts/test_readonly_user.sql

\echo '========================================='
\echo 'Testing Read-Only User Permissions'
\echo '========================================='
\echo ''

-- Test 1: SELECT should work
\echo 'Test 1: SELECT query (should succeed)'
SELECT COUNT(*) AS table_count FROM information_schema.tables WHERE table_schema = 'public';
\echo '✓ SELECT works'
\echo ''

-- Test 2: SELECT from a specific table (if it exists)
\echo 'Test 2: SELECT from iso_tank table (should succeed)'
SELECT COUNT(*) AS iso_tank_count FROM iso_tank;
\echo '✓ SELECT from iso_tank works'
\echo ''

-- Test 3: INSERT should fail
\echo 'Test 3: INSERT query (should fail with permission error)'
INSERT INTO iso_tank (id, tank_number) VALUES ('00000000-0000-0000-0000-000000000000', 'TEST-001');
\echo '✗ INSERT should have failed but did not!'
\echo ''

-- Test 4: UPDATE should fail
\echo 'Test 4: UPDATE query (should fail with permission error)'
UPDATE iso_tank SET tank_number = 'TEST-002' WHERE id = '00000000-0000-0000-0000-000000000000';
\echo '✗ UPDATE should have failed but did not!'
\echo ''

-- Test 5: DELETE should fail
\echo 'Test 5: DELETE query (should fail with permission error)'
DELETE FROM iso_tank WHERE id = '00000000-0000-0000-0000-000000000000';
\echo '✗ DELETE should have failed but did not!'
\echo ''

-- Test 6: DROP should fail
\echo 'Test 6: DROP TABLE query (should fail with permission error)'
DROP TABLE iso_tank;
\echo '✗ DROP should have failed but did not!'
\echo ''

-- Test 7: TRUNCATE should fail
\echo 'Test 7: TRUNCATE query (should fail with permission error)'
TRUNCATE TABLE iso_tank;
\echo '✗ TRUNCATE should have failed but did not!'
\echo ''

-- Test 8: ALTER should fail
\echo 'Test 8: ALTER TABLE query (should fail with permission error)'
ALTER TABLE iso_tank ADD COLUMN test_column TEXT;
\echo '✗ ALTER should have failed but did not!'
\echo ''

\echo '========================================='
\echo 'Permission Test Complete'
\echo '========================================='
\echo ''
\echo 'Expected results:'
\echo '  - Tests 1-2 should succeed (SELECT works)'
\echo '  - Tests 3-8 should fail with permission errors'
\echo ''
\echo 'If all write operations failed, the read-only user is correctly configured.'
