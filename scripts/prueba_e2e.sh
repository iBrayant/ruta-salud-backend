#!/usr/bin/env bash
# Prueba de punta a punta contra el gateway. Requiere el stack arriba y jq instalado (o python3).
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
B="${PUBLIC_BASE_URL:-http://localhost:8080}"
TOKEN_URL="$B/auth/realms/ruta-salud/protocol/openid-connect/token"
FECHA="${1:-$(date -d tomorrow +%F)}"
j() { python3 -I -c "import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1], {'d': d}))" "$1"; }
token() { curl -sf -d grant_type=password -d client_id=cli-pruebas -d "username=$1" --data-urlencode "password=$2" "$TOKEN_URL" | j 'd["access_token"]'; }
codigo() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
ok() { printf '  \033[32m✔\033[0m %s\n' "$1"; }
falla() { printf '  \033[31m✘\033[0m %s\n' "$1"; exit 1; }
esperar() { [[ "$1" == "$2" ]] && ok "$3 (HTTP $1)" || falla "$3: se esperaba $2 y llegó $1"; }

echo "1) Autenticación OAuth 2.0 (Keycloak)"
TC=$(token coordinador.fusa "$KC_PASS_COORDINADOR"); ok "token coordinador"
TE=$(token equipo.salud "$KC_PASS_EQUIPO"); ok "token equipo de salud"
TA=$(token auditor.fusa "$KC_PASS_AUDITOR"); ok "token auditor"
esperar "$(codigo "$B/api/veredas")" 401 "sin token → rechazado"
esperar "$(codigo -H 'Authorization: Bearer abc.def.ghi' "$B/api/veredas")" 401 "token falso → rechazado"
esperar "$(codigo -d grant_type=password -d client_id=cli-pruebas -d username=coordinador.fusa -d password=Malisima123 "$TOKEN_URL")" 401 "contraseña incorrecta → rechazada"

echo "2) Autorización por roles"
esperar "$(codigo -H "Authorization: Bearer $TE" -H 'Content-Type: application/json' -d "{\"fecha\":\"$FECHA\"}" "$B/api/rutas")" 403 "equipo de salud NO puede generar rutas"
esperar "$(codigo -H "Authorization: Bearer $TC" "$B/api/auditoria/eventos")" 403 "coordinador NO puede leer la auditoría"
esperar "$(codigo -H "Authorization: Bearer $TC" -H 'Content-Type: application/json' -d '{"accion":"falso","actor":"x","actor_tipo":"usuario","recurso":"x"}' "$B/api/auditoria/eventos")" 403 "nadie externo puede escribir en la auditoría"
esperar "$(codigo -H "Authorization: Bearer $TC" -H 'Content-Type: application/json' -d "{\"fecha\":\"$FECHA\",\"alpha\":7}" "$B/api/rutas")" 422 "parámetro fuera de rango → validación"

echo "3) Generar ruta priorizada ($FECHA)"
R=$(curl -sf -H "Authorization: Bearer $TC" -H 'Content-Type: application/json' -d "{\"fecha\":\"$FECHA\"}" "$B/api/rutas")
RID=$(echo "$R" | j 'd["ruta_id"]')
echo "$R" | j '"  ruta "+d["codigo"]+": "+" → ".join(p["nombre"] for p in d["orden"])'
echo "$R" | j '"  distancia "+str(d["distancia_total_km"])+" km · regreso "+d["regreso"]["hora"]+" · brecha vs óptimo "+str(d["optimizacion"]["brecha_vs_optimo_pct"])+"% · fuente "+d["fuente_distancias"]+" · clima "+str(d["clima_disponible"])'
echo "$R" | j '"  explicación: "+(d["explicacion"]["revision_etica"]["metodo"] if d["explicacion"] else "ninguna")'
ok "ruta generada"
esperar "$(codigo -H "Authorization: Bearer $TE" "$B/api/rutas/$RID")" 200 "equipo de salud puede consultarla"
esperar "$(codigo -H "Authorization: Bearer $TE" "$B/api/rutas/$RID?incluir_snapshot=true")" 403 "solo el auditor ve las entradas completas"

echo "4) Auditoría y reproducibilidad"
REP=$(curl -sf -X POST -H "Authorization: Bearer $TA" "$B/api/rutas/$RID/reproducir")
[[ "$(echo "$REP" | j 'd["resultado_coincide"] and d["integridad_entradas"]')" == "True" ]] && ok "la ruta se reproduce idéntica desde sus entradas" || falla "reproducción distinta: $REP"
curl -sf -H "Authorization: Bearer $TA" "$B/api/auditoria/eventos?recurso=ruta:$RID" | j '"  eventos de la ruta: "+", ".join(e["accion"] for e in d)'
V=$(curl -sf -H "Authorization: Bearer $TA" "$B/api/auditoria/verificar")
[[ "$(echo "$V" | j 'd["integra"]')" == "True" ]] && ok "cadena de hashes íntegra ($(echo "$V" | j 'd["eventos_verificados"]') eventos)" || falla "cadena rota: $V"

echo "5) Inmutabilidad del registro (intento de manipulación directa en la base)"
if docker compose exec -T postgres psql -U postgres -d auditoria_db -c "UPDATE eventos_auditoria SET actor='hacker' WHERE seq=1" 2>&1 | grep -q inmutable; then
  ok "UPDATE bloqueado por trigger"; else falla "el UPDATE no fue bloqueado"; fi
if docker compose exec -T postgres psql -U postgres -d auditoria_db -c "DELETE FROM eventos_auditoria" 2>&1 | grep -q inmutable; then
  ok "DELETE bloqueado por trigger"; else falla "el DELETE no fue bloqueado"; fi

echo "6) Simulación de 10 jornadas (equidad)"
curl -sf -H "Authorization: Bearer $TC" -H 'Content-Type: application/json' -d "{\"fecha\":\"$FECHA\",\"n_jornadas\":10,\"considerar_lluvia\":false}" "$B/api/rutas/simular" \
  | j '"  cobertura "+str(d["metricas"]["cobertura_pct"])+"% · nunca visitadas: "+str(d["metricas"]["veredas_nunca_visitadas"])'
echo
echo "Todo OK. Ruta de prueba: $RID"
