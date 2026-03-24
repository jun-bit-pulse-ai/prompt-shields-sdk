from uuid import UUID
from fastapi import Request, HTTPException
from sqlalchemy import select
from db.models import Tenant


async def resolve_tenant(request: Request) -> UUID:
    """Extract Bearer token, resolve to tenant_id. Phase 1: simple key lookup."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"type": "about:blank", "title": "Unauthorized", "status": 401,
                    "detail": "Missing or invalid Authorization header"}
        )
    api_key = auth.removeprefix("Bearer ").strip()

    # SECURITY TODO: Phase 1 uses plaintext key lookup for demo convenience.
    # Phase 2 MUST switch to bcrypt hash comparison (bcrypt is already in deps).
    # Never deploy plaintext key lookup to production or pilot environments.
    db = request.state.db
    stmt = select(Tenant).where(Tenant.settings["api_key"].astext == api_key)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise HTTPException(
            status_code=401,
            detail={"type": "about:blank", "title": "Unauthorized", "status": 401,
                    "detail": "Invalid API key"}
        )
    return tenant.id
