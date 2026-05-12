#!/bin/sh
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<'SQL'
SELECT 'CREATE DATABASE omnibase_infra'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'omnibase_infra'
)\gexec

SELECT 'CREATE DATABASE omniintelligence'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'omniintelligence'
)\gexec

SELECT 'CREATE DATABASE omnidash_analytics'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'omnidash_analytics'
)\gexec
SQL
