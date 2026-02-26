import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import asyncio
from app.api.chat import chat_websocket
from app.models.schemas import ChatRequest
from app.models.base import AsyncSessionLocal
from app.services.tenant_service import TenantService
from app.agents.support_agent import get_agent_for_channel
import traceback

async def main():
    async with AsyncSessionLocal() as db:
        try:
            tenant_service = TenantService(db)
            tenant_config = await tenant_service.get_config("obeikan")
            agent = get_agent_for_channel("chat", tenant_config, "obeikan")
            
            print('Invoking agent...')
            res = await agent.invoke(user_input='whats alaram code 2008', history=[])
            print('Success!', res)
        except Exception as e:
            print('Exception caught!')
            traceback.print_exc()

asyncio.run(main())
