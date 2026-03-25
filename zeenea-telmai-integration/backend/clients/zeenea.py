"""
Zeenea GraphQL API client.

Auth:     Authorization: Bearer {api_key}
Endpoint: https://{tenant}.zeenea.app/api/graphql

Property codes confirmed from live metamodel introspection:
  DTC          - Data Trust Classification: "✭" / "✭✭" / "✭✭✭"
  certification - "⭐️ Certified" / "❌ Not certified"
  assetStatus  - "🏆 Gold Standard" / "🟠 To be improved" / "❌ To be decomissioned"
  dataProfilingAvailable - "✅ Yes" / "❌ No"
  $z_tags      - list of strings

GraphQL mutation `updateItemProperties` is the standard Zeenea write-back mutation.
If a mutation error occurs we log the full error array for easier debugging.
"""

import httpx
import logging
from typing import List, Optional
from models import ZeneaDataset

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_DATASETS = [
    ZeneaDataset(id="zee-001", name="customer_orders",   technical_name="raw.customer_orders",            description="All customer orders including historical and current data"),
    ZeneaDataset(id="zee-002", name="product_catalog",   technical_name="core.product_catalog",           description="Master product catalog with pricing and attributes"),
    ZeneaDataset(id="zee-003", name="user_events",       technical_name="analytics.user_events",          description="Clickstream and behavioral event data from all channels"),
    ZeneaDataset(id="zee-004", name="inventory_levels",  technical_name="ops.inventory_levels",           description="Real-time inventory levels across all warehouse locations"),
    ZeneaDataset(id="zee-005", name="revenue_metrics",   technical_name="finance.revenue_metrics",        description="Aggregated revenue metrics by product, region, and period"),
    ZeneaDataset(id="zee-006", name="supplier_contracts", technical_name="procurement.supplier_contracts", description="Active and historical supplier contract terms and SLAs"),
]


# ---------------------------------------------------------------------------
# Property mapping: Telmai score → Zeenea property values
# ---------------------------------------------------------------------------

def _compute_properties(score: float, alert_count: int) -> List[dict]:
    """
    Map Telmai quality metrics to the confirmed Zeenea property schema.

    DTC (Data Trust Classification):
      ✭✭✭  score >= 85
      ✭✭   score >= 65
      ✭    score <  65

    certification:
      ⭐️ Certified      score >= 85 AND alert_count == 0
      ❌ Not certified   otherwise

    assetStatus:
      🏆 Gold Standard      score >= 85
      🟠 To be improved     score >= 60
      ❌ To be decomissioned score < 60   (note: Zeenea spells it this way)

    $z_tags: always includes "telmai-monitored" + a dq-score tag
    """
    if score >= 85:
        dtc = "✭✭✭"
    elif score >= 65:
        dtc = "✭✭"
    else:
        dtc = "✭"

    certification = "⭐️ Certified" if (score >= 85 and alert_count == 0) else "❌ Not certified"

    if score >= 85:
        asset_status = "🏆 Gold Standard"
    elif score >= 60:
        asset_status = "🟠 To be improved"
    else:
        asset_status = "❌ To be decomissioned"

    score_tag = f"dq-score-{int(round(score))}"

    return [
        {"code": "DTC",                    "value": dtc},
        {"code": "certification",          "value": certification},
        {"code": "assetStatus",            "value": asset_status},
        {"code": "dataProfilingAvailable", "value": "✅ Yes"},
        {"code": "$z_tags",                "value": ["telmai-monitored", score_tag]},
    ]


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class ZeneaClient:
    """
    Client for the Zeenea Data Catalog GraphQL API.

    Config params:
      url     - GraphQL endpoint, e.g. https://tenant.zeenea.app/api/graphql
      api_key - API key (sent as Bearer token)
    """

    def __init__(self, url: str, api_key: str):
        self.url = url or ""
        self.api_key = api_key or ""
        self._is_mock = not url or not api_key or api_key == "your_zeenea_api_key"

    def _headers(self) -> dict:
        # Zeenea catalog API uses X-API-Key, not Authorization: Bearer
        return {"X-API-Key": self.api_key}

    async def _graphql_query(self, query: str, variables: Optional[dict] = None) -> dict:
        """
        Execute a GraphQL *query* via GET with query string params.
        Zeenea catalog API: GET /api/catalog/graphql?query=...&variables=...
        """
        import json as _json
        params: dict = {"query": query}
        if variables:
            params["variables"] = _json.dumps(variables)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.url, params=params, headers=self._headers())
            response.raise_for_status()
            return response.json()

    async def _graphql_mutation(self, mutation: str, variables: Optional[dict] = None) -> dict:
        """
        Execute a GraphQL *mutation* via POST with JSON body.
        Mutations must use POST even though queries use GET.
        """
        payload: dict = {"query": mutation}
        if variables:
            payload["variables"] = variables

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.url,
                json=payload,
                headers={**self._headers(), "Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()

    async def get_datasets(self) -> List[ZeneaDataset]:
        """Return all datasets from the Zeenea catalog."""
        if self._is_mock:
            return MOCK_DATASETS

        # Zeenea GraphQL pagination uses cursor-based `after` / `first`
        query = """
        query GetDatasets($first: Int, $after: String) {
          datasets(first: $first, after: $after) {
            items {
              id
              name
              technicalName
              description
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        """

        datasets: List[ZeneaDataset] = []
        after: Optional[str] = None

        while True:
            data = await self._graphql_query(query, {"first": 100, "after": after})
            result = data.get("data", {}).get("datasets", {})
            for item in result.get("items", []):
                datasets.append(ZeneaDataset(
                    id=item["id"],
                    name=item["name"],
                    technical_name=item.get("technicalName") or item["name"],
                    description=item.get("description"),
                ))
            page_info = result.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")

        return datasets

    async def update_quality_properties(
        self,
        item_id: str,
        score: float,
        alert_count: int,
        last_checked: str,
    ) -> bool:
        """
        Write Telmai quality metrics back to a Zeenea dataset item.

        Uses the `updateItemProperties` mutation with the real property codes
        confirmed from the live Zeenea metamodel.

        Returns True on success, False if the API returned GraphQL errors.
        """
        properties = _compute_properties(score, alert_count)

        if self._is_mock:
            logger.info(
                "Mock mode — would update Zeenea item '%s' with: %s",
                item_id,
                [{p["code"]: p["value"]} for p in properties],
            )
            return True

        mutation = """
        mutation UpdateItemProperties(
          $itemKey: ItemKeyInput!
          $properties: [PropertyValueInput!]!
        ) {
          updateItemProperties(itemKey: $itemKey, properties: $properties) {
            key
            name
          }
        }
        """
        variables = {
            "itemKey":    {"id": item_id},
            "properties": properties,
        }

        data = await self._graphql_mutation(mutation, variables)

        if "errors" in data:
            logger.error(
                "Zeenea mutation errors for item '%s': %s",
                item_id,
                data["errors"],
            )
            return False

        return True

    async def test_connection(self) -> tuple[bool, str, Optional[int]]:
        if self._is_mock:
            return True, "Mock mode — no credentials configured", len(MOCK_DATASETS)

        try:
            datasets = await self.get_datasets()
            return True, "Connected successfully", len(datasets)
        except httpx.HTTPStatusError as e:
            return False, f"HTTP {e.response.status_code}: {e.response.text[:200]}", None
        except Exception as e:
            return False, str(e)[:200], None
