#!/bin/bash
# Initialisation script run once by the PostgreSQL Docker entrypoint.
# The POSTGRES_USER / POSTGRES_DB from docker-compose create the primary
# superuser (questboard) and the database automatically.  This script
# creates the secondary migration-only user using the password from the
# POSTGRES_MIGRATE_PASSWORD environment variable.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'questboard_migrate') THEN
            CREATE ROLE questboard_migrate WITH LOGIN;
        END IF;
    END
    \$\$;

    -- Set (or update) the password from the environment variable
    ALTER ROLE questboard_migrate WITH LOGIN PASSWORD '$POSTGRES_MIGRATE_PASSWORD';

    GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO questboard_migrate;
    GRANT ALL ON SCHEMA public TO questboard_migrate;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO questboard_migrate;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO questboard_migrate;
EOSQL
