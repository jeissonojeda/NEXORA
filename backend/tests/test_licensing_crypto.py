"""Pruebas del núcleo criptográfico y del documento firmado de licencia."""

import pytest

from app.licensing.canonical import canonical_json
from app.licensing.documents import (
    build_activation_request,
    build_license_payload,
    decode_activation_request,
    encode_activation_request,
    sign_license_document,
    verify_license_document,
)
from app.licensing.errors import (
    FORMAT_MISMATCH,
    INVALID_SIGNATURE,
    UNKNOWN_KEY,
    LicenseError,
)
from app.licensing.keys import (
    generate_keypair_pem,
    key_id,
    load_private_key,
    load_public_key,
)


def _keypair():
    priv_pem, pub_pem = generate_keypair_pem()
    return load_private_key(priv_pem), load_public_key(pub_pem)


def test_canonical_json_is_stable_and_sorted():
    a = canonical_json({"b": 1, "a": [2, 1]})
    b = canonical_json({"a": [2, 1], "b": 1})
    assert a == b
    assert a == b'{"a":[2,1],"b":1}'


def test_sign_and_verify_license_document_roundtrip():
    priv, pub = _keypair()
    payload = build_license_payload(
        license_id="lic-1",
        license_key="NEXORA-AAAA-BBBB-CCCC",
        customer_name="Supermercado Demo",
        plan_code="STANDARD",
        license_type="PERPETUAL",
        installation_id="install-1",
        installation_fingerprint="fp-abc",
        features=["sales", "inventory"],
    )
    doc = sign_license_document(payload, priv, public_key=pub)
    assert doc["format"] == "nexora-license-v1"
    assert doc["key_id"] == key_id(pub)

    verified = verify_license_document(doc, pub, expected_key_id=key_id(pub))
    assert verified["license_key"] == "NEXORA-AAAA-BBBB-CCCC"
    assert verified["features"] == ["inventory", "sales"]


def test_verify_rejects_tampered_payload():
    priv, pub = _keypair()
    payload = build_license_payload(
        license_id="lic-1",
        license_key="NEXORA-AAAA",
        customer_name="X",
        plan_code="P",
        license_type="ANNUAL",
    )
    doc = sign_license_document(payload, priv, public_key=pub)
    doc["payload"]["license_type"] = "PERPETUAL"  # manipulación
    with pytest.raises(LicenseError) as exc:
        verify_license_document(doc, pub, expected_key_id=key_id(pub))
    assert exc.value.error_code == INVALID_SIGNATURE


def test_verify_rejects_wrong_signing_key():
    priv, pub = _keypair()
    other_priv, other_pub = _keypair()
    payload = build_license_payload(
        license_id="lic-1",
        license_key="K",
        customer_name="X",
        plan_code="P",
        license_type="MONTHLY",
    )
    doc = sign_license_document(payload, other_priv, public_key=other_pub)
    with pytest.raises(LicenseError) as exc:
        verify_license_document(doc, pub, expected_key_id=key_id(pub))
    assert exc.value.error_code == UNKNOWN_KEY


def test_verify_rejects_bad_format():
    priv, pub = _keypair()
    with pytest.raises(LicenseError) as exc:
        verify_license_document({"format": "otro", "payload": {}}, pub)
    assert exc.value.error_code == FORMAT_MISMATCH


def test_activation_request_encode_decode_roundtrip():
    request = build_activation_request(
        license_key="NEXORA-XXXX-YYYY",
        installation_id="install-9",
        fingerprint="fp-9",
        nonce="nonce-123",
        app_version="1.0.0",
    )
    code = encode_activation_request(request)
    decoded = decode_activation_request(code)
    assert decoded == request


def test_decode_rejects_garbage():
    with pytest.raises(LicenseError):
        decode_activation_request("@@@no-es-base64@@@")
