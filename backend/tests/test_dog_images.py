"""반려견 사진(BE-34, 명세 12.5 사진, 13.9, 15.11). 얼굴을 가린 사진만 저장하고 원본은 두지 않는다."""

from __future__ import annotations

import io
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dates import today_local
from app.core.security import make_signed_url
from app.models import DogImage
from app.services import dog_images
from app.services.purge import purge
from app.storage.base import get_storage
from app.storage.keys import dog_prefix
from app.video import photo
from app.video.photo import (
    PhotoFormatError,
    PhotoTooLargeError,
    PhotoUnreadableError,
    declared_size,
    prepare_photo,
    sniff_format,
)
from app.video.render import VideoRenderError
from tests.conftest import bearer

WIDTH, HEIGHT = 320, 240
FACE_BOX = (100, 60, 180, 140)
CAPTION = "수술 직후 오른쪽 뒷다리"


def _pixels(width: int = WIDTH, height: int = HEIGHT) -> np.ndarray:
    """칸마다 색이 다른 무늬. 모자이크가 걸리면 그 자리의 값이 바뀐다."""
    ys, xs = np.mgrid[0:height, 0:width]
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[..., 0] = (xs * 7) % 256
    image[..., 1] = (ys * 5) % 256
    image[..., 2] = ((xs // 4 + ys // 4) % 2) * 255
    return image


def _encode(ext: str, image: np.ndarray | None = None) -> bytes:
    ok, data = cv2.imencode(f".{ext}", _pixels() if image is None else image)
    assert ok
    return data.tobytes()


def _decode(data: bytes) -> np.ndarray:
    return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)


PNG, JPG = _encode("png"), _encode("jpg")


def _no_faces(_image: np.ndarray) -> list:
    return []


def _one_face(_image: np.ndarray) -> list:
    return [FACE_BOX]


# ---- 사진 바꾸기(video/photo.py) ----


def test_format_is_decided_by_content_not_name() -> None:
    assert (sniff_format(PNG), sniff_format(JPG)) == ("png", "jpg")
    for data in (b"", b"GIF89a....", b"%PDF-1.7", b"hello.jpg", b"\x00" * 64):
        with pytest.raises(PhotoFormatError):
            sniff_format(data)


def test_declared_size_reads_the_header() -> None:
    assert declared_size(PNG, "png") == (WIDTH, HEIGHT)
    assert declared_size(JPG, "jpg") == (WIDTH, HEIGHT)
    for data, ext in ((PNG[:20], "png"), (JPG[:4], "jpg"), (b"\xff\xd8\xff\x00junk", "jpg")):
        with pytest.raises(PhotoUnreadableError):
            declared_size(data, ext)


def test_too_many_pixels_is_refused_before_decoding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cv2, "imdecode", lambda *_: pytest.fail("풀기 전에 걸러야 한다"))
    with pytest.raises(PhotoTooLargeError):
        prepare_photo(PNG, mask_faces=False, max_pixels=WIDTH * HEIGHT - 1)
    # 머리에 적힌 크기만 큰 PNG(작은 파일이 큰 그림으로 풀리는 것)
    bomb = PNG[:16] + (30_000).to_bytes(4, "big") + (30_000).to_bytes(4, "big") + PNG[24:]
    with pytest.raises(PhotoTooLargeError):
        prepare_photo(bomb, mask_faces=False, max_pixels=40_000_000)


BROKEN = {"cut_png": PNG[:60], "garbage_png": PNG[:33] + b"garbage" * 20, "cut_jpg": JPG[: len(JPG) // 20]}


@pytest.mark.parametrize("name", list(BROKEN))
def test_undecodable_content_is_unreadable(name: str) -> None:
    data = BROKEN[name]
    with pytest.raises(PhotoUnreadableError):
        prepare_photo(data, mask_faces=False, max_pixels=40_000_000)


@pytest.mark.parametrize("ext", ["png", "jpg"])
def test_photo_keeps_its_format_and_size(ext: str) -> None:
    data = PNG if ext == "png" else JPG
    result = prepare_photo(data, mask_faces=True, max_pixels=40_000_000, detect_faces=_no_faces)
    assert (result.ext, result.width, result.height, result.masked_faces) == (ext, WIDTH, HEIGHT, 0)
    assert sniff_format(result.data) == ext
    assert _decode(result.data).shape == (HEIGHT, WIDTH, 3)


def test_faces_are_masked_and_the_rest_is_untouched() -> None:
    result = prepare_photo(PNG, mask_faces=True, max_pixels=40_000_000, detect_faces=_one_face)
    assert result.masked_faces == 1
    before, after = _pixels(), _decode(result.data)
    x0, y0, x1, y1 = FACE_BOX
    assert not np.array_equal(after[y0:y1, x0:x1], before[y0:y1, x0:x1])
    # 상자는 30% 넓혀 가린다. 그 바깥은 그대로다(PNG는 무손실)
    assert np.array_equal(after[:30], before[:30])
    assert np.array_equal(after[:, :70], before[:, :70])


def test_without_masking_the_detector_is_not_called() -> None:
    result = prepare_photo(
        PNG, mask_faces=False, max_pixels=40_000_000, detect_faces=lambda _: pytest.fail("부르면 안 된다")
    )
    assert result.masked_faces == 0
    assert np.array_equal(_decode(result.data), _pixels())


def test_detector_failure_is_not_swallowed() -> None:
    def broken(_image: np.ndarray) -> list:
        raise VideoRenderError("얼굴 검출에 실패했습니다")

    with pytest.raises(VideoRenderError):
        prepare_photo(PNG, mask_faces=True, max_pixels=40_000_000, detect_faces=broken)


def test_metadata_in_the_file_is_dropped() -> None:
    comment = b"\xff\xfe" + (2 + 14).to_bytes(2, "big") + b"SECRET-COMMENT"
    with_comment = JPG[:2] + comment + JPG[2:]
    assert b"SECRET-COMMENT" in with_comment
    result = prepare_photo(with_comment, mask_faces=False, max_pixels=40_000_000)
    assert b"SECRET-COMMENT" not in result.data
    assert declared_size(result.data, "jpg") == (WIDTH, HEIGHT)


def test_the_bundled_detector_runs_in_this_process() -> None:
    """진짜 검출기가 API 프로세스에서 열리고, 얼굴이 없는 사진에서는 아무것도 가리지 않는다."""
    flat = np.full((HEIGHT, WIDTH, 3), 90, dtype=np.uint8)
    result = prepare_photo(_encode("png", flat), mask_faces=True, max_pixels=40_000_000)
    assert result.masked_faces == 0
    assert np.array_equal(_decode(result.data), flat)


# ---- API ----


def _url(dog) -> str:
    return f"/api/v1/dogs/{dog.id}/images"


def _upload(client: TestClient, dog, headers: dict, *, data: bytes = PNG, name: str = "IMG_0001.png", **form: Any):
    fields = {"kind": "PHOTO", **form}
    return client.post(_url(dog), headers=headers, files={"file": (name, data)}, data=fields)


def _list(client: TestClient, dog, headers: dict) -> list[dict]:
    response = client.get(_url(dog), headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _stored_files(dog) -> list[Path]:
    folder = get_storage().path(dog_prefix(dog.institution_id, dog.id)) / "images"
    return sorted(folder.iterdir()) if folder.is_dir() else []


def _fields(response) -> list[str]:
    return [item["field"] for item in response.json()["error"]["detail"]["fields"]]


@pytest.fixture
def no_faces(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(photo, "find_faces", _no_faces)


@pytest.fixture
def one_face(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(photo, "find_faces", _one_face)


def test_upload_stores_the_photo_and_lists_it(
    client: TestClient, db: Session, dog, staff, auth_headers, no_faces
) -> None:
    response = _upload(client, dog, auth_headers, kind="POST_OP", taken_on="2026-08-27", caption=f"  {CAPTION}  ")
    assert response.status_code == 201, response.text
    body = response.json()
    assert {key: body[key] for key in ("taken_on", "kind", "caption", "width", "height", "masked_faces", "staff")} == {
        "taken_on": "2026-08-27",
        "kind": "POST_OP",
        "caption": CAPTION,
        "width": WIDTH,
        "height": HEIGHT,
        "masked_faces": 0,
        "staff": {"id": str(staff.id), "name": "담당자"},
    }
    assert body["file_url"].startswith(f"/api/v1/images/{body['id']}/file?exp=")
    row = db.get(DogImage, uuid.UUID(body["id"]))
    # 7절 키: 반려견 접두어 아래, 휴대폰의 원래 파일 이름은 들어가지 않는다
    assert row.file_key == f"{dog.institution_id}/{dog.id}/images/{row.id}.png"
    assert [path.name for path in _stored_files(dog)] == [f"{row.id}.png"]
    assert _list(client, dog, auth_headers) == [body]


def test_file_url_opens_the_stored_photo_without_a_token(client: TestClient, dog, auth_headers, no_faces) -> None:
    for data, name, content_type in ((PNG, "a.png", "image/png"), (JPG, "a.jpeg", "image/jpeg")):
        body = _upload(client, dog, auth_headers, data=data, name=name).json()
        response = client.get(body["file_url"])  # Authorization 없음
        assert response.status_code == 200
        assert response.headers["content-type"] == content_type
        assert response.headers["cache-control"] == f"private, max-age={get_settings().FILE_URL_TTL_SEC}"
        assert _decode(response.content).shape == (HEIGHT, WIDTH, 3)
    # 확장자가 아니라 내용으로 가렸다. 이름이 .png여도 JPEG면 jpg로 저장한다
    body = _upload(client, dog, auth_headers, data=JPG, name="wrong.png").json()
    assert client.get(body["file_url"]).headers["content-type"] == "image/jpeg"


def test_faces_are_masked_before_storing_and_the_original_is_not_kept(
    client: TestClient, dog, auth_headers, one_face
) -> None:
    body = _upload(client, dog, auth_headers).json()
    assert body["masked_faces"] == 1
    (stored,) = _stored_files(dog)
    data = stored.read_bytes()
    assert data != PNG
    x0, y0, x1, y1 = FACE_BOX
    assert not np.array_equal(_decode(data)[y0:y1, x0:x1], _pixels()[y0:y1, x0:x1])
    assert client.get(body["file_url"]).content == data


@pytest.mark.parametrize(("kind", "masked"), [("PHOTO", 1), ("PRE_OP", 1), ("POST_OP", 1), ("XRAY", 0)])
def test_only_xray_is_left_unmasked(client: TestClient, dog, auth_headers, one_face, kind: str, masked: int) -> None:
    body = _upload(client, dog, auth_headers, kind=kind).json()
    assert body["masked_faces"] == masked
    (stored,) = _stored_files(dog)
    assert np.array_equal(_decode(stored.read_bytes()), _pixels()) is (masked == 0)


def test_list_is_by_taken_on_then_upload_order(client: TestClient, db: Session, dog, auth_headers, no_faces) -> None:
    late = _upload(client, dog, auth_headers, taken_on="2026-10-01", caption="셋째").json()
    early_first = _upload(client, dog, auth_headers, taken_on="2026-08-01", kind="XRAY", caption="첫째").json()
    early_second = _upload(client, dog, auth_headers, taken_on="2026-08-01", caption="둘째").json()
    # 시험은 한 트랜잭션 안이라 now()가 같다. 올린 시각을 따로 넣어 순서를 가른다
    uploaded = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
    for minutes, body in enumerate((late, early_first, early_second)):
        db.get(DogImage, uuid.UUID(body["id"])).created_at = uploaded + timedelta(minutes=minutes)
    db.flush()
    assert [item["id"] for item in _list(client, dog, auth_headers)] == [
        early_first["id"],
        early_second["id"],
        late["id"],
    ]


def test_taken_on_defaults_to_today_and_blank_fields_are_empty(client: TestClient, dog, auth_headers, no_faces) -> None:
    body = _upload(client, dog, auth_headers, taken_on="", caption="   ").json()
    assert (body["taken_on"], body["caption"]) == (today_local().isoformat(), None)
    assert _upload(client, dog, auth_headers).json()["caption"] is None


@pytest.mark.parametrize(
    ("form", "field"),
    [
        ({"kind": "SELFIE"}, "kind"),
        ({"kind": ""}, "kind"),
        ({"taken_on": "2026-13-01"}, "taken_on"),
        ({"taken_on": (date.today() + timedelta(days=2)).isoformat()}, "taken_on"),
        ({"caption": "가" * 101}, "caption"),
    ],
)
def test_form_rules(client: TestClient, db: Session, dog, auth_headers, no_faces, form: dict, field: str) -> None:
    response = _upload(client, dog, auth_headers, **form)
    assert response.status_code == 422, response.text
    assert _fields(response) == [field]
    assert db.scalar(select(func.count()).select_from(DogImage)) == 0 and _stored_files(dog) == []


def test_file_and_kind_are_required(client: TestClient, dog, auth_headers, no_faces) -> None:
    assert _fields(client.post(_url(dog), headers=auth_headers, data={"kind": "PHOTO"})) == ["file"]
    assert _fields(client.post(_url(dog), headers=auth_headers, files={"file": ("a.png", PNG)})) == ["kind"]
    assert _upload(client, dog, auth_headers, caption="가" * 100).status_code == 201


def test_file_checks_come_in_order_and_store_nothing(
    client: TestClient, db: Session, dog, auth_headers, no_faces, monkeypatch: pytest.MonkeyPatch
) -> None:
    def code(data: bytes) -> tuple[int, str]:
        response = _upload(client, dog, auth_headers, data=data)
        return response.status_code, response.json()["error"]["code"]

    assert code(b"not a photo at all") == (400, "IMAGE_FORMAT")
    assert code(PNG[:60]) == (400, "IMAGE_UNREADABLE")
    monkeypatch.setattr(dog_images, "IMAGE_MAX_MEGAPIXELS", 0)
    response = _upload(client, dog, auth_headers)
    assert (response.status_code, response.json()["error"]["code"]) == (413, "IMAGE_TOO_LARGE")
    # 크기는 형식보다 먼저 본다
    monkeypatch.setattr(dog_images, "IMAGE_MAX_MB", 1)
    response = _upload(client, dog, auth_headers, data=b"\x00" * (dog_images.MB + 1))
    assert (response.status_code, response.json()["error"]["code"]) == (413, "IMAGE_TOO_LARGE")
    assert "1 MB" in response.json()["error"]["message"]
    assert db.scalar(select(func.count()).select_from(DogImage)) == 0 and _stored_files(dog) == []


def test_detector_failure_stores_nothing(db: Session, dog, staff) -> None:
    def broken(_image: np.ndarray) -> list:
        raise VideoRenderError("얼굴 검출에 실패했습니다")

    with pytest.raises(VideoRenderError):
        dog_images.upload_image(
            db,
            institution_id=staff.institution_id,
            staff_id=staff.id,
            dog_id=dog.id,
            upload=UploadFile(file=io.BytesIO(PNG), filename="a.png"),
            kind="PHOTO",
            taken_on=None,
            caption=None,
            detect_faces=broken,
        )
    assert db.scalar(select(func.count()).select_from(DogImage)) == 0 and _stored_files(dog) == []


def test_file_link_must_be_signed_and_fresh(client: TestClient, dog, auth_headers, no_faces) -> None:
    body = _upload(client, dog, auth_headers).json()
    path = f"/api/v1/images/{body['id']}/file"
    ttl = get_settings().FILE_URL_TTL_SEC
    expired, _ = make_signed_url(path, now=datetime.now(UTC) - timedelta(seconds=ttl + 1))
    other, _ = make_signed_url(f"/api/v1/images/{uuid.uuid4()}/file")
    for url in (path, expired, path + "?" + other.split("?", 1)[1]):
        response = client.get(url, headers=auth_headers)  # 토큰이 있어도 서명이 없으면 열리지 않는다
        assert (response.status_code, response.json()["error"]["code"]) == (403, "FILE_LINK_EXPIRED")
    assert client.get(other).status_code == 404  # 서명은 맞지만 그런 사진이 없다


def test_delete_removes_the_file_and_the_row(client: TestClient, db: Session, dog, auth_headers, no_faces) -> None:
    keep = _upload(client, dog, auth_headers).json()
    gone = _upload(client, dog, auth_headers).json()
    assert client.delete(f"/api/v1/images/{gone['id']}", headers=auth_headers).status_code == 204
    assert [item["id"] for item in _list(client, dog, auth_headers)] == [keep["id"]]
    assert [path.stem for path in _stored_files(dog)] == [keep["id"]]
    assert client.get(gone["file_url"]).status_code == 404
    assert client.delete(f"/api/v1/images/{gone['id']}", headers=auth_headers).status_code == 404


def test_other_institution_and_trashed_dog_are_404(
    client: TestClient, db: Session, dog, other_staff, auth_headers, no_faces
) -> None:
    body = _upload(client, dog, auth_headers).json()
    theirs = bearer(other_staff)
    assert client.get(_url(dog), headers=theirs).status_code == 404
    assert _upload(client, dog, theirs).status_code == 404
    assert client.delete(f"/api/v1/images/{body['id']}", headers=theirs).status_code == 404
    assert client.get(_url(dog)).status_code == 401
    dog.deleted_at = datetime.now(UTC)
    db.flush()
    assert client.get(_url(dog), headers=auth_headers).status_code == 404
    assert _upload(client, dog, auth_headers).status_code == 404
    assert client.delete(f"/api/v1/images/{body['id']}", headers=auth_headers).status_code == 404
    assert len(_stored_files(dog)) == 1  # 막힌 요청은 아무것도 쓰거나 지우지 않았다


def test_caption_and_paths_are_not_in_the_log(client: TestClient, dog, auth_headers, no_faces, caplog) -> None:
    with caplog.at_level(logging.INFO):
        body = _upload(client, dog, auth_headers, caption=CAPTION, name="보리_보호자김씨.png").json()
    assert f"dog image stored image={body['id']}" in caplog.text
    assert CAPTION not in caplog.text and "보호자김씨" not in caplog.text
    assert str(dog.id) not in caplog.text.replace(f"/dogs/{dog.id}/images", "")


def test_purge_counts_and_deletes_images(client: TestClient, db: Session, dog, auth_headers, no_faces) -> None:
    _upload(client, dog, auth_headers)
    _upload(client, dog, auth_headers, kind="XRAY")
    counted = purge(db, get_storage(), "DOG", institution_id=dog.institution_id, target_id=dog.id)
    assert (counted.rows, counted.files) == (1 + 2, 2)  # 반려견 + 사진 둘
    done = purge(db, get_storage(), "DOG", institution_id=dog.institution_id, target_id=dog.id, dry_run=False)
    assert (done.rows, done.files) == (1 + 2, 2)
    assert db.scalar(select(func.count()).select_from(DogImage)) == 0
    assert _stored_files(dog) == []
