import os
import requests
from fastapi import FastAPI, Request
from openai import OpenAI

app = FastAPI()

LINE_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
client = OpenAI()  # OPENAI_API_KEY を環境変数に入れてたらこれでOK

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    print("LINEきた")
    print(body)

    if not LINE_TOKEN:
        return {"ok": False, "error": "LINE_CHANNEL_ACCESS_TOKEN is missing"}

    events = body.get("events", [])
    for ev in events:
        reply_token = ev.get("replyToken")
        msg = ev.get("message", {})
        text = msg.get("text")

        if not reply_token or text is None:
            continue

        # ===== AI生成 =====
        try:
            resp = client.responses.create(
                model="gpt-4o-mini",
                input=f"あなたは大阪の立ち飲み牡蠣屋の店主の相棒AI。関西弁で短めに返事して。\nユーザー: {text}\nAI:"
            )
            ai_text = resp.output_text.strip()
        except Exception as e:
            print("OpenAI error:", repr(e))
            ai_text = "ごめん、AI側が一瞬コケたわ💦 もう一回送って〜"

        # ===== LINEへ返信 =====
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

          
