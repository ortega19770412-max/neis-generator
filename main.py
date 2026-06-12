import os
import re
import random
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from openai import OpenAI

load_dotenv()

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MIN_BYTES = 200
MAX_BYTES = 700

FIXED_PREFIX_KEYWORD = "학교폭력예방교육"

def normalize_date(date_str: str) -> str:
    s = (date_str or "").strip()
    if not s:
        return ""
    s = s.replace("-", ".").replace("/", ".")
    parts = [p for p in s.split(".") if p]
    if len(parts) >= 3:
        y, m, d = parts[0], parts[1], parts[2]
        return f"{int(y):04d}.{int(m):02d}.{int(d):02d}."
    return s

def clean_text(text: str) -> str:
    return (text or "").strip()

def ends_with_noun_ending(text: str) -> bool:
    text = text.strip()
    return text.endswith(("함.", "임.", "됨."))

def ensure_noun_ending(text: str) -> str:
    text = clean_text(text)
    if not text:
        return text

    # 이미 종결형 어미로 끝나면 추가하지 않음
    if ends_with_noun_ending(text):
        return text

    # 어색한 중복 표현 제거
    replacements = {
        "었음됨.": "됨.",
        "였음됨.": "됨.",
        "음됨.": "됨.",
        "함됨.": "함.",
        "임됨.": "임.",
        "됨됨.": "됨.",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # 일반 서술형 종결을 명사형으로 변환
    if text.endswith("했다."):
        text = text[:-3] + "함."
    elif text.endswith("하였다."):
        text = text[:-4] + "함."
    elif text.endswith("했다"):
        text = text[:-2] + "함."
    elif text.endswith("하였다"):
        text = text[:-4] + "함."
    elif text.endswith("였다."):
        text = text[:-3] + "임."
    elif text.endswith("이다."):
        text = text[:-3] + "임."
    elif text.endswith("입니다."):
        text = text[:-4] + "임."
    elif text.endswith("습니다."):
        text = text[:-3] + "함."
    elif text.endswith("다."):
        text = text[:-2] + "함."
    elif text.endswith("다"):
        text = text[:-1] + "함."
    elif text.endswith("요."):
        text = text[:-2] + "함."

    # 최종 점검: 여전히 명사형 종결이 아니면 한 번만 붙임
    if not ends_with_noun_ending(text):
        if text.endswith("."):
            text = text[:-1]
        text += "됨."

    return text

def pad_to_min_bytes(text: str, min_bytes: int = MIN_BYTES) -> str:
    tails = [
        " 또한 신체적 폭력뿐 아니라 정신적·재산적 피해와 정보통신망을 이용한 피해도 학교폭력에 포함된다는 점을 이해하는 계기가 됨.",
        " 아울러 사례를 살펴보며 피해의 다양성을 인식하고, 서로를 존중하는 태도의 중요성을 되새기는 시간이 됨.",
        " 더불어 공감과 배려의 필요성을 생각해 보며 안전한 관계 형성의 중요성을 배우는 의미 있는 경험이 됨.",
        " 이를 통해 학교폭력의 범위를 폭넓게 이해하고, 바람직한 생활 태도를 익히는 계기가 됨.",
        " 나아가 폭력 예방의 중요성을 인식하고 공동체 의식을 기르는 시간이 됨."
    ]

    while len(text.encode("utf-8")) < min_bytes:
        text = text.rstrip(".") + random.choice(tails)

    return text

class ActivityRequest(BaseModel):
    activity_type: str
    activity_date: str
    activity_name: str
    activity_content: str

@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>NEIS 기록 생성기</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      max-width: 900px;
      margin: 40px auto;
      padding: 20px;
      background: #f7f9fc;
    }
    .card {
      background: white;
      padding: 24px;
      border-radius: 12px;
      box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    }
    label {
      display: block;
      margin-top: 14px;
      font-weight: bold;
    }
    input, select, textarea, button {
      width: 100%;
      box-sizing: border-box;
      margin-top: 6px;
      padding: 10px;
      border: 1px solid #ccc;
      border-radius: 8px;
      font-size: 15px;
    }
    textarea {
      min-height: 100px;
      resize: vertical;
    }
    button {
      margin-top: 18px;
      background: #2563eb;
      color: white;
      border: none;
      cursor: pointer;
      font-weight: bold;
    }
    button:hover {
      background: #1d4ed8;
    }
    .btn-secondary {
      background: #16a34a;
      margin-top: 10px;
    }
    .btn-secondary:hover {
      background: #15803d;
    }
    .hint {
      font-size: 13px;
      color: #555;
      margin-top: 4px;
    }
    .result {
      margin-top: 20px;
      padding: 16px;
      background: #eef6ff;
      border-radius: 8px;
      white-space: pre-wrap;
      word-break: break-word;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>NEIS 기록 생성기</h1>

    <label>활동 유형</label>
    <select id="activity_type">
      <option value="진로활동">진로활동</option>
      <option value="자율활동">자율활동</option>
    </select>

    <label>날짜</label>
    <input type="date" id="activity_date" />

    <label>활동명</label>
    <input type="text" id="activity_name" placeholder="예: 학교폭력예방교육" value="학교폭력예방교육" />

    <label>활동내용</label>
    <textarea id="activity_content" placeholder="예: 역할극, 사례분석, 토의"></textarea>
    <div class="hint">출력은 항상 "학교폭력예방교육(YYYY.MM.DD.)을 통해"로 시작합니다.</div>

    <button onclick="generateRecord()">기록 생성</button>
    <button class="btn-secondary" onclick="copyRecord()">결과 복사</button>

    <div id="result" class="result" style="display:none;"></div>
  </div>

  <script>
    function getResultText() {
      const result = document.getElementById("result");
      return result.textContent || "";
    }

    async function generateRecord() {
      const activity_type = document.getElementById("activity_type").value;
      const activity_date = document.getElementById("activity_date").value;
      const activity_name = document.getElementById("activity_name").value;
      const activity_content = document.getElementById("activity_content").value;

      const response = await fetch("/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          activity_type,
          activity_date,
          activity_name,
          activity_content
        })
      });

      const data = await response.json();
      const result = document.getElementById("result");
      result.style.display = "block";
      result.textContent = data.record || data.detail || "결과 없음";
    }

    async function copyRecord() {
      const text = getResultText();
      if (!text) {
        alert("복사할 결과가 없습니다.");
        return;
      }
      try {
        await navigator.clipboard.writeText(text);
        alert("결과가 복사되었습니다.");
      } catch (e) {
        alert("복사에 실패했습니다.");
      }
    }
  </script>
</body>
</html>
"""

@app.post("/generate")
def generate_record(req: ActivityRequest):
    activity_type = clean_text(req.activity_type)
    activity_date = normalize_date(req.activity_date)
    activity_name = clean_text(req.activity_name)
    activity_content = clean_text(req.activity_content)

    if not activity_type:
        return JSONResponse({"detail": "활동 유형이 비어 있습니다."}, status_code=400)
    if not activity_date:
        return JSONResponse({"detail": "날짜가 비어 있습니다."}, status_code=400)
    if not activity_name:
        return JSONResponse({"detail": "활동명이 비어 있습니다."}, status_code=400)
    if not activity_content:
        return JSONResponse({"detail": "활동내용이 비어 있습니다."}, status_code=400)

    prompt = f"""
너는 NEIS 학생생활기록부 문장을 작성하는 도우미다.

반드시 아래 조건을 지켜라.
- 출력은 1문장만 작성
- 문장은 반드시 "{FIXED_PREFIX_KEYWORD}({activity_date})을 통해"로 시작할 것
- 고정 템플릿처럼 보이지 않도록 뒤 문장은 매번 다양하게 작성할 것
- 활동내용이 키워드형이면 자연스럽게 풀어쓸 것
- 활동내용을 그대로 나열하지 말 것
- 학교폭력은 신체적 폭력뿐 아니라 정신적 피해, 재산적 피해, 정보통신망을 이용한 피해도 포함된다는 점을 드러낼 것
- 맞춤법과 어법을 정확히 지킬 것
- 문장 연결은 자연스러워야 함
- 명사형 종결어미로 끝낼 것
- 단, 이미 명사형 종결어미로 끝난 문장에는 종결어미를 중복해서 붙이지 말 것
- 어색한 종결(예: 됨됨, 었음됨) 금지
- 200바이트 이상 700바이트 이하
- 결과만 출력

활동 유형:
{activity_type}

활동명:
{activity_name}

날짜:
{activity_date}

활동내용:
{activity_content}

출력 예시:
{FIXED_PREFIX_KEYWORD}({activity_date})을 통해 사례를 살펴보고 토의와 역할극에 참여하며, 신체적 폭력뿐 아니라 정신적·재산적 피해와 정보통신망을 이용한 피해도 학교폭력에 해당함을 이해하는 시간이 됨.
"""

    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            input=prompt,
            temperature=0.95,
        )

        text = response.output_text.strip()
        text = ensure_noun_ending(text)
        text = pad_to_min_bytes(text, MIN_BYTES)

        if len(text.encode("utf-8")) > MAX_BYTES:
            raw = text.encode("utf-8")[:MAX_BYTES]
            text = raw.decode("utf-8", errors="ignore").rstrip(" ,;.")
            text = ensure_noun_ending(text)

        return {"record": text}

    except Exception as e:
        return JSONResponse({"detail": f"생성 중 오류 발생: {str(e)}"}, status_code=500)
