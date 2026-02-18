print("=== DEPLOY CHECK: AI VERSION 2026-02-18 14:45 ===")
import os
import requests
from fastapi import FastAPI, Request

from openai import OpenAI

app = FastAPI()

def get_env(name: str) -> str | None:
    return os.environ.get(name)

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    print("LINEきた")
    print(body)

    LINE_TOKEN = get_env("LINE_CHANNEL_ACCESS_TOKEN")
    OPENAI_API_KEY = get_env("OPENAI_API_KEY")

    if not LINE_TOKEN:
        return {"ok": False, "error": "LINE_CHANNEL_ACCESS_TOKEN is missing"}
    if not OPENAI_API_KEY:
        return {"ok": False, "error": "OPENAI_API_KEY is missing"}

    client = OpenAI(api_key=OPENAI_API_KEY)

    events = body.get("events", [])
    for ev in events:
        reply_token = ev.get("replyToken")
        msg = ev.get("message", {})
        text = msg.get("text")

        # テキスト以外は無視
        if not reply_token or text is None:
            continue

        # ChatGPTに投げる
        try:
            resp = client.responses.create(
                model="gpt-4.1-mini",
                input=f"次のメッセージに、短めでフレンドリーに関西弁で返事して。\n\n{text}"
            )
            reply_text = resp.output_text.strip()
            if not reply_text:
                reply_text = "ごめん、今ちょい詰まったわ🙏 もう一回言ってみて！"
        except Exception as e:
            print("OpenAI error:", e)
            reply_text = "ごめん、AI側でエラー出たわ🙏 ちょい待ってな！"

        # LINEに返信
        try:
            res = requests.post(
                "https://api.line.me/v2/bot/message/reply",
                headers={
                    "Authorization": f"Bearer {LINE_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "replyToken": reply_token,
                    "messages": [{"type": "text", "text": reply_text}],
                },
                timeout=10,
            )
            print("reply status:", res.status_code, res.text)
        except Exception as e:
            print("LINE reply error:", e)

    return {"ok": True}
