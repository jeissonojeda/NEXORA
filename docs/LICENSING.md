# Licenciamiento de NEXORA

Sistema comercial de licencias compuesto por **dos componentes independientes**:

1. **Servicio central de licencias** — lo ejecuta el propietario de NEXORA.
   Emite y firma las licencias, gestiona clientes/planes/instalaciones y el
   panel administrativo global. Tiene su **propia base de datos** y su propio
   modelo de autenticación.
2. **Instalación local** — el sistema del supermercado. Contiene únicamente la
   **clave pública**, verifica los documentos firmados y aplica la política de
   licencia.

Principios de diseño:

- La clave **privada** de firma vive solo en el servicio central / CLI admin.
  La instalación local solo lleva la clave **pública**. Nunca se commitea una
  clave privada.
- La IA y el frontend **nunca** son la autoridad: el backend verifica.
- La verificación es **offline**: una vez activada, la instalación funciona sin
  conexión (una licencia perpetua no caduca por desconexión).
- Revocar/vencer/transferir **nunca borra** los datos de negocio del cliente.
- El bloqueo por licencia está **desactivado en desarrollo/pruebas** y solo se
  activa en producción o con `LICENSE_ENFORCEMENT_ENABLED=true`.

## Tipos de licencia

| Tipo | Caducidad | Uso |
| --- | --- | --- |
| `PERPETUAL` | No caduca por tiempo | Pago único |
| `MONTHLY` | `expires_at` + `grace_days` | Suscripción mensual |
| `ANNUAL` | `expires_at` + `grace_days` | Suscripción anual |

Una licencia perpetua se emite con `expires_at = null` (nunca se fuerza una
suscripción).

## Criptografía

- **Ed25519** (`cryptography`, ya presente vía `python-jose[cryptography]`).
- Antes de firmar, el payload se serializa como **JSON canónico** (claves
  ordenadas, sin espacios, UTF-8) para que la firma sea reproducible.
- Formatos versionados: `nexora-license-v1` y
  `nexora-activation-request-v1`.

Documento de licencia:

```json
{
  "format": "nexora-license-v1",
  "payload": {
    "license_id": "...",
    "license_key": "NEXORA-XXXX-XXXX-XXXX",
    "customer_name": "...",
    "plan_code": "STANDARD",
    "license_type": "PERPETUAL",
    "issued_at": "...", "activated_at": "...", "expires_at": null,
    "grace_days": 0, "updates_until": null, "max_installations": 1,
    "features": ["inventory", "sales"],
    "min_version": null, "max_version": null,
    "installation_id": "...", "installation_fingerprint": "<sha256>",
    "nonce": null, "issued_by": "nexora-central"
  },
  "key_id": "<sha256 hex[:16] de la clave pública>",
  "signature": "<base64url>"
}
```

La verificación local comprueba la firma **y** que el documento esté atado a
**esta** instalación (`installation_id`) y a **esta** máquina
(`installation_fingerprint`). Así, copiar la carpeta a otro equipo no crea una
segunda instalación válida.

## Identidad de instalación

- `installation_id`: identificador aleatorio persistido en la base de datos al
  inicializar (`license_local_installation`).
- `fingerprint`: huella de máquina derivada de sistema, arquitectura, nombre de
  equipo y nodo (no se usa la MAC sola). Se firma su hash SHA-256.

## Flujos de activación

### Online

```
Instalación local                       Servicio central
POST /api/public/activate   ─────────►  valida licencia + cupo (bloqueo atómico)
{license_key, installation_id,          registra la instalación
 fingerprint, app_version}              firma el documento
                            ◄─────────  {status, document}
verifica y guarda el documento
```

### Manual (sin conexión)

```
1) Local: POST /api/license/manual-request {license_key}
     → devuelve request_code (base64url de la solicitud, incluye nonce)
2) Admin central: POST /api/admin/manual-requests/{id}/authorize
     → devuelve response_document (documento firmado con el nonce)
3) Local: POST /api/license/manual-import {response_code}
     → verifica y activa
```

La solicitud es idempotente (hash del `request_code`). El `nonce` evita
reutilizar una respuesta vieja.

## Estados locales

`NOT_ACTIVATED`, `ACTIVE`, `GRACE`, `EXPIRED`, `REVOKED`, `INVALID`,
`CLOCK_ROLLBACK`.

- `GRACE`: suscripción vencida dentro de `grace_days` (se permite operar).
- `CLOCK_ROLLBACK`: la marca de agua temporal (`last_seen_at`) detectó un
  retroceso del reloj más allá de la tolerancia (24 h).

## Endpoints

### Local (instalación del supermercado)

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/api/license/status` | Estado local (público). |
| POST | `/api/license/activate` | Activación online. |
| POST | `/api/license/manual-request` | Genera solicitud manual. |
| POST | `/api/license/manual-import` | Importa respuesta firmada. |

Los routers de negocio se registran con `Depends(require_license)`.

### Central (servicio del propietario)

- Público: `POST /api/public/activate`, `GET /api/public/status/{key}`,
  `POST /api/public/manual-request`, `GET /api/public/public-key`.
- Admin (JWT propio): `POST /api/admin/auth/login`, `GET/POST /api/admin/customers`,
  `GET/POST /api/admin/plans`, `GET/POST /api/admin/licenses`,
  `PATCH /api/admin/licenses/{id}/status`,
  `GET /api/admin/licenses/{id}/installations`,
  `POST /api/admin/licenses/{id}/installations/{iid}/release`,
  `POST /api/admin/transfers`,
  `GET /api/admin/manual-requests`,
  `POST /api/admin/manual-requests/{id}/authorize|reject`,
  `GET /api/admin/audit`.

## Configuración (variables de entorno)

### Instalación local

| Variable | Descripción |
| --- | --- |
| `LICENSE_PUBLIC_KEY_PATH` / `LICENSE_PUBLIC_KEY_PEM` | Clave pública (PEM). |
| `LICENSE_SERVER_URL` | URL del servicio central. |
| `LICENSE_ENFORCEMENT_ENABLED` | Fuerza el bloqueo (default `false`). |
| `LICENSE_APP_VERSION` | Versión reportada al activar. |

### Servicio central

| Variable | Descripción |
| --- | --- |
| `LICENSE_DATABASE_URL` | Base de datos propia del central. |
| `LICENSE_SIGNING_KEY_PATH` | Archivo PEM de la clave **privada**. |
| `LICENSE_PUBLIC_KEY_PATH` | Archivo PEM de la clave pública. |
| `LICENSE_JWT_SECRET` | Secreto JWT del panel admin (distinto del del súper). |
| `LICENSE_ACCESS_TOKEN_EXPIRE_MINUTES` | Expiración del token admin. |
| `LICENSE_RATE_LIMIT_*` | Límites anti abuso en activaciones. |

## Puesta en marcha

```bash
# 1) Generar el par de claves (una sola vez)
cd backend
python -m app.licensing.server.cli generate-keys \
    --private ./licensing_keys/private_key.pem \
    --public  ./licensing_keys/public_key.pem

# 2) Crear tablas y administrador del servicio central
python -m app.licensing.server.cli init-db
python -m app.licensing.server.cli create-admin --username owner --email owner@nexora.com

# 3) Ejecutar el servicio central
uvicorn app.licensing.server.main:app --host 0.0.0.0 --port 8100

# 4) Crear cliente + plan + licencia
python -m app.licensing.server.cli create-customer --name "Supermercado X"
python -m app.licensing.server.cli create-plan --code standard --name Standard --type PERPETUAL
python -m app.licensing.server.cli create-license --customer <uuid> --plan <uuid> --type PERPETUAL
```

En la instalación local, copiar el contenido de `public_key.pem` a
`LICENSE_PUBLIC_KEY_PEM` (o apuntar `LICENSE_PUBLIC_KEY_PATH`) y ejecutar
`alembic upgrade head` para crear `license_local` y
`license_local_installation`.

## Notas de seguridad

- Las claves están fuera del control de versiones; rotar implica un `key_id`
  nuevo (el documento lleva el `key_id`, y la instalación rechaza claves
  desconocidas).
- El límite de instalaciones se aplica de forma transaccional (bloqueo de fila)
  y con limitación de tasa en las activaciones.
- No se registran claves completas ni secretos en la auditoría.
