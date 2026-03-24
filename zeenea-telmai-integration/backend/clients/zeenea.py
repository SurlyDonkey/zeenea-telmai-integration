import httpx
import logging
from typing import List, Optional
from models import ZeneaDataset

logger = logging.getLogger(__name__)

MOCK_DATASETS = [
    ZeneaDataset(
        id="zee-001",
        name="customer_orders",
        technical_name="raw.customer_orders",
        description="All customer orders including historical and current data",
    ),
    ZeneaDataset(
        id="zee-002",
        name="product_catalog",
        technical_name="core.product_catalog",
        description="Master product catalog with pricing and attributes",
    ),
    ZeneaDataset(
        id="zee-003",
        name="user_events",
        technical_name="analytics.user_events",
        description="Clickstream and behavioral event data from all channels",
    ),
    ZeneaDataset(
        id="zee-004",
        name="inventory_levels",
        technical_name="ops.inventory_levels",
        description="Real-time inventory levels across all warehouse locations",
    ),
    ZeneaDataset(
        id="zee-005",
        name="revenue_metrics",
        technical_name="finance.revenue_metrics",
        description="Aggregated revenue metrics by product, region, and period",
    ),
    ZeneaDataset(
        id="zee-006",
        name="supplier_contracts",
        technical_name="procurement.supplier_contracts",
        description="Active and historical supplier contract terms and SLAs",
    ),
]


def _compute_properties(score: float, alert_count: int) -> List[dict]:
    """Map Telmai quality metrics to the real Zeenea property schema."""

    # DTC – Data Trust Classification
    if score >= 85:
        dtc = "✭✭✭"
    elif score >= 65:
        dtc = "✭✭"
    else:
        dtc = "✭"

    # Certification
    if score >= 85 and alert_count == 0:
        certification = "⭐️ Certified"
    else:
        certification = "❌ Not certified"

    # Asset Status
    if score >= 85:
        asset_status = "🏆 Gold Standard"
    elif score >= 60:
        asset_status = "🟠 To be improved"
    else:
        asset_status = "❌ To be decomissioned"

    # Tags
    score_int = int(round(score))
    tags = ["telmai-monitored", f"dq-score-{score_int}"]

    return [
        {"code": "DTC", "value": dtc},
        {"code": "certification", "value": certification},
        {"code": "assetStatus", "value": asset_status},
        {"code": "dataProfilingAvailable", "value": "✅ Yes"},
        {"code": "$z_tags", "value": tags},
    ]


class ZeneaClient:
    def __init__(self, url: str, api_key: str):
        self.url = url
        self.api_key = api_key
        self._is_mock = not url or not api_key or api_key == "your_zeenea_api_key"

    async def get_datasets(self) -> List[ZeneaDataset]:
        if self._is_mock:
            return MOCK_DATASETS

        query = """
        query GetDatasets {
          datasets {
            items {
              id
              name
              technicalName
              description
            }
          }
        }
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.url,
                json={"query": query},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
            items = data.get("data", {}).get("datasets", {}).get("items", [])
            return [
                ZeneaDataset(
                    id=item["id"],
                    name=item["name"],
                    technical_name=item.get("technicalName", item["name"]),
                    description=item.get("description"),
                )
                for item in items
            ]

    async def update_quality_properties(
        self,
        item_id: str,
        score: float,
        alert_count: int,
        last_checked: str,
    ) -> bool:
        """
        Write Telmai quality metrics back to Zeenea using the real property schema.

        Maps score / alert_count to DTC, certification, assetStatus,
        dataProfilingAvailable, and $z_tags via _compute_properties().
        """
        properties = _compute_properties(score, alert_count)

        if self._is_mock:
            logger.info(
                "Mock mode — would update Zeenea item '%s' with properties: %s",
                item_id,
                properties,
            )
            return True

        mutation = """
        mutation UpdateItemProperties($itemKey: ItemKeyInput!, $properties: [PropertyValueInput!]!) {
          updateItemProperties(itemKey: $itemKey, properties: $properties) {
            key
            name
          }
        }
        """
        variables = {
            "itemKey": {"id": item_id},
            "properties": properties,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.url,
                json={"query": mutation, "variables": variables},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
            return "errors" not in data

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
