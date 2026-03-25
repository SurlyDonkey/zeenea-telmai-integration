from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Dict, Any

from auth import verify_api_key
from database import AssetMapping, get_session
from clients import ZeneaClient, TelmaiClient
from store import get_zeenea_client, get_telmai_client

router = APIRouter(
    prefix="/api/quality",
    tags=["quality"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("")
async def get_quality_overview(
    session: Session = Depends(get_session),
) -> List[Dict[str, Any]]:
    zeenea: ZeneaClient = get_zeenea_client()
    telmai: TelmaiClient = get_telmai_client()

    zeenea_datasets = await zeenea.get_datasets()
    telmai_datasets = await telmai.get_datasets()
    telmai_by_id = {ds.id: ds for ds in telmai_datasets}

    mappings = {
        m.zeenea_id: m
        for m in session.exec(select(AssetMapping)).all()
    }

    result = []
    for zds in zeenea_datasets:
        mapping = mappings.get(zds.id)
        if not mapping:
            continue
        tds = telmai_by_id.get(mapping.telmai_id)
        if not tds:
            continue
        result.append(
            {
                "zeenea_id": zds.id,
                "zeenea_name": zds.name,
                "telmai_id": mapping.telmai_id,
                "quality_score": tds.quality_score,
                "alert_count": tds.alert_count,
                "last_synced": mapping.last_synced,
            }
        )

    return result


@router.get("/{zeenea_id}")
async def get_quality_detail(
    zeenea_id: str,
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    mapping = session.exec(
        select(AssetMapping).where(AssetMapping.zeenea_id == zeenea_id)
    ).first()
    if not mapping:
        raise HTTPException(
            status_code=404,
            detail=f"No mapping found for Zeenea dataset '{zeenea_id}'. Link it to a Telmai dataset first.",
        )

    zeenea: ZeneaClient = get_zeenea_client()
    telmai: TelmaiClient = get_telmai_client()

    zeenea_datasets = await zeenea.get_datasets()
    zds = next((ds for ds in zeenea_datasets if ds.id == zeenea_id), None)

    alerts = await telmai.get_incidents(asset_id=mapping.telmai_id)
    metrics = await telmai.get_dq_score(asset_id=mapping.telmai_id)

    telmai_datasets = await telmai.get_datasets()
    tds = next((ds for ds in telmai_datasets if ds.id == mapping.telmai_id), None)

    return {
        "zeenea_id": zeenea_id,
        "zeenea_name": zds.name if zds else zeenea_id,
        "zeenea_description": zds.description if zds else None,
        "telmai_id": mapping.telmai_id,
        "telmai_name": tds.display_name if tds else mapping.telmai_name,
        "quality_score": tds.quality_score if tds else None,
        "alert_count": tds.alert_count if tds else 0,
        "alerts": alerts,
        "metrics": metrics,
        "last_synced": mapping.last_synced,
    }
