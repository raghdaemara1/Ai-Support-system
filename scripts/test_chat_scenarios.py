import asyncio
import httpx
import time
import json
import os

API_URL = "http://localhost:8001"
TENANT_ID = "acme" 
CUSTOMER_ID = "automation-tester-" + str(int(time.time()))

async def run_scenarios():
    print(f"\n🚀 Starting Automated Chat Scenario Tests\n")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: Ensure Tenant Exists
        try:
            resp = await client.get(f"{API_URL}/admin/tenants/{TENANT_ID}")
            if resp.status_code == 404:
                print("Creating test tenant...")
                await client.post(
                    f"{API_URL}/admin/tenants",
                    json={
                        "name": "Acme Test",
                        "slug": TENANT_ID,
                        "config": {"persona_name": "TestBot", "channels": ["chat"]}
                    }
                )
        except Exception as e:
            print(f"Error connecting to API. Is it running on port 8001? {e}")
            return

        scenarios = [
            {
                "name": "1. Casual Greeting (No RAG needed)",
                "message": "Hello, who are you?",
                "expected_escalation": False
            },
            {
                "name": "2. RAG Knowledge Lookup",
                "message": "Please explain what alarm code 2008 means.",
                "expected_escalation": False
            },
            {
                "name": "3. Human Handoff Request",
                "message": "This isn't helping, I need to speak to a human engineer now.",
                "expected_escalation": True
            },
            {
                "name": "4. Emergency Safety Escalation (Bypasses LLM)",
                "message": "Help, there is smoke and fire coming from the machine!",
                "expected_escalation": True
            }
        ]

        for s in scenarios:
            print(f"--------------------------------------------------")
            print(f"🧪 SCENARIO: {s['name']}")
            print(f"🧑 USER: '{s['message']}'\n")
            
            start = time.time()
            try:
                response = await client.post(
                    f"{API_URL}/chat/message",
                    json={
                        "tenant_id": TENANT_ID,
                        "customer_id": CUSTOMER_ID,
                        "message": s["message"]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    bot_reply = data.get("content", "")
                    escalated = data.get("escalated", False)
                    latency = time.time() - start
                    
                    print(f"🤖 AGENT [{latency:.2f}s]: '{bot_reply}'")
                    
                    if escalated:
                        print(f"🚨 STATUS: ESCALATED TO HUMAN QUEUE")
                    else:
                        print(f"✅ STATUS: HANDLED BY AI")
                        
                    if escalated != s["expected_escalation"]:
                        print(f"⚠️  WARNING: Expected escalated={s['expected_escalation']} but got {escalated}")
                else:
                    print(f"❌ API ERROR: {response.text}")
                    
            except Exception as e:
                print(f"❌ CONNECTION ERROR: {e}")
            
            # Small delay between turns
            await asyncio.sleep(2)
            print()

if __name__ == "__main__":
    asyncio.run(run_scenarios())
