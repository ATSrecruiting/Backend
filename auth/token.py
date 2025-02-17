from datetime import datetime, timezone
import uuid
from fastapi import HTTPException, status
from pydantic import BaseModel, PlainSerializer
import jwt
from jose import JWTError
from typing import Annotated
from typing import Optional


UUIDStr = Annotated[uuid.UUID, PlainSerializer(lambda v: str(v), return_type=str)]
DateTimeStr = Annotated[
    datetime, PlainSerializer(lambda v: v.isoformat(), return_type=str)
]


class Payload(BaseModel):
    id: UUIDStr
    user_id: int
    token_type: str
    issued_at: DateTimeStr
    expires_at: DateTimeStr
    role_id: Optional[int] = None
    is_revoked: bool


class JwtToken(BaseModel):
    AccessToken: str
    RefreshToken: str


def create_token(payloadData: Payload, secretKey: str, algorithm: str) -> str:
    """
    Create a JWT token from a Payload model
    """

    to_encode = payloadData.model_dump(mode="json")

    encoded_jwt = jwt.encode(to_encode, secretKey, algorithm=algorithm)
    return encoded_jwt


def validate_token(token: str, secretKey: str, algorithm: str) -> Payload:
    """
    Validate and decode a JWT token
    """
    try:
        # Decode the token
        payload_dict = jwt.decode(token, secretKey, algorithms=[algorithm])

        # Reconstruct the Payload model
        payload = Payload(
            id=uuid.UUID(payload_dict["id"]),
            user_id=payload_dict["user_id"],
            token_type=payload_dict["token_type"],
            issued_at=datetime.fromisoformat(payload_dict["issued_at"]),
            expires_at=datetime.fromisoformat(payload_dict["expires_at"]),
            role_id=payload_dict["role_id"],
            is_revoked=payload_dict["is_revoked"],
        )

        current_time = datetime.now(timezone.utc)

        # Compare with the timezone-aware expires_at
        if payload.is_revoked or current_time > payload.expires_at:
            raise HTTPException(status_code=401, detail="Token expired or revoked")

        return payload

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
