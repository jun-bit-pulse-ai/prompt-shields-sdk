from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from collector.config import settings

engine = create_async_engine(settings.database_url)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    async with SessionLocal() as session:
        request.state.db = session
        response = await call_next(request)
        return response


# Placeholder route — will be replaced by registry.py in Task 5
@app.get("/api/v1/registry/assets")
async def list_assets(request: Request):
    from collector.auth import resolve_tenant
    tenant_id = await resolve_tenant(request)
    return {"data": [], "meta": {"total": 0, "has_more": False, "next_cursor": None}}
