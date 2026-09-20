from dataclasses import dataclass
from fastapi import Header, HTTPException
import jwt
from app.config import settings

@dataclass
class Principal:
    subject: str
    role: str
    tenant_id: str

async def current_principal(authorization: str | None = Header(default=None)) -> Principal:
    # Demo identity keeps the repository runnable. Production requires signed JWTs.
    if settings().environment == "development" and not authorization:
        return Principal("demo-user", "admin", "demo-tenant")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    try:
        claims = jwt.decode(authorization[7:], settings().jwt_secret, algorithms=["HS256"])
        return Principal(claims["sub"], claims["role"], claims["tenant_id"])
    except (jwt.InvalidTokenError, KeyError) as exc:
        raise HTTPException(401, "Invalid token") from exc

def require_role(principal: Principal, *roles: str) -> None:
    if principal.role not in roles:
        raise HTTPException(403, "Insufficient permissions")
