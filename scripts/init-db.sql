-- Initialize database for RealWorld FastAPI application
-- This script runs automatically when the PostgreSQL container starts

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create database user if not exists (handled by environment variables)
-- Tables will be created by Alembic migrations

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE realworld_db TO realworld;

-- Set timezone
SET timezone = 'UTC';