"""Media pipeline: validate -> decode -> strip metadata -> re-encode variants -> hash -> scan -> store."""
from __future__ import annotations

import hashlib
import hmac
import io
import socket
import struct
import time
import uuid
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.media.models import DestinationMedia, MediaAsset

Image.MAX_IMAGE_PIXELS = 60_000_000  # decompression-bomb guard (~60 MP)
ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF")
VARIANTS = {"sm": 480, "md": 1024, "lg": 1920}
GPS_TAG = 0x8825


# ---------------------------------------------------------------- storage

class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise AppError(400, "bad_key", "Invalid storage key")
        return p

    def put(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete_prefix(self, prefix: str) -> None:
        d = self._path(prefix)
        if d.exists():
            for f in sorted(d.rglob("*"), reverse=True):
                f.unlink() if f.is_file() else f.rmdir()
            d.rmdir()


def storage() -> LocalStorage:
    """S3/MinIO: set S3_ENDPOINT/S3_BUCKET and install boto3; see docs/DEPLOYMENT.md.

    The local backend is the tested default. An S3 backend implementing put/get/delete_prefix with
    server-side encryption is a documented extension point (unresolved: needs bucket credentials).
    """
    return LocalStorage(get_settings().media_root)


# ---------------------------------------------------------------- hashing

def dhash(img: Image.Image) -> str:
    """64-bit difference hash for near-duplicate detection (robust to re-encoding/resizing)."""
    g = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    px = list(g.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (1 if px[row * 9 + col] > px[row * 9 + col + 1] else 0)
    return f"{bits:016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


# ---------------------------------------------------------------- scanning

def scan_bytes(data: bytes) -> tuple[str, str | None]:
    """ClamAV clamd INSTREAM scan. Returns (clean|infected|unavailable, detail)."""
    s = get_settings()
    if not s.clamd_host:
        return "unavailable", "No malware scanner configured"
    try:  # pragma: no cover - requires clamd
        with socket.create_connection((s.clamd_host, s.clamd_port), timeout=20) as sock:
            sock.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), 8192):
                chunk = data[i:i + 8192]
                sock.sendall(struct.pack("!L", len(chunk)) + chunk)
            sock.sendall(struct.pack("!L", 0))
            reply = sock.recv(4096).decode(errors="replace").strip("\0\n ")
        return ("clean", None) if reply.endswith("OK") else ("infected", reply[:300])
    except OSError as exc:  # pragma: no cover
        return "unavailable", f"scanner error: {exc}"


# ---------------------------------------------------------------- ingest

def ingest_image(db: Session, data: bytes, *, owner_id, purpose: str, filename: str | None,
                 rights_confirmed: bool) -> MediaAsset:
    s = get_settings()
    if len(data) > s.media_max_bytes:
        raise AppError(413, "file_too_large", f"Images must be at most {s.media_max_bytes // (1024 * 1024)} MB.")
    if len(data) < 64 or not data.startswith(MAGIC):
        raise AppError(415, "unsupported_media", "Only JPEG, PNG or WebP images are accepted.")
    if data.startswith(b"RIFF") and data[8:12] != b"WEBP":
        raise AppError(415, "unsupported_media", "Only JPEG, PNG or WebP images are accepted.")
    try:
        probe = Image.open(io.BytesIO(data))
        fmt = probe.format
        probe.verify()  # structural check
        img: Image.Image = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise AppError(415, "invalid_image", "The file is not a valid image.") from exc
    if fmt not in ALLOWED_FORMATS:
        raise AppError(415, "unsupported_media", "Only JPEG, PNG or WebP images are accepted.")
    exif = img.getexif()
    had_gps = bool(exif.get_ifd(GPS_TAG)) if exif else False
    img = ImageOps.exif_transpose(img)  # bake orientation, then discard all metadata
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    # Rebuild from raw pixels: guarantees no EXIF/XMP/ICC/comment chunks survive.
    clean = Image.frombytes(img.mode, img.size, img.tobytes())
    status, detail = scan_bytes(data)
    if status == "infected":
        raise AppError(422, "malware_detected", "The file was rejected by the malware scanner.")
    media_id = uuid.uuid4()
    prefix = f"{purpose}/{media_id.hex[:2]}/{media_id.hex}"
    variants = {}
    store = storage()
    for name, max_side in VARIANTS.items():
        v = clean.copy()
        v.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        v.save(buf, format="WEBP", quality=82, method=4)  # no exif/icc args => none written
        key = f"{prefix}/{name}.webp"
        store.put(key, buf.getvalue())
        variants[name] = {"key": key, "w": v.width, "h": v.height, "bytes": buf.tell()}
    asset = MediaAsset(
        id=media_id, owner_id=owner_id, purpose=purpose, mime="image/webp", width=clean.width, height=clean.height,
        bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), phash=dhash(clean), storage_prefix=prefix,
        variants=variants, original_filename=(filename or "")[:200], exif_stripped=True, had_gps_metadata=had_gps,
        rights_confirmed_by_uploader=rights_confirmed,
        scan_status=status, scan_detail=detail,
        status="clean" if status == "clean" else ("clean" if (s.is_dev and s.allow_unscanned_media_in_dev) else "quarantine"),
    )
    db.add(asset)
    db.flush()
    return asset


def similar_assets(db: Session, asset: MediaAsset, max_distance: int = 6) -> list[dict]:
    """Near-duplicate candidates (exact sha256 or dHash within Hamming distance)."""
    out = []
    for other in db.execute(select(MediaAsset).where(MediaAsset.id != asset.id)).scalars():
        dist = 0 if other.sha256 == asset.sha256 else hamming(other.phash, asset.phash)
        if dist <= max_distance:
            out.append({"media_id": str(other.id), "distance": dist, "owner_id": str(other.owner_id) if other.owner_id else None})
    return sorted(out, key=lambda x: x["distance"])


# ---------------------------------------------------------------- URLs

def sign(media_id: str, variant: str, ttl: int = 3600) -> str:
    exp = int(time.time()) + ttl
    msg = f"{media_id}:{variant}:{exp}".encode()
    sig = hmac.new(get_settings().secret_key.encode(), msg, hashlib.sha256).hexdigest()[:32]
    return f"/api/media/{media_id}/{variant}?exp={exp}&sig={sig}"


def verify_signature(media_id: str, variant: str, exp: int, sig: str) -> bool:
    if exp < time.time():
        return False
    msg = f"{media_id}:{variant}:{exp}".encode()
    good = hmac.new(get_settings().secret_key.encode(), msg, hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(good, sig)


def public_url(asset: MediaAsset, variant: str = "md") -> str:
    return f"/api/media/{asset.id}/{variant}"


def asset_public(asset: MediaAsset, locale: str | None = None) -> dict:
    return {"id": str(asset.id), "width": asset.width, "height": asset.height,
            "urls": {k: public_url(asset, k) for k in asset.variants},
            "alt_text_i18n": asset.alt_text_i18n, "caption_i18n": asset.caption_i18n,
            "license": asset.license, "credit": asset.credit, "attribution_url": asset.attribution_url,
            "is_illustrative": asset.is_illustrative, "is_reconstruction": asset.is_reconstruction,
            "is_ai_generated": asset.is_ai_generated}


def destination_media_public(db: Session, destination_id) -> list[dict]:
    rows = db.execute(select(MediaAsset, DestinationMedia).join(DestinationMedia, DestinationMedia.media_id == MediaAsset.id)
                      .where(DestinationMedia.destination_id == destination_id, MediaAsset.status == "approved")
                      .order_by(DestinationMedia.is_hero.desc(), DestinationMedia.sort_order)).all()
    return [{**asset_public(a), "is_hero": link.is_hero} for a, link in rows]
