#!/usr/bin/env bash
# Genera .env con secretos aleatorios. No sobrescribe un .env existente.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then echo ".env ya existe; no se modifica." >&2; exit 1; fi
hex() { openssl rand -hex "$1"; }
clave_usuario() { echo "Rs$(hex 5)9x"; }   # cumple la política: mayúscula, minúscula, dígito, >=10
umask 077
cat > .env <<EOF
# ---- Generado por scripts/generar_env.sh el $(date -Iseconds). NO subir a git.
PUBLIC_BASE_URL=http://localhost:8080
FRONTEND_URL=http://localhost:5173
GATEWAY_PORT=8080

POSTGRES_PASSWORD=$(hex 16)
KEYCLOAK_DB_PASSWORD=$(hex 16)
RUTAS_DB_PASSWORD=$(hex 16)
AUDITORIA_DB_PASSWORD=$(hex 16)
REDIS_PASSWORD=$(hex 16)

KC_ADMIN_USER=admin
KC_ADMIN_PASSWORD=$(hex 12)
KC_SVC_RUTAS_SECRET=$(hex 24)
KC_SVC_IA_SECRET=$(hex 24)
KC_PASS_COORDINADOR=$(clave_usuario)
KC_PASS_EQUIPO=$(clave_usuario)
KC_PASS_AUDITOR=$(clave_usuario)

# ---- IA: el equipo agrega su clave aquí (nunca en el chat ni en el código)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
IA_CHATS_POR_HORA=30
IA_TOKENS_POR_DIA=300000
EOF
echo ".env creado. Agregue OPENAI_API_KEY antes de levantar el servicio de IA."
