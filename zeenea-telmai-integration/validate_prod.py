"""
Production validation script — run before first real deployment.

Tests:
  1. Zeenea connection (GET datasets)
  2. Zeenea introspection → discover real mutation name
  3. Zeenea write-back mutation (dry run on first dataset found)
  4. Telmai auth (OAuth2 token)
  5. Telmai asset list path
  6. Telmai DQ score path

Usage:
  pip install httpx
  python validate_prod.py
"""

import asyncio, json, os, sys, textwrap
import httpx

# ── Zeenea ──────────────────────────────────────────────────────────────────
ZEENEA_URL = os.getenv(
    "ZEENEA_URL",
    "https://demo-aha-1.preprod.zeenea.app/api/catalog/graphql",
)
ZEENEA_API_KEY = os.getenv(
    "ZEENEA_API_KEY",
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJ6ZWVuZWEiLCJhdWQiOiJ6ZWVuZWEiLCJleHAiOjE3ODgzOTM2MDAsImlhdCI6MTc3MjkxMDcxNiwiaWQiOiJlYTA2NTUyYS0yM2EyLTRkZWItODFlMC0xNDE4MzAyZjkyOTkiLCJleHBpcmVzQXQiOiIyMDI2LTA5LTAzVDAwOjAwOjAwWiIsImh0dHBzOi8vd3d3LnplZW5lYS5jb20vdGVuYW50IjoiZGVtby1haGEtMSIsIm5hbWUiOiJjd29vZFRlc3QifQ.b739WwJrquJqp21WNQU5M90HrThvYYsROViRrLi0GFl650Faikess9nviHWr6vDJi8YbHq2V9eGbuWWLI-vVghYZ4xak0g43wxYiUmItG2Wl6qOIsA1X9mU7gw81Y1ZgnKXUTeBmi-bC1kxwUjSAdMXykPPWJn6fO4bxvdHTQ6ZnIuX7B5LdPMbp6Jht2gKVgSxNv37ixnhcGJm5rCqCjpKf3Qai6YYw7dgCZOiHm5mRNS9tiGyeeYSUYjgyWRzOqvCkcd6W4rNXGaGiEXBfi7pYM1LSyO8cYV-PMiFduOzrpHcpyMlqe3qJve-9UiK8GYUDTq2fSbjMN_CgpPp_uIAEu08a69XufFGW9Za3JqBAPBpu0xtE4xIqRPPEocW4gDakskRnPIPH9-CH7Csa2CVKa-Id1LF_xkX3j392Fif5x4PmFJcYxVU9WfJ24ZtZNOIRauy0VwHMyIcm3nMYd-GxJsVOqwaqu4F5EBk5TKNhLtOcNegX1YnjT2fpeemjpWCoMLi57vn3-tVgwRLp3fnpMzu-r60YcNp17bakDXkPgSOJkNtQz-yzDZY_7JJHCSoed44EzYTKWb7ZvX5nCLR66IHHXy1CjRnLgc2moLpEYG_ycHgH6GRmnIXuSSr-_52qgkJrq1Xjy7-thHK0vI4qDd4wiFytzGPcG7xWH9U",
)

# ── Telmai (fill in or set env vars) ────────────────────────────────────────
TELMAI_ENDPOINT  = os.getenv("TELMAI_ENDPOINT",  "")
TELMAI_TENANT    = os.getenv("TELMAI_TENANT",    "")
TELMAI_USERNAME  = os.getenv("TELMAI_USERNAME",  "")
TELMAI_PASSWORD  = os.getenv("TELMAI_PASSWORD",  "")
TELMAI_CLIENT_ID = os.getenv("TELMAI_CLIENT_ID", "telmai")

# ── Helpers ──────────────────────────────────────────────────────────────────

PASS = "  ✅"
FAIL = "  ❌"
WARN = "  ⚠️ "
INFO = "  ℹ️ "

def section(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")

def ok(msg):   print(f"{PASS} {msg}")
def err(msg):  print(f"{FAIL} {msg}")
def warn(msg): print(f"{WARN} {msg}")
def info(msg): print(f"{INFO} {msg}")

def short(text, n=120):
    return textwrap.shorten(str(text), n, placeholder="…")


# ══════════════════════════════════════════════════════════════════════════════
# Zeenea tests
# ══════════════════════════════════════════════════════════════════════════════

async def zeenea_headers():
    return {"X-API-Key": ZEENEA_API_KEY}

async def zeenea_query(client: httpx.AsyncClient, query: str, variables: dict = None):
    params = {"query": query}
    if variables:
        params["variables"] = json.dumps(variables)
    r = await client.get(ZEENEA_URL, params=params, headers=await zeenea_headers())
    return r

async def zeenea_mutation(client: httpx.AsyncClient, mutation: str, variables: dict = None):
    payload = {"query": mutation}
    if variables:
        payload["variables"] = variables
    r = await client.post(
        ZEENEA_URL,
        json=payload,
        headers={**await zeenea_headers(), "Content-Type": "application/json"},
    )
    return r


async def test_zeenea_connection(client: httpx.AsyncClient):
    section("1. Zeenea — connection & dataset list")
    info(f"URL: {ZEENEA_URL}")

    query = """
    query { datasets(first: 3) { items { id name technicalName } pageInfo { hasNextPage } } }
    """
    try:
        r = await zeenea_query(client, query)
        info(f"HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            if "errors" in data:
                err(f"GraphQL errors: {short(data['errors'])}")
                return None
            items = data.get("data", {}).get("datasets", {}).get("items", [])
            ok(f"Got {len(items)} datasets")
            for d in items:
                print(f"       id={d['id']}  name={d['name']}")
            return items[0] if items else None
        else:
            err(f"HTTP {r.status_code}: {short(r.text)}")
            return None
    except Exception as e:
        err(str(e))
        return None


async def test_zeenea_introspection(client: httpx.AsyncClient):
    section("2. Zeenea — GraphQL introspection (discover mutations)")

    # Ask for the Mutation type's fields
    query = """
    query {
      __schema {
        mutationType {
          fields {
            name
            description
            args { name type { name kind ofType { name kind } } }
          }
        }
      }
    }
    """
    try:
        r = await zeenea_query(client, query)
        info(f"HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            if "errors" in data:
                err(f"Introspection errors: {short(data['errors'])}")
                return None
            mut_type = data.get("data", {}).get("__schema", {}).get("mutationType")
            if not mut_type:
                warn("No mutationType in schema (mutations may be disabled on this endpoint)")
                return None
            fields = mut_type.get("fields", [])
            ok(f"Found {len(fields)} mutation(s):")
            for f in fields:
                print(f"       • {f['name']} — {f.get('description','')[:80]}")
                for arg in f.get("args", []):
                    t = arg["type"]
                    type_name = t.get("name") or (t.get("ofType") or {}).get("name", "?")
                    print(f"           arg: {arg['name']}: {type_name}")
            # Return the name that looks like a property update
            update_mutations = [f["name"] for f in fields if "propert" in f["name"].lower() or "update" in f["name"].lower()]
            return update_mutations
        else:
            err(f"HTTP {r.status_code}: {short(r.text)}")
            return None
    except Exception as e:
        err(str(e))
        return None


async def test_zeenea_writeback(client: httpx.AsyncClient, dataset: dict, mutation_name: str = "updateItemProperties"):
    section(f"3. Zeenea — write-back mutation ({mutation_name})")
    if not dataset:
        warn("Skipping — no dataset from step 1")
        return

    item_id = dataset["id"]
    info(f"Target dataset: id={item_id}  name={dataset['name']}")

    # First, try to discover the exact input types via introspection
    introspect_q = f"""
    query {{
      __type(name: "{mutation_name}") {{ name kind }}
    }}
    """
    r = await zeenea_query(client, introspect_q)
    if r.status_code == 200:
        d = r.json().get("data", {}).get("__type")
        if d:
            info(f"Mutation type info: {d}")

    # Attempt the mutation with the confirmed property schema
    mutation = f"""
    mutation TestWriteback($itemKey: ItemKeyInput!, $properties: [PropertyValueInput!]!) {{
      {mutation_name}(itemKey: $itemKey, properties: $properties) {{
        key
        name
      }}
    }}
    """
    variables = {
        "itemKey":    {"id": item_id},
        "properties": [
            {"code": "DTC",         "value": "✭✭"},
            {"code": "certification", "value": "❌ Not certified"},
            {"code": "$z_tags",     "value": ["telmai-monitored", "dq-score-80"]},
        ],
    }

    try:
        r = await zeenea_mutation(client, mutation, variables)
        info(f"HTTP {r.status_code}")
        info(f"Response body: {short(r.text, 300)}")
        if r.status_code == 200:
            data = r.json()
            if "errors" in data:
                err(f"Mutation errors: {json.dumps(data['errors'], indent=2)}")
                # Try to extract useful hint
                for e in data.get("errors", []):
                    locs = e.get("locations", [])
                    ext  = e.get("extensions", {})
                    print(f"         message: {e.get('message')}")
                    print(f"         extensions: {ext}")
            else:
                ok(f"Mutation succeeded! Result: {short(data.get('data'))}")
        elif r.status_code == 400:
            # 400 usually means wrong mutation shape — parse and show
            try:
                body = r.json()
                err(f"Bad request — errors: {json.dumps(body, indent=2)[:500]}")
            except Exception:
                err(f"Bad request: {short(r.text)}")
        else:
            err(f"HTTP {r.status_code}: {short(r.text)}")
    except Exception as e:
        err(str(e))


# Alternate mutation names to try if updateItemProperties fails
ALTERNATE_MUTATIONS = [
    "updateProperties",
    "setItemProperties",
    "upsertItemProperties",
    "updateDatasetProperties",
    "patchItemProperties",
]

async def test_zeenea_alternate_mutations(client: httpx.AsyncClient, dataset: dict):
    section("3b. Zeenea — trying alternate mutation names")
    if not dataset:
        warn("Skipping — no dataset from step 1")
        return

    item_id = dataset["id"]
    for mut_name in ALTERNATE_MUTATIONS:
        mutation = f"""
        mutation {{
          {mut_name}(itemKey: {{id: "{item_id}"}}, properties: [{{code: "DTC", value: "✭✭"}}]) {{
            key
          }}
        }}
        """
        try:
            r = await zeenea_mutation(client, mutation)
            info(f"  {mut_name}: HTTP {r.status_code} — {short(r.text, 80)}")
        except Exception as e:
            info(f"  {mut_name}: exception — {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Telmai tests
# ══════════════════════════════════════════════════════════════════════════════

async def test_telmai_auth(client: httpx.AsyncClient):
    section("4. Telmai — OAuth2 token")
    if not TELMAI_ENDPOINT:
        warn("TELMAI_ENDPOINT not set — skipping Telmai tests")
        return None

    info(f"Endpoint: {TELMAI_ENDPOINT}")
    info(f"Tenant:   {TELMAI_TENANT}")
    info(f"Username: {TELMAI_USERNAME}")

    try:
        r = await client.post(
            f"{TELMAI_ENDPOINT.rstrip('/')}/auth/token",
            data={
                "grant_type": "password",
                "username":   TELMAI_USERNAME,
                "password":   TELMAI_PASSWORD,
                "clientId":   TELMAI_CLIENT_ID,
                "tenant":     TELMAI_TENANT,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        info(f"HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            token = data.get("access_token", "")
            expires = data.get("expires", data.get("expires_in", "?"))
            ok(f"Token obtained — expires in {expires}s, starts: {token[:40]}…")
            return token
        else:
            err(f"HTTP {r.status_code}: {short(r.text)}")
            return None
    except Exception as e:
        err(str(e))
        return None


async def test_telmai_assets(client: httpx.AsyncClient, token: str):
    section("5. Telmai — asset list (/configuration/assets)")
    if not token:
        warn("Skipping — no token")
        return None

    url = f"{TELMAI_ENDPOINT.rstrip('/')}/api/backend/{TELMAI_TENANT}/configuration/assets"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    info(f"GET {url}")

    try:
        r = await client.get(url, headers=headers)
        info(f"HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            items = data if isinstance(data, list) else data.get("data", data.get("items", []))
            ok(f"Got {len(items)} asset(s)")
            for a in items[:5]:
                asset_id = a.get("id") or a.get("assetId", "?")
                name     = a.get("name") or a.get("displayName", "?")
                print(f"       id={asset_id}  name={name}")
            return items[0] if items else None
        elif r.status_code == 404:
            err("404 — path /configuration/assets not found; trying alternate paths…")
            for alt in ["assets", "sources", "datasets", "configuration/sources"]:
                alt_url = f"{TELMAI_ENDPOINT.rstrip('/')}/api/backend/{TELMAI_TENANT}/{alt}"
                r2 = await client.get(alt_url, headers=headers)
                info(f"  GET …/{alt}: HTTP {r2.status_code}")
                if r2.status_code == 200:
                    ok(f"  Found at /{alt}!")
                    break
            return None
        else:
            err(f"HTTP {r.status_code}: {short(r.text)}")
            return None
    except Exception as e:
        err(str(e))
        return None


async def test_telmai_dq_score(client: httpx.AsyncClient, token: str, asset: dict):
    section("6. Telmai — DQ score (/configuration/assets/{id}/dq_score)")
    if not token or not asset:
        warn("Skipping — no token or asset from step 5")
        return

    asset_id = asset.get("id") or asset.get("assetId", "")
    url = f"{TELMAI_ENDPOINT.rstrip('/')}/api/backend/{TELMAI_TENANT}/configuration/assets/{asset_id}/dq_score"
    headers = {"Authorization": f"Bearer {token}"}
    info(f"GET {url}")

    try:
        r = await client.get(url, headers=headers)
        info(f"HTTP {r.status_code}")
        if r.status_code == 200:
            ok(f"DQ score response: {short(r.text, 200)}")
        else:
            err(f"HTTP {r.status_code}: {short(r.text)}")
    except Exception as e:
        err(str(e))


async def test_telmai_incidents(client: httpx.AsyncClient, token: str):
    section("7. Telmai — incidents (/incidents)")
    if not token:
        warn("Skipping — no token")
        return

    url = f"{TELMAI_ENDPOINT.rstrip('/')}/api/backend/{TELMAI_TENANT}/incidents"
    headers = {"Authorization": f"Bearer {token}"}
    info(f"GET {url}")

    try:
        r = await client.get(url, headers=headers)
        info(f"HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            items = data if isinstance(data, list) else data.get("data", [])
            ok(f"Got {len(items)} incident(s)")
        else:
            err(f"HTTP {r.status_code}: {short(r.text)}")
    except Exception as e:
        err(str(e))


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    print("=" * 60)
    print("  Zeenea ↔ Telmai — Production Validation Script")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        # ── Zeenea ──────────────────────────────────────
        dataset = await test_zeenea_connection(client)
        mutation_names = await test_zeenea_introspection(client)

        # Pick the best mutation name from introspection, fall back to default
        if mutation_names:
            chosen_mutation = mutation_names[0]
            ok(f"Using discovered mutation: {chosen_mutation}")
        else:
            chosen_mutation = "updateItemProperties"
            warn(f"Introspection unavailable — trying default: {chosen_mutation}")

        await test_zeenea_writeback(client, dataset, chosen_mutation)

        # If the primary mutation failed, try alternates
        if dataset:
            await test_zeenea_alternate_mutations(client, dataset)

        # ── Telmai ──────────────────────────────────────
        token = await test_telmai_auth(client)
        asset = await test_telmai_assets(client, token)
        await test_telmai_dq_score(client, token, asset)
        await test_telmai_incidents(client, token)

    print("\n" + "=" * 60)
    print("  Validation complete — review results above.")
    print("  ✅ = confirmed working   ❌ = needs fix   ⚠️  = action needed")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
