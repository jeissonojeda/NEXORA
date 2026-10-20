"""Herramienta de línea de comandos del servicio central de licencias.

Uso::

    python -m app.licensing.server.cli init-db
    python -m app.licensing.server.cli generate-keys
    python -m app.licensing.server.cli create-admin --username owner --email a@b.c
    python -m app.licensing.server.cli create-customer --name "Supermercado X"
    python -m app.licensing.server.cli create-plan --code standard --name Standard \
        --type PERPETUAL
    python -m app.licensing.server.cli create-license --customer <uuid> \
        --type PERPETUAL --max-installations 2
    python -m app.licensing.server.cli list-licenses
"""

from __future__ import annotations

import argparse
import getpass
import sys
from uuid import UUID

from app.core.exceptions import AppError
from app.licensing.server.db import LicenseBase, LicenseSessionLocal, engine
from app.licensing.server.models import LicenseAdmin  # noqa: F401 (registra tablas)
from app.licensing.server import models as _models  # noqa: F401
from app.licensing.server.security import hash_password
from app.licensing.server.services import licenses as licenses_service
from app.licensing.server.signing import write_keypair
from app.licensing.server.config import get_license_settings


def _prompt_password() -> str:
    while True:
        first = getpass.getpass("Contraseña: ")
        if len(first) < 8:
            print("La contraseña debe tener al menos 8 caracteres.")
            continue
        second = getpass.getpass("Confirmar contraseña: ")
        if first != second:
            print("Las contraseñas no coinciden.")
            continue
        return first


def cmd_init_db(args: argparse.Namespace) -> int:
    LicenseBase.metadata.create_all(bind=engine)
    print("Base de datos del servicio central inicializada.")
    return 0


def cmd_generate_keys(args: argparse.Namespace) -> int:
    settings = get_license_settings()
    private_path = args.private or settings.LICENSE_SIGNING_KEY_PATH
    public_path = args.public or settings.LICENSE_PUBLIC_KEY_PATH
    if not private_path or not public_path:
        print(
            "Debe indicar --private y --public (o configurar "
            "LICENSE_SIGNING_KEY_PATH/LICENSE_PUBLIC_KEY_PATH)."
        )
        return 2
    try:
        write_keypair(private_path, public_path, overwrite=args.overwrite)
    except FileExistsError as exc:
        print(str(exc))
        return 2
    print(f"Clave privada: {private_path}")
    print(f"Clave pública: {public_path}")
    print(
        "Copie el contenido de la clave pública en la instalación local "
        "(LICENSE_PUBLIC_KEY_PATH o LICENSE_PUBLIC_KEY_PEM)."
    )
    return 0


def cmd_create_admin(args: argparse.Namespace) -> int:
    password = args.password or _prompt_password()
    with LicenseSessionLocal() as db:
        exists = (
            db.query(LicenseAdmin).filter(LicenseAdmin.username == args.username).first()
        )
        if exists is not None:
            print("Ya existe un administrador con ese usuario.")
            return 1
        admin = LicenseAdmin(
            username=args.username,
            email=args.email,
            password_hash=hash_password(password),
        )
        db.add(admin)
        db.commit()
    print(f"Administrador '{args.username}' creado.")
    return 0


def cmd_create_customer(args: argparse.Namespace) -> int:
    from app.licensing.server import schemas

    with LicenseSessionLocal() as db:
        customer = licenses_service.create_customer(
            db,
            schemas.CustomerCreate(
                name=args.name,
                email=args.email,
                identification=args.identification,
                phone=args.phone,
                notes=args.notes,
            ),
        )
    print(f"Cliente creado: {customer.id}")
    return 0


def cmd_create_plan(args: argparse.Namespace) -> int:
    from app.licensing.server import schemas

    with LicenseSessionLocal() as db:
        plan = licenses_service.create_plan(
            db,
            schemas.PlanCreate(
                code=args.code,
                name=args.name,
                license_type=args.type,
                default_max_installations=args.max_installations,
                duration_days=args.duration_days,
                features=args.features or [],
            ),
        )
    print(f"Plan creado: {plan.id} ({plan.code})")
    return 0


def cmd_create_license(args: argparse.Namespace) -> int:
    from app.licensing.server import schemas

    with LicenseSessionLocal() as db:
        license = licenses_service.create_license(
            db,
            schemas.LicenseCreate(
                customer_id=UUID(args.customer),
                plan_id=UUID(args.plan) if args.plan else None,
                license_type=args.type,
                max_installations=args.max_installations,
                features=args.features or [],
                grace_days=args.grace_days,
            ),
        )
        print(f"Licencia creada: {license.id}")
        print(f"Clave pública de licencia: {license.license_key}")
    return 0


def cmd_list_licenses(args: argparse.Namespace) -> int:
    with LicenseSessionLocal() as db:
        rows = licenses_service.list_licenses(db)
        for license in rows:
            count = licenses_service.count_active_installations(db, license.id)
            print(
                f"{license.license_key}  {license.license_type:<9} "
                f"{license.status:<9} instalaciones={count}/{license.max_installations}"
            )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="licensing-central")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init-db", help="Crea las tablas del servicio central")
    p.set_defaults(func=cmd_init_db)

    p = sub.add_parser("generate-keys", help="Genera el par de claves Ed25519")
    p.add_argument("--private")
    p.add_argument("--public")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_generate_keys)

    p = sub.add_parser("create-admin", help="Crea un administrador global")
    p.add_argument("--username", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--password")
    p.set_defaults(func=cmd_create_admin)

    p = sub.add_parser("create-customer", help="Crea un cliente")
    p.add_argument("--name", required=True)
    p.add_argument("--email")
    p.add_argument("--identification")
    p.add_argument("--phone")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_create_customer)

    p = sub.add_parser("create-plan", help="Crea un plan")
    p.add_argument("--code", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--type", required=True, choices=["PERPETUAL", "MONTHLY", "ANNUAL"])
    p.add_argument("--max-installations", type=int, default=1)
    p.add_argument("--duration-days", type=int)
    p.add_argument("--features", nargs="*")
    p.set_defaults(func=cmd_create_plan)

    p = sub.add_parser("create-license", help="Crea una licencia")
    p.add_argument("--customer", required=True, help="UUID del cliente")
    p.add_argument("--plan", help="UUID del plan")
    p.add_argument("--type", required=True, choices=["PERPETUAL", "MONTHLY", "ANNUAL"])
    p.add_argument("--max-installations", type=int, default=1)
    p.add_argument("--grace-days", type=int, default=0)
    p.add_argument("--features", nargs="*")
    p.set_defaults(func=cmd_create_license)

    p = sub.add_parser("list-licenses", help="Lista las licencias")
    p.set_defaults(func=cmd_list_licenses)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except AppError as exc:
        print(f"Error: {exc.message} ({exc.error_code})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
