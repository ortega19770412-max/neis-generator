from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from datetime import datetime
import urllib.request
import urllib.error
import json
import os
import re
import html


HOST = "127.0.0.1"
PORT = 8000


def load_env():
    """
    .env 파일에서 OPENAI_API_KEY를 읽습니다.
    python-dotenv 없이 직접 읽는 함수입니다.
    """
    env_path = ".env"

    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value


load_env()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def normalize_date(date_value):
    """
    2020-05-01 형식으로 입력된 날짜를
    2020.05.01. 형식으로 바꿉니다.
    """
    date_value = date_value.strip()

    patterns = [
        "%Y-%m-%d",
        "%Y.%m.%d.",
        "%Y.%m.%d",
        "%Y/%m/%d"
    ]

    for pattern in patterns:
        try:
            parsed_date = datetime.strptime(date_value, pattern)
            return parsed_date.strftime("%Y.%m.%d.")
        except ValueError:
            continue

    return date_value


def clean_result(result, activity_name, date):
    """
    AI가 생성한 문장을 원하는 형식에 맞게 정리합니다.
    """
    result = result.strip()
    result = result.replace("\n", " ")
    result = result.strip("\"'“”‘’")
    result = re.sub(r"\s+", " ", result)

    required_start = f"{activity_name}({date})을 통해"

    if not result.startswith(required_start):
        result = required_start + " " + result

    if not result.endswith("."):
        result += "."

    return result


def build_prompt(activity_type, activity_name, date):
    """
    OpenAI API에 보낼 요청 문장을 만듭니다.
    """
    prompt = f"""
다음 입력값을 바탕으로 학교생활기록부 창의적 체험활동 특기사항 문장을 작성해 주세요.

입력값:
- 활동 구분: {activity_type}
- 활동명: {activity_name}
- 날짜: {date}

작성 조건:
1. 출력은 반드시 한 문장만 작성합니다.
2. 문장은 반드시 "{activity_name}({date})을 통해"로 시작합니다.
3. 문장 끝은 반드시 "시간이 됨.", "기회가 됨.", "계기가 됨." 중 하나로 끝냅니다.
4. 활동 구분이 "자율활동"이면 공동체 의식, 안전의식, 인성, 민주시민의식, 학교생활 태도, 예방교육, 자치활동 관점에서 작성합니다.
5. 활동 구분이 "진로활동"이면 자기 이해, 진로 탐색, 직업 세계 이해, 학과 탐색, 진로 설계 관점에서 작성합니다.
6. 학생 이름은 쓰지 않습니다.
7. 수상, 발표, 리더십, 봉사, 실천, 성과, 향상, 변화 등 입력값에 없는 구체적 사실은 쓰지 않습니다.
8. 과장된 표현을 쓰지 않습니다.
9. 실제 자료가 제공되지 않았으므로 활동명에서 일반적으로 추론 가능한 범위의 내용만 작성합니다.
10. 학교생활기록부 문체로 객관적이고 간결하게 작성합니다.
11. 최종 결과 문장만 출력합니다.
"""
    return prompt


def call_openai_api(prompt):
    """
    외부 패키지 없이 urllib로 OpenAI Responses API를 직접 호출합니다.
    """
    if not OPENAI_API_KEY:
        raise Exception(".env 파일에 OPENAI_API_KEY가 설정되어 있지 않습니다.")

    url = "https://api.openai.com/v1/responses"

    payload = {
        "model": "gpt-4.1-mini",
        "input": prompt,
        "temperature": 0.2
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_body = response.read().decode("utf-8")
            result_json = json.loads(response_body)

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise Exception(f"OpenAI API 오류: {e.code} {error_body}")

    except urllib.error.URLError as e:
        raise Exception(f"네트워크 오류: {str(e)}")

    # Responses API 응답에서 output_text가 있으면 사용합니다.
    if "output_text" in result_json:
        return result_json["output_text"]

    # output 배열에서 텍스트를 찾습니다.
    try:
        output_items = result_json.get("output", [])
        texts = []

        for item in output_items:
            content_items = item.get("content", [])
            for content in content_items:
                if content.get("type") in ["output_text", "text"]:
                    texts.append(content.get("text", ""))

        if texts:
            return "\n".join(texts)

    except Exception:
        pass

    raise Exception(f"API 응답에서 텍스트를 찾지 못했습니다: {result_json}")


def render_page(result="", activity_type="자율활동", activity_name="", date=""):
    """
    HTML 화면을 문자열로 만듭니다.
    """
    result_safe = html.escape(result)
    activity_name_safe = html.escape(activity_name)
    date_safe = html.escape(date)

    selected_autonomous = "selected" if activity_type == "자율활동" else ""
    selected_career = "selected" if activity_type == "진로활동" else ""

    page = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>자율활동·진로활동 특기사항 생성기</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f5f6f8;
            margin: 0;
            padding: 40px;
        }}

        .container {{
            max-width: 850px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border: 1px solid #ddd;
            border-radius: 12px;
        }}

        h1 {{
            margin-top: 0;
            font-size: 26px;
        }}

        .description {{
            color: #555;
            line-height: 1.6;
            margin-bottom: 25px;
        }}

        label {{
            display: block;
            margin-top: 18px;
            margin-bottom: 8px;
            font-weight: bold;
        }}

        select,
        input,
        textarea {{
            width: 100%;
            box-sizing: border-box;
            padding: 12px;
            font-size: 16px;
            border: 1px solid #bbb;
            border-radius: 6px;
        }}

        button {{
            margin-top: 22px;
            width: 100%;
            padding: 14px;
            font-size: 17px;
            font-weight: bold;
            background-color: #2563eb;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
        }}

        button:hover {{
            background-color: #1d4ed8;
        }}

        .result-box {{
            margin-top: 30px;
        }}

        textarea {{
            line-height: 1.6;
        }}

        .notice {{
            margin-top: 20px;
            padding: 14px;
            background-color: #fff8e1;
            border: 1px solid #f3d27a;
            border-radius: 6px;
            color: #5c4700;
            line-height: 1.6;
        }}

        .example {{
            margin-top: 20px;
            padding: 14px;
            background-color: #f0f4ff;
            border: 1px solid #c7d2fe;
            border-radius: 6px;
            line-height: 1.6;
        }}

        .copy-button {{
            background-color: #374151;
        }}

        .copy-button:hover {{
            background-color: #111827;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>자율활동·진로활동 특기사항 생성기</h1>

        <p class="description">
            활동 구분, 활동명, 날짜를 입력하면 학교생활기록부 창의적 체험활동 특기사항 문장을 생성합니다.
        </p>

        <div class="notice">
            이 프로그램은 활동 자료 없이 활동명과 날짜만으로 초안을 생성합니다.
            실제 학교생활기록부에 반영하기 전에는 반드시 교사가 사실 여부와 표현 적절성을 확인해야 합니다.
        </div>

        <form method="post" action="/generate">
            <label for="activity_type">활동 구분</label>
            <select id="activity_type" name="activity_type">
                <option value="자율활동" {selected_autonomous}>자율활동</option>
                <option value="진로활동" {selected_career}>진로활동</option>
            </select>

            <label for="activity_name">활동명</label>
            <input
                type="text"
                id="activity_name"
                name="activity_name"
                placeholder="예: 학교폭력예방교육"
                value="{activity_name_safe}"
                required
            >

            <label for="date">날짜</label>
            <input
                type="date"
                id="date"
                name="date"
                value="{date_safe}"
                required
            >

            <button type="submit">특기사항 생성하기</button>
        </form>

        <div class="example">
            <strong>출력 예시</strong><br>
            학교폭력예방교육(2020.05.01.)을 통해 학교폭력이 신체적 폭력뿐만 아니라 언어폭력, 사이버폭력, 따돌림 등 정신적 피해를 주는 행동까지 포함한다는 점을 이해하고, 서로를 존중하는 학교생활의 중요성을 배우는 시간이 됨.
        </div>

        <div class="result-box">
            <label for="result">출력 결과</label>
            <textarea id="result" rows="7" readonly>{result_safe}</textarea>
            <button type="button" class="copy-button" onclick="copyResult()">결과 복사하기</button>
        </div>
    </div>

    <script>
        function copyResult() {{
            const resultBox = document.getElementById("result");
            resultBox.select();
            document.execCommand("copy");
            alert("출력 결과를 복사했습니다.");
        }}
    </script>
</body>
</html>
"""
    return page


class RecordGeneratorHandler(BaseHTTPRequestHandler):
    def send_html(self, content, status=200):
        content_bytes
