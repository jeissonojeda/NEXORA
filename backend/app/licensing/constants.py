"""Constantes y enums del sistema de licencias."""

from enum import Enum


class LicenseType(str, Enum):
    """Tipo comercial de la licencia."""

    PERPETUAL = "PERPETUAL"  # pago único, no caduca por desconexión
    MONTHLY = "MONTHLY"  # suscripción mensual
    ANNUAL = "ANNUAL"  # suscripción anual


class LicenseStatus(str, Enum):
    """Estado administrativo de la licencia en el servicio central."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class InstallationStatus(str, Enum):
    """Estado de una instalación registrada."""

    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"  # liberada (transferencia / desinstalación)
    REVOKED = "REVOKED"  # revocada administrativamente


class ManualRequestStatus(str, Enum):
    """Estado de una solicitud de activación manual."""

    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    REJECTED = "REJECTED"


class TransferStatus(str, Enum):
    """Estado de una transferencia de instalación."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class LocalLicenseStatus(str, Enum):
    """Estado de la licencia tal como lo ve la instalación local."""

    NOT_ACTIVATED = "NOT_ACTIVATED"
    ACTIVE = "ACTIVE"
    GRACE = "GRACE"  # suscripción vencida dentro del periodo de gracia
    EXPIRED = "EXPIRED"  # suscripción vencida fuera del periodo de gracia
    REVOKED = "REVOKED"
    INVALID = "INVALID"  # firma/estado no verificable
    CLOCK_ROLLBACK = "CLOCK_ROLLBACK"  # se detectó retroceso del reloj


# Identificadores de formato versionados (no romper el orden de firma).
LICENSE_FORMAT = "nexora-license-v1"
REQUEST_FORMAT = "nexora-activation-request-v1"
SIGNING_ALGORITHM = "Ed25519"

# Tolerancia (segundos) para considerar que el reloj retrocedió antes de marcar
# CLOCK_ROLLBACK. Evita falsos positivos por ajustes menores de NTP.
CLOCK_ROLLBACK_TOLERANCE_SECONDS = 24 * 60 * 60

VALID_LICENSE_TYPES = {t.value for t in LicenseType}
VALID_LICENSE_STATUSES = {s.value for s in LicenseStatus}
VALID_INSTALLATION_STATUSES = {s.value for s in InstallationStatus}
VALID_MANUAL_REQUEST_STATUSES = {s.value for s in ManualRequestStatus}
VALID_TRANSFER_STATUSES = {s.value for s in TransferStatus}
