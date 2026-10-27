-- Körs en gång när TRoE-databasen skapas (docker-entrypoint-initdb.d). Mintaka läser historiken med TimescaleDB:s aggregat last();
-- imagen timescaledb-ha skapar inte tillägget själv. Orion-LD skapar PostGIS vid uppstart.
CREATE EXTENSION IF NOT EXISTS timescaledb;
