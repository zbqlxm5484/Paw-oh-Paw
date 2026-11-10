"""시연 기관 데이터 넣기(S15P31A404-273, 박규원 요청 11-10).

    python -m scripts.seed_demo --data <demo_seed 폴더> [--videos <영상 폴더>] [--reset [--yes]] [--no-render]

AI·프론트가 만든 폴더(demo.json + shots/<회차키>/NN.analysis.json·NN.keypoints.json)를 읽어 시연 기관 하나에
담당자·반려견·이력·바이탈·메모·회차·촬영을 넣는다. 형식은 폴더의 README.md를 따른다.

- 날짜는 demo.json의 "D-n"을 실행한 날(APP_TIMEZONE) 기준으로 바꾼다. 시연 전날 --reset으로 다시 넣으면 홈의
  오늘·최근 7일이 비지 않는다.
- 촬영 결과는 워커가 분석 결과를 받았을 때와 같은 길로 넣는다: analysis.json을 저장소에 쓰고 apply_result로 DONE과
  통과 행을 넣는다. 끝난 회차는 워커와 같은 aggregate_session으로 수치·대칭 점수·보고서 PENDING 행을 만든다.
  보고서 PDF는 워커가 만든다.
- 팀 서비스는 관절점 파일을 저장하지 않고 분석 API에서 받는다. 넣은 촬영은 분석 API에 작업이 없으므로, 관절 각도
  파일(angles.json)과 결과 영상(제니처럼 영상이 있는 촬영만)을 이 스크립트가 받은 관절점 파일로 직접 만든다. 영상이
  없는 촬영은 결과 영상이 FAILED(영상 없음)이고, original_key는 파일 없는 자리 키다.
- job_id는 촬영 ID로 만든 UUID5다. 각도 API(15.6)가 job_id를 보기 때문이다. 분석 API에는 그런 작업이 없어 지우기는
  404(이미 없음 = 성공)이고, --reset은 이 번호들을 분석 API에 묻지 않는다.
- 계정은 모두 CLIENT다(조영운 11-10). ADMIN·STAFF는 크림오프 계정이라 웹이 관리 페이지로만 보낸다.
- --reset은 이 기관의 자료만 파기(15.9 INSTITUTION, 파기 기록 1행)한 뒤 다시 넣는다. 계정·기관은 남긴다.
  다른 기관은 건드리지 않는다. 같은 기관 코드가 다른 이름으로 있으면 아무것도 하지 않고 끝낸다.
- 비밀번호는 파일에 없다. 계정을 새로 만들 때만 묻는다(--password로도 줄 수 있다).
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import logging
import shutil
import sys
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClient, build_analysis_client
from app.core.config import get_settings
from app.core.dates import local_zone, today_local
from app.core.db import SessionLocal
from app.core.errors import AppError
from app.core.security import PasswordRuleError, hash_password
from app.models import (
    Dog,
    DogHistory,
    DogNote,
    DogVital,
    Institution,
    MeasureSession,
    Shot,
    Staff,
)
from app.models.enums import (
    DogStage,
    FocusLimb,
    HistoryKind,
    HistorySite,
    NoteCategory,
    PurgeScope,
    SessionStatus,
    Sex,
    ShotStatus,
    StaffRole,
    VideoStatus,
)
from app.services.aggregation import AggregationError, aggregate_session
from app.services.analysis_copies import Cleared, read_shot_copies
from app.services.analysis_results import ResultFormatError, apply_result, parse_result
from app.services.purge import purge
from app.services.shot_angles import build_angles, dump_angles
from app.services.size_class import classify_size
from app.services.symmetry import session_scores
from app.services.uploads import check_video
from app.storage import keys
from app.storage.base import StorageService, get_storage
from app.video.render import VideoRenderError, render_video

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1
# 넣은 촬영의 job_id를 만드는 이름 공간. 같은 촬영 ID면 같은 번호라 --reset이 이 번호를 알아본다
JOB_NAMESPACE = uuid.UUID("6f1c2d4e-3b5a-4c7d-9e8f-0a1b2c3d4e5f")
CONFIRM_WORD = "RESET"
# 영상이 없는 촬영의 영상 정보 자리 값(칸이 NOT NULL). 화면에는 결과 영상 없음으로 보인다
PLACEHOLDER_VIDEO = {
    "width": 1920,
    "height": 1080,
    "fps": Decimal("30.00"),
    "duration_sec": Decimal("5.00"),
    "bitrate_kbps": 8000,
    "codec": "h264",
}


class SeedDemoError(Exception):
    """사람이 고칠 수 있는 입력·상태 문제. 아무것도 넣지 않고 끝낸다."""


# ---------------------------------------------------------------- 읽기


def parse_day(value: Any, today: date, *, where: str) -> date:
    """ "D-n" → today − n일. D-0은 오늘이다."""
    if not isinstance(value, str) or not value.startswith("D-") or not value[2:].isdigit():
        raise SeedDemoError(f"{where}: 날짜는 'D-n' 형식이어야 합니다({value!r})")
    return today - timedelta(days=int(value[2:]))


def _require(item: dict[str, Any], name: str, where: str) -> Any:
    if name not in item:
        raise SeedDemoError(f"{where}: '{name}'이 없습니다")
    return item[name]


def _enum(value: Any, enum_cls: type, where: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    allowed = {member.value for member in enum_cls}
    if value not in allowed:
        raise SeedDemoError(f"{where}: {value!r}는 {', '.join(sorted(allowed))} 중 하나여야 합니다")
    return value


@dataclass
class DemoData:
    root: Path
    raw: dict[str, Any]
    videos_dir: Path | None

    @property
    def institution(self) -> dict[str, Any]:
        return self.raw["institution"]

    def path(self, relative: str) -> Path:
        return self.root / relative


def load_data(root: Path, videos_dir: Path | None = None) -> DemoData:
    """demo.json을 읽고 서로 가리키는 이름과 파일이 다 있는지 먼저 본다. 넣기 전에 끝내야 반쯤 넣는 일이 없다."""
    manifest = root / "demo.json"
    if not manifest.is_file():
        raise SeedDemoError(f"demo.json이 없습니다: {manifest}")
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SeedDemoError(f"demo.json을 읽지 못했습니다: {error}") from None
    if raw.get("format_version") != FORMAT_VERSION:
        raise SeedDemoError(f"demo.json format_version은 {FORMAT_VERSION}이어야 합니다")
    for name in ("institution", "staff", "dogs", "histories", "vitals", "notes", "sessions"):
        _require(raw, name, "demo.json")
    institution = raw["institution"]
    for name in ("code", "name"):
        if not isinstance(institution.get(name), str) or not institution[name].strip():
            raise SeedDemoError(f"institution.{name}이 비어 있습니다")

    staff_ids = {item["login_id"] for item in raw["staff"]}
    dog_keys = {item["key"] for item in raw["dogs"]}
    session_keys = {item["key"] for item in raw["sessions"]}
    if len(staff_ids) != len(raw["staff"]) or len(dog_keys) != len(raw["dogs"]):
        raise SeedDemoError("담당자 login_id나 반려견 key가 겹칩니다")
    if len(session_keys) != len(raw["sessions"]):
        raise SeedDemoError("회차 key가 겹칩니다")

    def refer(value: Any, known: set[str], what: str, where: str, *, optional: bool = False) -> None:
        if value is None and optional:
            return
        if value not in known:
            raise SeedDemoError(f"{where}: 없는 {what}({value!r})를 가리킵니다")

    for i, item in enumerate(raw["histories"]):
        refer(item.get("dog"), dog_keys, "반려견", f"histories[{i}]")
        refer(item.get("staff"), staff_ids, "담당자", f"histories[{i}]")
    for i, item in enumerate(raw["vitals"]):
        refer(item.get("dog"), dog_keys, "반려견", f"vitals[{i}]")
        refer(item.get("staff"), staff_ids, "담당자", f"vitals[{i}]")
        refer(item.get("session"), session_keys, "회차", f"vitals[{i}]", optional=True)
    for i, item in enumerate(raw["notes"]):
        refer(item.get("dog"), dog_keys, "반려견", f"notes[{i}]")
        refer(item.get("staff"), staff_ids, "담당자", f"notes[{i}]")
        refer(item.get("session"), session_keys, "회차", f"notes[{i}]", optional=True)

    data = DemoData(root=root, raw=raw, videos_dir=videos_dir)
    for item in raw["sessions"]:
        where = f"sessions[{item['key']}]"
        refer(item.get("dog"), dog_keys, "반려견", where)
        refer(item.get("staff"), staff_ids, "담당자", where)
        if item.get("status") not in (SessionStatus.DONE.value, SessionStatus.MEASURING.value):
            raise SeedDemoError(f"{where}: status는 DONE 또는 MEASURING이어야 합니다")
        for shot in item.get("shots", []):
            for name in ("analysis", "keypoints"):
                if shot.get(name) and not data.path(shot[name]).is_file():
                    raise SeedDemoError(f"{where} 촬영 {shot.get('seq_no')}: 파일이 없습니다({shot[name]})")
            if shot.get("analysis") and not shot.get("keypoints"):
                raise SeedDemoError(f"{where} 촬영 {shot.get('seq_no')}: 관절점 파일이 없습니다")
    return data


def video_path(data: DemoData, shot: dict[str, Any]) -> Path | None:
    """촬영의 원본 영상. 영상이 없는 촬영이면 None. --videos가 있으면 그 폴더에서 파일 이름으로 찾는다."""
    name = shot.get("video_file")
    if not name:
        return None
    if data.videos_dir is not None:
        return data.videos_dir / name
    folder = shot.get("video_dir") or (data.raw.get("videos") or {}).get("dir")
    base = data.root.parent / folder if folder else data.root
    return base / name


# ---------------------------------------------------------------- 시각


def _at(day: date, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute, second), tzinfo=local_zone())


def demo_job_id(shot_id: uuid.UUID) -> str:
    return str(uuid.uuid5(JOB_NAMESPACE, str(shot_id)))


def put_copy(storage: StorageService, src: Path, key: str) -> None:
    """저장소의 put_file은 원본 파일을 옮긴다(업로드 임시 파일용).

    받은 영상과 두 회차가 함께 쓰는 결과 영상이 사라지지 않게 사본을 넣는다.
    """
    with tempfile.TemporaryDirectory(prefix="seed_demo_put_") as tmp:
        copy = Path(tmp) / src.name
        shutil.copyfile(src, copy)
        storage.put_file(copy, key)


# ---------------------------------------------------------------- 결과 영상


@dataclass
class RenderCache:
    """같은 영상·같은 관절점이면 결과 영상도 같다(제니 1회차와 2회차). 한 번만 만들어 다시 쓴다."""

    workdir: Path
    ffmpeg_path: str
    render: Callable[..., Any] = render_video
    made: dict[str, Path] = field(default_factory=dict)

    def get(self, video: Path, keypoints: Path) -> Path:
        digest = hashlib.sha256(video.name.encode("utf-8") + keypoints.read_bytes()).hexdigest()[:16]
        if digest not in self.made:
            output = self.workdir / f"{digest}.mp4"
            self.render(video, keypoints, output, ffmpeg_path=self.ffmpeg_path)
            self.made[digest] = output
        return self.made[digest]


# ---------------------------------------------------------------- 넣기


@dataclass
class SeedReport:
    institution_id: uuid.UUID
    created_accounts: list[str] = field(default_factory=list)
    kept_accounts: list[str] = field(default_factory=list)
    purged_rows: int = 0
    dogs: int = 0
    sessions: int = 0
    shots: int = 0
    rendered: int = 0
    skipped_shots: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    scores: list[tuple[str, int | None, int | None]] = field(default_factory=list)  # (회차키, 기대, 서버)


def find_institution(db: Session, data: DemoData) -> Institution | None:
    institution = db.scalars(select(Institution).where(Institution.code == data.institution["code"])).one_or_none()
    if institution is not None and institution.name != data.institution["name"]:
        raise SeedDemoError(
            f"기관 코드 {institution.code}가 이미 다른 이름({institution.name})으로 있습니다. "
            "시연 기관이 아니면 지우지 않습니다. demo.json의 institution.code를 바꾸세요"
        )
    return institution


def has_demo_rows(db: Session, institution_id: uuid.UUID) -> bool:
    return db.scalar(select(Dog.id).where(Dog.institution_id == institution_id).limit(1)) is not None


def reset_institution(
    db: Session, storage: StorageService, institution: Institution, analysis: AnalysisClient | None
) -> int:
    """이 기관의 반려견과 그 아래 전부를 파기한다(15.9 INSTITUTION, 계정·기관은 남김). commit은 부르는 쪽이 한다.

    넣은 촬영의 job_id는 분석 API에 없는 번호라 파기 전에 비우고, 그 촬영들은 이미 끝낸 것으로 넘겨(cleared) 촬영
    단위로도 묻지 않는다(분석 API에 보낸 적이 없다). 그래서 파기는 시연 중에 실제로 올린 촬영의 사본만 지우고, 파기
    기록의 analysis_jobs_deleted도 그 수만 센다. 파기가 실패하면 함께 되돌아간다.
    """
    pairs = db.execute(
        select(Shot.id, Shot.job_id)
        .join(MeasureSession, Shot.session_id == MeasureSession.id)
        .join(Dog, MeasureSession.dog_id == Dog.id)
        .where(Dog.institution_id == institution.id, Shot.job_id.is_not(None))
    ).all()
    seeded = [shot_id for shot_id, job_id in pairs if job_id == demo_job_id(shot_id)]
    cleared: Cleared = {}
    if seeded:
        db.execute(update(Shot).where(Shot.id.in_(seeded)).values(job_id=None))
        cleared = {shot: frozenset() for shot in read_shot_copies(db, Shot.id.in_(seeded))}
    try:
        out = purge(
            db,
            storage,
            PurgeScope.INSTITUTION.value,
            institution_id=institution.id,
            dry_run=False,
            analysis=analysis,
            cleared=cleared,
        )
    except AppError as error:
        db.rollback()
        raise SeedDemoError(
            f"시연 기관 자료를 지우지 못했습니다({error.code}). "
            "분석 중인 촬영이 끝났는지, 분석 서버에 연결되는지 확인한 뒤 다시 하세요"
        ) from None
    return out.rows


def ensure_accounts(
    db: Session, data: DemoData, institution: Institution, password: str | None, report: SeedReport
) -> dict[str, uuid.UUID]:
    """담당자 계정. 없으면 만들고(CLIENT), 시연 기관에 이미 있으면 그대로 쓴다. 다른 기관의 같은 아이디면 끝낸다."""
    ids: dict[str, uuid.UUID] = {}
    for item in data.raw["staff"]:
        login_id, name = item["login_id"], item["name"]
        if item.get("role", StaffRole.CLIENT.value) != StaffRole.CLIENT.value:
            note = f"{login_id}: demo.json 역할 {item.get('role')} 대신 CLIENT로 넣습니다(ADMIN·STAFF는 크림오프 계정)"
            if note not in report.notes:
                report.notes.append(note)
        existing = db.scalars(select(Staff).where(Staff.login_id == login_id)).one_or_none()
        if existing is not None:
            if existing.institution_id != institution.id:
                raise SeedDemoError(f"아이디 {login_id}가 다른 기관에 이미 있습니다. demo.json의 login_id를 바꾸세요")
            if existing.role != StaffRole.CLIENT.value:
                report.notes.append(f"{login_id}: 있던 계정의 역할 {existing.role}를 CLIENT로 바꿨습니다")
                existing.role = StaffRole.CLIENT.value
            ids[login_id] = existing.id
            report.kept_accounts.append(login_id)
            continue
        if password is None:
            raise SeedDemoError("새 계정을 만들려면 비밀번호가 필요합니다")
        try:
            password_hash = hash_password(password)
        except PasswordRuleError as error:
            raise SeedDemoError(str(error)) from None
        staff = Staff(
            institution_id=institution.id,
            login_id=login_id,
            password_hash=password_hash,
            name=name,
            role=StaffRole.CLIENT.value,
        )
        db.add(staff)
        db.flush()
        ids[login_id] = staff.id
        report.created_accounts.append(login_id)
    return ids


def missing_accounts(db: Session, data: DemoData) -> list[str]:
    wanted = [item["login_id"] for item in data.raw["staff"]]
    have = set(db.scalars(select(Staff.login_id).where(Staff.login_id.in_(wanted))))
    return [login_id for login_id in wanted if login_id not in have]


def _earliest(days: list[date], default: date) -> date:
    return min(days) if days else default


def seed(
    db: Session,
    storage: StorageService,
    data: DemoData,
    *,
    today: date,
    password: str | None,
    reset: bool = False,
    analysis: AnalysisClient | None = None,
    render_cache: RenderCache | None = None,
    progress: Callable[[str], None] = lambda _message: None,
) -> SeedReport:
    """시연 기관에 데이터를 넣는다. flush까지만 하고 commit은 부르는 쪽이 한다(--reset의 파기는 따로 commit한다).

    render_cache가 없으면 결과 영상을 만들지 않는다. 넣다가 실패하면 되돌리고, 이 기관 접두어 아래에 방금 쓴 파일을
    지운다(이때 DB에는 이 기관의 반려견이 없으므로 그 아래 파일은 모두 이번에 쓴 것이다).
    """
    inst = data.institution
    institution = find_institution(db, data)
    report = SeedReport(institution_id=institution.id if institution else uuid.uuid4())
    if institution is not None and has_demo_rows(db, institution.id):
        if not reset:
            raise SeedDemoError(f"기관 {inst['code']}에 이미 시연 자료가 있습니다. 다시 넣으려면 --reset을 붙이세요")
        report.purged_rows = reset_institution(db, storage, institution, analysis)
        db.commit()
        progress(f"시연 기관 자료를 지웠습니다(행 {report.purged_rows}개)")
    try:
        _insert(
            db,
            storage,
            data,
            institution,
            report,
            today=today,
            password=password,
            render_cache=render_cache,
            progress=progress,
        )
    except BaseException:
        db.rollback()
        storage.delete_prefix(keys.institution_prefix(report.institution_id))
        raise
    return report


def _insert(
    db: Session,
    storage: StorageService,
    data: DemoData,
    institution: Institution | None,
    report: SeedReport,
    *,
    today: date,
    password: str | None,
    render_cache: RenderCache | None,
    progress: Callable[[str], None],
) -> None:
    settings = get_settings()
    small_max, medium_max = Decimal(str(settings.SIZE_SMALL_MAX_KG)), Decimal(str(settings.SIZE_MEDIUM_MAX_KG))
    inst = data.institution
    if institution is None:
        institution = Institution(id=report.institution_id, code=inst["code"], name=inst["name"], contract_ends_at=None)
        db.add(institution)
        db.flush()
    staff_ids = ensure_accounts(db, data, institution, password, report)

    raw = data.raw
    day_of = {
        item["key"]: parse_day(item["measured_on"], today, where=f"sessions[{item['key']}]") for item in raw["sessions"]
    }

    # 반려견: 등록 시각은 그 반려견의 가장 이른 기록 날로 둔다(목록의 최근 등록 순서가 자연스럽게)
    dog_ids: dict[str, uuid.UUID] = {}
    for item in raw["dogs"]:
        where = f"dogs[{item['key']}]"
        weight = Decimal(str(_require(item, "weight_kg", where)))
        size = classify_size(weight, small_max_kg=small_max, medium_max_kg=medium_max)
        if item.get("size_class") and item["size_class"] != size:
            report.notes.append(
                f"{item['name']}: 체급은 체중으로 다시 정해 {size}로 넣습니다(demo.json {item['size_class']})"
            )
        days = [day_of[s["key"]] for s in raw["sessions"] if s["dog"] == item["key"]]
        days += [parse_day(h["occurred_on"], today, where=where) for h in raw["histories"] if h["dog"] == item["key"]]
        days += [parse_day(v["measured_on"], today, where=where) for v in raw["vitals"] if v["dog"] == item["key"]]
        registered = _at(_earliest(days, today), 9)
        dog = Dog(
            institution_id=institution.id,
            name=_require(item, "name", where),
            breed=item.get("breed") or "",
            weight_kg=weight,
            size_class=size,
            size_class_manual=False,
            birth_year=item.get("birth_year"),
            sex=_enum(item.get("sex"), Sex, where, optional=True),
            focus_limb=_enum(item.get("focus_limb"), FocusLimb, where, optional=True),
            stage=_enum(item.get("stage") or DogStage.REHAB.value, DogStage, where),
            created_at=registered,
            updated_at=registered,
        )
        db.add(dog)
        db.flush()
        dog_ids[item["key"]] = dog.id
        report.dogs += 1

    for i, item in enumerate(raw["histories"]):
        where = f"histories[{i}]"
        occurred = parse_day(item["occurred_on"], today, where=where)
        db.add(
            DogHistory(
                dog_id=dog_ids[item["dog"]],
                occurred_on=occurred,
                kind=_enum(item.get("kind"), HistoryKind, where),
                title=_require(item, "title", where),
                site=_enum(item.get("site"), HistorySite, where, optional=True),
                clinician=item.get("clinician"),
                staff_id=staff_ids[item["staff"]],
                created_at=_at(occurred, 18),
            )
        )

    session_ids: dict[str, uuid.UUID] = {}
    to_aggregate: list[tuple[str, uuid.UUID, datetime]] = []
    total = sum(len(s.get("shots", [])) for s in raw["sessions"])
    for order, item in enumerate(raw["sessions"]):
        key, day = item["key"], day_of[item["key"]]
        dog_id = dog_ids[item["dog"]]
        dog_item = next(d for d in raw["dogs"] if d["key"] == item["dog"])
        weight = Decimal(str(item.get("weight_kg") or dog_item["weight_kg"]))
        start = _at(day, 10, order % 50)
        measure = MeasureSession(
            dog_id=dog_id,
            staff_id=staff_ids[item["staff"]],
            measured_on=day,
            weight_kg=weight,
            size_class=classify_size(weight, small_max_kg=small_max, medium_max_kg=medium_max),
            status=SessionStatus.MEASURING.value,
            created_at=start,
            updated_at=start,
        )
        db.add(measure)
        db.flush()
        session_ids[key] = measure.id
        report.sessions += 1
        last = start
        for shot_item in item.get("shots", []):
            seq = shot_item["seq_no"]
            label = f"{key} 촬영 {seq:02d}"
            if not shot_item.get("analysis"):
                report.skipped_shots.append(
                    f"{label}: 분석 결과가 없어 넣지 않았습니다(상태 {shot_item.get('status')})"
                )
                continue
            last = start + timedelta(minutes=seq)
            _seed_shot(
                db,
                storage,
                data,
                institution.id,
                dog_id,
                measure.id,
                shot_item,
                uploaded=last,
                render_cache=render_cache,
                report=report,
            )
            report.shots += 1
            progress(f"촬영 {report.shots}/{total} {label}")
        if item["status"] == SessionStatus.DONE.value:
            completed = last + timedelta(minutes=2)
            db.execute(
                update(MeasureSession)
                .where(MeasureSession.id == measure.id)
                .values(status=SessionStatus.AGGREGATING.value, completed_at=completed)
            )
            to_aggregate.append((key, measure.id, completed + timedelta(minutes=1)))
    db.flush()

    for i, item in enumerate(raw["vitals"]):
        where = f"vitals[{i}]"
        day = parse_day(item["measured_on"], today, where=where)
        moment = _at(day, 9, 30)
        db.add(
            DogVital(
                dog_id=dog_ids[item["dog"]],
                measured_on=day,
                weight_kg=None if item.get("weight_kg") is None else Decimal(str(item["weight_kg"])),
                temp_c=None if item.get("temp_c") is None else Decimal(str(item["temp_c"])),
                heart_rate=item.get("heart_rate"),
                sbp=item.get("sbp"),
                dbp=item.get("dbp"),
                staff_id=staff_ids[item["staff"]],
                session_id=session_ids.get(item["session"]) if item.get("session") else None,
                created_at=moment,
                updated_at=moment,
            )
        )

    now = datetime.now(local_zone())
    for i, item in enumerate(raw["notes"]):
        where = f"notes[{i}]"
        body = str(_require(item, "body", where)).strip()
        if not 1 <= len(body) <= 2000:
            raise SeedDemoError(f"{where}: 내용은 1~2,000자여야 합니다")
        session_key = item.get("session")
        written = _at(day_of[session_key], 18) if session_key else now - timedelta(minutes=len(raw["notes"]) - i)
        db.add(
            DogNote(
                dog_id=dog_ids[item["dog"]],
                session_id=session_ids[session_key] if session_key else None,
                category=_enum(item.get("category"), NoteCategory, where),
                body=body,
                important=bool(item.get("important")),
                staff_id=staff_ids[item["staff"]],
                created_at=written,
                updated_at=written,
            )
        )
    db.flush()

    # 끝난 회차: 워커와 같은 집계(수치 행·DONE·보고서 PENDING). PDF는 워커가 만든다
    for key, measure_id, aggregated in to_aggregate:
        try:
            if not aggregate_session(db, storage, measure_id, now=aggregated):
                raise SeedDemoError(f"{key}: 회차 집계를 하지 못했습니다")
        except AggregationError as error:
            raise SeedDemoError(f"{key}: 회차 집계 실패({error})") from None
    db.flush()

    scores = session_scores(db, [measure_id for _key, measure_id, _at_time in to_aggregate])
    expected = {item["key"]: item.get("expected_symmetry") for item in raw["sessions"]}
    for key, measure_id, _at_time in to_aggregate:
        report.scores.append((key, expected[key], scores.get(measure_id)))
    partial = [
        item["key"] for item in raw["sessions"] if item.get("report_editions") not in (None, [], ["OWNER", "VET"])
    ]
    if partial:
        report.notes.append(
            "보고서는 회차마다 두 판본을 모두 만듭니다(서버 규칙). 한 판본만 적은 회차: " + ", ".join(partial)
        )


def _seed_shot(
    db: Session,
    storage: StorageService,
    data: DemoData,
    institution_id: uuid.UUID,
    dog_id: uuid.UUID,
    session_id: uuid.UUID,
    item: dict[str, Any],
    *,
    uploaded: datetime,
    render_cache: RenderCache | None,
    report: SeedReport,
) -> None:
    """촬영 하나: 원본(있으면) → analysis.json → 결과 반영(apply_result) → 관절 각도 파일 → 결과 영상(있으면)."""
    shot_id = uuid.uuid4()
    job_id = demo_job_id(shot_id)
    label = f"촬영 {item['seq_no']:02d}"
    analysis_bytes = data.path(item["analysis"]).read_bytes()
    keypoints_path = data.path(item["keypoints"])
    try:
        result = json.loads(analysis_bytes)
        parsed = parse_result(result, shot_id=shot_id)
    except (ValueError, ResultFormatError) as error:
        raise SeedDemoError(f"{item['analysis']}: 분석 결과를 읽지 못했습니다({error})") from None
    wanted = item.get("validity")
    if wanted and wanted != parsed.validity:
        report.notes.append(f"{item['analysis']}: 판정이 demo.json({wanted})과 다르게 읽혔습니다({parsed.validity})")

    video = video_path(data, item)
    info: dict[str, Any] = dict(PLACEHOLDER_VIDEO)
    below_min = False
    ext = "mp4"
    if video is not None:
        if not video.is_file():
            raise SeedDemoError(f"{label}: 영상이 없습니다({video}). --videos로 영상 폴더를 알려 주세요")
        try:
            probed, ext, warnings = check_video(video, video.name)
        except AppError as error:
            raise SeedDemoError(f"{video.name}: 업로드 검사에 걸립니다({error.code})") from None
        info = {
            "width": probed.width,
            "height": probed.height,
            "fps": probed.fps,
            "duration_sec": probed.duration_sec,
            "bitrate_kbps": probed.bitrate_kbps,
            "codec": probed.codec,
        }
        below_min = "BELOW_MIN_SPEC" in warnings
    original = keys.original_key(institution_id, dog_id, session_id, shot_id, ext)
    if video is not None:
        put_copy(storage, video, original)

    db.add(
        Shot(
            id=shot_id,
            session_id=session_id,
            seq_no=item["seq_no"],
            status=ShotStatus.ANALYZING.value,
            attempt_count=1,
            job_id=job_id,
            video_status=VideoStatus.PENDING.value,
            original_key=original,
            below_min_spec=below_min,
            uploaded_at=uploaded,
            submitted_at=uploaded + timedelta(seconds=5),
            created_at=uploaded,
            updated_at=uploaded,
            **info,
        )
    )
    db.flush()
    analysis = keys.analysis_key(institution_id, dog_id, session_id, shot_id)
    storage.write_bytes(analysis, analysis_bytes)
    if not apply_result(db, shot_id, parsed, analysis_key=analysis, analyzed_at=uploaded + timedelta(seconds=40)):
        raise SeedDemoError(f"{label}: 결과를 넣지 못했습니다")

    try:
        keypoints = json.loads(keypoints_path.read_text(encoding="utf-8"))
        storage.write_bytes(
            keys.angles_key(institution_id, dog_id, session_id, shot_id),
            dump_angles(build_angles(result, keypoints, shot_id=shot_id, job_id=job_id)),
        )
    except (ValueError, KeyError, TypeError) as error:
        report.notes.append(f"{item['keypoints']}: 관절 각도 파일을 만들지 못했습니다({error})")

    video_values: dict[str, Any] = {"video_status": VideoStatus.FAILED.value}
    if video is not None and render_cache is not None:
        try:
            output = render_cache.get(video, keypoints_path)
        except VideoRenderError as error:
            report.notes.append(f"{video.name}: 결과 영상을 만들지 못했습니다({error})")
        else:
            result_key = keys.result_key(institution_id, dog_id, session_id, shot_id)
            put_copy(storage, output, result_key)
            video_values = {
                "video_status": VideoStatus.READY.value,
                "result_key": result_key,
                "video_ready_at": uploaded + timedelta(seconds=90),
            }
            report.rendered += 1
    db.execute(update(Shot).where(Shot.id == shot_id).values(**video_values))


# ---------------------------------------------------------------- 실행


def _ask_password() -> str:
    first = getpass.getpass("시연 계정 비밀번호: ")
    second = getpass.getpass("비밀번호 다시: ")
    if first != second:
        raise SeedDemoError("두 비밀번호가 다릅니다")
    return first


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m scripts.seed_demo", description="시연 기관 데이터 넣기")
    parser.add_argument("--data", required=True, type=Path, help="demo.json이 있는 폴더(demo_seed)")
    parser.add_argument("--videos", type=Path, help="원본 영상 폴더. 빼면 demo.json의 video_dir(폴더의 부모 기준)")
    parser.add_argument(
        "--reset", action="store_true", help="이 시연 기관의 자료를 지우고 다시 넣는다(계정·기관은 남김)"
    )
    parser.add_argument("--yes", action="store_true", help="--reset 확인 문구를 묻지 않는다")
    parser.add_argument("--no-render", action="store_true", help="결과 영상을 만들지 않는다(빠름, 결과 영상 없음)")
    parser.add_argument("--password", help="새 계정 비밀번호. 빼면 화면에서 묻는다(계정이 다 있으면 묻지 않음)")
    parser.add_argument("--today", type=date.fromisoformat, help="D-0으로 쓸 날짜(YYYY-MM-DD). 빼면 오늘")
    return parser


def _print_report(report: SeedReport) -> None:
    print(f"기관 {report.institution_id}")
    if report.purged_rows:
        print(f"- 지운 행 {report.purged_rows}개(파기 기록 1행)")
    created = ", ".join(report.created_accounts) or "없음"
    kept = ", ".join(report.kept_accounts) or "없음"
    print(f"- 계정: 새로 {created} / 있던 것 {kept}")
    print(f"- 반려견 {report.dogs}, 회차 {report.sessions}, 촬영 {report.shots}, 결과 영상 {report.rendered}")
    print("- 대칭 점수(회차키: demo.json 기대값 → 서버 계산)")
    for key, expected, actual in report.scores:
        mark = "" if expected == actual else "  ← 다름"
        print(f"  {key}: {expected} → {actual}{mark}")
    for line in report.skipped_shots + report.notes:
        print(f"- {line}")
    print("보고서 PDF는 워커가 만듭니다(회차마다 두 판본). 워커가 돌고 있는지 확인하세요.")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    settings = get_settings()
    today = args.today or today_local()
    try:
        data = load_data(args.data, args.videos)
        with SessionLocal() as db:
            institution = find_institution(db, data)
            if institution is not None and has_demo_rows(db, institution.id) and args.reset and not args.yes:
                question = f"기관 {institution.code}({institution.name})의 시연 자료를 모두 지우고 다시 넣습니다."
                answer = input(f"{question} 계속하려면 {CONFIRM_WORD}: ")
                if answer.strip() != CONFIRM_WORD:
                    print("그만둡니다")
                    return 1
            password = args.password
            if password is None and missing_accounts(db, data):
                password = _ask_password()
            storage = get_storage()
            analysis = build_analysis_client(settings) if args.reset else None
            with tempfile.TemporaryDirectory(prefix="seed_demo_") as tmp:
                cache = None if args.no_render else RenderCache(Path(tmp), settings.FFMPEG_PATH)
                report = seed(
                    db,
                    storage,
                    data,
                    today=today,
                    password=password,
                    reset=args.reset,
                    analysis=analysis,
                    render_cache=cache,
                    progress=lambda message: print(message, flush=True),
                )
                db.commit()
    except SeedDemoError as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1
    _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
