import os
import requests
from fastapi import FastAPI, Request

app = FastAPI()

LINE_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


def call_gpt(user_text: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "あなたは大阪の牡蠣小屋の店主の相棒AIです。関西弁で短く返して。"},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.7,
    }

    r = requests.post(url, headers=headers, json=payload, timeout=20)
    data = r.json()

    # エラー時の保険
    if "choices" not in data:
        return f"AIエラーや… {data}"

    return data["choices"][0]["message"]["content"].strip()


@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    print("LINEきた")
    print(body)

    if not LINE_TOKEN:
        return {"ok": False, "error": "LINE_CHANNEL_ACCESS_TOKEN is missing"}

    if not OPENAI_API_KEY:
        return {"ok": False, "error": "OPENAI_API_KEY is missing"}

    events = body.get("events", [])
    for ev in events:
        reply_token = ev.get("replyToken")
        msg = ev.get("message", {})
        text = msg.get("text")

        if not reply_token or text is None:
            continue

        # GPTに投げる
        ai_text = call_gpt(text)

        # LINEに返信
        res = requests.post(
            "https://api.line.me/v2/bot/message/reply",
            headers={
                "Authorization": f"Bearer {LINE_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "replyToken": reply_token,
                "messages": [{"type": "text", "text": ai_text}],
            },
            timeout=10,
        )

        print("reply status:", res.status_code, res.text)

    return {"ok": True}
