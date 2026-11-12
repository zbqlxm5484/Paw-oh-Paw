"""영상 업로드 검사·저장(13.1, 15.6, 17.3 BE-05)과 ffprobe 읽기.

시험 영상은 ffmpeg(FFMPEG_PATH)로 만든다. 2초짜리 작은 파일이라 몇 초면 된다. ffmpeg가 없으면 이 파일 전체를 건너뛴다.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import uuid
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import delete_created_files
from app.core.config import get_settings
from app.models import MeasureSession, Shot
from app.storage.base import get_storage
from app.storage.keys import session_prefix
from app.video.probe import VideoProbeError, probe
from tests.conftest import bearer

SHOT_UPLOAD_KEYS = {
    "id",
    "seq_no",
    "status",
    "fail_reason",
    "validity",
    "validity_reason",
    "video_status",
    "below_min_spec",
    "passes",
    "uploaded_at",
    "analyzed_at",
    "warnings",
}
X264_CBR = [
    *("-c:v", "libx264", "-b:v", "5000k", "-minrate", "5000k", "-maxrate", "5000k", "-bufsize", "2500k"),
    *("-x264-params", "nal-hrd=cbr:force-cfr=1", "-pix_fmt", "yuv420p"),
]
X265_CBR = [
    *("-c:v", "libx265", "-pix_fmt", "yuv420p"),
    *("-x265-params", "bitrate=5000:vbv-maxrate=5000:vbv-bufsize=2500:strict-cbr=1:log-level=error"),
]


def _ffmpeg(*args: str) -> None:
    subprocess.run([get_settings().FFMPEG_PATH, "-y", "-v", "error", *args], check=True, capture_output=True)


def _testsrc(size: str, rate: int, duration: float) -> list[str]:
    return ["-f", "lavfi", "-i", f"testsrc=duration={duration}:size={size}:rate={rate}"]


@pytest.fixture(scope="session")
def videos() -> Iterator[dict[str, Path]]:
    """이름 → 경로. ok·hevc는 통과, 나머지는 13.1의 검사 하나씩에 걸리거나 경고를 받는다."""
    try:
        subprocess.run([get_settings().FFMPEG_PATH, "-version"], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("ffmpeg가 없어 업로드 테스트를 건너뛴다(FFMPEG_PATH)")
    root = Path(tempfile.mkdtemp(prefix="cf-vid-"))  # 짧은 경로(Windows 260자 한도)
    files: dict[str, Path] = {}

    def make(name: str, *args: str) -> None:
        files[name] = root / name
        _ffmpeg(*args, str(files[name]))

    make("ok.mp4", *_testsrc("1280x720", 30, 2), *X264_CBR)
    make("hevc.mov", *_testsrc("1280x720", 30, 2), *X265_CBR)
    make("portrait.mp4", *_testsrc("720x1280", 30, 2), *X264_CBR)
    make("lowspec.mp4", *_testsrc("320x180", 15, 2), "-c:v", "libx264", "-pix_fmt", "yuv420p")
    make("aspect43.mp4", *_testsrc("640x480", 30, 2), *X264_CBR)
    make("mpeg4.mp4", *_testsrc("1280x720", 30, 2), "-c:v", "mpeg4", "-q:v", "2")
    make("short.mp4", *_testsrc("1280x720", 30, 0.5), *X264_CBR)
    make("long.mp4", *_testsrc("320x180", 30, 31), "-c:v", "libx264", "-pix_fmt", "yuv420p")
    # 휴대폰 세로 촬영: 저장은 가로(1280×720)이고 회전 값 90만 붙는다(13.1)
    make("rotated.mp4", "-display_rotation", "90", "-i", str(files["ok.mp4"]), "-c", "copy")
    files["text.mp4"] = root / "text.mp4"
    files["text.mp4"].write_text("not a video", encoding="utf-8")
    yield files
    shutil.rmtree(root, ignore_errors=True)


# ---- ffprobe 읽기 (13.1) ----


def test_probe_reads_video_info(videos: dict[str, Path]) -> None:
    info = probe(videos["ok.mp4"], get_settings().FFPROBE_PATH)
    assert (info.width, info.height, info.rotation, info.codec) == (1280, 720, 0, "h264")
    assert info.fps == Decimal("30.00")
    assert info.duration_sec == Decimal("2.00")
    assert info.bitrate_kbps >= 4000


def test_probe_swaps_width_and_height_when_rotated(videos: dict[str, Path]) -> None:
    info = probe(videos["rotated.mp4"], get_settings().FFPROBE_PATH)
    assert (info.width, info.height, info.rotation) == (720, 1280, 90)


def test_probe_rejects_non_video(videos: dict[str, Path]) -> None:
    with pytest.raises(VideoProbeError):
        probe(videos["text.mp4"], get_settings().FFPROBE_PATH)


# ---- 업로드 API (BE-05) ----


def _upload(client: TestClient, headers: dict, session_id, path: Path, name: str | None = None):
    with path.open("rb") as file:
        return client.post(
            f"/api/v1/sessions/{session_id}/shots",
            files={"file": (name or path.name, file, "application/octet-stream")},
            headers=headers,
        )


@pytest.fixture
def session_id(client: TestClient, auth_headers: dict, dog) -> uuid.UUID:
    response = client.post(f"/api/v1/dogs/{dog.id}/sessions", json={}, headers=auth_headers)
    assert response.status_code == 201
    return uuid.UUID(response.json()["id"])


def _tmp_files() -> list[Path]:
    return [p for p in Path(get_settings().UPLOAD_TMP_DIR).iterdir() if p.is_file()]


def test_upload_saves_file_and_creates_uploaded_shot(
    client: TestClient, db: Session, auth_headers: dict, dog, session_id: uuid.UUID, videos: dict[str, Path]
) -> None:
    response = _upload(client, auth_headers, session_id, videos["ok.mp4"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == SHOT_UPLOAD_KEYS
    assert (body["seq_no"], body["status"], body["video_status"]) == (1, "UPLOADED", "PENDING")
    assert body["warnings"] == [] and body["below_min_spec"] is False
    assert body["passes"] == [] and body["validity"] is None and body["analyzed_at"] is None
    assert body["uploaded_at"].endswith("Z")

    shot = db.get(Shot, uuid.UUID(body["id"]))
    assert (shot.width, shot.height, shot.codec) == (1280, 720, "h264")
    assert (shot.fps, shot.duration_sec) == (Decimal("30.00"), Decimal("2.00"))
    assert shot.bitrate_kbps >= 4000
    prefix = session_prefix(dog.institution_id, dog.id, session_id)
    assert shot.original_key == f"{prefix}{shot.id}/original.mp4"
    assert len(get_storage().read_bytes(shot.original_key)) == videos["ok.mp4"].stat().st_size
    assert _tmp_files() == []  # 임시 파일은 저장소로 옮겨졌다

    second = _upload(client, auth_headers, session_id, videos["hevc.mov"]).json()
    assert second["seq_no"] == 2
    second_shot = db.get(Shot, uuid.UUID(second["id"]))
    assert second_shot.codec == "hevc" and second_shot.original_key.endswith("/original.mov")

    detail = client.get(f"/api/v1/sessions/{session_id}", headers=auth_headers).json()
    assert [s["seq_no"] for s in detail["shots"]] == [2, 1]
    assert detail["shots"][0]["status"] == "UPLOADED"


def test_upload_warnings_do_not_block(
    client: TestClient, db: Session, auth_headers: dict, session_id: uuid.UUID, videos: dict[str, Path]
) -> None:
    low = _upload(client, auth_headers, session_id, videos["lowspec.mp4"])
    assert low.status_code == 201, low.text
    assert [w["code"] for w in low.json()["warnings"]] == ["BELOW_MIN_SPEC"]
    assert low.json()["below_min_spec"] is True
    assert "640" in low.json()["warnings"][0]["message"]
    assert db.get(Shot, uuid.UUID(low.json()["id"])).below_min_spec is True

    aspect = _upload(client, auth_headers, session_id, videos["aspect43.mp4"])
    assert aspect.status_code == 201, aspect.text
    assert [w["code"] for w in aspect.json()["warnings"]] == ["ASPECT_NOT_16_9"]
    assert aspect.json()["below_min_spec"] is False


@pytest.mark.parametrize(
    ("name", "upload_as", "code"),
    [
        ("ok.mp4", "clip.avi", "VIDEO_FORMAT"),
        ("ok.mp4", "noextension", "VIDEO_FORMAT"),
        ("text.mp4", None, "VIDEO_UNREADABLE"),
        ("mpeg4.mp4", None, "VIDEO_CODEC"),
        ("portrait.mp4", None, "VIDEO_PORTRAIT"),
        ("rotated.mp4", None, "VIDEO_PORTRAIT"),
        ("short.mp4", None, "VIDEO_DURATION"),
        ("long.mp4", None, "VIDEO_DURATION"),
    ],
)
def test_upload_rejections_leave_nothing_behind(
    client: TestClient,
    db: Session,
    auth_headers: dict,
    dog,
    session_id: uuid.UUID,
    videos: dict[str, Path],
    name: str,
    upload_as: str | None,
    code: str,
) -> None:
    response = _upload(client, auth_headers, session_id, videos[name], upload_as)
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == code
    if code == "VIDEO_DURATION":
        assert "1~30초" in response.json()["error"]["message"]
    assert db.scalars(select(Shot.id).where(Shot.session_id == session_id)).all() == []
    assert _tmp_files() == []
    assert get_storage().stat_prefix(session_prefix(dog.institution_id, dog.id, session_id)) == (0, 0)


@pytest.fixture
def one_mb_limit(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("UPLOAD_MAX_MB", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_upload_too_large_is_413(
    client: TestClient, auth_headers: dict, session_id: uuid.UUID, videos: dict[str, Path], one_mb_limit: None
) -> None:
    assert videos["ok.mp4"].stat().st_size > 1024 * 1024
    response = _upload(client, auth_headers, session_id, videos["ok.mp4"])
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "VIDEO_TOO_LARGE"
    assert "1 MB" in response.json()["error"]["message"]
    assert _tmp_files() == []


def test_closed_session_is_checked_before_the_file(
    client: TestClient, db: Session, auth_headers: dict, session_id: uuid.UUID, videos: dict[str, Path]
) -> None:
    db.get(MeasureSession, session_id).status = "DONE"
    db.flush()
    response = _upload(client, auth_headers, session_id, videos["text.mp4"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SESSION_CLOSED"


def test_missing_file_field_is_422(client: TestClient, auth_headers: dict, session_id: uuid.UUID) -> None:
    response = client.post(f"/api/v1/sessions/{session_id}/shots", headers=auth_headers)
    assert response.status_code == 422
    assert [f["field"] for f in response.json()["error"]["detail"]["fields"]] == ["file"]


def test_other_institution_session_is_404(
    client: TestClient, db: Session, auth_headers: dict, other_staff, videos: dict[str, Path]
) -> None:
    from app.models import Dog

    theirs = Dog(
        institution_id=other_staff.institution_id,
        name="남의개",
        breed="믹스",
        weight_kg=Decimal("5"),
        size_class="SMALL",
    )
    db.add(theirs)
    db.flush()
    their_session = client.post(f"/api/v1/dogs/{theirs.id}/sessions", json={}, headers=bearer(other_staff)).json()
    response = _upload(client, auth_headers, their_session["id"], videos["ok.mp4"])
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# ---- 실패한 요청의 파일 정리 (12.4, 11.7) ----


def test_delete_created_files_removes_files_recorded_on_the_session(db: Session) -> None:
    storage = get_storage()
    key = f"i/d/s/{uuid.uuid4()}/original.mp4"
    storage.write_bytes(key, b"video")
    db.info["created_files"] = [key, "i/d/s/missing/original.mp4"]  # 없는 키가 섞여도 나머지는 지운다
    delete_created_files(db)
    assert storage.stat_prefix("i/d/s/") == (0, 0)
    assert db.info["created_files"] == []
