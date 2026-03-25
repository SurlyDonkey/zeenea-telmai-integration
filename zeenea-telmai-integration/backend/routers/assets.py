from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from datetime import datetime, timezone

from auth import verify_api_key
from database import AssetMapping, get_session
from models import MappedAsset, LinkRequest
from clients import ZeneaClient, TelmaiClient
from store import get_zeenea_client, get_telmai_client

router = APIRouter(
    prefix="/api/assets",
    tags=["assets"],
    dependencies=[Depends(verify_api_key)],
)

# Demo seed data — applied once when the mappings table is empty
_DEMO_MAPPINGS = [
    ("zee-001", "tel-001", "Customer Orders"),
    ("zee-002", "tel-002", "Product Catalog"),
    ("zee-003", "tel-003", "User Events Stream"),
    ("zee-004", "tel-004", "Inventory Levels"),
    ("zee-005", "tel-005", "Revenue Metrics"),
]


def _seed_demo_if_empty(session: Session) -> None:
    existing = session.exec(select(AssetMapping)).first()
    if existing:
        return
    now = datetime.now(timezone.utc)
    for zeenea_id, telmai_id, telmai_name in _DEMO_MAPPINGS:
        session.add(
            AssetMapping(
                zeenea_id=zeenea_id,
                telmai_id=telmai_id,
                telmai_name=telmai_name,
                last_synced=now,
            )
        )
    session.commit()


@router.get("", response_model=List[MappedAsset])
async def get_assets(session: Session = Depends(get_session)):
    _seed_demo_if_empty(session)

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
        if mapping:
            tds = telmai_by_id.get(mapping.telmai_id)
            result.append(
                MappedAsset(
                    zeenea_id=zds.id,
                    zeenea_name=zds.name,
                    telmai_id=mapping.telmai_id,
                    telmai_name=tds.display_name if tds else mapping.telmai_name,
                    quality_score=tds.quality_score if tds else None,
                    alert_count=tds.alert_count if tds else 0,
                    last_synced=mapping.last_synced,
                    status="linked",
                )
            )
        else:
            result.append(
                MappedAsset(
                    zeenea_id=zds.id,
                    zeenea_name=zds.name,
                    telmai_id=None,
                    telmai_name=None,
                    quality_score=None,
                    alert_count=0,
                    last_synced=None,
                    status="unlinked",
                )
            )

    return result


@router.post("/{zeenea_id}/link", response_model=MappedAsset)
async def link_asset(
    zeenea_id: str,
    body: LinkRequest,
    session: Session = Depends(get_session),
):
    zeenea: ZeneaClient = get_zeenea_client()
    telmai: TelmaiClient = get_telmai_client()

    zeenea_datasets = await zeenea.get_datasets()
    zeenea_dataset = next((ds for ds in zeenea_datasets if ds.id == zeenea_id), None)
    if not zeenea_dataset:
        raise HTTPException(status_code=404, detail=f"Zeenea dataset '{zeenea_id}' not found")

    telmai_datasets = await telmai.get_datasets()
    telmai_dataset = next((ds for ds in telmai_datasets if ds.id == body.telmai_id), None)
    if not telmai_dataset:
        raise HTTPException(status_code=404, detail=f"Telmai dataset '{body.telmai_id}' not found")

    # Upsert
    existing = session.exec(
        select(AssetMapping).where(AssetMapping.zeenea_id == zeenea_id)
    ).first()
    now = datetime.now(timezone.utc)
    if existing:
        existing.telmai_id = body.telmai_id
        existing.telmai_name = telmai_dataset.display_name
        existing.last_synced = now
        session.add(existing)
    else:
        session.add(
            AssetMapping(
                zeenea_id=zeenea_id,
                telmai_id=body.telmai_id,
                telmai_name=telmai_dataset.display_name,
                last_synced=now,
            )
        )
    session.commit()

    return MappedAsset(
        zeenea_id=zeenea_id,
        zeenea_name=zeenea_dataset.name,
        telmai_id=body.telmai_id,
        telmai_name=telmai_dataset.display_name,
        quality_score=telmai_dataset.quality_score,
        alert_count=telmai_dataset.alert_count,
        last_synced=now,
        status="linked",
    )


@router.delete("/{zeenea_id}/link")
async def unlink_asset(zeenea_id: str, session: Session = Depends(get_session)):
    mapping = session.exec(
        select(AssetMapping).where(AssetMapping.zeenea_id == zeenea_id)
    ).first()
    if not mapping:
        raise HTTPException(
            status_code=404,
            detail=f"No mapping found for Zeenea dataset '{zeenea_id}'",
        )
    session.delete(mapping)
    session.commit()
    return {"detail": f"Mapping for '{zeenea_id}' removed successfully"}
