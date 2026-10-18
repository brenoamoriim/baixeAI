"""Real AI models (run inside worker-ai). Skipped elsewhere, with the reason shown."""

import io
import uuid

import pytest
from PIL import Image, ImageDraw

from app.core.errors import AppError
from app.tools.ai import providers, verify
from app.tools.ai.handlers import BackgroundRemoverHandler, ObjectRemoverHandler
from app.tools.base import ToolUserError
from tests.conftest import make_user

HAS_MODELS = (providers.MODEL_DIR / providers.ISNET_FILE).is_file() and (
    providers.MODEL_DIR / providers.LAMA_FILE
).is_file()
ai = pytest.mark.skipif(not HAS_MODELS, reason="run inside worker-ai (models not in this image)")


@ai
@pytest.mark.parametrize("candidate", verify.candidates(), ids=lambda c: c.key)
def test_real_ai_candidate(candidate, tmp_path):
    verify.run_candidate(candidate, tmp_path)


def test_rejects_bad_options():
    bg = BackgroundRemoverHandler()
    with pytest.raises(AppError):
        bg.validate_options("png", "png", {"background": "red; rm -rf /"}, {})
    with pytest.raises(AppError):
        bg.validate_options("pdf", "png", {}, {})
    assert bg.validate_options("png", "jpg", {}, {}) == {"background": "#ffffff"}  # JPEG cannot be transparent
    obj = ObjectRemoverHandler()
    meta = {"width": 10, "height": 10, "extra": {"mask_upload_id": {"format": "png", "width": 20, "height": 10}}}
    with pytest.raises(AppError) as exc:
        obj.validate_options("png", "png", {"mask_upload_id": "x"}, meta)
    assert exc.value.code == "invalid_mask"
    with pytest.raises(AppError):
        obj.validate_options("png", "png", {"mask_upload_id": "x", "mask_expand": "999"}, meta)


@ai
def test_empty_mask_is_user_error(tmp_path):
    image = tmp_path / "in.png"
    Image.new("RGB", (64, 64), "white").save(image)
    mask = tmp_path / "mask.png"
    Image.new("L", (64, 64), 0).save(mask)
    with pytest.raises(ToolUserError) as exc:
        ObjectRemoverHandler().execute("png", "png", {"mask_expand": "0"}, tmp_path, image,
                                       {"extra_paths": {"mask_upload_id": mask}})
    assert exc.value.code == "empty_mask"


# ---------------------------------------------------------------- full flow through the API


def _png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


def _upload(client, name, data):
    return client.post("/api/v1/uploads", files={"file": (name, data, "application/octet-stream")}).json()


def _credits(client):
    return client.get("/api/v1/me/credits").json()["total_general"]


def _job(client, tool, upload, out, **options):
    return client.post("/api/v1/jobs", headers={"Idempotency-Key": uuid.uuid4().hex}, json={
        "tool_id": tool, "input_format": upload["format"], "output_format": out,
        "options": {"upload_id": upload["id"], **options}})


@ai
def test_background_flow_and_charge(client):
    client.login(make_user().email)
    up = _upload(client, "retrato.png", _png(verify.disc_image()))
    assert up["status"] == "ready"
    estimate = client.post("/api/v1/jobs/estimate", json={
        "tool_id": "background_remover", "input_format": "png", "output_format": "png",
        "options": {"upload_id": up["id"]}})
    assert estimate.json() == {"cost": 1}
    job = _job(client, "background_remover", up, "png").json()
    assert job["status"] == "completed", job
    link = client.post(f"/api/v1/jobs/{job['id']}/download-link").json()["url"]
    with Image.open(io.BytesIO(client.get(link).content)) as out:
        assert out.mode == "RGBA" and out.size == (640, 480)
    assert _credits(client) == 4


@ai
def test_object_remover_requires_rights_and_records_acceptance(client, db):
    from sqlalchemy import select

    from app.models import TermsAcceptance

    client.login(make_user().email)
    image, mask = verify.square_scene()
    up = _upload(client, "foto.png", _png(image))
    mk = _upload(client, "mascara.png", _png(mask.convert("RGB")))
    # cost is visible before accepting
    estimate = client.post("/api/v1/jobs/estimate", json={
        "tool_id": "object_remover", "input_format": "png", "output_format": "png",
        "options": {"upload_id": up["id"]}})
    assert estimate.json() == {"cost": 1}
    refused = _job(client, "object_remover", up, "png", mask_upload_id=mk["id"])
    assert refused.status_code == 400 and refused.json()["error"]["code"] == "rights_not_accepted"
    assert _credits(client) == 5
    job = _job(client, "object_remover", up, "png", mask_upload_id=mk["id"], accept_rights=True).json()
    assert job["status"] == "completed", job
    assert _credits(client) == 4
    rows = db.execute(select(TermsAcceptance)).scalars().all()
    assert [(r.document, str(r.job_id)) for r in rows] == [("image_edit_rights", job["id"])]


@ai
def test_cannot_use_another_users_mask(new_client):
    alice, bob = new_client(), new_client()
    alice.login(make_user().email)
    bob.login(make_user().email)
    image, mask = verify.square_scene()
    alice_mask = _upload(alice, "m.png", _png(mask.convert("RGB")))
    bob_image = _upload(bob, "f.png", _png(image))
    r = _job(bob, "object_remover", bob_image, "png", mask_upload_id=alice_mask["id"], accept_rights=True)
    assert r.status_code == 404 and _credits(bob) == 5


@ai
def test_model_failure_refunds(client, monkeypatch):
    def boom(*args, **kwargs):
        raise FileNotFoundError("model gone")

    monkeypatch.setattr(providers.IsNetBackground, "mask", boom)
    client.login(make_user().email)
    up = _upload(client, "a.png", _png(verify.disc_image()))
    job = _job(client, "background_remover", up, "png").json()
    assert job["status"] == "failed" and job["error_class"] == "system"
    assert _credits(client) == 5


@ai
def test_non_image_rejected_before_charge(client):
    client.login(make_user().email)
    up = _upload(client, "doc.pdf", b"%PDF-1.4\n%fake\n")
    r = _job(client, "background_remover", up, "png")
    assert r.status_code in (400, 404) and _credits(client) == 5


@ai
def test_mask_must_match_image_size(client):
    client.login(make_user().email)
    up = _upload(client, "f.png", _png(verify.disc_image()))
    small = Image.new("RGB", (100, 100), "black")
    ImageDraw.Draw(small).rectangle((10, 10, 50, 50), fill="white")
    mk = _upload(client, "m.png", _png(small))
    r = _job(client, "object_remover", up, "png", mask_upload_id=mk["id"], accept_rights=True)
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_mask" and _credits(client) == 5
