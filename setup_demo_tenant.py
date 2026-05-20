"""Create demo-tenant and seed it with sample knowledge for UI testing."""
import urllib.request, json, urllib.parse, time

BASE = "http://localhost:8001"

def req(method, path, body=None, params=None):
    url = BASE + path + (("?" + urllib.parse.urlencode(params)) if params else "")
    data = json.dumps(body).encode() if body else b""
    r = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")
    except Exception as ex:
        return 0, {"error": str(ex)}

# Create demo-tenant (ignore 400 if already exists)
s, b = req("POST", "/admin/tenants", {
    "name": "Demo Corp",
    "slug": "demo-tenant",
    "config": {
        "persona_name": "Aria",
        "persona_description": "A helpful AI customer support agent for Demo Corp.",
        "channels": ["chat", "email", "voice"],
        "language": "en",
        "escalation_keywords": ["human", "agent", "urgent", "refund", "broken", "cancel"],
        "max_turns_before_escalate": 8,
    }
})
if s == 200:
    tid = b["tenant"]["id"]
    print(f"Created demo-tenant: id={tid}")
elif s == 400 and "already exists" in str(b):
    # Already exists — look it up
    s2, b2 = req("GET", "/admin/tenants/demo-tenant")
    tid = b2.get("id")
    print(f"demo-tenant already exists: id={tid}")
else:
    print(f"Unexpected response {s}: {b}")
    exit(1)

# Seed rich knowledge base
knowledge_chunks = [
    (
        "Return & Refund Policy: Customers may return any item within 30 days of purchase for a full refund. "
        "Items must be unused and in original packaging. Refunds are processed within 5-7 business days to the original payment method. "
        "To start a return, email returns@democorp.com or call 1-800-555-0100. "
        "Shipping costs are covered by Demo Corp for defective items. Customer pays return shipping for change-of-mind returns. "
        "Exchanges are accepted within 60 days of purchase.",
        "return_policy"
    ),
    (
        "Shipping Information: Standard shipping takes 5-7 business days and costs $4.99. "
        "Express shipping takes 2-3 business days and costs $12.99. "
        "Overnight shipping is available for $24.99. "
        "All orders over $50 qualify for free standard shipping. "
        "Orders are processed within 1 business day. Tracking numbers are emailed once shipped.",
        "shipping_policy"
    ),
    (
        "Product Warranty: All products come with a 1-year limited warranty covering manufacturing defects. "
        "Electronics carry a 2-year warranty. The warranty does not cover accidental damage or misuse. "
        "To claim warranty, contact support@democorp.com with your order number and a photo of the defect. "
        "Warranty replacements are shipped within 3-5 business days at no cost to the customer.",
        "warranty_policy"
    ),
    (
        "Contact & Support: Customer support is available Monday–Friday 9am–6pm EST. "
        "Email: support@democorp.com. Phone: 1-800-555-0100. Live chat is available on the website. "
        "For urgent issues outside business hours, leave a voicemail and we will respond within 1 business day. "
        "Average response time for emails is 4 hours during business hours.",
        "contact_info"
    ),
    (
        "Account & Orders: To track your order, log in to your account and visit 'My Orders'. "
        "You can cancel an order within 1 hour of placing it. After that, the order enters processing and cannot be cancelled. "
        "To update your shipping address before dispatch, contact support immediately. "
        "Password resets can be done via the 'Forgot Password' link on the login page.",
        "account_orders"
    ),
]

for content, source_name in knowledge_chunks:
    s, b = req("POST", f"/admin/tenants/{tid}/knowledge/text", params={
        "content": content,
        "source_name": source_name,
    })
    print(f"Seeded {source_name}: status={b.get('status')} chunks={b.get('chunks_ingested')}")

print("\ndemo-tenant is ready. Use tenant_id: demo-tenant in the UI.")
print(f"Internal UUID: {tid}")
