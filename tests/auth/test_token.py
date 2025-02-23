import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import HTTPException, status


from auth.token import Payload, create_token, validate_token


SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"


def create_valid_payload():
    """Helper to create a valid payload."""
    return Payload(
        id=uuid.uuid4(),
        user_id=1,
        token_type="access",
        issued_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        role_id=1,
        is_revoked=False,
    )


def test_create_and_validate_token_success():
    payload = create_valid_payload()
    token = create_token(payload, SECRET_KEY, ALGORITHM)

    validated_payload = validate_token(token, SECRET_KEY, ALGORITHM)

    assert str(validated_payload.id) == str(payload.id)
    assert validated_payload.user_id == payload.user_id
    assert validated_payload.token_type == payload.token_type
    # Compare ISO format strings for datetimes
    assert validated_payload.issued_at.isoformat() == payload.issued_at.isoformat()
    assert validated_payload.expires_at.isoformat() == payload.expires_at.isoformat()
    assert validated_payload.role_id == payload.role_id
    assert validated_payload.is_revoked == payload.is_revoked


def test_validate_token_expired():
    payload = Payload(
        id=uuid.uuid4(),
        user_id=1,
        token_type="access",
        issued_at=datetime.now(timezone.utc) - timedelta(hours=1),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # expired token
        role_id=1,
        is_revoked=False,
    )
    token = create_token(payload, SECRET_KEY, ALGORITHM)

    with pytest.raises(HTTPException) as exc_info:
        validate_token(token, SECRET_KEY, ALGORITHM)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_validate_token_revoked():
    payload = Payload(
        id=uuid.uuid4(),
        user_id=1,
        token_type="access",
        issued_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        role_id=1,
        is_revoked=True,
    )
    token = create_token(payload, SECRET_KEY, ALGORITHM)

    with pytest.raises(HTTPException) as exc_info:
        validate_token(token, SECRET_KEY, ALGORITHM)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
