-- Initialisation script run once by the PostgreSQL Docker entrypoint.
-- The POSTGRES_USER / POSTGRES_DB from docker-compose create the primary
-- superuser (questboard) and the database automatically. This script
-- creates the secondary migration-only user.

-- Migration user: full DDL privileges, used by Alembic only.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'questboard_migrate') THEN
        CREATE ROLE questboard_migrate WITH LOGIN PASSWORD 'changeme_migrate';
    END IF;
END
$$;

GRANT ALL PRIVILEGES ON DATABASE questboard TO questboard_migrate;
GRANT ALL ON SCHEMA public TO questboard_migrate;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO questboard_migrate;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO questboard_migrate;

-- NOTE: After running the initial migration, tighten the app user's privileges:
--   REVOKE ALL ON ALL TABLES IN SCHEMA public FROM questboard;
--   GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO questboard;
--   GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO questboard;
-- This is documented in the README first-run guide.
