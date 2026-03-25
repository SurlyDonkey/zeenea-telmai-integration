"""
Zeenea GraphQL API client.

Confirmed via live introspection and mutation tests against demo-aha-1.preprod.zeenea.app:

AUTH
  Header: X-API-SECRET  (NOT X-API-Key, NOT Authorization: Bearer)
  Value:  your Zeenea JWT/API key

QUERIES  (GET /api/catalog/graphql?query=...)
  items(type: "dataset", first: N, after: cursor)
    → nodes { key  name  type }
  item(ref: "<key>")
    → key  name  property(ref: "<code>")  quality { ... }

MUTATIONS  (POST /api/catalog/graphql  JSON body)
  updateItem(input: UpdateItemInput!)
    updates.properties[]:
      command: REPLACE | MERGE | REMOVE | CLEAR   (no "SET" — use REPLACE)
      ref:     property code string
      value:   property value

  updateDataQualityStatementV2(input: UpdateDataQualityStatementInput!)
    quality:
      originator:    free-form string, e.g. "Telmai"
      trustScore:    FRACTION 0.0–1.0  (82.5% → 0.825)
      dashboardLink: URL string
      checks[]:
        name:   string
        result: PASS | FAIL | WARNING
        score:  string (optional)

ITEM TYPE CODES  (case-sensitive lowercase strings)
  "dataset", "data-process", "data-product", "contact", ...

PROPERTY CODES  (confirmed from live metamodel — NOT all apply to every dataset type)
  DTC                    Data Trust Classification: "✭" / "✭✭" / "✭✭✭"
  certification          "⭐️ Certified" / "❌ Not certified"
  assetStatus            "🏆 Gold Standard" / "🟠 To be improved" / "❌ To be decomissioned"
                         NOTE: only exists on some item types; skip gracefully if not found
  dataProfilingAvailable "✅ Yes" / "❌ No"
  $z_tags                list of strings (use MERGE to append, REPLACE to overwrite)
"""

import json as _json
import logging
from typing import Any, Dict, List, Optional

import httpx

from models import ZeneaDataset

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock data  (used when credentials are not configured)
# ---------------------------------------------------------------------------

MOCK_DATASETS = [
    ZeneaDataset(id="zee-001", name="customer_orders",    technical_name="raw.customer_orders",             description="All customer orders including historical and current data"),
    ZeneaDataset(id="zee-002", name="product_catalog",    technical_name="core.product_catalog",            description="Master product catalog with pricing and attributes"),
    ZeneaDataset(id="zee-003", name="user_events",        technical_name="analytics.user_events",           description="Clickstream and behavioral event data from all channels"),
    ZeneaDataset(id="zee-004", name="inventory_levels",   technical_name="ops.inventory_levels",            description="Real-time inventory levels across all warehouse locations"),
    ZeneaDataset(id="zee-005", name="revenue_metrics",    technical_name="finance.revenue_metrics",         description="Aggregated revenue metrics by product, region, and period"),
    ZeneaDataset(id="zee-006", name="supplier_contracts", technical_name="procurement.supplier_contracts",  description="Active and historical supplier contract terms and SLAs"),
]


# ---------------------------------------------------------------------------
# Quality helpers
# ---------------------------------------------------------------------------

def _compute_properties(score: float, alert_count: int) -> List[Dict[str, Any]]:
    """
    Map Telmai quality metrics to confirmed Zeenea property values.

    DTC (Data Trust Classification):
      ✭✭✭  score >= 85
      ✭✭   score >= 65
      ✭    score <  65

    certification:
      ⭐️ Certified     score >= 85 AND alert_count == 0
      ❌ Not certified  otherwise

    assetStatus  (only set when the property exists on the item type):
      🏆 Gold Standard       score >= 85
      🟠 To be improved      score >= 60
      ❌ To be decomissioned  score < 60

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
        {"command": "REPLACE", "ref": "DTC",                    "value": dtc},
        {"command": "REPLACE", "ref": "certification",          "value": certification},
        {"command": "REPLACE", "ref": "assetStatus",            "value": asset_status},
        {"command": "REPLACE", "ref": "dataProfilingAvailable", "value": "✅ Yes"},
        {"command": "MERGE",   "ref": "$z_tags",                "value": ["telmai-monitored", score_tag]},
    ]


def _dq_checks_from_score(score: float) -> List[Dict[str, Any]]:
    """Convert a Telmai aggregate score into Zeenea DQ check results."""
    result = "PASS" if score >= 85 else ("WARNING" if score >= 65 else "FAIL")
    return [
        {
            "name":   "Telmai overall quality score",
            "result": result,
            "score":  str(round(score, 1)),
        }
    ]


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class ZeneaClient:
    """
    Client for the Zeenea Data Catalog GraphQL API.

    Config params:
      url     - GraphQL endpoint, e.g. https://{tenant}.zeenea.app/api/catalog/graphql
      api_key - API key (sent as X-API-SECRET header)
    """

    def __init__(self, url: str, api_key: str):
        self.url = url or ""
        self.api_key = api_key or ""
        self._is_mock = not url or not api_key or api_key == "your_zeenea_api_key"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        # Confirmed: Zeenea catalog API uses X-API-SECRET header
        return {"X-API-SECRET": self.api_key}

    async def _graphql_query(self, query: str, variables: Optional[dict] = None) -> dict:
        """
        Execute a GraphQL query via GET with ?query=...&variables=... params.
        Zeenea catalog API serves read queries over GET.
        """
        params: dict = {"query": query}
        if variables:
            params["variables"] = _json.dumps(variables)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(self.url, params=params, headers=self._headers())
            response.raise_for_status()
            return response.json()

    async def _graphql_mutation(self, mutation: str, variables: Optional[dict] = None) -> dict:
        """
        Execute a GraphQL mutation via POST with JSON body.
        Mutations must use POST even though queries use GET.
        """
        payload: dict = {"query": mutation}
        if variables:
            payload["variables"] = variables

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.post(
                self.url,
                json=payload,
                headers={**self._headers(), "Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_datasets(self) -> List[ZeneaDataset]:
        """
        Return all datasets from the Zeenea catalog.

        Uses the confirmed query shape:
          items(type: "dataset", first: 100, after: cursor)
            nodes { key name type }

        The item `key` is used as the stable identifier (format: source/schema/table).
        """
        if self._is_mock:
            return MOCK_DATASETS

        query = """
        query GetDatasets($first: Int, $after: String) {
          items(type: "dataset", first: $first, after: $after) {
            nodes {
              key
              name
              type
            }
            pageInfo {
              hasNextPage
              endCursor
            }
            totalCount
          }
        }
        """

        datasets: List[ZeneaDataset] = []
        after: Optional[str] = None

        while True:
            data = await self._graphql_query(query, {"first": 100, "after": after})

            if "errors" in data:
                logger.error("Zeenea get_datasets errors: %s", data["errors"])
                break

            result = data.get("data", {}).get("items", {})
            for node in result.get("nodes", []):
                key = node["key"]
                # key format: "source/schema/table" — use as both id and technical_name
                datasets.append(ZeneaDataset(
                    id=key,
                    name=node.get("name") or key.split("/")[-1],
                    technical_name=key,
                    description=None,
                ))

            page_info = result.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")

        return datasets

    async def update_quality_properties(
        self,
        item_key: str,
        score: float,
        alert_count: int,
        last_checked: str,
    ) -> bool:
        """
        Write Telmai quality metrics back to a Zeenea dataset item using two mutations:

        1. updateItem — sets DTC, certification, assetStatus, $z_tags
           command: REPLACE for single-value props, MERGE for $z_tags
           NOTE: assetStatus may not exist on all item types; errors are logged and skipped.

        2. updateDataQualityStatementV2 — sets the native DQ panel
           trustScore: pass as FRACTION (0.0–1.0), e.g. 82.5% → 0.825

        Returns True if at least the DQ statement mutation succeeded.
        """
        if self._is_mock:
            props = _compute_properties(score, alert_count)
            logger.info(
                "Mock mode — would update Zeenea item '%s': score=%.1f alerts=%d props=%s",
                item_key, score, alert_count,
                [{p["ref"]: p["value"]} for p in props],
            )
            return True

        success = False

        # ── Mutation 1: item properties ──────────────────────────────────────
        props = _compute_properties(score, alert_count)

        # First try with assetStatus; if it fails, retry without it
        for attempt_props in [props, [p for p in props if p["ref"] != "assetStatus"]]:
            prop_mutation = """
            mutation UpdateItemProps($input: UpdateItemInput!) {
              updateItem(input: $input) {
                item { key name }
              }
            }
            """
            prop_variables = {
                "input": {
                    "ref":     item_key,
                    "updates": {"properties": attempt_props},
                }
            }

            try:
                data = await self._graphql_mutation(prop_mutation, prop_variables)
            except httpx.HTTPStatusError as exc:
                logger.error("Zeenea updateItem HTTP error for '%s': %s", item_key, exc)
                break

            errors = data.get("errors", [])
            not_found = [
                e for e in errors
                if e.get("extensions", {}).get("code") == "PROPERTY_NOT_FOUND"
            ]
            other_errors = [e for e in errors if e not in not_found]

            if other_errors:
                logger.error("Zeenea updateItem errors for '%s': %s", item_key, other_errors)
                break

            if not_found and attempt_props == props:
                # assetStatus not available on this item type — retry without it
                missing = [e["extensions"].get("value") for e in not_found]
                logger.warning(
                    "Zeenea: properties not found on item '%s': %s — retrying without them",
                    item_key, missing,
                )
                continue

            # Success (possibly with partial properties)
            logger.info("Zeenea updateItem succeeded for '%s'", item_key)
            break

        # ── Mutation 2: native DQ statement ──────────────────────────────────
        dq_mutation = """
        mutation UpdateDQ($input: UpdateDataQualityStatementInput!) {
          updateDataQualityStatementV2(input: $input) {
            item { key name }
            clientMutationId
          }
        }
        """
        dq_variables = {
            "input": {
                "ref": item_key,
                "quality": {
                    "originator":    "Telmai",
                    "trustScore":    round(score / 100.0, 4),  # 82.5 → 0.8250
                    "dashboardLink": "https://app.telm.ai",
                    "checks":        _dq_checks_from_score(score),
                },
            }
        }

        try:
            dq_data = await self._graphql_mutation(dq_mutation, dq_variables)
            dq_errors = dq_data.get("errors", [])
            if dq_errors:
                logger.error(
                    "Zeenea updateDataQualityStatementV2 errors for '%s': %s",
                    item_key, dq_errors,
                )
            else:
                logger.info(
                    "Zeenea DQ statement updated for '%s' (score=%.1f → %.4f)",
                    item_key, score, score / 100.0,
                )
                success = True
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Zeenea updateDataQualityStatementV2 HTTP error for '%s': %s",
                item_key, exc,
            )

        return success

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
