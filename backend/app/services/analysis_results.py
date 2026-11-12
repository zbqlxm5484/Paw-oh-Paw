"""분석 결과 저장(명세 6절 결과 저장 원칙, 12.4, 14.3, 17.3 BE-07·08·11).

분석 API가 done이라고 답하면 워커가 결과 JSON을 받아 (1) 파일로 그대로 보관하고(촬영 키의 analysis.json, 7절)
(2) 촬영 판정·사유·모델과 통과별 행(walk_pass)만 DB에 넣는다. 통과별 수치는 JSON에만 있고 회차 집계(작업 단위 8)가
거기서 읽는다.

여기는 (2)만 맡는다. JSON을 읽어 저장할 값으로 바꾸는 parse_result와, 조건을 건 UPDATE로 DONE을 만들고 통과 행을
넣는 apply_result다. 파일 쓰기·commit·실패했을 때 파일 지우기는 워커(app/worker/main.py)가 한다(12.4 "파일을 먼저
쓰고 키를 붙인다"). Spring에 빗대면 @Transactional 없이 flush까지만 하는 서비스이고, 트랜잭션 경계는 부르는 쪽이 쥔다.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from typing import Any

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.clients.analysis import DEFAULT_VALIDITY_REASON, map_camera_side, map_gait, map_reason, map_validity
from app.models import Shot, WalkPass
from app.models.enums import ShotStatus, Validity

logger = logging.getLogger(__name__)

# shot.model_name·model_version은 VARCHAR(50)이다(12.2)
MODEL_FIELD_MAX = 50
# walk_pass.pass_no는 SMALLINT, start_frame·end_frame은 INTEGER다(12.2). 넘는 값을 DB까지 보내면 저장 중 오류가 난다
PASS_NO_MAX = 32_767
FRAME_MAX = 2_147_483_647
# 결과를 받아들이는 상태. 12.4: SUBMITTED → DONE도 가능
SAVABLE = (ShotStatus.SUBMITTED.value, ShotStatus.ANALYZING.value)


class ResultFormatError(Exception):
    """결과 JSON이 6절 계약과 달라 읽을 수 없을 때.

    워커는 촬영을 FAILED(ANALYSIS_FAILED)로 두고 이 메시지를 로그에 남긴다.
    """


@dataclass(frozen=True)
class PassRow:
    """walk_pass 한 행(12.2)."""

    pass_no: int
    camera_side: str
    gait_type: str
    is_valid: bool
    exclude_reason: str | None
    start_frame: int
    end_frame: int


@dataclass(frozen=True)
class ParsedResult:
    validity: str
    validity_reason: str | None
    model_name: str | None
    model_version: str | None
    passes: list[PassRow]


def _whole_number(value: Any) -> int | None:
    """JSON의 정수. numpy 값을 내보내면 40.0처럼 오므로 정수값인 실수도 받는다. bool과 나머지는 None."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _frame(value: Any, *, field: str, position: int) -> int:
    number = _whole_number(value)
    if number is None or not 0 <= number <= FRAME_MAX:
        raise ResultFormatError(f"passes[{position}].{field}={value!r}")
    return number


def _pass_no(value: Any, *, position: int, shot_id: uuid.UUID) -> int:
    """통과 순번. 분석 API의 index를 쓰고, 없거나 못 쓰는 값(0 이하, SMALLINT 초과)이면 받은 순서로 매긴다.

    그러면 DB의 pass_no가 JSON의 index와 달라지므로 경고로 남긴다(BE-11).
    """
    number = _whole_number(value)
    if number is not None and 1 <= number <= PASS_NO_MAX:
        return number
    logger.warning("passes[%d].index=%r unusable shot=%s; numbered by position", position, value, shot_id)
    return position


def _model_field(value: Any, *, field: str, shot_id: uuid.UUID) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) > MODEL_FIELD_MAX:
        logger.warning("model.%s longer than %d chars shot=%s; truncated", field, MODEL_FIELD_MAX, shot_id)
        text = text[:MODEL_FIELD_MAX]
    return text


def parse_result(result: Any, *, shot_id: uuid.UUID) -> ParsedResult:
    """결과 JSON → 저장할 값.

    분석 API의 소문자 값은 clients/analysis.py의 대응표로 바꾼다. 계약과 다르면(모르는 판정값, 통과의 카메라 쪽·유효
    여부·프레임이 없거나 DB 범위를 넘음) ResultFormatError이고, 모르는 사유 코드는 UNKNOWN_REASON으로 두고 원래 코드를
    로그에 남긴다(14.3). 여기서 걸러진 값만 DB로 가므로 저장 중에 형식 때문에 오류가 나지 않는다.
    """
    if not isinstance(result, dict):
        raise ResultFormatError(f"result={type(result).__name__}")
    validity = map_validity(result.get("validity"))
    if validity is None:
        raise ResultFormatError(f"validity={result.get('validity')!r}")
    raw_reason = result.get("validity_reason")
    if validity == Validity.VALID.value:
        validity_reason = None
    elif raw_reason is None:
        validity_reason = DEFAULT_VALIDITY_REASON.get(validity)  # PARTIAL은 None 그대로
    else:
        validity_reason = map_reason(raw_reason, shot_id=shot_id, where="validity_reason")

    raw_passes = result.get("passes")
    if not isinstance(raw_passes, list):
        raise ResultFormatError(f"passes={raw_passes!r}")
    passes: list[PassRow] = []
    for position, item in enumerate(raw_passes, start=1):
        if not isinstance(item, dict):
            raise ResultFormatError(f"passes[{position}]={item!r}")
        camera_side = map_camera_side(item.get("camera_side"))
        if camera_side is None:
            raise ResultFormatError(f"passes[{position}].camera_side={item.get('camera_side')!r}")
        is_valid = item.get("valid")
        if not isinstance(is_valid, bool):
            # 없거나 문자열이면 전부 제외(또는 전부 유효)로 조용히 저장되므로 형식 오류로 막는다
            raise ResultFormatError(f"passes[{position}].valid={is_valid!r}")
        passes.append(
            PassRow(
                pass_no=_pass_no(item.get("index"), position=position, shot_id=shot_id),
                camera_side=camera_side,
                gait_type=map_gait(item.get("gait")),
                is_valid=is_valid,
                exclude_reason=None
                if is_valid
                else map_reason(item.get("reason_code"), shot_id=shot_id, where=f"passes[{position}].reason_code"),
                start_frame=_frame(item.get("start_frame"), field="start_frame", position=position),
                end_frame=_frame(item.get("end_frame"), field="end_frame", position=position),
            )
        )
    if len({row.pass_no for row in passes}) != len(passes):
        # index가 겹치면(uq_pass_no 위반) 받은 순서대로 다시 매긴다. DB의 pass_no가 JSON의 index와 달라지므로 남긴다
        logger.warning("duplicate pass index shot=%s; all passes renumbered by position", shot_id)
        passes = [replace(row, pass_no=position) for position, row in enumerate(passes, start=1)]

    raw_model = result.get("model")
    model = raw_model if isinstance(raw_model, dict) else {}
    return ParsedResult(
        validity=validity,
        validity_reason=validity_reason,
        model_name=_model_field(model.get("name"), field="name", shot_id=shot_id),
        model_version=_model_field(model.get("version"), field="version", shot_id=shot_id),
        passes=passes,
    )


def apply_result(
    db: Session, shot_id: uuid.UUID, parsed: ParsedResult, *, analysis_key: str, analyzed_at: datetime
) -> bool:
    """조건을 건 UPDATE로 촬영을 DONE으로 바꾸고 통과 행을 넣는다(flush까지).

    SUBMITTED·ANALYZING이 아니면(그사이 지워졌거나 실패 처리됨) 아무것도 쓰지 않고 False다. 부르는 쪽이 True면
    commit하고, False면 방금 쓴 analysis.json을 지운다(12.4).
    """
    changed = db.execute(
        update(Shot)
        .where(Shot.id == shot_id, Shot.status.in_(SAVABLE))
        .values(
            status=ShotStatus.DONE.value,
            validity=parsed.validity,
            validity_reason=parsed.validity_reason,
            analysis_key=analysis_key,
            model_name=parsed.model_name,
            model_version=parsed.model_version,
            analyzed_at=analyzed_at,
            fail_reason=None,
        )
    ).rowcount
    if not changed:
        return False
    db.execute(delete(WalkPass).where(WalkPass.shot_id == shot_id))  # 남아 있던 통과 행이 있으면 새 결과로 바꾼다
    db.add_all(WalkPass(shot_id=shot_id, **asdict(row)) for row in parsed.passes)
    db.flush()
    return True
