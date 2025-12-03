import os
import json
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import requests
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

def call_gemini(prompt: str):
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    r = requests.post(GEMINI_URL, headers=headers, params=params, json=body)
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    print("=== Gemini 回覆原始內容 ===")
    print(text)
    print("===========================")
    return text

def parse_candidates(text):
    """
    將 Gemini 回覆轉成純 JSON array
    移除 ```json 或 ``` 包裹
    """
    text = text.strip()
    # 移除 ```json 或 ``` 包裹
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()
    if text.endswith("```"):
        text = text[:-len("```")].strip()
    
    # 嘗試解析 JSON
    try:
        candidates = json.loads(text)
    except:
        # 若失敗就依行拆
        candidates = [line.strip() for line in text.split("\n") if line.strip()][:3]
    # 確保最多三個元素
    return candidates[:3]

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

SESSION_DB = {}

class StartSessionBody(BaseModel):
    gender: str
    age: int
    interests: list[str]

class NextRoundBody(BaseModel):
    session_id: str
    user_reply: str

# -----------------------------
# 忽略 favicon.ico 404
# -----------------------------
@app.get("/favicon.ico")
async def favicon():
    return FileResponse("static/favicon.ico") if os.path.exists("static/favicon.ico") else {}

# -----------------------------
# 前端首頁
# -----------------------------
@app.get("/")
def index():
    return FileResponse("static/index.html")

# -----------------------------
# 開始 session
# -----------------------------
@app.post("/session/start")
def start_session(body: StartSessionBody):
    import uuid
    print("=== 使用者送出 Start ===")
    print(body)
    session_id = str(uuid.uuid4())
    SESSION_DB[session_id] = {
        "settings": body.model_dump(),
        "round": 1,
        "history": []
    }

    prompt = f"""
你現在是交友網站的虛擬對象。
設定：
- 性別: {body.gender}
- 年齡: {body.age}
- 興趣: {', '.join(body.interests)}
請提出一個問題，只能有一個問題，25字以內。
"""
    question = call_gemini(prompt).strip()

    answer_prompt = f"""
問題：「{question}」
請生成三個使用者可能回覆，每個回覆 25 字以內，輸出 JSON Array 例如 ["答1","答2","答3"]
"""
    candidates_text = call_gemini(answer_prompt)
    candidates = parse_candidates(candidates_text)

    print(f"=== 送給前端的問題與候選回答 ===\n問題: {question}\n候選回答: {candidates}")
    return {"session_id": session_id, "question": question, "candidate_answers": candidates, "round": 1, "total_rounds":5}

# -----------------------------
# 下一題
# -----------------------------
@app.post("/session/next")
def next_round(body: NextRoundBody):
    session = SESSION_DB.get(body.session_id)
    if not session:
        return {"error": "session not found"}

    print("=== 使用者回覆 ===")
    print(body.user_reply)
    session["history"].append({"user": body.user_reply})
    session["round"] += 1

    # 超過上限題數，生成建議回覆
    if session["round"] > 5:
        # 準備送給 Gemini 的 prompt
        history = session["history"]
        prompt = f"""
你是一個戀愛互動分析師。
使用者的對話紀錄如下：
{history}
請針對每個問題與使用者的回覆，給出完整建議（不限25字），條列幾點改進建議，輸出純文字
"""
        result_text = call_gemini(prompt)
        try:
            result = json.loads(result_text)
        except:
            result = {"score": 0, "analysis": result_text, "suggestions": []}

        print("=== Session 建議回覆 ===")
        print(result)
        print("===================")

        return {"done": True, "history": history, "score_result": result}

    # 尚未達上限，生成下一題問題
    prompt = f"""
你是交友網站的虛擬對象。
使用者回覆：「{body.user_reply}」
請提出一個問題，只能有一個問題，25字以內。
"""
    question = call_gemini(prompt).strip()

    answer_prompt = f"""
問題：「{question}」
請生成三個使用者可能回覆，每個回覆40 字以內，輸出 JSON Array 例如 ["答1","答2","答3"]
"""
    candidates_text = call_gemini(answer_prompt)
    candidates = parse_candidates(candidates_text)

    print(f"=== 送給前端的問題與候選回答 ===\n問題: {question}\n候選回答: {candidates}")

    return {"question": question, "candidate_answers": candidates, "round": session["round"], "total_rounds":5}


# -----------------------------
# 結束並給分
# -----------------------------
@app.post("/session/score")
def score_session(body: NextRoundBody):
    history = SESSION_DB.get(body.session_id, {}).get("history", [])
    prompt = f"""
你是一個戀愛互動分析師。
使用者完成對話：
{history}
請給分數（0~100）、原因、3點改進建議，輸出 JSON：
{{"score": 數字, "analysis": "...", "suggestions": ["..","..",".."]}}
"""
    result_text = call_gemini(prompt)
    try:
        result = json.loads(result_text)
    except:
        result = {"score": 0, "analysis": result_text, "suggestions": []}

    print("=== Session Score ===")
    print(result)
    print("===================")
    return {"result": result}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
