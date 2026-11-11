"""무효·제외·측정 불가 사유의 문장 (F-03, PR-F03-04). S15P31A404-185

결과 JSON에서 화면은 사유 코드로, 보고서·로그는 문장으로 쓴다(결과 형식 2절). 문장은 두 가지다.

- REASON_TEXT: 코드마다 하나인 기본 문장. 백엔드 명세(backend/docs/backend-spec.md) 14.3과 글자까지 같다.
  팀 서비스는 코드로 자기 문구 파일(messages/ko.yaml)을 쓰므로, 이 문장은 기업 서버처럼 팀 서비스 없이 결과를 받는 쪽과
  로그를 위한 것이다
- reason_detail·validity_reason_text: 그 통과·촬영에서 **실제로 잰 값과 기준값**을 넣은 문장. 다시 찍을 때 무엇을
  고칠지 알 수 있게 한다. 기준값은 engine/validity.yaml에서 읽는다
- 수치의 reason_detail(metric_reason_detail): 측정 불가 수치에 붙는 문장. 통과 안에서 무엇을 몇 번 보았는지 적는다.
  S15P31A404-259

보고서 금지 표현(backend/app/report/terms.yaml)을 쓰지 않는다: 진단·원인·정상 여부 단정 없이 잰 값과 기준만 적는다.
"""
from typing import Optional

REASON_TEXT = {
    # 촬영
    "MAT_NOT_FOUND": "측정 구간(매트)을 찾지 못했습니다. 매트가 화면에 다 보이게 다시 찍어 주세요.",
    "NO_VALID_PASS": "쓸 수 있는 통과가 없습니다. 다시 찍어 주세요.",
    "FEW_VALID_PASSES": "쓸 수 있는 통과가 일부만 있습니다.",
    # 통과
    "RUNNING": "뛰었습니다. 천천히 걷게 해 주세요.",
    "STOPPED": "중간에 멈췄습니다.",
    "SITTING": "중간에 앉거나 엎드렸습니다.",
    "TURNED": "중간에 돌아섰습니다.",
    "TOWARD_CAMERA": "카메라 쪽으로 걸었습니다. 옆으로 일직선으로 걷게 해 주세요.",
    "PARTIAL_PASS": "측정 구간을 일부만 지났습니다.",
    "NORMALIZATION_LIMIT": "카메라와의 각도나 거리가 커서 보정할 수 없습니다.",
    "NOT_SIDE_VIEW": "옆모습이 찍히지 않았습니다.",
    "OCCLUDED": "몸이 가려졌습니다.",
    "OVERLAP": "다른 동물이나 사람과 겹쳤습니다.",
    "NO_DOG": "반려견이 화면에 없습니다.",
    "GAIT_PACE": "측대보라 수치 계산에서 뺐습니다.",
    "GAIT_OTHER": "평보·속보가 아니라 수치 계산에서 뺐습니다.",
    # 수치
    "NOT_ENOUGH_CYCLES": "보행 주기가 부족해 계산하지 못했습니다.",
    "LOW_CONFIDENCE": "관절점 인식이 불안정해 계산하지 못했습니다.",
}

# 기업 판별 기준 문서 2절의 무효 사유 (engine/validity.py SHOT_INVALID_REASONS와 같음)
COMPANY_INVALID = {"GAIT_PACE", "RUNNING", "TURNED", "STOPPED", "SITTING", "PARTIAL_PASS", "OVERLAP"}


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def pass_reason_detail(code: Optional[str], checks: dict, cfg: dict) -> Optional[str]:
    """통과 하나를 뺀 이유를 잰 값과 기준값으로 쓴 문장. 잰 값이 없으면 기본 문장"""
    if not code:
        return None
    r = cfg["pass_rules"]
    c = checks or {}
    base = REASON_TEXT.get(code, code)

    def has(*keys):
        return all(c.get(k) is not None for k in keys)

    if code == "RUNNING" and has("speed_body_per_s"):
        return (f"몸통이 1초에 몸통 길이의 {c['speed_body_per_s']:.1f}배를 움직여 뛰기 기준({r['running_speed']:g}배)보다 "
                f"빨랐습니다. 천천히 걷게 해 주세요.")
    if code == "STOPPED" and has("stopped_s"):
        return f"{c['stopped_s']:.1f}초 동안 멈췄습니다(기준 {r['stopped_min_s']:g}초). 멈추지 않고 지나가게 해 주세요."
    if code == "SITTING" and has("sitting_s"):
        return (f"골반 높이가 이 통과의 평소 높이의 {_pct(r['sitting_height_ratio'])} 아래로 {c['sitting_s']:.1f}초 낮아졌습니다"
                f"(기준 {r['sitting_min_s']:g}초). 앉거나 엎드리지 않고 지나가게 해 주세요.")
    if code == "TURNED" and has("opposite_ratio", "reverse_s"):
        if c["opposite_ratio"] > r["turned_frame_ratio"]:
            why = f"반대 방향을 본 프레임이 {_pct(c['opposite_ratio'])}였습니다(기준 {_pct(r['turned_frame_ratio'])})"
        else:
            why = f"몸통이 {c['reverse_s']:.1f}초 동안 뒤로 움직였습니다(기준 {r['turned_reverse_s']:g}초)"
        return f"{why}. 한 방향으로 끝까지 걷게 해 주세요."
    if code == "TOWARD_CAMERA" and has("height_scale"):
        return (f"통과 처음과 끝의 몸 크기가 {c['height_scale']:.2f}배 달라졌습니다(기준 {r['toward_camera_scale']:g}배). "
                f"카메라와 나란히, 옆으로 일직선으로 걷게 해 주세요.")
    if code == "PARTIAL_PASS":
        if c.get("ends_before_exit"):
            return "화면을 끝까지 지나가기 전에 영상이 끝났습니다. 매트를 다 지나갈 때까지 찍어 주세요."
        if has("inside_s"):
            return (f"몸 전체가 화면 안에 보인 시간이 {c['inside_s']:.1f}초로 기준({r['min_inside_s']:g}초)보다 "
                    f"짧았습니다. 화면을 가로질러 지나가게 해 주세요.")
    if code == "NOT_SIDE_VIEW" and has("side_view_ratio"):
        return (f"옆모습으로 찍힌 프레임이 {_pct(c['side_view_ratio'])}로 기준({_pct(r['side_view_min_ratio'])})보다 "
                f"적었습니다. 카메라가 반려견의 옆면을 보게 해 주세요.")
    if code == "OCCLUDED" and has("occluded_ratio"):
        return (f"카메라 쪽 다리가 가려진 프레임이 {_pct(c['occluded_ratio'])}였습니다"
                f"(기준 {_pct(r['occluded_frame_ratio'])}). 다리를 가리는 사람이나 물건이 없게 해 주세요.")
    if code == "NO_DOG" and has("no_dog_ratio"):
        return (f"통과 중 반려견을 찾지 못한 프레임이 {_pct(c['no_dog_ratio'])}였습니다"
                f"(기준 {_pct(r['no_dog_frame_ratio'])}).")
    return base


def shot_reason_detail(code: Optional[str], passes: list, cfg: dict, found_ratio: float) -> Optional[str]:
    """촬영 판정 사유(validity_reason)의 문장. 기업 무효 사유면 어느 통과 때문인지 적는다"""
    if not code:
        return None
    if code == "NO_DOG":
        return (f"영상 전체에서 반려견을 찾은 프레임이 {_pct(found_ratio)}뿐입니다"
                f"(기준 {_pct(cfg['shot_rules']['no_dog_frame_ratio'])}). 반려견이 화면에 들어오게 다시 찍어 주세요.")
    if code in COMPANY_INVALID:
        hit = next((p for p in passes if p.get("reason_code") == code), None)
        if hit:
            detail = hit.get("reason_detail") or REASON_TEXT.get(code, code)
            return f"{hit['index']}번 통과: {detail} 이 사유가 있는 통과가 있으면 촬영 전체를 쓰지 않습니다."
    if code == "NO_VALID_PASS":
        return f"통과 {len(passes)}번 중 쓸 수 있는 통과가 없습니다. 다시 찍어 주세요."
    if code == "FEW_VALID_PASSES":
        used = sum(1 for p in passes if p.get("valid"))
        return (f"쓸 수 있는 통과가 {used}번으로 기준({cfg['shot_rules']['min_valid_passes']}번)보다 적습니다. "
                f"더 찍으면 결과가 안정됩니다.")
    return REASON_TEXT.get(code, code)


METRIC_NAMES = {
    "stride_length": "걸음 길이", "stance_ratio": "입각기 비율", "paw_lift": "발 높이", "walk_speed": "보행 속도",
    "stifle_cycle_rom": "무릎 주기별 가동 범위",
}
JOINT_KO = {"shoulder": "어깨", "elbow": "팔꿈치", "carpus": "앞발목", "hip": "고관절", "stifle": "무릎", "tarsus": "뒷발목"}
PAW_KO = {"front": "앞발", "hind": "뒷발"}


def metric_reason_detail(facts: dict) -> str:
    """측정 불가 수치 하나의 문장. facts는 engine/gait_metrics.py·engine/joint_rom.py가 그 통과에서 센 값이다

    kind: no_body_length(몸통 길이를 못 잼), paw_hidden(발끝이 안 보임), few_touchdowns(착지를 두 번 이어서 못 봄),
    no_swing(들림을 앞뒤 디딤과 함께 못 봄), no_trunk(몸통 속도를 못 잼), joint_hidden(관절 세 점이 안 보임)
    """
    kind = facts["kind"]
    paw = PAW_KO.get(facts.get("paw"), "")
    if kind == "no_body_length":
        return ("등과 골반 관절점을 함께 믿을 만한 프레임이 없어 몸통 길이를 재지 못했습니다. "
                "거리·속도 수치는 몸통 길이로 나누어 냅니다.")
    if kind == "paw_hidden":
        return (f"{paw}끝 관절점을 믿을 만한 프레임이 {_pct(facts['ratio'])}로 기준({_pct(facts['min'])})보다 "
                f"적었습니다. 카메라 쪽 {paw}이 가려지지 않게 찍어 주세요.")
    if kind == "few_touchdowns":
        what = "무릎 주기별 가동 범위는" if facts.get("metric") == "stifle_cycle_rom" else "보행 주기는"
        return (f"몸 전체가 보인 {facts['seen_s']:.1f}초 동안 {paw} 착지를 {facts['touchdowns']}번 보았습니다. "
                f"{what} 착지에서 다음 착지까지로 재므로 착지를 두 번 이어서 봐야 합니다. "
                f"화면을 지나는 시간이 길어지게 카메라를 조금 뒤로 두면 잴 수 있습니다.")
    if kind == "no_swing":
        return (f"몸 전체가 보인 {facts['seen_s']:.1f}초 동안 {paw}이 들렸다가 다시 디딘 것을 보지 못했습니다"
                f"(디딤 {facts['stances']}번). 발 높이는 앞뒤 디딤 사이의 들림에서 잽니다.")
    if kind == "no_trunk":
        return "등과 골반 관절점이 이어서 보이지 않아 몸통이 움직인 속도를 재지 못했습니다."
    if kind == "joint_hidden":
        joint = JOINT_KO.get(facts["joint"], facts["joint"])
        return (f"{joint} 각도를 잴 세 관절점을 모두 믿을 만한 프레임이 {_pct(facts['ratio'])}로 "
                f"기준({_pct(facts['min'])})보다 적었습니다.")
    return REASON_TEXT.get(facts.get("reason", ""), "")
