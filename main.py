import os
import re
import requests
from fastapi import FastAPI, Request
from openai import OpenAI

app = FastAPI()

LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OWNER_USER_ID = os.getenv("OWNER_USER_ID")

# ====== 店内状態（メモリ保存：再起動でリセット） ======
state = {
    "count": None,            # 店内人数（int）
    "status": "不明",         # "空き" / "満席" / "普通" / "不明"
    "note": "",               # 例: "ビニールカーテン中で最大10名"
    "shell_oysters": None,    # 殻付き（生牡蠣）残り数（int）
}

def get_client():
    if not OPENAI_API_KEY:
        return None
    return OpenAI(api_key=OPENAI_API_KEY)

def is_owner(user_id: str | None) -> bool:
    return bool(OWNER_USER_ID) and (user_id == OWNER_USER_ID)

def line_reply(reply_token: str, text: str):
    if not LINE_TOKEN:
        print("LINE token missing")
        return
    r = requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers={
            "Authorization": f"Bearer {LINE_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "replyToken": reply_token,
            "messages": [{"type": "text", "text": text}],
        },
        timeout=10,
    )
    print("reply status:", r.status_code, r.text)

def _status_from_count(c: int) -> str:
    # あなたの店は最大10名想定（ビニールカーテン時）
    if c >= 10:
        return "満席"
    if c <= 3:
        return "空き"
    return "普通"

def crowd_message() -> str:
    c = state.get("count")
    status = state.get("status") or "不明"
    note = state.get("note") or ""

    # countがあればstatus自動補正
    if isinstance(c, int):
        status = _status_from_count(c)

    base = "いまの店内状況やで👇\n"
    if isinstance(c, int):
        base += f"・人数：{c}名くらい\n"
    else:
        base += "・人数：未更新\n"

    base += f"・状態：{status}\n"
    if note:
        base += f"・メモ：{note}\n"

    # 空いてる時の一言
    if isinstance(c, int) and c <= 3:
        base += "\nいま少ないし、サクッと牡蠣いけるで〜来て来て🦪✨"

    return base.strip()

def oysters_message() -> str:
    """
    殻付き（生牡蠣）在庫の案内
    0以下なら代替メニュー（カキフライ/ホイル焼き）を推す
    """
    n = state.get("shell_oysters")
    if not isinstance(n, int):
        return "殻付き（生牡蠣）の在庫、まだ未更新やねん🙏（店主が #牡蠣 で更新するやつ）"

    if n <= 0:
        return (
            "ごめん！殻付き（生牡蠣）は今日は売り切れやねん🙏\n"
            "でも **カキフライ** と **ホイル焼き** はいけるで🦪🔥\n"
            "食べたい方「フライ」か「ホイル」って送って〜"
        )
    if n <= 10:
        return f"殻付き（生牡蠣）あと **{n}個** くらい⚠️ なくなる前に急げ〜！"
    if n >= 50:
        return f"殻付き（生牡蠣）はまだまだあるで😎（残り目安 {n}個）"
    return f"殻付き（生牡蠣）はまだあるで〜（残り目安 {n}個）"

@app.get("/")
def health():
    return {"ok": True}

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    print("LINEきた", body)

    if not LINE_TOKEN:
        return {"ok": False, "error": "LINE_CHANNEL_ACCESS_TOKEN is missing"}

    events = body.get("events", [])
    for ev in events:
        reply_token = ev.get("replyToken")

        source = ev.get("source") or {}
        user_id = source.get("userId")

        msg = ev.get("message") or {}
        text = msg.get("text")

        if not reply_token or text is None:
            continue

        text = text.strip()

        # ======================
        # ① 店主だけが使える更新コマンド
        # ======================
        if is_owner(user_id):
            # #人数 7 / #人数:7 / 人数 7
            m = re.match(r"^#?人数\s*[:：]?\s*(\d+)\s*$", text)
            if m:
                state["count"] = int(m.group(1))
                state["status"] = _status_from_count(state["count"])
                line_reply(reply_token, f"OK！いま店内{state['count']}名くらいに更新したで👌")
                continue

            # ✅ A) #4人 / 4人（店主が送った時だけ人数更新）
            m = re.match(r"^#?\s*(\d+)\s*人\s*$", text)
            if m:
                state["count"] = int(m.group(1))
                state["status"] = _status_from_count(state["count"])
                line_reply(reply_token, f"OK！いま店内{state['count']}名くらいに更新したで👌")
                continue

            # #満席 / 満席
            if text in ("#満席", "満席"):
                state["status"] = "満席"
                line_reply(reply_token, "OK！状態を「満席」にしたで👌")
                continue

            # #空き / 空き
            if text in ("#空き", "空き"):
                state["status"] = "空き"
                line_reply(reply_token, "OK！状態を「空き」にしたで👌 いま来どきやな🦪")
                continue

            # #メモ ビニールカーテン中で最大10名
            m = re.match(r"^#?メモ\s*[:：]?\s*(.+)\s*$", text)
            if m:
                state["note"] = m.group(1).strip()
                line_reply(reply_token, f"OK！メモ更新したで👌\n{state['note']}")
                continue

            # #牡蠣 12（= 殻付き(生牡蠣)の残り）
            m = re.match(r"^#?牡蠣\s*[:：]?\s*(\d+)\s*$", text)
            if m:
                state["shell_oysters"] = int(m.group(1))
                n = state["shell_oysters"]
                if n <= 10:
                    msg2 = f"OK！殻付き（生牡蠣）残り {n}個⚠️ 焦らせモードでいくで🔥"
                elif n >= 50:
                    msg2 = f"OK！殻付き（生牡蠣）残り {n}個。まだまだあるで😎"
                else:
                    msg2 = f"OK！殻付き（生牡蠣）残り {n}個やで〜"
                line_reply(reply_token, msg2)
                continue

            # #状況（店主用まとめ）
            if text in ("#状況", "状況", "#ステータス", "ステータス"):
                line_reply(reply_token, crowd_message() + "\n\n" + oysters_message())
                continue

        # ======================
        # ② お客さんが聞ける質問（誰でも）
        # ======================

        # ✅ B) 店内人数・混み具合（「何人おる？」系も確実に拾う）
        if re.search(r"(人数|何人|今何人|何人おる|何人いる|混み|混んで|空いて|席|入れる|満席)", text):
            line_reply(reply_token, crowd_message())
            continue

        # 牡蠣（殻付き/生牡蠣）在庫・「牡蠣ある？」系は全部ここで返す
        if re.search(r"(牡蠣|かき)", text):
            if re.search(r"(ある|あります|いける|食べれる|食べられる|在庫|残り|あと|何個|売り切れ|ありますか|\?)", text) \
               or text.strip() in ("牡蠣ある", "牡蠣ある？", "牡蠣ありますか", "牡蠣あるかな", "生牡蠣ある？", "殻付きある？"):
                line_reply(reply_token, oysters_message())
                continue

        # カキフライ/ホイル焼き単体で聞かれた時（売り切れ案内を補助）
        if re.search(r"(フライ|カキフライ|ホイル|ホイル焼き)", text):
            # 牡蠣ゼロなら代替推し、あるなら普通に案内
            n = state.get("shell_oysters")
            if isinstance(n, int) and n <= 0:
                line_reply(reply_token, "殻付きは売り切れやけど、カキフライとホイル焼きはOKやで🦪🔥")
            else:
                line_reply(reply_token, "カキフライもホイル焼きもいけるで🦪🔥 どっちにする？")
            continue

        # ======================
        # ③ それ以外はOpenAIで雑談（任意）
        # ======================
        ai_text = "まいど！どうしたん？🦪"
        client = get_client()

        if client is None:
            ai_text = "OpenAIキー読めてへんっぽい！RailwayのVariables見て〜"
        else:
            try:
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "あなたは大阪の立ち飲み牡蠣小屋の店主の相棒AI。関西弁で短めに返事して。"
                                "店内人数・混み具合・在庫の数字は絶対に推測しない。"
                                "聞かれても未更新なら『未更新やから店主に聞いて〜』と返す。"
                            ),
                        },
                        {"role": "user", "content": text},
                    ],
                )
                ai_text = (resp.choices[0].message.content or "").strip() or ai_text
            except Exception as e:
                print("OpenAI error:", repr(e))
                ai_text = "ごめん、AI側が一瞬コケたわ💦 もっかい送って〜"

        line_reply(reply_token, ai_text)

    return {"ok": True}
