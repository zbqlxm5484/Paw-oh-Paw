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
from app.report.judge import WITHIN_RANGE, usable_tolerance
from app.report.numbers import NO_VALUE, CompareLine, GaitTable, gait_label

EDITION_LABELS = {"OWNER": "보호자용", "VET": "수의사용"}
SIZE_LABELS = {"SMALL": "소형", "MEDIUM": "중형", "LARGE": "대형"}
SEX_LABELS = {"M": "수컷", "F": "암컷", "MALE": "수컷", "FEMALE": "암컷"}


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
    previous_gaps: list[str] = field(default_factory=list)  # 보행 유형이 달라 비교하지 않은 묶음
    disclaimer: str = f"이 보고서는 {DISCLAIMER}이며 진단을 대신하지 않습니다."

    def texts(self) -> dict[str, str]:
        """검사에 넘길 문장 묶음(이름 → 문장들). HTML 표의 이름·사유는 generate가 더한다."""
        blocks = {
            "title": self.title,
            "intro": self.intro,
            "summary": " ".join(self.summary),
            "gaits": " ".join(" ".join(notes) for notes in self.gait_notes.values()),
            "previous": " ".join(filter(None, [self.previous_note, *self.previous_gaps])),
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
    allowed = usable_tolerance(tolerance.get(top.code), top.min_passes)
    if allowed is None or top.diff_value is None:
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


def _previous_note(inp: ReportInput, tables: list[GaitTable]) -> str | None:
    """직전 회차 비교 표의 안내(5절 비교 규칙). 평가 단어 없이 방향만 말한다. 비교 표가 하나도 없으면 None이다."""
    if not inp.previous or not any(table.changes for table in tables):
        return None
    measured_on = inp.previous.get("measured_on")
    if inp.previous_model_changed:
        return f"직전 회차({measured_on})는 분석 방식이 달라 값만 표에 함께 적고, 변화는 판단하지 않았습니다."
    head = (
        f"직전 회차({measured_on})와 이번 회차의 값을 표에 나란히 적었습니다. "
        "차이는 이번 값에서 직전 값을 뺀 것입니다."
    )
    caution = "값의 차이는 측정 조건에 따라서도 생길 수 있습니다."
    if not inp.tolerance:
        return f"{head} {caution}"
    counts = ""
    if inp.edition == "VET":  # 보호자용에는 개수를 적지 않는다(박규원 MR 86 리뷰)
        cells = [cell for table in tables for row in table.changes for cell in row.cells.values() if cell.change]
        outside = sum(1 for cell in cells if cell.change != WITHIN_RANGE)
        counts = f"(범위 밖 {outside}개, 범위 안 {len(cells) - outside}개)"
    return (
        f"{head} 오차 범위보다 크게 달라진 값은 증가·감소로 적었습니다{counts}. "
        '"범위 안"은 달라진 크기가 오차 범위 안이라는 뜻이고, 정상 범위라는 뜻은 아닙니다. '
        f"판단할 기준이 없거나 걸음 수가 적으면 값과 차이만 적었습니다. {caution}"
    )


def _previous_gaps(inp: ReportInput, tables: list[GaitTable]) -> list[str]:
    """보행 유형이 달라 비교하지 않은 묶음(5절: 같은 유형끼리만). 이번 회차에 수치 표가 없으면 적지 않는다."""
    if not inp.previous or not tables:
        return []
    measured_on = inp.previous.get("measured_on")
    before = [str(gait.get("gait_type")) for gait in inp.previous.get("gaits") or []]
    now = {table.gait_type for table in tables}
    gaps = [
        f"{table.label} 수치는 직전 회차({measured_on})에 같은 보행 유형이 없어 비교하지 않았습니다."
        for table in tables
        if table.gait_type not in before
    ]
    gaps.extend(
        f"직전 회차({measured_on})의 {gait_label(gait_type)} 수치는 "
        "이번 회차에 같은 보행 유형이 없어 비교하지 않았습니다."
        for gait_type in dict.fromkeys(before)
        if gait_type not in now
    )
    return gaps


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
        previous_note=_previous_note(inp, tables),
        caution=_caution(inp),
        previous_gaps=_previous_gaps(inp, tables),
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
        previous_gaps=draft.previous_gaps,
    )
