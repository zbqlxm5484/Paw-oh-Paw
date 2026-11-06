"""파일 키(7절 형식, 11.11). 키는 이 함수들로만 만든다.

{기관ID}/{반려견ID}/{회차ID}/{촬영ID}/original.{mp4|mov} · result.mp4 · analysis.json · angles.json
{기관ID}/{반려견ID}/{회차ID}/reports/{보고서ID}.pdf
모든 ID는 UUID다. 반려견 이름이나 휴대폰의 원래 파일명은 키에 들어가지 않는다. 접두어는 /로 끝난다.
"""

import uuid

ORIGINAL_EXTENSIONS = ("mp4", "mov")


def institution_prefix(institution_id: uuid.UUID) -> str:
    return f"{institution_id}/"


def dog_prefix(institution_id: uuid.UUID, dog_id: uuid.UUID) -> str:
    return f"{institution_id}/{dog_id}/"


def session_prefix(institution_id: uuid.UUID, dog_id: uuid.UUID, session_id: uuid.UUID) -> str:
    return f"{institution_id}/{dog_id}/{session_id}/"


def shot_prefix(institution_id: uuid.UUID, dog_id: uuid.UUID, session_id: uuid.UUID, shot_id: uuid.UUID) -> str:
    return f"{institution_id}/{dog_id}/{session_id}/{shot_id}/"


def original_key(
    institution_id: uuid.UUID, dog_id: uuid.UUID, session_id: uuid.UUID, shot_id: uuid.UUID, ext: str
) -> str:
    """ext는 점 없는 소문자(mp4·mov)."""
    ext = ext.lower().lstrip(".")
    if ext not in ORIGINAL_EXTENSIONS:
        raise ValueError(f"원본 영상 확장자는 {ORIGINAL_EXTENSIONS} 중 하나여야 합니다: {ext!r}")
    return f"{shot_prefix(institution_id, dog_id, session_id, shot_id)}original.{ext}"


def result_key(institution_id: uuid.UUID, dog_id: uuid.UUID, session_id: uuid.UUID, shot_id: uuid.UUID) -> str:
    return f"{shot_prefix(institution_id, dog_id, session_id, shot_id)}result.mp4"


def analysis_key(institution_id: uuid.UUID, dog_id: uuid.UUID, session_id: uuid.UUID, shot_id: uuid.UUID) -> str:
    return f"{shot_prefix(institution_id, dog_id, session_id, shot_id)}analysis.json"


def angles_key(institution_id: uuid.UUID, dog_id: uuid.UUID, session_id: uuid.UUID, shot_id: uuid.UUID) -> str:
    """통과별 프레임 관절 각도(12.4 관절 각도 파일). DB에 키 칸이 없어 늘 이 함수로 만든다."""
    return f"{shot_prefix(institution_id, dog_id, session_id, shot_id)}angles.json"


def report_key(institution_id: uuid.UUID, dog_id: uuid.UUID, session_id: uuid.UUID, report_id: uuid.UUID) -> str:
    return f"{session_prefix(institution_id, dog_id, session_id)}reports/{report_id}.pdf"
