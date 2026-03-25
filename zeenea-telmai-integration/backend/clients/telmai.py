"""
Telmai REST API client.

Confirmed API structure (live-tested against data-observability.actian.com):

  Auth — two supported modes:
    A) Static API token (Okta / SSO deployments like Actian):
         Set api_token directly. Used as-is as a Bearer token.
         Obtain from the Telmai UI → Profile → API Token (or from browser session).
    B) OAuth2 password grant (standard Telmai deployments):
         POST {auth_endpoint}/api/auth/token?grantType=password&username=...&password=...&clientId=...&tenant=...
         Note: params go as QUERY PARAMS (not form body), field is grantType (not grant_type).

  Base URL:  {endpoint}/api/backend/{tenant}/
  Assets:    GET  .../configuration/assets          → list[{id, name, dq_score, ...}]
  Incidents: GET  .../incidents                     → list[{id, severity, asset_id, status, ...}]
  DQ Config: GET  .../configuration/assets/{id}/dq_score → {weights: {...}, max_incidents, ...}
             NOTE: returns weight config, not score. Actual score is on the asset object (dq_score 0-100).
  Alerts:    POST .../configuration/sources/{sourceId}/alerts?job_id={jobId}
"""

import httpx
import time
import logging
from typing import List, Optional, Dict, Any
from models import TelmaiDataset

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock data (used when credentials are not configured)
# ---------------------------------------------------------------------------

MOCK_DATASETS = [
    TelmaiDataset(id="tel-001", name="customer_orders",    display_name="Customer Orders",     external_id="zee-001", quality_score=92.4, alert_count=1),
    TelmaiDataset(id="tel-002", name="product_catalog",    display_name="Product Catalog",      external_id="zee-002", quality_score=78.1, alert_count=3),
    TelmaiDataset(id="tel-003", name="user_events",        display_name="User Events Stream",   external_id="zee-003", quality_score=55.6, alert_count=8),
    TelmaiDataset(id="tel-004", name="inventory_levels",   display_name="Inventory Levels",     external_id="zee-004", quality_score=88.9, alert_count=2),
    TelmaiDataset(id="tel-005", name="revenue_metrics",    display_name="Revenue Metrics",      external_id="zee-005", quality_score=96.2, alert_count=0),
]

MOCK_INCIDENTS = {
    "tel-001": [
        {"id": "a1", "asset_id": "tel-001", "severity": "WARNING", "impact": "LOW",
         "description": "1.2% null values detected in customer_id", "status": "open",
         "tags": ["null_check"], "attribute": "customer_id"},
    ],
    "tel-002": [
        {"id": "a2", "asset_id": "tel-002", "severity": "HIGH",    "impact": "MEDIUM",
         "description": "Price values outside expected range [0, 10000]", "status": "open",
         "tags": ["range_check"], "attribute": "price"},
        {"id": "a3", "asset_id": "tel-002", "severity": "WARNING", "impact": "LOW",
         "description": "Dataset not updated in 36 hours", "status": "open",
         "tags": ["freshness"], "attribute": None},
        {"id": "a4", "asset_id": "tel-002", "severity": "WARNING", "impact": "LOW",
         "description": "0.3% duplicate SKU values found", "status": "open",
         "tags": ["uniqueness"], "attribute": "sku"},
    ],
    "tel-003": [
        {"id": "a5",  "asset_id": "tel-003", "severity": "CRITICAL", "impact": "HIGH",
         "description": "Row count dropped 42% vs 7-day average", "status": "open",
         "tags": ["volume_anomaly"], "attribute": None},
        {"id": "a6",  "asset_id": "tel-003", "severity": "HIGH",    "impact": "HIGH",
         "description": "8.7% null values in session_id", "status": "open",
         "tags": ["null_check"], "attribute": "session_id"},
        {"id": "a7",  "asset_id": "tel-003", "severity": "WARNING", "impact": "LOW",
         "description": "New categorical value 'smart_tv' detected in device_type", "status": "open",
         "tags": ["schema_drift"], "attribute": "device_type"},
        {"id": "a8",  "asset_id": "tel-003", "severity": "WARNING", "impact": "LOW",
         "description": "3.1% null values in user_id", "status": "open",
         "tags": ["null_check"], "attribute": "user_id"},
        {"id": "a9",  "asset_id": "tel-003", "severity": "WARNING", "impact": "MEDIUM",
         "description": "Distribution shift in event_type column", "status": "open",
         "tags": ["distribution"], "attribute": "event_type"},
        {"id": "a10", "asset_id": "tel-003", "severity": "WARNING", "impact": "LOW",
         "description": "Ingestion latency > 15 min for past 2 hours", "status": "open",
         "tags": ["latency"], "attribute": None},
        {"id": "a11", "asset_id": "tel-003", "severity": "HIGH",    "impact": "HIGH",
         "description": "Duplicate event_id records found", "status": "open",
         "tags": ["uniqueness"], "attribute": "event_id"},
        {"id": "a12", "asset_id": "tel-003", "severity": "WARNING", "impact": "LOW",
         "description": "Inconsistent timestamp formats detected", "status": "open",
         "tags": ["format_check"], "attribute": "timestamp"},
    ],
    "tel-004": [
        {"id": "a13", "asset_id": "tel-004", "severity": "WARNING", "impact": "LOW",
         "description": "Negative quantity values in 0.8% of rows", "status": "open",
         "tags": ["range_check"], "attribute": "quantity"},
        {"id": "a14", "asset_id": "tel-004", "severity": "WARNING", "impact": "LOW",
         "description": "3 warehouse locations not updated in 12 hours", "status": "open",
         "tags": ["freshness"], "attribute": None},
    ],
    "tel-005": [],
}

MOCK_DQ_SCORES = {
    "tel-001": {"completeness": 98.8, "accuracy": 95.4, "consistency": 88.3, "timeliness": 100.0},
    "tel-002": {"completeness": 89.2, "accuracy": 71.4, "consistency": 90.8, "timeliness": 62.1},
    "tel-003": {"completeness": 72.1, "accuracy": 58.9, "consistency": 55.0, "timeliness": 44.2},
    "tel-004": {"completeness": 93.4, "accuracy": 84.6, "consistency": 90.1, "timeliness": 78.9},
    "tel-005": {"completeness": 99.2, "accuracy": 97.1, "consistency": 94.5, "timeliness": 96.4},
}


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class TelmaiClient:
    """
    Client for the Telmai Data Observability API.

    Config params:
      endpoint     - base URL, e.g. https://app.telm.ai
      tenant       - your Telmai tenant name
      api_token    - static Bearer token (Okta/SSO deployments — skips OAuth2 flow)
      username     - Telmai login (OAuth2 password grant only)
      password     - Telmai login (OAuth2 password grant only)
      client_id    - OAuth2 client ID, default "telmai"
      auth_endpoint - auth server URL (defaults to endpoint)

    If api_token is set it takes precedence over username/password.
    """

    def __init__(
        self,
        endpoint: str,
        tenant: str,
        api_token: str = "",
        username: str = "",
        password: str = "",
        client_id: str = "telmai",
        auth_endpoint: Optional[str] = None,
    ):
        self.endpoint = endpoint.rstrip("/") if endpoint else ""
        self.tenant = tenant or ""
        self.api_token = api_token or ""
        self.username = username or ""
        self.password = password or ""
        self.client_id = client_id or "telmai"
        self.auth_endpoint = (auth_endpoint or endpoint or "").rstrip("/")

        # Mock mode if neither token nor username/password are provided
        self._is_mock = not endpoint or not tenant or (not api_token and not (username and password))

        # OAuth2 token cache (unused in static token mode)
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _backend_url(self, path: str) -> str:
        """Build a full backend API URL."""
        return f"{self.endpoint}/api/backend/{self.tenant}/{path.lstrip('/')}"

    def _config_url(self, path: str) -> str:
        """Build a full configuration API URL (same host in most deployments)."""
        return f"{self.endpoint}/api/backend/{self.tenant}/{path.lstrip('/')}"

    async def _get_token(self) -> str:
        """
        Return a valid Bearer token.

        Static token mode: returns api_token directly (no OAuth2 call).
        OAuth2 mode: POST to {auth_endpoint}/api/auth/token with query params
                     (Telmai uses ?grantType=password&username=... not a form body).
        """
        # Static token — used as-is (Okta / SSO deployments)
        if self.api_token:
            return self.api_token

        # OAuth2 password grant — use cached token if still valid
        if self._access_token and time.time() < self._token_expires_at - 30:
            return self._access_token

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.auth_endpoint}/api/auth/token",
                params={                          # ← query params, NOT form body
                    "grantType": "password",      # ← grantType, NOT grant_type
                    "username":  self.username,
                    "password":  self.password,
                    "clientId":  self.client_id,
                    "tenant":    self.tenant,
                },
                headers={"accept": "*/*"},
                content=b"",
            )
            response.raise_for_status()
            data = response.json()

        self._access_token = data["access_token"]
        expires_in = data.get("expires", 3600)
        self._token_expires_at = time.time() + expires_in
        logger.debug("Telmai token refreshed, expires in %s s", expires_in)
        return self._access_token

    async def _headers(self) -> Dict[str, str]:
        token = await self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def get_datasets(self) -> List[TelmaiDataset]:
        """
        Return all assets/datasets registered in Telmai.
        Each asset includes its latest DQ score and open incident count.
        """
        if self._is_mock:
            return MOCK_DATASETS

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                self._config_url("configuration/assets"),
                headers=await self._headers(),
            )
            response.raise_for_status()
            items = response.json()
            items = items if isinstance(items, list) else items.get("data", items.get("items", []))

            results = []
            for item in items:
                asset_id = item.get("id") or item.get("assetId", "")
                # dq_score is on the asset object directly (0-100 scale)
                score = item.get("dq_score") or item.get("qualityScore")
                if score is not None:
                    score = float(score)

                results.append(TelmaiDataset(
                    id=asset_id,
                    name=item.get("name", asset_id),
                    display_name=item.get("displayName") or item.get("name", asset_id),
                    external_id=item.get("externalId") or item.get("canonical_id"),
                    quality_score=score,
                    alert_count=item.get("openIncidents") or item.get("open_incidents") or 0,
                ))
            return results

    async def get_incidents(self, asset_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Return open incidents from Telmai.
        Optionally filter by asset_id.
        Maps to GET /api/backend/{tenant}/incidents
        """
        if self._is_mock:
            if asset_id:
                return MOCK_INCIDENTS.get(asset_id, [])
            return [inc for incs in MOCK_INCIDENTS.values() for inc in incs]

        params: Dict[str, Any] = {}
        if asset_id:
            params["asset_ids"] = asset_id

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                self._backend_url("incidents"),
                headers=await self._headers(),
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else data.get("data", [])

    async def get_dq_score(self, asset_id: str) -> Dict[str, float]:
        """
        Return the DQ score breakdown for an asset.
        Maps to GET /api/backend/{tenant}/configuration/assets/{assetId}/dq_score
        Returns dict with keys: completeness, accuracy, consistency, timeliness
        """
        if self._is_mock:
            return MOCK_DQ_SCORES.get(asset_id, {})

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                self._config_url(f"configuration/assets/{asset_id}/dq_score"),
                headers=await self._headers(),
            )
            if response.status_code == 404:
                return {}
            response.raise_for_status()
            data = response.json()
            # Response shape: { enabled, weights: { completeness, accuracy, consistency, timeliness }, thresholds }
            weights = data.get("weights", data)
            return {
                "completeness": weights.get("completeness", 0),
                "accuracy":     weights.get("accuracy", 0),
                "consistency":  weights.get("consistency", 0),
                "timeliness":   weights.get("timeliness", 0),
            }

    async def get_monitors(self, asset_id: str) -> List[Dict[str, Any]]:
        """
        Return all monitors configured for an asset.
        Maps to GET /api/backend/{tenant}/configuration/assets/{assetId}/monitors
        """
        if self._is_mock:
            return []

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                self._config_url(f"configuration/assets/{asset_id}/monitors"),
                headers=await self._headers(),
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else data.get("data", [])

    async def check_for_alerts(
        self,
        source_id: str,
        job_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve alerts for a specific data upload job.
        Called immediately after Telmai completes a scan (webhook flow).

        Maps to:
          POST /api/backend/{tenant}/configuration/sources/{sourceID}/alerts?job_id={job_id}

        Returns list of alert objects:
          { type, source, description, job_id, create_time, save_time,
            metric_value, policy_name, priority, source_name, source_type }
        """
        if self._is_mock:
            # Return a small set of mock alerts for the requested source
            all_alerts = [a for alerts in MOCK_INCIDENTS.values() for a in alerts]
            return all_alerts[:3]

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._backend_url(f"configuration/sources/{source_id}/alerts"),
                params={"job_id": job_id},
                headers=await self._headers(),
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else data.get("data", [])

    async def register_dataset(
        self,
        name: str,
        display_name: str,
        external_id: str,
    ) -> Dict[str, Any]:
        """
        Register a new asset/dataset in Telmai.
        Stores the Zeenea item ID as externalId for reverse-sync.
        """
        if self._is_mock:
            return {"id": f"tel-mock-{external_id}", "name": name,
                    "displayName": display_name, "externalId": external_id}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._config_url("configuration/assets"),
                headers=await self._headers(),
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
            await self._get_token()
            datasets = await self.get_datasets()
            return True, "Connected successfully", len(datasets)
        except httpx.HTTPStatusError as e:
            return False, f"HTTP {e.response.status_code}: {e.response.text[:200]}", None
        except Exception as e:
            return False, str(e)[:200], None
