from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError, not_found
from app.core.security import rate_limit
from app.modules.audit import service as audit
from app.modules.content.models import Destination
from app.modules.identity.deps import optional_principal, require, verified_principal
from app.modules.identity.service import Principal
from app.modules.media import service as svc
from app.modules.media.models import DestinationMedia, MediaAsset
from app.modules.platform.service import require_flag

router = APIRouter(prefix="/api", tags=["media"])


def asset_staff(a: MediaAsset) -> dict:
    return {**svc.asset_public(a), "status": a.status, "scan_status": a.scan_status, "purpose": a.purpose,
            "had_gps_metadata": a.had_gps_metadata, "exif_stripped": a.exif_stripped, "phash": a.phash,
            "rights_confirmed_by_uploader": a.rights_confirmed_by_uploader,
            "custodial_approval_ref": a.custodial_approval_ref, "owner_id": str(a.owner_id) if a.owner_id else None,
            "signed_preview": svc.sign(str(a.id), "md")}


@router.post("/media", status_code=201, dependencies=[Depends(rate_limit("write"))])
async def upload(request: Request, file: UploadFile = File(...),
                 purpose: Literal["community", "destination", "competition"] = Form("community"),
                 rights_confirmed: bool = Form(False), p: Principal = Depends(verified_principal),
                 db: Session = Depends(get_db)):
    if purpose == "destination" and not p.has("media.manage"):
        raise AppError(403, "forbidden", "Only media staff can upload destination imagery.")
    if purpose in ("community", "competition"):
        require_flag(db, "community_uploads")
        if not rights_confirmed:
            raise AppError(422, "rights_required", "Confirm that you created this image and may share it.")
    data = await file.read(get_max() + 1)
    asset = svc.ingest_image(db, data, owner_id=p.id, purpose=purpose, filename=file.filename,
                             rights_confirmed=rights_confirmed)
    audit.record(db, action="media.upload", resource_type="media", resource_id=asset.id, actor=p, request=request,
                 changes={"purpose": purpose, "scan": asset.scan_status, "gps_stripped": asset.had_gps_metadata})
    db.commit()
    return {**asset_staff(asset), "duplicates": svc.similar_assets(db, asset)}


def get_max() -> int:
    from app.core.config import get_settings
    return get_settings().media_max_bytes


@router.get("/media/{media_id}/{variant}")
def serve(media_id: uuid.UUID, variant: Literal["sm", "md", "lg"], exp: int | None = None, sig: str | None = None,
          p: Principal | None = Depends(optional_principal), db: Session = Depends(get_db)):
    a = db.get(MediaAsset, media_id)
    if a is None or variant not in a.variants or a.status in ("rejected", "infected"):
        raise not_found("Media")
    public = a.status == "approved"
    allowed = public or (exp is not None and sig is not None and svc.verify_signature(str(media_id), variant, exp, sig))
    if not allowed and p is not None:
        allowed = p.id == a.owner_id or p.has("media.manage") or p.has("community.moderate")
    if not allowed:
        raise not_found("Media")  # do not reveal existence of unpublished media
    data = svc.storage().get(a.variants[variant]["key"])
    cache = "public, max-age=86400, immutable" if public else "private, no-store"
    return Response(data, media_type="image/webp", headers={"Cache-Control": cache,
                                                             "Content-Disposition": "inline",
                                                             "Cross-Origin-Resource-Policy": "cross-origin"})


class RightsIn(BaseModel):
    license: str = Field(min_length=2, max_length=120)
    credit: str = Field(min_length=2, max_length=200)
    attribution_url: HttpUrl | None = None
    is_illustrative: bool = False
    is_reconstruction: bool = False
    is_ai_generated: bool = False
    custodial_approval_ref: str | None = Field(default=None, max_length=200)
    alt_text_i18n: dict[Literal["en", "ti", "am"], str] = Field(default_factory=dict)
    caption_i18n: dict[Literal["en", "ti", "am"], str] = Field(default_factory=dict)


@router.get("/bureau/media")
def list_media(status: str | None = None, _=Depends(require("media.manage")), db: Session = Depends(get_db)):
    stmt = select(MediaAsset).order_by(MediaAsset.created_at.desc()).limit(200)
    if status:
        stmt = stmt.where(MediaAsset.status == status)
    return [asset_staff(a) for a in db.execute(stmt).scalars()]


@router.put("/bureau/media/{media_id}/rights")
def set_rights(media_id: uuid.UUID, body: RightsIn, request: Request, p: Principal = Depends(require("media.manage")),
               db: Session = Depends(get_db)):
    a = db.get(MediaAsset, media_id)
    if a is None:
        raise not_found("Media")
    for k, v in body.model_dump(mode="json").items():
        setattr(a, k, v)
    audit.record(db, action="media.rights", resource_type="media", resource_id=a.id, actor=p, request=request,
                 changes={"license": body.license, "credit": body.credit})
    db.commit()
    return asset_staff(a)


@router.post("/bureau/media/{media_id}/{decision}")
def review(media_id: uuid.UUID, decision: Literal["approve", "reject"], request: Request,
           p: Principal = Depends(require("media.manage")), db: Session = Depends(get_db)):
    a = db.get(MediaAsset, media_id)
    if a is None:
        raise not_found("Media")
    if decision == "approve":
        if a.status != "clean":
            raise AppError(409, "not_scanned", "Media must pass malware scanning before approval.")
        if not a.license or not a.credit or not a.alt_text_i18n.get("en"):
            raise AppError(422, "rights_incomplete", "Licence, credit and English alt text are required before publication.")
        a.status = "approved"
    else:
        a.status = "rejected"
    a.reviewed_by = p.id
    audit.record(db, action=f"media.{decision}", resource_type="media", resource_id=a.id, actor=p, request=request)
    db.commit()
    return asset_staff(a)


class LinkIn(BaseModel):
    media_id: uuid.UUID
    is_hero: bool = False
    sort_order: int = 100


@router.post("/bureau/destinations/{dest_id}/media", status_code=201)
def link_media(dest_id: uuid.UUID, body: LinkIn, request: Request, p: Principal = Depends(require("media.manage")),
               db: Session = Depends(get_db)):
    d = db.get(Destination, dest_id)
    a = db.get(MediaAsset, body.media_id)
    if d is None or a is None:
        raise not_found("Destination or media")
    if a.status != "approved":
        raise AppError(409, "media_not_approved", "Approve the media (rights + scan) before attaching it.")
    if body.is_hero:
        for link in db.execute(select(DestinationMedia).where(DestinationMedia.destination_id == d.id)).scalars():
            link.is_hero = False
    db.add(DestinationMedia(destination_id=d.id, media_id=a.id, is_hero=body.is_hero, sort_order=body.sort_order))
    if d.status == "published":
        d.status = "draft"
    audit.record(db, action="destination.media_link", resource_type="destination", resource_id=d.id, actor=p,
                 request=request, changes={"media_id": str(a.id)})
    db.commit()
    return {"status": "linked"}
