import os
import re
import traceback
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

app = FastAPI()

# 경로 설정
base_dir = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

def normalize_date(date_str):
    if not date_str: return ""
    nums = re.findall(r'\d+', date_str)
    if len(nums) >= 3:
        return f"{nums[0]}.{nums[1]}.{nums[2]}."
    return date_str

def clean_noun_ending(text):
    if not text: return text
    text = re.sub(r'이 학생은|해당 학생은|본인은|필자는|저는', '', text).strip()
    sentences = text.split('. ')
    processed = []
    for sent in sentences:
        sent = sent.strip().rstrip('.')
        if not sent: continue
        # 중복 어미 교정 (예: 성장함함 -> 성장함)
        sent = re.sub(r'([가-힣]{2,})음함$', r'\1음', sent)
        sent = re.sub(r'([가-힣]{2,})함함$', r'\1함', sent)
        if not sent.endswith(('함', '됨', '임', '음', '기', '함.', '됨.', '임.')):
            if sent.endswith(('했다', '하였다')): sent = sent[:-2] + '함'
            elif sent.endswith(('되었다', '됐다')): sent = sent[:-2] + '됨'
            elif sent.endswith('이다'): sent = sent[:-2] + '임'
        processed.append(sent + ".")
    return " ".join(processed)

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    try:
        # 이 부분이 수정되었습니다. (unhashable type: 'dict' 에러 해결)
        return templates.TemplateResponse(request=request, name="index.html")
    except Exception as e:
        return HTMLResponse(content=f"Template Error: {str(e)}", status_code=500)

@app.post("/generate")
async def generate_record(
    activity_type: str = Form(...),
    activity_name: str = Form(...),
    activity_date: str = Form(...),
    student_keywords: str = Form(...)
):
    try:
        if not api_key:
            return JSONResponse({"result": "Error: API 키가 설정되지 않았습니다."}, status_code=500)

        norm_date = normalize_date(activity_date)
        
        system_role = f"너는 고등학교 '{activity_type}' 생활기록부 작성 전문가야."
        user_content = f"""
작성대상 활동: {activity_name} ({norm_date})
핵심 내용: {student_keywords}

[지침]
1. 시작: '{activity_name}({norm_date}) 시간에 참여하여' 또는 '{activity_name}({norm_date}) 활동을 통해'로 문장을 시작할 것.
2. 연결성: 각 문장을 '특히', '나아가', '이를 바탕으로', '이에 더해'와 같은 연결어를 사용하여 자연스러운 문단으로 작성할 것.
3. 금지어: '이 학생은'과 같은 주어는 절대 쓰지 말 것.
4. 어미: 반드시 명사형 종결 어미(~함, ~임, ~됨, ~음)를 사용할 것.
5. 분량: 250~300자 내외로 상세하게 작성할 것.
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_role},
                {"role": "user", "content": user_content}
            ],
            temperature=0.8
        )
        generated_text = response.choices[0].message.content.strip()
        final_text = clean_noun_ending(generated_text)
        
        return {"result": final_text}

    except Exception as e:
        print(traceback.format_exc())
        return JSONResponse({"result": f"서버 오류: {str(e)}"}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

