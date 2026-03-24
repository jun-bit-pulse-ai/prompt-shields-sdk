"""End-to-end test: ingest events -> query registry -> verify data integrity."""
import pytest
from httpx import AsyncClient, ASGITransport
from collector.app import app

HEADERS = {"Authorization": "Bearer ps-test-key-12345"}


@pytest.mark.asyncio
async def test_full_flow(seeded_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Ingest from SDK
        r1 = await client.post("/ingest/events", headers=HEADERS, json={"events": [
            {"vendor": "openai", "model": "gpt-4o", "use_case_name": "screening",
             "business_unit": "HR", "source": "sdk", "owner_email": "jane@test.com",
             "data_classification": "confidential", "tokens_in": 100, "tokens_out": 200}
        ]})
        assert r1.status_code == 200
        assert r1.json()["assets_created"] == 1

        # 2. Ingest same asset from gateway (different source)
        r2 = await client.post("/ingest/events", headers=HEADERS, json={"events": [
            {"vendor": "openai", "model": "gpt-4o", "use_case_name": "screening",
             "business_unit": "HR", "source": "gateway", "tokens_in": 150, "tokens_out": 250}
        ]})
        assert r2.status_code == 200
        assert r2.json()["assets_created"] == 0  # merged, not new

        # 3. Query registry — should have 1 asset with verified confidence
        r3 = await client.get("/api/v1/registry/assets", headers=HEADERS)
        assert r3.status_code == 200
        assets = r3.json()["data"]
        assert len(assets) == 1
        assert set(assets[0]["discovery_source"]) == {"sdk", "gateway"}
        assert assets[0]["confidence"] == "verified"
        assert assets[0]["owner_email"] == "jane@test.com"

        # 4. Get by ID
        asset_id = assets[0]["id"]
        r4 = await client.get(f"/api/v1/registry/assets/{asset_id}", headers=HEADERS)
        assert r4.status_code == 200
        assert r4.json()["vendor"] == "openai"

        # 5. Vendors endpoint
        r5 = await client.get("/api/v1/registry/vendors", headers=HEADERS)
        assert r5.status_code == 200
        assert "openai" in r5.json()["data"]

        # 6. Filter by business unit
        r6 = await client.get("/api/v1/registry/assets?business_unit=HR", headers=HEADERS)
        assert r6.status_code == 200
        assert len(r6.json()["data"]) == 1

        # 7. 404 for non-existent asset
        import uuid
        r7 = await client.get(f"/api/v1/registry/assets/{uuid.uuid4()}", headers=HEADERS)
        assert r7.status_code == 404
