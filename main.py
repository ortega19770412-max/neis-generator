import os
import re
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from openai import OpenAI

load_dotenv()

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# NEIS 바이트 제한 설정 (약 750바이트 미만 권장)
MAX_BYTES = 740

def normalize_date(date_str: str) -> str:
    s = (date_str or "").strip()
    if not s: return ""
    s = s.replace("-", ".").replace("/", ".")
    parts = [p for p in s.split(".") if p]
    if len(parts) >= 3:
        return f"{int(parts[0]):04d}.{int(parts[1]):02d}.{int(parts[2]):02d}."
    return s

def clean_text(text: str) -> str:
    return (text or "").strip()

def ensure_noun_ending(text: str) -> str:
    """서술형을 생활기록부용 명사형으로 자연스럽게 변환"""
    text = clean_text(text)
    if not text: return text

    # 1. 어색한 결합(깨달음함, 성취함함 등) 방지를 위한 사전 치환
    text = text.replace("깨달음함.", "깨달음.").replace("느낌함.", "느낌.").replace("배움함.", "배움.")
    text = text.replace("함함.", "함.").replace("됨됨.", "됨.")

    # 2. 문장 끝 서술어 변환
    conversions = [
        (r"하였다\.?$", "함."), (r"했다\.?$", "함."), (r"하였다$", "함."),
        (r"이다\.?$", "임."), (r"였다\.?$", "임."), (r"입니다\.?$", "임."),
        (r"습니다\.?$", "함."), (r"한다\.?$", "함."), (r"다\.?$", "함.")
    ]
    for pattern, replacement in conversions:
        if re.search(pattern, text):
            text = re.sub(pattern, replacement, text)
            break
    
    # 3. 최종 확인: 명사형 어미가 아니면 '함.' 추가 (단, 이미 명사로 끝났다면 점만 찍기)
    if not text.endswith(("함.", "임.", "됨.", "음.", "기.")):
        text = text.rstrip(".") + "함."
    
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
  <meta charset="UTF-8" /><title>NEIS 기록 생성기</title>
  <style>
    body { font-family: 'Malgun Gothic', sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; background: #f8fafc; color: #1e293b; }
    .card { background: white; padding: 30px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); }
    h2 { color: #2563eb; margin-bottom: 25px; text-align: center; }
    label { display: block; margin-top: 15px; font-weight: 600; font-size: 14px; }
    input, select, textarea { width: 100%; margin-top: 8px; padding: 12px; border: 1px solid #e2e8f0; border-radius: 10px; font-size: 15px; box-sizing: border-box; }
    textarea { resize: vertical; min-height: 100px; }
    button { width: 100%; margin-top: 20px; padding: 14px; border: none; border-radius: 10px; font-size: 16px; font-weight: bold; cursor: pointer; transition: 0.2s; }
    .btn-generate { background: #2563eb; color: white; }
    .btn-generate:hover { background: #1d4ed8; }
    .btn-copy { background: #64748b; color: white; margin-top: 10px; display: none; }
    .btn-copy:hover { background: #475569; }
    .result-container { margin-top: 25px; position: relative; }
    .result { padding: 20px; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 10px; white-space: pre-wrap; line-height: 1.7; font-size: 15px; min-height: 50px; }
  </style>
</head>
<body>
  <div class="card">
    <h2>📝 NEIS 맞춤형 기록 생성기</h2>
    <label>활동 유형</label>
    <select id="activity_type"><option value="자율활동">자율활동</option><option value="진로활동">진로활동</option><option value="동아리">동아리활동</option></select>
    <label>활동 날짜</label><input type="date" id="activity_date" />
    <label>활동명</label><input type="text" id="activity_name" placeholder="활동명을 입력하세요 (예: 환경보호 캠페인)" />
    <label>내용 키워드</label>
    <textarea id="activity_content" placeholder="학생의 구체적인 활동이나 특징을 입력하세요."></textarea>
    
    <button class="btn-generate" onclick="generate()">기록 생성하기</button>
    
    <div class="result-container">
      <div id="result" class="result">생성된 내용이여기에 표시됩니다.</div>
      <button id="copyBtn" class="btn-copy" onclick="copyToClipboard()">📋 결과 복사하기</button>
    </div>
  </div>

  <script>
    async function generate() {
      const btn = document.querySelector('.btn-generate');
      const resultDiv = document.getElementById("result");
      const copyBtn = document.getElementById("copyBtn");
      
      btn.innerText = "GPT가 문장을 정제 중입니다...";
      btn.disabled = true;

      try {
        const res = await fetch("/generate", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            activity_type: document.getElementById("activity_type").value,
            activity_date: document.getElementById("activity_date").value,
            activity_name: document.getElementById("activity_name").value,
            activity_content: document.getElementById("activity_content").value
          })
        });
        const data = await res.json();
        resultDiv.textContent = data.record || data.detail;
        copyBtn.style.display = "block";
      } catch (e) {
        resultDiv.textContent = "오류가 발생했습니다.";
      } finally {
        btn.innerText = "기록 생성하기";
        btn.disabled = false;
      }
    }

    function copyToClipboard() {
      const text = document.getElementById("result").textContent;
      navigator.clipboard.writeText(text).then(() => {
        alert("기록이 클립보드에 복사되었습니다!");
      });
    }
  </script>
</body>
</html>
"""

@app.post("/generate")
def generate_record(req: ActivityRequest):
    date_str = normalize_date(req.activity_date)
    content = clean_text(req.activity_content)
    name = clean_text(req.activity_name)

    prompt = f"""
전문의적인 생활기록부 작성자로서 아래 정보를 바탕으로 학생의 특성이 드러나는 문장을 작성하라.

[정보]
- 활동명: {name}
- 날짜: {date_str}
- 내용: {content}

[규칙]
1. 반드시 "{name}({date_str})을 통해"로 시작할 것.
2. '학교폭력'이라는 키워드는 활동명에 '학교폭력'이 포함된 경우에만 사용할 것. 그 외에는 활동 내용에 맞는 성취 위주로 작성할 것.
3. 입력된 {content}을 바탕으로 학생이 어떻게 행동했는지 구체적인 서사로 풀어서 130~170자 정도의 분량으로 작성할 것.
4. 문장 속에서 '깨달음함', '배움함'과 같은 어색한 중복 표현이 생기지 않도록 매끄러운 '함.', '임.', '됨.' 어미를 사용할 것.
5. 결과는 단 한 개의 완성된 문장으로 출력할 것.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 고등학교 생활기록부 작성 전문가다. 문법적으로 완벽한 명사형 종결 어미를 사용하며, 학생의 활동에 따른 개별적 특성을 구체적으로 서술한다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
        )
        text = response.choices[0].message.content.strip()
        
        # 후처리 로직 적용 (어색한 문미 수정)
        text = ensure_noun_ending(text)

        # 바이트 제한
        if len(text.encode("utf-8")) > MAX_BYTES:
            while len(text.encode("utf-8")) > MAX_BYTES:
                text = text[:-1]
            text = ensure_noun_ending(text)

        return {"record": text}
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
