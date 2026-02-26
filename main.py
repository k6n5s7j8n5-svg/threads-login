import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    PushMessageRequest,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from db import init_db, get_status, set_status, get_draft, set_draft

app = FastAPI()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
ADMIN_LINE_USER_ID = os.getenv("ADMIN_LINE_USER_ID", "")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    # 起動はするが、LINEは動かない
    pass

handler = WebhookHandler(LINE_CHANNEL_SECRET)
config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

def is_admin(user_id: str) -> bool:
    return bool(ADMIN_LINE_USER_ID) and user_id == ADMIN_LINE_USER_ID

def push_text(user_id: str, text: str):
    if not LINE_CHANNEL_ACCESS_TOKEN:
        return
    with ApiClient(config) as api_client:
        api = MessagingApi(api_client)
        api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=text)]))

def reply_text(reply_token: str, text: str):
    with ApiClient(config) as api_client:
        api = MessagingApi(api_client)
        api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)]))

@app.on_event("startup")
def startup():
    init_db()

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/status")
def status():
    people, oysters, updated_at = get_status()
    return {"people": people, "oysters": oysters, "updated_at": updated_at}

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")

    try:
        handler.handle(body, signature)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return PlainTextResponse("OK")

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    user_id = event.source.user_id
    text = (event.message.text or "").strip()

    # Customer command
    if text in ["状況", "店内", "いま", "今"]:
        people, oysters, updated_at = get_status()
        msg = f"【店内状況】\n店内人数: {people}人\n牡蠣残数: {oysters}個\n(更新: {updated_at})"
        reply_text(event.reply_token, msg)
        return

    # Admin commands
    if not is_admin(user_id):
        reply_text(event.reply_token, "「状況」と送ると店内状況が見れます。")
        return

    # Approve / edit draft
    if text.upper() == "OK":
        d, _, _ = get_draft()
        if not d:
            reply_text(event.reply_token, "まだ下書きがありません。")
            return
        set_draft(d, approved=True)
        reply_text(event.reply_token, "OK。投稿予約を確定したで。")
        return

    if text.startswith("修正:") or text.startswith("修正："):
        new_text = text.split(":", 1)[1].strip() if ":" in text else text.split("：", 1)[1].strip()
        set_draft(new_text, approved=True)
        reply_text(event.reply_token, "修正OK。投稿予約を更新したで。")
        return

    # Status update
    # patterns: "人数 3" / "牡蠣 120" / "更新 3 120"
    parts = text.replace("　", " ").split()  # full-width space to half-width
    if len(parts) >= 2 and parts[0] in ["人数", "ひと", "客", "店内"]:
        try:
            set_status(people=int(parts[1]))
            people, oysters, updated_at = get_status()
            reply_text(event.reply_token, f"更新OK\n店内人数: {people}人\n牡蠣残数: {oysters}個")
        except:
            reply_text(event.reply_token, "人数は数字で送って: 例）人数 4")
        return

    if len(parts) >= 2 and parts[0] in ["牡蠣", "かき", "カキ", "残", "残数"]:
        try:
            set_status(oysters=int(parts[1]))
            people, oysters, updated_at = get_status()
            reply_text(event.reply_token, f"更新OK\n店内人数: {people}人\n牡蠣残数: {oysters}個")
        except:
            reply_text(event.reply_token, "牡蠣は数字で送って: 例）牡蠣 120")
        return

    if len(parts) >= 3 and parts[0] == "更新":
        try:
            set_status(people=int(parts[1]), oysters=int(parts[2]))
            people, oysters, updated_at = get_status()
            reply_text(event.reply_token, f"更新OK\n店内人数: {people}人\n牡蠣残数: {oysters}個")
        except:
            reply_text(event.reply_token, "例）更新 4 120 で送って")
        return

    reply_text(
        event.reply_token,
        "管理コマンド:\n人数 4\n牡蠣 120\n更新 4 120\nOK（下書き確定）\n修正: 文章（差し替え）"
    )
