import asyncio
from app.models.base import get_db
from app.services.tenant_service import TenantService
from app.agents.support_agent import get_agent_for_channel

async def main():
    async for db in get_db():
        tenant_service = TenantService(db)
        tenant_config = await tenant_service.get_config("obeikan")
        agent = get_agent_for_channel("chat", tenant_config, "obeikan")
        
        print('Invoking agent...')
        res = await agent._graph.ainvoke({"messages": [("user", "whats alaram code 2008")]}, config={"configurable": {"thread_id": "test_id"}})
        
        for msg in res.get("messages", []):
            print(f'[{msg.type.upper()}] content: {repr(msg.content)}')
            if hasattr(msg, "tool_calls"):
                print(f'  tool_calls: {msg.tool_calls}')
        break

asyncio.run(main())
