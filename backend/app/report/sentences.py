"""문장(8절 만드는 순서 3). 김지윤의 문장 템플릿(MR 80 리뷰)을 글자 그대로 쓴다.

규칙: 수치와 좌우 차이만 말하고 진단·치료·정상 여부를 단정하지 않는다(terms.yaml forbidden). 보호자용은 쉬운 말로 쓰고,
쓰인 전문 용어는 용어 설명 칸에 자동으로 넣어 checks의 전문 용어 검사를 통과한다. 수의사용은 대칭 지수까지 적는다.
문장을 바꿀 때는 checks(금지 표현)와 tests/test_report_module.py를 함께 돌린다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.report.checks import DISCLAIMER, TermRules, contains_term, load_rules, normalize
from app.report.inputs import ReportInput
from app.report.numbers import NO_VALUE, CompareLine, GaitTable

EDITION_LABELS = {"OWNER": "보호자용", "VET": "수의사용"}
SIZE_LABELS = {"SMALL": "소형", "MEDIUM": "중형", "LARGE": "대형"}
SEX_LABELS = {"M": "수컷", "F": "암컷", "MALE": "수컷", "FEMALE": "암컷"}
# 오차 범위는 한쪽 8회 기준이다. 4회면 흔들림이 약 1.4배라 범위와 견주지 않는다(박규원 MR 80 답변)
TOLERANCE_MIN_PASSES = 5


@dataclass(frozen=True)
class Sentences:
    title: str
    edition_label: str
    intro: str
    summary: list[str]
    gait_notes: dict[str, list[str]]
    previous_note: str | None
    caution: list[str]
    glossary: list[tuple[str, str]] = field(default_factory=list)
    disclaimer: str = f"이 보고서는 {DISCLAIMER}이며 진단을 대신하지 않습니다."

    def texts(self) -> dict[str, str]:
        """검사에 넘길 문장 묶음(이름 → 문장들). HTML 표의 이름·사유는 generate가 더한다."""
        blocks = {
            "title": self.title,
            "intro": self.intro,
            "summary": " ".join(self.summary),
            "gaits": " ".join(" ".join(notes) for notes in self.gait_notes.values()),
            "previous": self.previous_note or "",
            "caution": " ".join(self.caution),
            "glossary": " ".join(f"{term}: {explanation}" for term, explanation in self.glossary),
            "footer": self.disclaimer,
        }
        return {name: text for name, text in blocks.items() if text}


def _intro(inp: ReportInput) -> str:
    counts = inp.result.get("pass_counts") or {}
    shots = inp.result.get("shot_counts") or {}
    parts = [f"{inp.session.measured_on}에 {inp.dog.name}의 걷는 모습을 촬영해 수치를 냈습니다."]
    profile: list[str] = []
    weight = inp.session.weight_kg if inp.session.weight_kg is not None else inp.dog.weight_kg
    if weight is not None:
        profile.append(f"체중 {weight:g} kg")
    size = inp.session.size_class or inp.dog.size_class
    if size:
        profile.append(f"{SIZE_LABELS.get(size, size)}견")
    if inp.dog.breed:
        profile.append(inp.dog.breed)
    if profile:
        parts.append(", ".join(profile) + ".")
    parts.append(
        f"촬영 {shots.get('total', 0)}건에서 걸음 {counts.get('measured', 0)}회를 보았고, "
        f"그중 {counts.get('used', 0)}회로 수치를 냈습니다(제외 {counts.get('excluded', 0)}회)."
    )
    return " ".join(parts)


def _difference_note(top: CompareLine, tolerance: dict[str, float]) -> str:
    """보호자용 요약의 둘째 문장. 좌우 차이도 회차 비교의 오차 범위 표(15.8)와 견주고, 비교는 Decimal로 한다(15.1)."""
    allowed = tolerance.get(top.code)
    enough_passes = top.min_passes is not None and top.min_passes >= TOLERANCE_MIN_PASSES
    if allowed is None or top.diff_value is None or not enough_passes:
        return (
            "좌우 차이는 촬영 조건에 따라서도 달라질 수 있어, 이 수치만으로 변화를 판단하지 않습니다. "
            "다음 측정과 같은 조건에서 비교해 보세요."
        )
    if abs(Decimal(str(top.diff_value))) <= Decimal(str(allowed)):
        return "이 차이는 측정 오차 범위 안에 있습니다."
    return (
        "이 차이는 측정 오차 범위보다 큽니다. "
        "다음 측정에서도 같은 다리에 차이가 이어지는지 담당 수의사와 함께 봐 주세요."
    )


def _summary(inp: ReportInput, tables: list[GaitTable]) -> list[str]:
    lines: list[str] = []
    for notice in inp.result.get("notices") or []:
        message = notice.get("message") if isinstance(notice, dict) else None
        if message:
            lines.append(str(message))
    found = next(((table, line) for table in tables for line in table.compare if line.comparable), None)
    if found is None:
        if not lines:
            lines.append("왼쪽과 오른쪽을 비교할 수 있는 수치가 없어 차이를 적지 않았습니다.")
        return lines
    table, top = found
    name = f"{top.pair_label} {top.label}"
    values = f"왼쪽 {top.left}, 오른쪽 {top.right}, 차이 {top.diff}입니다."
    if top.symmetry_index == NO_VALUE:  # 왼쪽·오른쪽이 모두 0이면 비율이 없다(15.7)
        lines.append(f"{table.label}에서 좌우 차이를 비율로 낼 수 있는 항목은 없습니다. {name}: {values}")
        return lines
    # 비교 줄은 대칭 지수가 큰 순서다(15.7). 단위가 달라 값의 차이끼리는 견주지 않으므로 "비율"이라고 밝힌다
    sentence = f"{table.label}에서 왼쪽과 오른쪽의 차이를 비율로 볼 때 가장 큰 항목은 {name}입니다. {values}"
    if inp.edition == "VET":
        sentence += f" 대칭 지수 {top.symmetry_index}."
    lines.append(sentence)
    if inp.edition == "OWNER":
        lines.append(_difference_note(top, inp.tolerance))
    return lines


def _gait_notes(tables: list[GaitTable]) -> dict[str, list[str]]:
    notes: dict[str, list[str]] = {}
    for table in tables:
        items = [f"{table.label}: 수치 {table.measured + table.unmeasurable}개 중 {table.measured}개를 측정했습니다."]
        if table.unmeasurable:
            items.append(f"측정하지 못한 {table.unmeasurable}개는 표에 사유를 적었습니다.")
        skipped = [line for line in table.compare if not line.comparable and line.reason]
        if skipped:
            reasons = " ".join(dict.fromkeys(str(line.reason) for line in skipped))
            items.append(f"좌우 비교를 하지 못한 항목 {len(skipped)}개: {reasons}")
        notes[table.gait_type] = items
    if not tables:
        notes["NONE"] = [
            "수치를 낼 수 있는 걸음이 없었습니다. "
            "매트를 옆으로 곧게 지나가도록, 반대 방향으로도 걷게 해 다시 촬영해 주세요."
        ]
    return notes


def _previous_note(inp: ReportInput) -> str | None:
    if not inp.previous:
        return None
    measured_on = inp.previous.get("measured_on")
    if inp.previous.get("model_version") not in (None, inp.session.model_version):
        return f"직전 회차({measured_on})는 분석 방식이 달라 값만 표에 함께 적고, 변화는 판단하지 않았습니다."
    return (
        f"직전 회차({measured_on})의 값을 표의 괄호 안에 함께 적었습니다. "
        "값의 차이는 측정 조건에 따라서도 생길 수 있습니다."
    )


def _caution(inp: ReportInput) -> list[str]:
    common = (
        "수치는 촬영 조건(바닥, 걷는 속도, 카메라 각도)에 따라 달라질 수 있습니다. "
        "같은 조건에서 다시 잰 값과 비교해 주세요."
    )
    if inp.edition == "OWNER":
        return [common, "걱정되는 변화가 있으면 담당 수의사와 상의해 주세요."]
    return [common, "이 수치는 영상에서 추정한 값이며, 임상 판단의 보조 자료입니다."]


def _glossary(text: str, rules: TermRules) -> list[tuple[str, str]]:
    """쓰인 용어의 설명. 설명 문구가 또 다른 용어를 쓰면 그 설명도 넣는다(검사는 용어 설명 칸까지 본다)."""
    seen = normalize(text)
    used: set[str] = set()
    while found := [j for j in rules.jargon if j.term not in used and contains_term(seen, j.term)]:
        used.update(j.term for j in found)
        seen += " " + " ".join(j.explanation for j in found)
    return [(j.term, j.explanation) for j in rules.jargon if j.term in used]


def compose(inp: ReportInput, tables: list[GaitTable], rules: TermRules | None = None) -> Sentences:
    """입력과 표 → 문장. 보호자용이면 본문에 쓰인 전문 용어의 설명을 glossary에 넣는다."""
    rules = rules or load_rules()
    edition_label = EDITION_LABELS[inp.edition]
    draft = Sentences(
        title=f"{inp.dog.name} 보행 평가 보고서",
        edition_label=edition_label,
        intro=_intro(inp),
        summary=_summary(inp, tables),
        gait_notes=_gait_notes(tables),
        previous_note=_previous_note(inp),
        caution=_caution(inp),
    )
    if inp.edition != "OWNER":
        return draft
    body = " ".join(draft.texts().values()) + " " + " ".join(row.label for table in tables for row in table.rows)
    return Sentences(
        title=draft.title,
        edition_label=draft.edition_label,
        intro=draft.intro,
        summary=draft.summary,
        gait_notes=draft.gait_notes,
        previous_note=draft.previous_note,
        caution=draft.caution,
        glossary=_glossary(body, rules),
    )
