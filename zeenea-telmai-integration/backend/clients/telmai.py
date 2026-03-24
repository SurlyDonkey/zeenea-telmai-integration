import httpx
from typing import List, Optional, Dict, Any
from models import TelmaiDataset

MOCK_DATASETS = [
    TelmaiDataset(
        id="tel-001",
        name="customer_orders",
        display_name="Customer Orders",
        external_id="zee-001",
        quality_score=92.4,
        alert_count=1,
    ),
    TelmaiDataset(
        id="tel-002",
        name="product_catalog",
        display_name="Product Catalog",
        external_id="zee-002",
        quality_score=78.1,
        alert_count=3,
    ),
    TelmaiDataset(
        id="tel-003",
        name="user_events",
        display_name="User Events Stream",
        external_id="zee-003",
        quality_score=55.6,
        alert_count=8,
    ),
    TelmaiDataset(
        id="tel-004",
        name="inventory_levels",
        display_name="Inventory Levels",
        external_id="zee-004",
        quality_score=88.9,
        alert_count=2,
    ),
    TelmaiDataset(
        id="tel-005",
        name="revenue_metrics",
        display_name="Revenue Metrics",
        external_id="zee-005",
        quality_score=96.2,
        alert_count=0,
    ),
]

MOCK_ALERTS = {
    "tel-001": [
        {"id": "a1", "dataset_id": "tel-001", "rule": "null_check", "column": "customer_id", "severity": "warning", "message": "1.2% null values detected in customer_id"},
    ],
    "tel-002": [
        {"id": "a2", "dataset_id": "tel-002", "rule": "range_check", "column": "price", "severity": "error", "message": "Price values outside expected range [0, 10000]"},
        {"id": "a3", "dataset_id": "tel-002", "rule": "freshness", "column": None, "severity": "warning", "message": "Dataset not updated in 36 hours"},
        {"id": "a4", "dataset_id": "tel-002", "rule": "uniqueness", "column": "sku", "severity": "warning", "message": "0.3% duplicate SKU values found"},
    ],
    "tel-003": [
        {"id": "a5", "dataset_id": "tel-003", "rule": "volume_anomaly", "column": None, "severity": "critical", "message": "Row count dropped 42% compared to 7-day average"},
        {"id": "a6", "dataset_id": "tel-003", "rule": "null_check", "column": "session_id", "severity": "error", "message": "8.7% null values in session_id"},
        {"id": "a7", "dataset_id": "tel-003", "rule": "schema_drift", "column": "device_type", "severity": "warning", "message": "New categorical value 'smart_tv' detected"},
        {"id": "a8", "dataset_id": "tel-003", "rule": "null_check", "column": "user_id", "severity": "warning", "message": "3.1% null values in user_id"},
        {"id": "a9", "dataset_id": "tel-003", "rule": "distribution", "column": "event_type", "severity": "warning", "message": "Distribution shift in event_type column"},
        {"id": "a10", "dataset_id": "tel-003", "rule": "latency", "column": None, "severity": "warning", "message": "Ingestion latency > 15 minutes for past 2 hours"},
        {"id": "a11", "dataset_id": "tel-003", "rule": "uniqueness", "column": "event_id", "severity": "error", "message": "Duplicate event_id records found"},
        {"id": "a12", "dataset_id": "tel-003", "rule": "format_check", "column": "timestamp", "severity": "warning", "message": "Inconsistent timestamp formats detected"},
    ],
    "tel-004": [
        {"id": "a13", "dataset_id": "tel-004", "rule": "range_check", "column": "quantity", "severity": "warning", "message": "Negative quantity values in 0.8% of rows"},
        {"id": "a14", "dataset_id": "tel-004", "rule": "freshness", "column": None, "severity": "warning", "message": "3 warehouse locations not updated in 12 hours"},
    ],
    "tel-005": [],
}

MOCK_METRICS = {
    "tel-001": {"completeness": 98.8, "uniqueness": 99.1, "validity": 95.4, "freshness": 100.0, "consistency": 88.3},
    "tel-002": {"completeness": 89.2, "uniqueness": 97.0, "validity": 71.4, "freshness": 62.1, "consistency": 90.8},
    "tel-003": {"completeness": 72.1, "uniqueness": 61.3, "validity": 58.9, "freshness": 44.2, "consistency": 55.0},
    "tel-004": {"completeness": 93.4, "uniqueness": 98.7, "validity": 84.6, "freshness": 78.9, "consistency": 90.1},
    "tel-005": {"completeness": 99.2, "uniqueness": 99.8, "validity": 97.1, "freshness": 96.4, "consistency": 94.5},
}


class TelmaiClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._is_mock = not base_url or not token or token == "your_telmai_token"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def get_datasets(self) -> List[TelmaiDataset]:
        if self._is_mock:
            return MOCK_DATASETS

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/datasets",
                headers=self._headers(),
            )
            response.raise_for_status()
            items = response.json()
            return [
                TelmaiDataset(
                    id=item["id"],
                    name=item.get("name", item["id"]),
                    display_name=item.get("displayName", item.get("name", item["id"])),
                    external_id=item.get("externalId"),
                    quality_score=item.get("qualityScore"),
                    alert_count=item.get("alertCount", 0),
                )
                for item in (items if isinstance(items, list) else items.get("data", []))
            ]

    async def get_alerts(self, dataset_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if self._is_mock:
            if dataset_id:
                return MOCK_ALERTS.get(dataset_id, [])
            all_alerts = []
            for alerts in MOCK_ALERTS.values():
                all_alerts.extend(alerts)
            return all_alerts

        url = f"{self.base_url}/alerts"
        params = {}
        if dataset_id:
            params["datasetId"] = dataset_id

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers(), params=params)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else data.get("data", [])

    async def get_metrics(self, dataset_id: str) -> Dict[str, float]:
        if self._is_mock:
            return MOCK_METRICS.get(dataset_id, {})

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/metrics/{dataset_id}",
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def register_dataset(
        self,
        name: str,
        display_name: str,
        external_id: str,
    ) -> Dict[str, Any]:
        if self._is_mock:
            return {
                "id": f"tel-mock-{external_id}",
                "name": name,
                "display_name": display_name,
                "external_id": external_id,
            }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/datasets",
                headers=self._headers(),
                json={
                    "name": name,
                    "displayName": display_name,
                    "externalId": external_id,
                },
            )
            response.raise_for_status()
            return response.json()

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
