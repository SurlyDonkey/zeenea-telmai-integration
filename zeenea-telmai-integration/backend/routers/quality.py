from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from clients import ZeneaClient, TelmaiClient
from store import mappings_store, get_zeenea_client, get_telmai_client

router = APIRouter(prefix="/api/quality", tags=["quality"])


@router.get("")
async def get_quality_overview() -> List[Dict[str, Any]]:
    zeenea: ZeneaClient = get_zeenea_client()
    telmai: TelmaiClient = get_telmai_client()

    zeenea_datasets = await zeenea.get_datasets()
    telmai_datasets = await telmai.get_datasets()
    telmai_by_id = {ds.id: ds for ds in telmai_datasets}

    result = []
    for zds in zeenea_datasets:
        mapping = mappings_store.get(zds.id)
        if not mapping:
            continue
        telmai_id = mapping["telmai_id"]
        tds = telmai_by_id.get(telmai_id)
        if not tds:
            continue
        result.append(
            {
                "zeenea_id": zds.id,
                "zeenea_name": zds.name,
                "telmai_id": telmai_id,
                "quality_score": tds.quality_score,
                "alert_count": tds.alert_count,
                "last_synced": mapping.get("last_synced"),
            }
        )

    return result


@router.get("/{zeenea_id}")
async def get_quality_detail(zeenea_id: str) -> Dict[str, Any]:
    mapping = mappings_store.get(zeenea_id)
    if not mapping:
        raise HTTPException(
            status_code=404,
            detail=f"No mapping found for Zeenea dataset '{zeenea_id}'. Link it to a Telmai dataset first.",
        )

    zeenea: ZeneaClient = get_zeenea_client()
    telmai: TelmaiClient = get_telmai_client()

    telmai_id = mapping["telmai_id"]
    zeenea_datasets = await zeenea.get_datasets()
    zds = next((ds for ds in zeenea_datasets if ds.id == zeenea_id), None)

    alerts = await telmai.get_alerts(dataset_id=telmai_id)
    metrics = await telmai.get_metrics(dataset_id=telmai_id)

    telmai_datasets = await telmai.get_datasets()
    tds = next((ds for ds in telmai_datasets if ds.id == telmai_id), None)

    return {
        "zeenea_id": zeenea_id,
        "zeenea_name": zds.name if zds else zeenea_id,
        "zeenea_description": zds.description if zds else None,
        "telmai_id": telmai_id,
        "telmai_name": tds.display_name if tds else mapping.get("telmai_name"),
        "quality_score": tds.quality_score if tds else None,
        "alert_count": tds.alert_count if tds else 0,
        "alerts": alerts,
        "metrics": metrics,
        "last_synced": mapping.get("last_synced"),
    }
