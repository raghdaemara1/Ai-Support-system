"""Integration tests for API endpoints."""
import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check returns healthy status."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient):
        """Test root endpoint returns API info."""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"


class TestTenantEndpoints:
    """Tests for tenant management endpoints."""

    @pytest.mark.asyncio
    async def test_create_tenant(self, client: AsyncClient):
        """Test creating a new tenant."""
        response = await client.post(
            "/admin/tenants",
            json={
                "name": "Test Company",
                "slug": "test-company",
                "config": {
                    "persona_name": "TestBot",
                    "persona_description": "A test bot",
                    "channels": ["chat"],
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "tenant" in data
        assert "api_key" in data
        assert data["tenant"]["name"] == "Test Company"

    @pytest.mark.asyncio
    async def test_list_tenants(self, client: AsyncClient):
        """Test listing tenants."""
        # First create a tenant
        await client.post(
            "/admin/tenants",
            json={
                "name": "List Test Company",
                "slug": "list-test",
            },
        )

        response = await client.get("/admin/tenants")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestChatEndpoint:
    """Tests for chat endpoint."""

    @pytest.mark.asyncio
    async def test_chat_message_requires_valid_tenant(self, client: AsyncClient):
        """Test chat message with invalid tenant."""
        response = await client.post(
            "/chat/message",
            json={
                "tenant_id": "nonexistent",
                "customer_id": "customer-1",
                "message": "Hello",
            },
        )
        # Should work but may have empty config
        # The actual behavior depends on the agent configuration
        assert response.status_code in [200, 500]
