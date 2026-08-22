from app.core.security import hash_password, verify_password

from tests.conftest import TEST_PASSWORD


def test_hash_password_produces_different_value_than_plain() -> None:
    hashed = hash_password(TEST_PASSWORD)
    assert hashed != TEST_PASSWORD
    assert hashed.startswith("$2")


def test_verify_password_with_correct_password_returns_true() -> None:
    assert verify_password(TEST_PASSWORD, hash_password(TEST_PASSWORD)) is True


def test_verify_password_with_wrong_password_returns_false() -> None:
    assert verify_password("WrongPass456", hash_password(TEST_PASSWORD)) is False


def test_hash_password_generates_unique_hashes_for_same_password() -> None:
    first = hash_password(TEST_PASSWORD)
    second = hash_password(TEST_PASSWORD)
    assert first != second


def test_verify_password_with_invalid_hash_returns_false() -> None:
    assert verify_password(TEST_PASSWORD, "not-a-valid-hash") is False
