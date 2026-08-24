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


_category_counter = {"n": 0}
_product_counter = {"n": 0}
_supplier_counter = {"n": 0}
_customer_counter = {"n": 0}


@pytest.fixture(scope="function")
def make_customer(db_session: Session):
    from decimal import Decimal

    from app.models.customer import Customer

    def _factory(
        name: str | None = None,
        identification: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        city: str | None = None,
        notes: str | None = None,
        is_active: bool = True,
        credit_enabled: bool = False,
        credit_limit: str = "0.00",
    ) -> Customer:
        _customer_counter["n"] += 1
        customer = Customer(
            name=name or f"Cliente {_customer_counter['n']}",
            identification=identification or f"CID-{_customer_counter['n']:08d}",
            phone=phone,
            email=email,
            address=address,
            city=city,
            notes=notes,
            is_active=is_active,
            credit_enabled=credit_enabled,
            credit_limit=Decimal(credit_limit),
            current_balance=Decimal("0"),
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)
        return customer

    return _factory


@pytest.fixture(scope="function")
def make_supplier(db_session: Session):
    from app.models.supplier import Supplier

    def _factory(
        name: str | None = None,
        identification: str | None = None,
        contact_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        city: str | None = None,
        notes: str | None = None,
        is_active: bool = True,
    ) -> Supplier:
        _supplier_counter["n"] += 1
        supplier = Supplier(
            name=name or f"Proveedor {_supplier_counter['n']}",
            identification=identification or f"ID-{_supplier_counter['n']:08d}",
            contact_name=contact_name,
            phone=phone,
            email=email,
            address=address,
            city=city,
            notes=notes,
            is_active=is_active,
        )
        db_session.add(supplier)
        db_session.commit()
        db_session.refresh(supplier)
        return supplier

    return _factory


@pytest.fixture(scope="function")
def make_category(db_session: Session):
    from app.models.category import Category

    def _factory(
        name: str | None = None,
        description: str | None = None,
        is_active: bool = True,
    ) -> Category:
        _category_counter["n"] += 1
        category = Category(
            name=name or f"Categoría {_category_counter['n']}",
            description=description,
            is_active=is_active,
        )
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)
        return category

    return _factory


@pytest.fixture(scope="function")
def make_product(db_session: Session, make_category):
    from decimal import Decimal

    from app.models.product import Product

    def _factory(
        name: str | None = None,
        barcode: str | None = None,
        category=None,
        sale_price: str = "100.00",
        purchase_price: str = "50.00",
        stock: int = 10,
        minimum_stock: int = 2,
        is_active: bool = True,
        **kwargs,
    ) -> Product:
        _product_counter["n"] += 1
        if category is None:
            category = make_category()
        product = Product(
            name=name or f"Producto {_product_counter['n']}",
            barcode=barcode,
            purchase_price=Decimal(purchase_price),
            sale_price=Decimal(sale_price),
            category_id=category.id,
            stock=stock,
            minimum_stock=minimum_stock,
            is_active=is_active,
            **kwargs,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    return _factory
