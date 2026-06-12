# compose_neis_note_module.py
from datetime import datetime
from typing import List, Optional

# 기본 filler 문장들 (필요시 추가/수정)
DEFAULT_FILLERS = [
    "교육 활동의 목적과 과정을 충실히 수행하였으며 학생의 자기주도적 학습 태도가 돋보였음.",
    "과제 해결 과정에서 책임감 있게 참여하였고 협력적 태도를 지속적으로 보였음.",
    "수업 중 적극적으로 질문하고 토론에 참여하여 사고력과 표현력이 향상됨.",
    "프로젝트 결과를 성실히 제출하였으며 피드백을 수용하는 태도가 우수함."
]

def _format_date_obj(date_obj_or_str) -> str:
    # date_obj_or_str이 datetime이면 포맷, 문자열이면 YYYY-MM-DD 또는 유사 포맷 처리 시도
    if isinstance(date_obj_or_str, datetime):
        return date_obj_or_str.strftime("%Y.%m.%d.")
    if isinstance(date_obj_or_str, str):
        s = date_obj_or_str.strip()
        # 간단한 형태들 처리: 2020-05-01, 2020.05.01, 20200501 등
        try:
            if "-" in s:
                dt = datetime.fromisoformat(s)
                return dt.strftime("%Y.%m.%d.")
            if "." in s:
                parts = [p for p in s.split(".") if p]
                if len(parts) >= 3:
                    y,m,d = parts[:3]
                    return f"{int(y):04d}.{int(m):02d}.{int(d):02d}."
            if len(s) == 8 and s.isdigit():
                dt = datetime.strptime(s, "%Y%m%d")
                return dt.strftime("%Y.%m.%d.")
        except Exception:
            pass
    # 포맷 불가 시 빈 문자열 반환
    return ""

def compose_neis_note(
    event_name: str,
    date_obj,  # datetime or str
    ranked_sentences: List[str],
    bridge: str = "을 통해",
    min_bytes: int = 150,
    remove_spaces: bool = False,
    fillers: Optional[List[str]] = None,
) -> str:
    """
    NEIS 용 활동기록 문자열 생성.
    출력 포맷 예시: EventName(2020.05.01.)을 통해[학생은 ... .]
    - min_bytes: UTF-8 바이트 기준 최소 길이
    - remove_spaces: True면 공백 제거(최적화용)
    """
    if fillers is None:
        fillers = DEFAULT_FILLERS

    date_str = _format_date_obj(date_obj) or ""
    header = f"{event_name}({date_str}){bridge}["
    closing = "]."

    # 랭크된 문장들을 연결 (기본적으로 전체 문장 연결하되 필요시 자름)
    body_parts = []
    for s in ranked_sentences:
        s = s.strip()
        if not s:
            continue
        # 문장 마침표 보장
        if not s.endswith((".","다","함","음","임","니다")):
            s = s + "."
        body_parts.append(s)

    # 초기 본문
    body = " ".join(body_parts).strip()
    # 빈 본문이면 최소한 한 filler 추가
    if not body:
        body = fillers[0]

    candidate = header + body + closing

    # 공백 제거 옵션이 설정되면 적용
    if remove_spaces:
        candidate = "".join(candidate.split())

    # UTF-8 바이트 길이 계산
    cur_bytes = len(candidate.encode("utf-8"))
    fill_index = 0
    # filler를 순환하면서 min_bytes 만족할 때까지 추가
    while cur_bytes < min_bytes:
        extra = fillers[fill_index % len(fillers)]
        # 문장 구분을 위해 공백/구두점 처리
        if not candidate.endswith((" ", "[")):
            candidate = candidate[:-2] + " " + extra + closing if candidate.endswith("].") else candidate + " " + extra + closing
        else:
            candidate = candidate + extra + closing
        if remove_spaces:
            candidate = "".join(candidate.split())
        cur_bytes = len(candidate.encode("utf-8"))
        fill_index += 1
        # 안전장치: 지나치게 많은 반복은 중단
        if fill_index > 10:
            break

    return candidate
