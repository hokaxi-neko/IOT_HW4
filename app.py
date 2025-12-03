import streamlit as st
import requests
import json

# -----------------------------
# Gemini 設定
# -----------------------------
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


def call_gemini(prompt: str):
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}
    body = {"contents": [{"parts": [{"text": prompt}]}]}

    r = requests.post(GEMINI_URL, headers=headers, params=params, json=body)
    r.raise_for_status()

    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return text


def parse_candidates(text):
    text = text.strip()

    # remove Markdown fences
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    try:
        return json.loads(text)[:3]
    except:
        return [line.strip() for line in text.split("\n") if line.strip()][:3]


# -----------------------------
# Streamlit App
# -----------------------------
st.title("💘 AI 交友互動模擬器 (Streamlit 版本)")

# 初始化 session_state
if "started" not in st.session_state:
    st.session_state.started = False
    st.session_state.round = 1
    st.session_state.history = []
    st.session_state.question = ""
    st.session_state.candidate_answers = []


# -----------------------------
# Step 1: 開始設定
# -----------------------------
if not st.session_state.started:
    st.subheader("起始設定")
    gender = st.selectbox("性別", ["男", "女", "其他"])
    age = st.number_input("年齡", 18, 80, 25)
    interests = st.text_input("興趣（用逗號分隔）", value="音樂, 電影")

    if st.button("開始對話"):
        st.session_state.started = True
        st.session_state.round = 1
        st.session_state.history = []

        # 呼叫模型產生第一題
        prompt = f"""
你現在是交友網站的虛擬對象。
設定：
- 性別: {gender}
- 年齡: {age}
- 興趣: {interests}
請提出一個問題，只能有一個問題，25字以內。
"""
        question = call_gemini(prompt).strip()

        ans_prompt = f"""
問題：「{question}」
請生成三個使用者可能回覆，每個回覆25字以內。
輸出 JSON Array
"""
        answers = parse_candidates(call_gemini(ans_prompt))

        st.session_state.question = question
        st.session_state.candidate_answers = answers

    st.stop()


# -----------------------------
# Step 2: 對話進行中
# -----------------------------
st.subheader(f"Round {st.session_state.round} / 5")
st.write(f"**問題：** {st.session_state.question}")

user_reply = st.radio("你的回覆：", options=st.session_state.candidate_answers)

if st.button("送出回答"):
    st.session_state.history.append({"user": user_reply})
    st.session_state.round += 1

    # 結束回合
    if st.session_state.round > 5:
        st.subheader("❤️ 分析結果產生中...")

        analyze_prompt = f"""
你是一個戀愛互動分析師。
使用者對話紀錄：
{st.session_state.history}
請提供完整建議（不限字），條列改善方向。
輸出純文字
"""
        analysis = call_gemini(analyze_prompt)

        st.write("### 🔍 你的互動分析")
        st.write(analysis)

        st.stop()

    # 下一題
    prompt = f"""
你是交友網站的虛擬對象。
使用者回覆：「{user_reply}」
請提出一個問題，只能有一個問題，25字以內。
"""
    question = call_gemini(prompt).strip()

    ans_prompt = f"""
問題：「{question}」
請生成三個使用者可能回覆，每個回覆40字以內。
輸出 JSON Array
"""
    answers = parse_candidates(call_gemini(ans_prompt))

    st.session_state.question = question
    st.session_state.candidate_answers = answers

    st.rerun()


# -----------------------------
# 重新開始
# -----------------------------
if st.button("重新開始"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
