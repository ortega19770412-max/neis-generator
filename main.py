import os
import re
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openai import OpenAI
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

# 템플릿 설정 (templates 폴더가 있어야 함)
templates = Jinja2Templates(directory="templates")

def normalize_date(date_str):
    """날짜 형식을 YYYY.MM.DD. 형태로 표준화"""
    if not date_str: return ""
    nums = re.findall(r'\d+', date_str)
    if len(nums) >= 3:
        return f"{nums[0]}.{nums[1]}.{nums[2]}."
    return date_str

def ensure_noun_ending(text):
    """문장 끝을 명사형 어미(~함, ~임, ~됨)로 강제 변환 및 중복 어미 수정"""
    if not text: return text
    text = text.strip()
    # 1단계: 마침표 제거 후 끝단 처리
    text = re.sub(r'\.$', '', text)
    
    # 2단계: 다/요/오 등으로 끝나는 경우 처리
    if text.endswith(("하였다", "했다", "함")):
        text = re.sub(r'(하였다|했다|함)$', '함', text)
    elif text.endswith(("되었다", "됐다", "됨")):
        text = re.sub(r'(되었다|됐다|됨)$', '됨', text)
    elif not text.endswith(("함", "임", "됨", "기", "음")):
        text += "함"
    
    # 3단계: 마침표 다시 찍기
    return text + "."

def pad_to_min_bytes(text, min_bytes, activity_name):
    """바이트가 부족할 경우 활동 성격에 맞는 꼬리표 추가"""
    current_bytes = len(text.encode('utf-8'))
    
    # 활동 성격 구분
    is_violence = any(k in activity_name for k in ["폭력", "예방", "안전", "인권"])
    
    if is_violence:
        tails = [
            " 타인을 존중하며 갈등을 평화적으로 해결하는 공동체 의식을 실천하기 위해 노력함.",
            " 학교폭력의 위험성을 깊이 인지하고 안전한 학교 문화를 조성하는 데 앞장서는 태도를 보임.",
            " 상대방의 입장에서 공감하며 성숙한 대화로 문제를 해결하려는 의지가 돋보임."
        ]
    else:
        tails = [
            " 활동을 통해 자신의 소질을 발견하고 진로를 구체화하는 데 적극적으로 임함.",
            " 창의적인 사고와 책임감 있는 태도로 주어진 과제를 성실히 수행하여 성장을 이룸.",
            " 배운 내용을 바탕으로 자기주도적 역량을 강화하며 지속적으로 탐구하는 자세를 보임."
        ]
        
    idx = 0
    while len(text.encode('utf-8')) < min_bytes and idx < len(tails):
        text = text.rstrip('.') + tails[idx]
        idx += 1
    return text

@app.get("/", response_class=HTMLResponse)
async def read_form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/generate")
async def generate_record(
    activity_name: str = Form(...),
    activity_date: str = Form(...),
    student_keywords: str = Form(...)
):
    norm_date = normalize_date(activity_date)
    prefix = f"{activity_name}({norm_date})"
    
    # 활동명에 따른 동적 프롬프트 분기
    is_violence = any(k in activity_name for k in ["폭력", "예방", "안전", "인권"])
    
    if is_violence:
        system_role = "너는 대한민국 고등학교 교사야. 학생의 학교폭력 예방 활동 기록을 전문적으로 작성해."
        user_content = f"""
활동명: {activity_name} ({norm_date})
학생 키워드: {student_keywords}

위 정보를 바탕으로 '학교폭력 예방'의 취지에 맞게 생활기록부를 작성하라.
1. 반드시 '신체적, 정신적, 재산적, 정보통신망(사이버)' 피해의 위험성을 깨달았다는 내용을 포함할 것.
2. 타인에 대한 이해와 존중, 갈등의 평화적 해결 의지를 강조할 것.
3. 반드시 명사형 어미(~함, ~됨, ~임)로 끝맺을 것.
4. 시작은 반드시 '{prefix}'로 할 것.
5. 분량: 한글 기준 150자 내외.
"""
    else:
        system_role = "너는 대한민국 고등학교 교사야. 학생의 진로 및 자율활동 기록을 전문적으로 작성해."
        user_content = f"""
활동명: {activity_name} ({norm_date})
학생 키워드: {student_keywords}

위 정보를 바탕으로 해당 활동의 성격(진로/자율/체험/캠프 등)에 맞춰 생활기록부를 작성하라.
1. 학생이 배운 점, 구체적 성장 과정, 자기주도적 역량을 중심으로 서술할 것.
2. '학교폭력' 관련 내용은 절대 포함하지 말 것.
3. 반드시 명사형 어미(~함, ~됨, ~임)로 끝맺을 것.
4. 시작은 반드시 '{prefix}'로 할 것.
5. 분량: 한글 기준 150자 내외.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_role},
            {"role": "user", "content": user_content}
        ],
        temperature=0.7
    )

    generated_text = response.choices[0].message.content.strip()
    
    # 후처리: 접두어 확인, 어미 정리, 바이트 조절(200~700)
    if not generated_text.startswith(activity_name):
        generated_text = f"{prefix} {generated_text}"
    
    generated_text = ensure_noun_ending(generated_text)
    final_text = pad_to_min_bytes(generated_text, 250, activity_name)
    
    # 최대 700바이트 제한(NEIS 기준)
    while len(final_text.encode('utf-8')) > 700:
        final_text = final_text[:-1]
    
    return {"result": final_text}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

