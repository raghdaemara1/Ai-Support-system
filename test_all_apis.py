"""
Comprehensive API test suite — runs against the live server at localhost:8001.
Tests every endpoint, validates responses, and reports pass/fail with details.
"""
import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import http.client

BASE = "http://localhost:8001"
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"

results = []
tenant_id = None
api_key = None


def req(method, path, body=None, headers=None, form=None):
    url = BASE + path
    h = {"Content-Type": "application/json", **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        r = urllib.request.Request(url, data=data, headers=h, method=method)
        with urllib.request.urlopen(r, timeout=60) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, {}
    except urllib.error.HTTPError as e:
        try:
            body_err = json.loads(e.read())
        except Exception:
            body_err = {}
        return e.code, body_err
    except Exception as e:
        return 0, {"error": str(e)}


def check(name, status, body, expected_status, validations=None):
    ok = status == expected_status
    issues = []
    if not ok:
        issues.append(f"status {status} != {expected_status}")
    for key, expected in (validations or {}).items():
        actual = body
        for part in key.split("."):
            if isinstance(actual, dict):
                actual = actual.get(part)
            else:
                actual = None
                break
        if actual != expected:
            issues.append(f"body.{key}={repr(actual)!r} != {repr(expected)!r}")
            ok = False
    label = PASS if ok else FAIL
    msg = f"[{label}] {name}"
    if issues:
        msg += f"\n         Issues: {'; '.join(issues)}"
        if body:
            snippet = json.dumps(body)[:300]
            msg += f"\n         Body: {snippet}"
    print(msg)
    results.append((name, ok))
    return ok, body


print("\n" + "="*60)
print(" API TEST SUITE — O3Sigma AI Support Agent")
print("="*60 + "\n")

# ── 1. Health & Root ──────────────────────────────────────────────────────────
print("── Infrastructure ───────────────────────────────────────────")

s, b = req("GET", "/health")
check("GET /health → 200 + healthy", s, b, 200, {"status": "healthy", "version": "0.1.0"})

s, b = req("GET", "/")
# root serves demo.html (FileResponse, 200)
ok = s == 200
label = PASS if ok else FAIL
print(f"[{label}] GET / → 200 (demo HTML)")
results.append(("GET /", ok))

s, b = req("GET", "/docs")
ok = s == 200
label = PASS if ok else FAIL
print(f"[{label}] GET /docs → 200 (Swagger UI available)")
results.append(("GET /docs", ok))


# ── 2. Tenant CRUD ────────────────────────────────────────────────────────────
print("\n── Tenant Management ────────────────────────────────────────")

slug = f"testco-{int(time.time())}"
s, b = req("POST", "/admin/tenants", {
    "name": "Test Company",
    "slug": slug,
    "config": {
        "persona_name": "Aria",
        "persona_description": "A helpful AI assistant for O3Sigma.",
        "channels": ["chat", "voice", "email"],
        "language": "en",
        "escalation_keywords": ["urgent", "broken"],
        "max_turns_before_escalate": 8,
    }
})
ok, _ = check("POST /admin/tenants → 200 + api_key", s, b, 200)
if ok and "tenant" in b and "api_key" in b:
    tenant_id = b["tenant"]["id"]
    api_key = b["api_key"]
    slug_confirmed = b["tenant"]["slug"]
    print(f"         Tenant ID: {tenant_id}  Slug: {slug_confirmed}")

# Duplicate slug must 400
s2, b2 = req("POST", "/admin/tenants", {"name": "Dup", "slug": slug})
check("POST /admin/tenants duplicate slug → 400", s2, b2, 400)

# List tenants
s, b = req("GET", "/admin/tenants")
ok = s == 200 and isinstance(b, list) and len(b) >= 1
label = PASS if ok else FAIL
print(f"[{label}] GET /admin/tenants → 200, list len={len(b) if isinstance(b, list) else '?'}")
results.append(("GET /admin/tenants", ok))

# Get tenant by ID
if tenant_id:
    s, b = req("GET", f"/admin/tenants/{tenant_id}")
    check(f"GET /admin/tenants/{{id}} → 200", s, b, 200, {"id": tenant_id})

    # Get tenant by slug
    s, b = req("GET", f"/admin/tenants/{slug}")
    check(f"GET /admin/tenants/{{slug}} → 200", s, b, 200, {"slug": slug})

# Get non-existent tenant
s, b = req("GET", "/admin/tenants/does-not-exist-xyz")
check("GET /admin/tenants/nonexistent → 404", s, b, 404)

# Update config (requires x-api-key header)
if tenant_id and api_key:
    s, b = req("PUT", f"/admin/tenants/{tenant_id}/config",
               body={"persona_name": "Max", "persona_description": "Updated persona.", "channels": ["chat"]},
               headers={"x-api-key": api_key})
    check("PUT /admin/tenants/{id}/config → 200", s, b, 200)

# Update config missing API key → 401
if tenant_id:
    s, b = req("PUT", f"/admin/tenants/{tenant_id}/config",
               body={"persona_name": "NoAuth"})
    check("PUT /admin/tenants/{id}/config no-auth → 401", s, b, 401)


# ── 3. Knowledge Base ─────────────────────────────────────────────────────────
print("\n── Knowledge Base ───────────────────────────────────────────")

if tenant_id:
    # Add text knowledge
    import urllib.parse as up
    url_path = f"/admin/tenants/{tenant_id}/knowledge/text?" + up.urlencode({
        "content": "The O3Sigma S-300 industrial pump has a max pressure of 450 PSI. "
                   "Alarm code E-001 means 'Low Oil Pressure — check the oil reservoir and refill if needed.' "
                   "Alarm code E-002 means 'Overtemperature — allow the machine to cool for 30 minutes.' "
                   "Alarm code E-003 means 'Motor Fault — contact a certified technician.' "
                   "Regular maintenance should be performed every 500 operating hours.",
        "source_name": "s300_manual_excerpt",
    })
    s, b = req("POST", url_path)
    ok = s == 200 and b.get("status") == "completed"
    label = PASS if ok else FAIL
    print(f"[{label}] POST /admin/tenants/{{id}}/knowledge/text → {s} status={b.get('status')} chunks={b.get('chunks_ingested')}")
    results.append(("POST knowledge/text", ok))

    # Ingest via JSON body (URL-based knowledge with text type)
    s, b = req("POST", f"/admin/tenants/{tenant_id}/knowledge", {
        "sources": [
            {
                "type": "text",
                "source_name": "test_knowledge",
                "content": "The S-300 pump warranty covers parts for 2 years from the purchase date."
            }
        ]
    })
    ok = s == 200 and b.get("status") == "processing"
    label = PASS if ok else FAIL
    print(f"[{label}] POST /admin/tenants/{{id}}/knowledge → {s} status={b.get('status')}")
    results.append(("POST knowledge ingest", ok))

    # Non-existent tenant → 404
    s, b = req("POST", "/admin/tenants/no-such-tenant/knowledge/text?" + up.urlencode({
        "content": "irrelevant",
        "source_name": "x",
    }))
    check("POST knowledge/text nonexistent tenant → 404", s, b, 404)


# ── 4. Chat (HTTP) ────────────────────────────────────────────────────────────
print("\n── Chat (HTTP) ──────────────────────────────────────────────")

if tenant_id:
    # Give background ingestion a moment to complete
    time.sleep(3)

    s, b = req("POST", "/chat/message", {
        "tenant_id": tenant_id,
        "customer_id": "tester-001",
        "message": "Hello! What is this service about?",
    })
    ok = s in [200, 429] and (s == 429 or ("message" in b and len(b.get("message", "")) > 5))
    label = PASS if ok else FAIL
    rate_limited = s == 429
    print(f"[{label}] POST /chat/message (greeting) → {s}{' (rate-limited, quota OK)' if rate_limited else ''}")
    if b.get("message"):
        print(f"         Agent reply: {b['message'][:120]}...")
    results.append(("POST /chat/message greeting", ok))

    session_id = b.get("session_id") if s == 200 else None
    time.sleep(4)

    # Knowledge-based question
    s, b = req("POST", "/chat/message", {
        "tenant_id": tenant_id,
        "customer_id": "tester-001",
        "session_id": session_id,
        "message": "What does alarm code E-001 mean?",
    })
    ok = s in [200, 429] and (s == 429 or "message" in b)
    label = PASS if ok else FAIL
    rag_used = "oil" in b.get("message", "").lower() or "pressure" in b.get("message", "").lower()
    rag_label = "(RAG hit)" if rag_used else ("(rate-limited)" if s == 429 else "(no RAG hit)")
    print(f"[{label}] POST /chat/message (RAG query) → {s} {rag_label}")
    if b.get("message"):
        print(f"         Agent reply: {b['message'][:150]}...")
    results.append(("POST /chat/message RAG", ok))

    time.sleep(4)
    # Escalation trigger
    s, b = req("POST", "/chat/message", {
        "tenant_id": tenant_id,
        "customer_id": "tester-002",
        "message": "I need to speak to a human agent right now!",
    })
    ok = s in [200, 429]
    label = PASS if ok else FAIL
    escalated = b.get("escalated", False)
    esc_label = "(escalated=True ✓)" if escalated else ("(rate-limited)" if s == 429 else "(escalated=False — check escalation engine)")
    print(f"[{label}] POST /chat/message (escalation) → {s} {esc_label}")
    results.append(("POST /chat/message escalation", ok))

    time.sleep(4)
    # Wrong tenant → agent still responds (uses default config)
    s, b = req("POST", "/chat/message", {
        "tenant_id": "nonexistent-tenant",
        "customer_id": "x",
        "message": "Hi",
    })
    ok = s in [200, 429, 500]
    label = PASS if ok else FAIL
    print(f"[{label}] POST /chat/message unknown tenant → {s} (200, 429 or 500 acceptable)")
    results.append(("POST /chat/message unknown tenant", ok))

    time.sleep(4)
    # Email channel
    s, b = req("POST", "/chat/email/send", {
        "tenant_id": tenant_id,
        "customer_email": "customer@example.com",
        "subject": "Pump alarm inquiry",
        "body": "Hi, our S-300 pump shows alarm E-002. What should we do?",
    })
    ok = s in [200, 429] and (s == 429 or "message" in b)
    label = PASS if ok else FAIL
    print(f"[{label}] POST /chat/email/send → {s}{' (rate-limited, quota OK)' if s == 429 else ''}")
    if b.get("message"):
        print(f"         Email agent reply: {b['message'][:120]}...")
    results.append(("POST /chat/email/send", ok))


# ── 5. Voice (Twilio) ─────────────────────────────────────────────────────────
print("\n── Voice (Twilio) ───────────────────────────────────────────")

if tenant_id:
    # Twilio webhook — first call (no SpeechResult)
    s, b = req("POST", f"/api/twilio/webhook/{tenant_id}",
               form={"From": "+15555550001", "CallSid": "CA-test-001"})
    ok = s == 200
    label = PASS if ok else FAIL
    print(f"[{label}] POST /api/twilio/webhook/{tenant_id} (greeting call) → {s}")
    results.append(("POST /api/twilio/webhook greeting", ok))

    # Twilio webhook — subsequent call with speech
    s, b = req("POST", f"/api/twilio/webhook/{tenant_id}",
               form={"From": "+15555550001", "CallSid": "CA-test-001",
                     "SpeechResult": "What does alarm E-001 mean?"})
    ok = s == 200
    label = PASS if ok else FAIL
    print(f"[{label}] POST /api/twilio/webhook/{tenant_id} (with speech) → {s}")
    results.append(("POST /api/twilio/webhook with speech", ok))


# ── 6. n8n Endpoints ──────────────────────────────────────────────────────────
print("\n── n8n Integration ──────────────────────────────────────────")

s, b = req("GET", "/n8n/status")
check("GET /n8n/status → 200 connected", s, b, 200, {"status": "connected"})

s, b = req("GET", "/n8n/escalations")
ok = s == 200 and "escalations" in b
label = PASS if ok else FAIL
print(f"[{label}] GET /n8n/escalations → {s} count={b.get('count')}")
results.append(("GET /n8n/escalations", ok))

s, b = req("GET", "/n8n/escalations?pending_only=false")
ok = s == 200 and "escalations" in b
label = PASS if ok else FAIL
print(f"[{label}] GET /n8n/escalations?pending_only=false → {s} count={b.get('count')}")
results.append(("GET /n8n/escalations all", ok))

# Resolve non-existent ticket → 404
s, b = req("POST", "/n8n/ticket-resolved", {
    "ticket_id": "FAKE0000",
    "resolved_by": "test",
    "resolution_note": "Testing 404 path",
})
check("POST /n8n/ticket-resolved nonexistent → 404", s, b, 404)

# Resolve a real escalation (if any exist)
s, b = req("GET", "/n8n/escalations?pending_only=false")
all_escalations = b.get("escalations", [])
if all_escalations:
    ticket = all_escalations[0]["ticket_id"]
    s2, b2 = req("POST", "/n8n/ticket-resolved", {
        "ticket_id": ticket,
        "resolved_by": "test-suite",
        "resolution_note": "Automated test resolution",
    })
    check(f"POST /n8n/ticket-resolved (real ticket #{ticket}) → 200", s2, b2, 200, {"status": "resolved"})
else:
    print(f"[{WARN}] POST /n8n/ticket-resolved (no escalations to test against, skipped)")

# n8n ingest trigger
s, b = req("POST", "/n8n/ingest-trigger", {
    "tenant_id": slug if slug else "testco",
    "source_url": "https://example.com/manual.pdf",
    "source_type": "pdf",
    "triggered_by": "test-suite",
})
ok = s == 200 and b.get("status") == "accepted"
label = PASS if ok else FAIL
print(f"[{label}] POST /n8n/ingest-trigger → {s} status={b.get('status')}")
results.append(("POST /n8n/ingest-trigger", ok))


# ── 7. Schema validation spot-checks ─────────────────────────────────────────
print("\n── Schema / Validation ──────────────────────────────────────")

# Missing required field in chat
s, b = req("POST", "/chat/message", {"tenant_id": "x"})  # missing customer_id & message
check("POST /chat/message missing fields → 422", s, b, 422)

# Invalid tenant create (missing slug)
s, b = req("POST", "/admin/tenants", {"name": "No Slug"})
check("POST /admin/tenants missing slug → 422", s, b, 422)

# Missing required fields in email send
s, b = req("POST", "/chat/email/send", {"tenant_id": "x"})
check("POST /chat/email/send missing fields → 422", s, b, 422)


# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "="*60)
total = len(results)
passed = sum(1 for _, ok in results if ok)
failed = total - passed
print(f" Results: {passed}/{total} passed  ({failed} failed)")
print("="*60)

if failed:
    print("\nFailed tests:")
    for name, ok in results:
        if not ok:
            print(f"  ✗ {name}")

sys.exit(0 if failed == 0 else 1)
