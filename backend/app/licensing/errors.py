"""Errores del dominio de licencias.

Se mantienen independientes de FastAPI para poder reutilizarse tanto en el
servicio central como en la instalación local. Las rutas traducen estos errores
a respuestas HTTP.
"""


class LicenseError(Exception):
    """Error de licencia con código estable para el cliente."""

    def __init__(self, error_code: str, message: str, http_status: int = 400) -> None:
        self.error_code = error_code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


# --- Verificación criptográfica / documento ---
INVALID_DOCUMENT = "LICENSE_DOCUMENT_INVALID"
INVALID_SIGNATURE = "LICENSE_SIGNATURE_INVALID"
UNKNOWN_KEY = "LICENSE_KEY_UNKNOWN"
FORMAT_MISMATCH = "LICENSE_FORMAT_MISMATCH"

# --- Estado comercial ---
LICENSE_NOT_FOUND = "LICENSE_NOT_FOUND"
LICENSE_REVOKED = "LICENSE_REVOKED"
LICENSE_SUSPENDED = "LICENSE_SUSPENDED"
LICENSE_EXPIRED = "LICENSE_EXPIRED"

# --- Instalaciones ---
INSTALLATION_LIMIT_REACHED = "LICENSE_INSTALLATION_LIMIT_REACHED"
INSTALLATION_NOT_FOUND = "INSTALLATION_NOT_FOUND"
INSTALLATION_ALREADY_ACTIVE = "INSTALLATION_ALREADY_ACTIVE"
FINGERPRINT_MISMATCH = "LICENSE_FINGERPRINT_MISMATCH"
INSTALLATION_MISMATCH = "LICENSE_INSTALLATION_MISMATCH"

# --- Solicitudes manuales ---
REQUEST_NOT_FOUND = "ACTIVATION_REQUEST_NOT_FOUND"
REQUEST_ALREADY_RESOLVED = "ACTIVATION_REQUEST_ALREADY_RESOLVED"
REQUEST_LICENSE_MISMATCH = "ACTIVATION_REQUEST_LICENSE_MISMATCH"

# --- Límites / abuso ---
RATE_LIMITED = "LICENSE_RATE_LIMITED"
