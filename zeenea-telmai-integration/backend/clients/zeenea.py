import httpx
from typing import List, Optional
from models import ZeneaDataset

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

    async def update_quality_property(
        self,
        item_id: str,
        score: float,
        alert_count: int,
        last_checked: str,
    ) -> bool:
        if self._is_mock:
            return True

        mutation = """
        mutation UpdateQualityProperties($id: ID!, $properties: [PropertyInput!]!) {
          updateDatasetProperties(id: $id, properties: $properties) {
            id
            name
          }
        }
        """
        variables = {
            "id": item_id,
            "properties": [
                {"key": "telmai_quality_score", "value": str(score)},
                {"key": "telmai_alert_count", "value": str(alert_count)},
                {"key": "telmai_last_checked", "value": last_checked},
            ],
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
