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
# Render 배포 시 환경변수 OPENAI_API_KEY가 설정되어 있어야 합니다.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

# 템플릿 설정 (경로 확인)
# 프로젝트 루트에 templates 폴더가 반드시 있어야 하며, 그 안에 index.html이 있어야 함
templates = Jinja2Templates(directory="templates")

def normalize_date(date_str):
    """날짜 형식을 YYYY.MM.DD. 형태로 표준화"""
    if not date_str: return ""
    nums = re.findall(r'\d+', date_str)
    if len(nums) >= 3:
        # 연도가 2자리인 경우 2000년대 처리 (선택사항)
        year = nums[0]
        if len(year) == 2: year = "20" + year
        return f"{year}.{nums[1]}.{nums[2]}."
    return date_str

def ensure_noun_ending(text):
    """문장 끝을 명사형 어미(~함, ~임, ~됨)로 강제 변환"""
    if not text: return text
    text = text.strip()
    text = re.sub(r'\.$', '', text) # 마지막 마침표 일단 제거
    
    # 중복 어미 방지 및 변환
    if text.endswith(("하였다", "했다", "함")):
        text = re.sub(r'(하였다|했다|함)$', '함', text)
    elif text.endswith(("되었다", "됐다", "됨")):
        text = re.sub(r'(되었다|됐다|됨)$', '됨', text)
    elif not text.endswith(("함", "임", "됨", "기", "음")):
        text += "함"
    
    return text + "."

def pad_to_min_bytes(text, min_bytes, activity_name):
    """바이트가 부족할 경우 활동 성격에 맞는 꼬리표 추가"""
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
    # index.html이 templates 폴더 안에 있는지 확인 필수
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/generate")
async def generate_record(
    activity_name: str = Form(...),
    activity_date: str = Form(...),
    student_keywords: str = Form(...)
):
    norm_date = normalize_date(activity_date)
    prefix = f"{activity_name}({norm_date})"
    
    is_violence = any(k in activity_name for k in ["폭력", "예방", "안전", "인권"])
    
    if is_violence:
        system_role = "너는 고등학교 교사야. 학생의 학교폭력 예방 활동 기록을 작성해."
        user_content = f"활동명: {activity_name} ({norm_date})\n핵심어: {student_keywords}\n\n위 정보를 기반으로 '신체적, 정신적, 재산적, 사이버' 피해의 위험성을 깨달았다는 내용을 포함하여 명사형 어미로 150자 내외의 생기부 문장을 작성해."
    else:
        system_role = "너는 고등학교 교사야. 학생의 진로 활동 기록을 작성해."
        user_content = f"활동명: {activity_name} ({norm_date})\n핵심어: {student_keywords}\n\n위 정보를 기반으로 진로 역량과 배운 점을 중심으로 명사형 어미로 150자 내외의 생기부 문장을 작성해. 폭력 예방 내용은 절대 포함하지 마."

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_role},
                {"role": "user", "content": user_content}
            ],
            temperature=0.8
        )
        generated_text = response.choices[0].message.content.strip()
    except Exception as e:
        return {"result": f"API 에러가 발생했습니다: {str(e)}"}
    
    # 텍스트 정제
    if not generated_text.startswith(activity_name):
        generated_text = f"{prefix} {generated_text}"
    
    generated_text = ensure_noun_ending(generated_text)
    final_text = pad_to_min_bytes(generated_text, 250, activity_name)
    
    # NEIS 700바이트 제한 (안전하게 690바이트에서 절단)
    while len(final_text.encode('utf-8')) > 690:
        final_text = final_text[:-1]
    
    return {"result": final_text}

if __name__ == "__main__":
    import uvicorn
    # Render는 PORT 환경 변수를 사용하므로 아래와 같이 설정해야 500 에러를 피할 수 있습니다.
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

