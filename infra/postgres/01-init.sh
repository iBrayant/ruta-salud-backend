#!/bin/sh
# Inicialización de PostgreSQL (solo corre la primera vez, con el volumen vacío).
# Una base por microservicio + usuarios con privilegios mínimos.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<SQL
CREATE ROLE keycloak      LOGIN PASSWORD '${KEYCLOAK_DB_PASSWORD}';
CREATE ROLE rutas_app     LOGIN PASSWORD '${RUTAS_DB_PASSWORD}';
CREATE ROLE auditoria_app LOGIN PASSWORD '${AUDITORIA_DB_PASSWORD}';
CREATE DATABASE keycloak_db  OWNER keycloak;
CREATE DATABASE rutas_db     OWNER ${POSTGRES_USER};
CREATE DATABASE auditoria_db OWNER ${POSTGRES_USER};
REVOKE ALL ON DATABASE rutas_db, auditoria_db, keycloak_db FROM PUBLIC;
GRANT CONNECT ON DATABASE rutas_db     TO rutas_app;
GRANT CONNECT ON DATABASE auditoria_db TO auditoria_app;
SQL

# ---------------------------------------------------------------- rutas_db
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname rutas_db <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO rutas_app;

CREATE TABLE rutas (
    id                uuid PRIMARY KEY,
    codigo            text NOT NULL UNIQUE,
    fecha_jornada     date NOT NULL,
    creado_en         timestamptz NOT NULL,
    creado_por        text NOT NULL,
    estado            text NOT NULL CHECK (estado IN ('propuesta', 'ejecutada')),
    parametros        jsonb NOT NULL,
    snapshot          jsonb NOT NULL,      -- todas las entradas del algoritmo (reproducibilidad)
    huella_entradas   char(64) NOT NULL,
    resultado         jsonb NOT NULL,
    huella_resultado  char(64) NOT NULL,
    version_datos     text NOT NULL,
    explicacion       jsonb,
    ejecutada_por     text,
    ejecutada_en      timestamptz
);
CREATE INDEX rutas_fecha_idx ON rutas (fecha_jornada);
CREATE INDEX rutas_estado_idx ON rutas (estado);

-- El servicio puede crear y leer rutas, pero solo actualizar estado y explicación:
-- parámetros, entradas y resultado quedan inmutables para la aplicación.
GRANT SELECT, INSERT ON rutas TO rutas_app;
GRANT UPDATE (estado, explicacion, ejecutada_por, ejecutada_en) ON rutas TO rutas_app;
SQL

# ---------------------------------------------------------------- auditoria_db
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname auditoria_db <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO auditoria_app;

CREATE TABLE eventos_auditoria (
    seq                bigint PRIMARY KEY,
    ts                 timestamptz NOT NULL,
    accion             text NOT NULL,
    actor              text NOT NULL,
    actor_tipo         text NOT NULL,
    roles              jsonb NOT NULL,
    recurso            text NOT NULL,
    detalle            jsonb NOT NULL,
    ip                 text NOT NULL,
    servicio_origen    text NOT NULL,
    hash_anterior      char(64) NOT NULL,
    registro_canonico  text NOT NULL,      -- fuente de verdad que se firma con SHA-256
    hash               char(64) NOT NULL UNIQUE
);
CREATE INDEX eventos_recurso_idx ON eventos_auditoria (recurso);
CREATE INDEX eventos_accion_idx ON eventos_auditoria (accion);
CREATE INDEX eventos_ts_idx ON eventos_auditoria (ts);

-- Append-only: ni la aplicación ni nadie puede modificar o borrar eventos.
CREATE FUNCTION bloquear_modificacion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'El registro de auditoría es inmutable (operación % bloqueada)', TG_OP;
END $$;
CREATE TRIGGER auditoria_sin_update BEFORE UPDATE OR DELETE ON eventos_auditoria
    FOR EACH ROW EXECUTE FUNCTION bloquear_modificacion();
CREATE TRIGGER auditoria_sin_truncate BEFORE TRUNCATE ON eventos_auditoria
    FOR EACH STATEMENT EXECUTE FUNCTION bloquear_modificacion();

GRANT SELECT, INSERT ON eventos_auditoria TO auditoria_app;
SQL
