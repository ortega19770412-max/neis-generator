import os
import random
from dotenv import load_dotenv

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from openai import OpenAI

load_dotenv()

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MIN_BYTES = 200
MAX_BYTES = 700

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

    if ends_with_noun_ending(text):
        return text

    # 어색한 중복 종결 처리
    bad_replacements = {
        "었음됨.": "됨.", "였음됨.": "됨.", "음됨.": "됨.",
        "함됨.": "함.", "임됨.": "임.", "됨됨.": "됨.", "함함.": "함."
    }
    for old, new in bad_replacements.items():
        text = text.replace(old, new)

    # 동사형 제거 및 명사형 변환
    endings = {
        "했다.": "함.", "하였다.": "함.", "했다": "함.", "하였다": "함.",
        "이었다.": "임.", "였다.": "임.", "이다.": "임.", "입니다.": "임.",
        "습니다.": "함.", "다.": "함.", "다": "함.", "요.": "함."
    }
    for old, new in endings.items():
        if text.endswith(old):
            text = text[:-len(old)] + new
            break

    if not ends_with_noun_ending(text):
        text = text.rstrip(".") + "됨."
    return text

def pad_to_min_bytes(text: str, activity_name: str, min_bytes: int = MIN_BYTES) -> str:
    # 활동 성격에 따른 꼬리 문구 분기
    if "폭력" in activity_name or "예방" in activity_name:
        tails = [
            " 신체적 폭력뿐만 아니라 정신적 피해, 재산적 피해 및 정보통신망을 이용한 폭력의 심각성을 깊이 이해함.",
            " 이를 통해 타인을 존중하는 마음을 기르고 안전한 학교 문화를 조성하는 데 기여할 것을 다짐함.",
            " 폭력의 다양한 양상을 파악하며 서로 배려하고 공감하는 공동체 의식의 중요성을 체득함."
        ]
    else:
        tails = [
            " 해당 활동을 통해 자신의 소질을 발견하고 주도적으로 탐색하며 공동체 역량을 강화함.",
            " 동료와 협력하며 문제를 해결하는 과정에서 성숙한 태도와 책임감을 기르는 계기가 됨.",
            " 주어진 과제를 성실히 수행하며 자신의 역량을 발휘하고 긍정적인 변화를 이끌어냄."
        ]

    while len(text.encode("utf-8")) < min_bytes:
        addon = random.choice(tails)
        if not text.endswith(" "): text += " "
        text = text.rstrip(".") + addon
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
    body { font-family: 'Malgun Gothic', sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; background: #f4f7f6; }
    .card { background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    h1 { color: #2c3e50; text-align: center; }
    label { display: block; margin-top: 15px; font-weight: bold; }
    input, select, textarea { width: 100%; margin-top: 8px; padding: 12px; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; font-size: 15px; }
    button { width: 100%; margin-top: 20px; padding: 15px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; }
    .btn-gen { background: #3498db; color: white; }
    .btn-copy { background: #2ecc71; color: white; margin-top: 10px; }
    .result { margin-top: 25px; padding: 20px; background: #fffbe6; border: 1px solid #ffe58f; border-radius: 8px; display: none; white-space: pre-wrap; line-height: 1.6; }
  </style>
</head>
<body>
  <div class="card">
    <h1>📝 NEIS 기록 생성기</h1>
    <label>활동 유형</label>
    <select id="activity_type">
      <option value="자율활동">자율활동</option>
      <option value="진로활동">진로활동</option>
      <option value="동아리활동">동아리활동</option>
    </select>
    <label>날짜</label><input type="date" id="activity_date" />
    <label>활동명</label><input type="text" id="activity_name" placeholder="예: 학급 자치 회의, 진로 캠프" />
    <label>활동 내용</label>
    <textarea id="activity_content" placeholder="핵심 키워드나 내용을 입력하세요."></textarea>
    <button class="btn-gen" onclick="generate()">기록 생성</button>
    <button class="btn-copy" onclick="copy()">복사하기</button>
    <div id="result" class="result"></div>
  </div>
  <script>
    async function generate() {
      const resDiv = document.getElementById('result');
      resDiv.style.display = 'block';
      resDiv.innerText = '생성 중...';
      const response = await fetch('/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          activity_type: document.getElementById('activity_type').value,
          activity_date: document.getElementById('activity_date').value,
          activity_name: document.getElementById('activity_name').value,
          activity_content: document.getElementById('activity_content').value
        })
      });
      const data = await response.json();
      resDiv.innerText = data.record || data.detail;
    }
    function copy() {
      const text = document.getElementById('result').innerText;
      if(!text || text === '생성 중...') return;
      navigator.clipboard.writeText(text).then(() => alert('복사되었습니다!'));
    }
  </script>
</body>
</html>
"""

@app.post("/generate")
async def generate_record(req: ActivityRequest):
    activity_type = clean_text(req.activity_type)
    activity_date = normalize_date(req.activity_date)
    activity_name = clean_text(req.activity_name)
    activity_content = clean_text(req.activity_content)

    if not all([activity_type, activity_date, activity_name, activity_content]):
        return JSONResponse({"detail": "모든 정보를 입력해주세요."}, status_code=400)

    prefix = f"{activity_name}({activity_date})을 통해"

    system_prompt = "너는 대한민국 고등학교 생기부 작성 전문가이다. 관찰 위주의 객관적이고 전문적인 문체로 작성하라."
    user_prompt = f"""
다음 정보를 바탕으로 생기부 {activity_type} 기록을 1문장으로 작성하라.
- 시작 문구: "{prefix}"
- 활동 내용: {activity_content}
- 조건 1: 활동 내용의 핵심 키워드를 반영하여 구체적인 변화나 성장이 드러나게 작성.
- 조건 2: 활동명이 '폭력'이나 '예방'을 포함하면 신체적, 정신적, 재산적, 정보통신망 이용 피해 예방 내용을 포함할 것.
- 어미: 반드시 '~함.', '~임.', '~됨.'과 같은 명사형 종결 어미로 마칠 것.
- 길이: 200~700바이트 사이로 상세하게 작성.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
        )

        text = response.choices[0].message.content.strip()
        
        # 시작 문구 검증 및 보정
        if not text.startswith(activity_name):
            text = f"{prefix} {text.replace(prefix, '').strip()}"

        text = ensure_noun_ending(text)
        
        # 최소 바이트 체크 및 패딩
        if len(text.encode("utf-8")) < MIN_BYTES:
            text = pad_to_min_bytes(text, activity_name, MIN_BYTES)

        # 최대 바이트 체크 및 절삭
        if len(text.encode("utf-8")) > MAX_BYTES:
            raw = text.encode("utf-8")[:MAX_BYTES-15]
            text = raw.decode("utf-8", errors="ignore").rstrip()
            text = ensure_noun_ending(text)

        return {"record": text}

    except Exception as e:
        return JSONResponse({"detail": f"생성 오류: {str(e)}"}, status_code=500)
