"""Tenant management service."""
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.schemas import TenantConfig, TenantCreate
from app.core.security import generate_api_key, hash_api_key
from app.core.logging import get_logger

logger = get_logger(__name__)


class TenantService:
    """Service for managing tenants."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tenant(self, data: TenantCreate) -> tuple[Tenant, str]:
        """
        Create a new tenant.

        Returns:
            tuple of (Tenant, api_key) - api_key is only returned once!
        """
        api_key = generate_api_key()
        api_key_hash = hash_api_key(api_key)

        tenant = Tenant(
            id=str(uuid.uuid4()),
            name=data.name,
            slug=data.slug,
            api_key_hash=api_key_hash,
            config=data.config.model_dump(),
            is_active=True,
        )

        self.db.add(tenant)
        await self.db.commit()
        await self.db.refresh(tenant)

        logger.info("Created tenant", tenant_id=tenant.id, slug=tenant.slug)

        return tenant, api_key

    async def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get a tenant by ID."""
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get a tenant by slug."""
        result = await self.db.execute(
            select(Tenant).where(Tenant.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_tenant_by_id_or_slug(self, tenant_id: str) -> Optional[Tenant]:
        """Get a tenant by UUID or slug (tries UUID first, then slug)."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            tenant = await self.get_tenant_by_slug(tenant_id)
        return tenant

    async def get_config(self, tenant_id: str) -> TenantConfig:
        """Get tenant configuration, accepting either UUID or slug."""
        tenant = await self.get_tenant_by_id_or_slug(tenant_id)
        if not tenant:
            # Return default config if tenant not found
            return TenantConfig()

        return TenantConfig(**tenant.config)

    async def update_config(
        self,
        tenant_id: str,
        config: TenantConfig,
    ) -> Optional[Tenant]:
        """Update tenant configuration."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return None

        tenant.config = config.model_dump()
        await self.db.commit()
        await self.db.refresh(tenant)

        logger.info("Updated tenant config", tenant_id=tenant_id)

        return tenant

    async def list_tenants(
        self,
        active_only: bool = True,
    ) -> list[Tenant]:
        """List all tenants."""
        query = select(Tenant)
        if active_only:
            query = query.where(Tenant.is_active == True)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def deactivate_tenant(self, tenant_id: str) -> bool:
        """Deactivate a tenant."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False

        tenant.is_active = False
        await self.db.commit()

        logger.info("Deactivated tenant", tenant_id=tenant_id)

        return True
