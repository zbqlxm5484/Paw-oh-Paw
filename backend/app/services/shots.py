"""촬영 응답 만들기(15.3). 업로드 검사·저장과 삭제·다시 분석은 작업 단위 5(70)·7에서 더한다."""

from __future__ import annotations

from app.models import Shot, WalkPass
from app.models.enums import ShotStatus
from app.schemas.common import reason_out
from app.schemas.shots import PassOut, ShotOut


def to_pass_out(walk_pass: WalkPass) -> PassOut:
    return PassOut(
        pass_no=walk_pass.pass_no,
        camera_side=walk_pass.camera_side,
        gait_type=walk_pass.gait_type,
        is_valid=walk_pass.is_valid,
        exclude_reason=reason_out(walk_pass.exclude_reason),
        start_frame=walk_pass.start_frame,
        end_frame=walk_pass.end_frame,
    )


def to_shot_out(shot: Shot) -> ShotOut:
    """passes는 DONE일 때만 채우고 pass_no 오름차순이다(15.3)."""
    passes = sorted(shot.passes, key=lambda p: p.pass_no) if shot.status == ShotStatus.DONE else []
    return ShotOut(
        id=shot.id,
        seq_no=shot.seq_no,
        status=shot.status,
        fail_reason=reason_out(shot.fail_reason),
        validity=shot.validity,
        validity_reason=reason_out(shot.validity_reason),
        video_status=shot.video_status,
        below_min_spec=shot.below_min_spec,
        passes=[to_pass_out(p) for p in passes],
        uploaded_at=shot.uploaded_at,
        analyzed_at=shot.analyzed_at,
    )
