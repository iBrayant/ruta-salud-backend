# Ruta Salud Rural · Fusagasugá

Microservicios para priorizar y optimizar las visitas domiciliarias del Hospital San Rafael a las veredas de Fusagasugá. Usa datos oficiales del municipio, OAuth 2.0 con Keycloak, una auditoría que no se puede alterar y una IA que explica la ruta (pero no la decide).

## Arquitectura
```
                    Cloudflare Tunnel (opcional)
                               │
                     Nginx gateway :8080 (solo 127.0.0.1)
        ┌──────────────┬───────┴──────┬──────────────┐
   /api/rutas      /api/ia       /api/auditoria    /auth
   /api/veredas        │               │              │
   ┌──────────┐   ┌──────────┐   ┌────────────┐  ┌──────────┐
   │  rutas   │──▶│    ia    │──▶│ auditoria  │  │ Keycloak │  OAuth 2.0 / OIDC
   └──────────┘   └──────────┘   └────────────┘  └──────────┘
     │  │  │           │  │              │              │
     │  │  └── OSRM, Open-Meteo          │              │
     │  │              └── OpenAI        │              │
   ──┴──┴──────── red "datos" (interna, sin internet) ───┴──
        PostgreSQL (rutas_db · auditoria_db · keycloak_db) · Redis
```
Cada servicio sigue la arquitectura limpia: `domain` (reglas puras) → `application` (casos de uso y puertos) → `infrastructure` (adaptadores) → `presentation` (FastAPI).

## Cómo levantarlo
```bash
./scripts/generar_env.sh          # crea .env con secretos aleatorios (una sola vez)
# edite .env y ponga su OPENAI_API_KEY (opcional: sin ella, la explicación usa una plantilla)
docker compose up -d --build
./scripts/prueba_e2e.sh           # prueba de punta a punta
```
Las contraseñas de los usuarios de prueba (`coordinador.fusa`, `equipo.salud`, `auditor.fusa`) están en `.env`.

Documentación interactiva de cada API:
- http://localhost:8080/api/rutas/docs
- http://localhost:8080/api/auditoria/docs
- http://localhost:8080/api/ia/docs

## Endpoints principales
| Método | Ruta | Rol | Qué hace |
|---|---|---|---|
| GET | `/api/veredas` | todos | Las 15 veredas con el índice de vulnerabilidad desglosado |
| POST | `/api/rutas` | coordinador | Genera la ruta priorizada: orden de visita, distancia total y explicación |
| POST | `/api/rutas/simular` | coordinador, auditor | Simula N jornadas y calcula métricas de cobertura y equidad |
| GET | `/api/rutas`, `/api/rutas/{id}` | todos | Consulta las rutas |
| POST | `/api/rutas/{id}/ejecutada` | coordinador | Confirma que la jornada se hizo (alimenta la equidad) |
| POST | `/api/rutas/{id}/reproducir` | auditor | Recalcula la ruta con sus entradas originales y compara |
| POST | `/api/ia/consultas` | coordinador, equipo_salud | Preguntas sobre una ruta |
| GET | `/api/auditoria/eventos`, `/verificar` | auditor | Consulta el registro y verifica la cadena de hashes |

## Datos
Ver `data/FUENTES.md`: fuentes oficiales, método de cálculo y limitaciones.
