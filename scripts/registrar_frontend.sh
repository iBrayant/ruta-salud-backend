#!/usr/bin/env bash
# Registra la URL del frontend (p. ej. Vercel) en el cliente web de Keycloak: redirecciones y orígenes CORS.
# Uso: ./scripts/registrar_frontend.sh https://ruta-salud.vercel.app
set -euo pipefail
cd "$(dirname "$0")/.."
URL="${1:?Uso: $0 <url-del-frontend>}"
URL="${URL%/}"
[[ "$URL" =~ ^https?://[^/]+$ ]] || { echo "La URL debe ser solo el origen, p. ej. https://proyecto.vercel.app" >&2; exit 1; }
set -a; source .env; set +a
K="docker compose exec -T keycloak /opt/keycloak/bin/kcadm.sh"
$K config credentials --server http://localhost:8080/auth --realm master --user "$KC_ADMIN_USER" --password "$KC_ADMIN_PASSWORD" >/dev/null
CID=$($K get clients -r ruta-salud -q clientId=web-ruta-salud --fields id --format csv --noquotes | tr -d '\r')
$K update "clients/$CID" -r ruta-salud \
  -s "redirectUris=[\"$URL/*\",\"http://localhost:3000/*\"]" \
  -s 'webOrigins=["+"]'
sed -i "s#^FRONTEND_URL=.*#FRONTEND_URL=$URL#" .env
echo "Keycloak acepta ahora $URL (y localhost:3000). FRONTEND_URL actualizado en .env."
