import asyncio
import traceback
from app.models.base import AsyncSessionLocal
from app.services.tenant_service import TenantService
from app.agents.support_agent import get_agent_for_channel

async def main():
    try:
        async with AsyncSessionLocal() as db:
            tenant_service = TenantService(db)
            tenant_config = await tenant_service.get_config("obeikan")
            agent = get_agent_for_channel("chat", tenant_config, "obeikan")
            
            print("Invoking LangGraph Agent directly...")
            res = await agent._graph.ainvoke(
                {"messages": [("user", "Whats alarm code 2008?")]}, 
                config={"configurable": {"thread_id": "test_123_456"}}
            )
            
            for msg in res.get("messages", []):
                print(f"[{msg.type.upper()}] {repr(msg.content)}")
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    print(f"  TOOL CALLS: {msg.tool_calls}")
    except Exception as e:
        print("EXCEPTION CAUGHT!")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
