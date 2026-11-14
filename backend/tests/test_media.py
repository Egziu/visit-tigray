from __future__ import annotations

import io

from PIL import Image

from tests.test_content import make_destination


def jpeg_with_gps(color=(200, 120, 60), size=(640, 480)) -> bytes:
    img = Image.new("RGB", size, color)
    for x in range(0, size[0], 40):  # some structure so dHash is meaningful
        for y in range(size[1]):
            img.putpixel((x, y), (10, 10, 10))
    exif = Image.Exif()
    exif[0x010F] = "TestCamera"
    gps = {1: "N", 2: (13.0, 29.0, 0.0), 3: "E", 4: (39.0, 28.0, 0.0)}
    exif[0x8825] = gps
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def upload(c, data, purpose="community", rights=True, name="photo.jpg"):
    return c.post("/api/media", files={"file": (name, data, "image/jpeg")},
                  data={"purpose": purpose, "rights_confirmed": str(rights).lower()})


def test_upload_strips_exif_and_gps(visitor, client):
    v = visitor()
    raw = jpeg_with_gps()
    assert Image.open(io.BytesIO(raw)).getexif().get_ifd(0x8825)  # precondition: GPS present
    r = upload(v, raw)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["had_gps_metadata"] is True and body["exif_stripped"] is True
    served = v.get(body["urls"]["md"])
    assert served.status_code == 200 and served.headers["content-type"] == "image/webp"
    out = Image.open(io.BytesIO(served.content))
    assert not out.getexif() and "exif" not in out.info and "icc_profile" not in out.info
    # Unapproved media is invisible to anonymous users (404, not 403)
    assert client.get(body["urls"]["md"]).status_code == 404
    # ...unless they hold a valid signed URL
    assert client.get(body["signed_preview"]).status_code == 200
    assert client.get(body["signed_preview"].replace("sig=", "sig=0")).status_code == 404


def test_rejects_non_images_and_polyglots(visitor):
    v = visitor()
    assert upload(v, b"<?php echo 1; ?>" + b"x" * 100).status_code == 415
    assert upload(v, b"\xff\xd8\xff" + b"<script>alert(1)</script>" * 10).status_code == 415
    assert upload(v, b"GIF89a" + b"\0" * 100).status_code == 415
    assert upload(v, jpeg_with_gps(), rights=False).json()["error"]["code"] == "rights_required"


def test_unverified_and_anonymous_cannot_upload(visitor, client):
    assert upload(client, jpeg_with_gps()).status_code == 401
    assert upload(visitor(verified=False), jpeg_with_gps()).json()["error"]["code"] == "email_unverified"


def test_destination_media_requires_rights_and_approval(staff, client):
    media = staff("content_editor")
    v = upload(media, jpeg_with_gps(), purpose="destination", rights=False)
    assert v.status_code == 201
    mid = v.json()["id"]
    assert media.post(f"/api/bureau/media/{mid}/approve").json()["error"]["code"] == "rights_incomplete"
    media.put(f"/api/bureau/media/{mid}/rights", json={
        "license": "CC BY 4.0", "credit": "Synthetic test image", "is_illustrative": True,
        "alt_text_i18n": {"en": "Synthetic striped test pattern"}})
    assert media.post(f"/api/bureau/media/{mid}/approve").status_code == 200
    did = make_destination(media, publish_with=None)
    assert media.post(f"/api/bureau/destinations/{did}/media", json={"media_id": mid, "is_hero": True}).status_code == 201
    media.post(f"/api/bureau/destinations/{did}/publish", json={})
    d = client.get("/api/destinations/aksum-test").json()
    assert d["media"][0]["is_illustrative"] is True and d["media"][0]["credit"] == "Synthetic test image"
    assert client.get(d["media"][0]["urls"]["sm"]).status_code == 200


def test_duplicate_detection(visitor):
    v = visitor()
    first = upload(v, jpeg_with_gps()).json()
    # re-encoded / resized copy of the same picture
    img = Image.open(io.BytesIO(jpeg_with_gps())).resize((320, 240))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    second = v.post("/api/media", files={"file": ("copy.png", buf.getvalue(), "image/png")},
                    data={"purpose": "community", "rights_confirmed": "true"}).json()
    assert any(dup["media_id"] == first["id"] for dup in second["duplicates"])
