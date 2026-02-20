import os
import re
import requests
from fastapi import FastAPI, Request
from openai import OpenAI

app = FastAPI()

LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("openai_api_key")
OWNER_USER_ID = os.getenv("OWNER_USER_ID")

# ====== 店内状態（メモリ保存：再起動でリセット） ======
state = {
    "count": None,            # 店内人数（int）
    "status": "不明",         # "空き" / "満席" / "普通" / "不明"
    "note": "冬はビニールカーテンで最大10名くらい",  # 任意メモ
    "shell_oysters": None,    # 殻付き（生牡蠣）残り数（int）
    "cap": 10,                # キャパ上限（0なら上限なし）
}

# ====== 基本 ======
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

# 店主だけに通知したい時用（push）
def line_push(to_user_id: str, text: str):
    if not LINE_TOKEN:
        print("LINE token missing")
        return
    r = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {LINE_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "to": to_user_id,
            "messages": [{"type": "text", "text": text}],
        },
        timeout=10,
    )
    print("push status:", r.status_code, r.text)

# ====== 自動満席判定（cap対応） ======
def status_from_count(c: int) -> str:
    cap = state.get("cap", 10)
    # cap=0 は上限なし → 満席判定しない
    if isinstance(cap, int) and cap > 0 and c >= cap:
        return "満席"
    if c <= 3:
        return "空き"
    return "普通"

def crowd_message() -> str:
    c = state.get("count")
    status = state.get("status") or "不明"
    note = state.get("note") or ""
    cap = state.get("cap", 10)

    # countがあればstatus自動補正
    if isinstance(c, int):
        status = status_from_count(c)

    lines = ["いまの店内状況やで👇"]

    if isinstance(c, int):
        lines.append(f"・人数：{c}名くらい")
    else:
        lines.append("・人数：未更新")

    if isinstance(cap, int) and cap == 0:
        lines.append("・キャパ：上限なし（オープン仕様）")
    else:
        lines.append(f"・キャパ：最大{cap}名くらい")

    lines.append(f"・状態：{status}")

    if note:
        lines.append(f"・メモ：{note}")

    if isinstance(c, int) and c <= 3:
        lines.append("")
        lines.append("いま少ないし、サクッと牡蠣いけるで〜来て来て🦪✨")

    if isinstance(c, int) and status == "満席":
        lines.append("")
        lines.append("いま満席や🙏 少し時間ずらすか、空いたらまた聞いて〜！")

    return "\n".join(lines).strip()

# ====== 牡蠣在庫 ======
def oysters_message() -> str:
    n = state.get("shell_oysters")
    if not isinstance(n, int):
        return "殻付き（生牡蠣）の在庫、まだ未更新やねん🙏（店主に聞いてみて〜）"

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

# ====== ヘルプ ======
def owner_help() -> str:
    return (
        "【店主コマンド】\n"
        "・#人数 4  /  #4人  … 店内人数更新\n"
        "・#キャパ 10 … 最大人数（冬仕様）\n"
        "・#キャパ 0  … 上限なし（暖かい日）\n"
        "・#満席 / #空き … 状態を手動で上書き（必要な時だけ）\n"
        "・#メモ 〇〇 … 表示メモ更新\n"
        "・#牡蠣 12 … 殻付き（生牡蠣）残り更新\n"
        "・#状況 … まとめ表示\n"
    )

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
        if not reply_token:
            continue

        source = ev.get("source") or {}
        user_id = source.get("userId")

        msg = ev.get("message") or {}
        text = msg.get("text")
        if text is None:
            continue

        text = text.strip()

        # ======================
        # ① 店主だけが使える更新コマンド
        # ======================
        if is_owner(user_id):
            # #ヘルプ
            if text in ("#ヘルプ", "ヘルプ", "#help", "help"):
                line_reply(reply_token, owner_help())
                continue

            # #キャパ 10 / #キャパ 0（0 = 上限なし）
            m = re.match(r"^#?キャパ\s*[:：]?\s*(\d+)\s*$", text)
            if m:
                before_cap = state.get("cap", 10)
                state["cap"] = int(m.group(1))
                cap = state["cap"]

                # cap変更後、countがあるならstatusも再計算
                if isinstance(state.get("count"), int):
                    state["status"] = status_from_count(state["count"])

                if cap == 0:
                    line_reply(reply_token, "OK！キャパ上限なしモードにしたで👌（満席判定オフ）")
                else:
                    line_reply(reply_token, f"OK！キャパを {cap}名 にしたで👌")

                # 参考：冬→上限なしへ変えた時の一言
                if before_cap != cap:
                    print(f"cap changed: {before_cap} -> {cap}")
                continue

            # #人数 7 / #人数:7 / 人数 7
            m = re.match(r"^#?人数\s*[:：]?\s*(\d+)\s*$", text)
            if m:
                prev_status = state.get("status")
                state["count"] = int(m.group(1))
                state["status"] = status_from_count(state["count"])
                line_reply(reply_token, f"OK！いま店内{state['count']}名くらいに更新したで👌")

                # 満席→空きになったら店主にプッシュしたい時（任意）
                # if OWNER_USER_ID and prev_status == "満席" and state["status"] == "空き":
                #     line_push(OWNER_USER_ID, "【通知】満席→空きに変わったで！今がチャンス🦪✨")

                continue

            # ✅ #4人 / 4人
            m = re.match(r"^#?\s*(\d+)\s*人\s*$", text)
            if m:
                prev_status = state.get("status")
                state["count"] = int(m.group(1))
                state["status"] = status_from_count(state["count"])
                line_reply(reply_token, f"OK！いま店内{state['count']}名くらいに更新したで👌")

                # 満席→空き通知（任意）
                # if OWNER_USER_ID and prev_status == "満席" and state["status"] == "空き":
                #     line_push(OWNER_USER_ID, "【通知】満席→空きに変わったで！今がチャンス🦪✨")

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

            # #メモ 〜
            m = re.match(r"^#?メモ\s*[:：]?\s*(.+)\s*$", text)
            if m:
                state["note"] = m.group(1).strip()
                line_reply(reply_token, f"OK！メモ更新したで👌\n{state['note']}")
                continue

            # #牡蠣 12
            m = re.match(r"^#?牡蠣\s*[:：]?\s*(\d+)\s*$", text)
            if m:
                state["shell_oysters"] = int(m.group(1))
                n = state["shell_oysters"]
                if n <= 0:
                    msg2 = "OK！殻付き（生牡蠣）0に更新。売り切れモードや🙏"
                elif n <= 10:
                    msg2 = f"OK！殻付き（生牡蠣）残り {n}個⚠️ 焦らせモードでいくで🔥"
                elif n >= 50:
                    msg2 = f"OK！殻付き（生牡蠣）残り {n}個。まだまだあるで😎"
                else:
                    msg2 = f"OK！殻付き（生牡蠣）残り {n}個やで〜"
                line_reply(reply_token, msg2)
                continue

            # #状況
            if text in ("#状況", "状況", "#ステータス", "ステータス"):
                line_reply(reply_token, crowd_message() + "\n\n" + oysters_message())
                continue

        # ======================
        # ② お客さんが聞ける質問（誰でも）
        # ======================
        # 店内人数・混み具合（何人おる？系も確実に拾う）
        if re.search(r"(人数|何人|今何人|何人おる|何人いる|混み|混んで|空いて|席|入れる|満席)", text):
            line_reply(reply_token, crowd_message())
            continue

        # 牡蠣ある？（生牡蠣/殻付き/在庫/残り）
        if re.search(r"(牡蠣|かき|生牡蠣|殻|殻付き)", text):
            if re.search(r"(ある|あります|いける|食べれる|食べられる|\?|？|在庫|残り|あと|まだ|売り切れ|何個)", text) or len(text) <= 8:
                line_reply(reply_token, oysters_message())
                continue

        # 売り切れ時の提案に乗ってきた時
        if text in ("フライ", "カキフライ"):
            line_reply(reply_token, "ほなカキフライで決まりや🦪🔥 サクサクで優勝やで！")
            continue
        if text in ("ホイル", "ホイル焼き"):
            line_reply(reply_token, "ホイル焼きいこ🦪🔥 バター醤油系で飛ぶで〜！")
            continue

        # ======================
        # ③ それ以外はOpenAIで雑談（任意）
        # ======================
        ai_text = "まいど！どないしたん？🦪"
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
                                "未更新なら『未更新やから店主に聞いて〜』と返す。"
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
