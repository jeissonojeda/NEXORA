import argparse
import getpass
import sys

from app.core.rbac import Roles
from app.db.seed import seed_rbac
from app.db.session import SessionLocal
from app.schemas.user import UserCreate
from app.services.user_service import UserService


def _read_secret(prompt: str) -> str:
    if sys.stdin.isatty() and sys.stdout.isatty():
        return getpass.getpass(prompt)
    print(prompt)
    line = sys.stdin.readline()
    if not line:
        print("ERROR: Entrada no disponible.", file=sys.stderr)
        sys.exit(1)
    return line.rstrip("\r\n")


def _prompt_password() -> str:
    password = _read_secret(
        "Contraseña (min 8, mayúscula, minúscula y número): "
    )
    confirm = _read_secret("Confirmar contraseña: ")
    if password != confirm:
        print("ERROR: Las contraseñas no coinciden.", file=sys.stderr)
        sys.exit(1)
    return password


def cmd_create_admin(args: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        service = UserService(db)
        username = input("Username: ").strip()
        email = input("Email: ").strip()
        first_name = input("Nombre: ").strip()
        last_name = input("Apellido: ").strip()
        password = _prompt_password()

        UserCreate(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        admin_count = service.users.count_admins()
        if admin_count > 0:
            answer = input(
                f"Ya existen {admin_count} administrador(es). ¿Continuar? [y/N]: "
            )
            if answer.strip().lower() not in ("y", "yes", "s", "si"):
                print("Cancelado.")
                sys.exit(0)

        user = service.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role_name=args.role,
        )
        print(f"OK: Administrador '{user.username}' creado con id {user.id}")
    finally:
        db.close()


def cmd_seed_rbac(_: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        result = seed_rbac(db)
        print(f"OK: {result}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Utilidades de administración del sistema",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed_parser = subparsers.add_parser(
        "seed-rbac",
        help="Crea roles y permisos iniciales si no existen (idempotente)",
    )
    seed_parser.set_defaults(func=cmd_seed_rbac)

    admin_parser = subparsers.add_parser(
        "create-admin",
        help="Crea un usuario administrador de forma interactiva",
    )
    admin_parser.add_argument(
        "--role",
        default=Roles.ADMIN,
        help=f"Rol a asignar (default: {Roles.ADMIN})",
    )
    admin_parser.set_defaults(func=cmd_create_admin)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
