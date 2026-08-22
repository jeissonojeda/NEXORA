from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.rbac import Roles
from app.core.security import create_access_token
from app.db.base import Base
from app.db.seed import seed_rbac
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.services.user_service import UserService

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

TEST_PASSWORD = "TestPass123"


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def rbac_seeded(db_session: Session) -> None:
    seed_rbac(db_session)


def _make_user(
    db_session: Session,
    username: str,
    email: str,
    role_name: str | None,
    is_active: bool = True,
) -> User:
    service = UserService(db_session)
    user = service.create_user(
        username=username,
        email=email,
        password=TEST_PASSWORD,
        first_name=f"First {username}",
        last_name="Test",
        role_name=role_name,
    )
    if not is_active:
        user.is_active = False
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_user(db_session: Session, rbac_seeded: None) -> User:
    return _make_user(db_session, "admin1", "admin1@demomail.com", Roles.ADMIN)


@pytest.fixture(scope="function")
def cashier_user(db_session: Session, rbac_seeded: None) -> User:
    return _make_user(db_session, "cashier1", "cashier1@demomail.com", Roles.CASHIER)


@pytest.fixture(scope="function")
def inventory_manager_user(db_session: Session, rbac_seeded: None) -> User:
    return _make_user(
        db_session, "invmgr1", "invmgr1@demomail.com", Roles.INVENTORY_MANAGER
    )


@pytest.fixture(scope="function")
def no_role_user(db_session: Session, rbac_seeded: None) -> User:
    return _make_user(db_session, "norole1", "norole1@demomail.com", None)


@pytest.fixture(scope="function")
def inactive_user(db_session: Session, rbac_seeded: None) -> User:
    return _make_user(
        db_session, "inactive1", "inactive1@demomail.com", Roles.ADMIN,
        is_active=False,
    )


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}
