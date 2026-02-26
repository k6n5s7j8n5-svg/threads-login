import os
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from openai import OpenAI

from db import init_db, get_draft, set_draft
from threads_poster import post_to_threads

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)

TZ = os.getenv("TZ", "Asia/Tokyo")
POST_TIME = os.getenv("POST_TIME", "12:00")  # HH:MM
ADMIN_LINE_USER_ID = os.getenv("ADMIN_LINE_USER_ID", "")

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

def push_text(text: str):
    if not (LINE_CHANNEL_ACCESS_TOKEN and ADMIN_LINE_USER_ID):
        return
    with ApiClient(config) as api_client:
        api = MessagingApi(api_client)
        api.push_message(PushMessageRequest(to=ADMIN_LINE_USER_ID, messages=[TextMessage(text=text)]))

def generate_copy() -> str:
    if not client:
        return "【仮】牡蠣が食べたくなる投稿文（OPENAI_API_KEY未設定）"

    prompt = (
        "あなたは大阪の小さな立ち飲み牡蠣店の店主のSNS担当です。"
        "Threads投稿用に、牡蠣が食べたくなる短い文章を1つ作って。"
        "条件: 80〜140文字、絵文字は1〜3個、煽りすぎない、店名は入れない、改行はOK。"
    )

    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
    )
    return r.choices[0].message.content.strip()

def job_midnight():
    text = generate_copy()
    set_draft(text, approved=False)
    push_text("【明日のThreads下書き】\n" + text + "\n\n返信:\nOK → このまま\n修正:〜 → 差し替え")

def job_post():
    text, approved, updated_at = get_draft()
    if not text:
        push_text("下書きが無いから投稿できへんかった。")
        return
    if not approved:
        push_text("下書きが未確定(OK/修正が未返信)やから投稿せえへんかった。\n" + text)
        return

    try:
        post_to_threads(text)
        push_text("Threads投稿完了 ✅")
        # 投稿後は未確定に戻す（翌日用）
        set_draft(text, approved=False)
    except Exception as e:
        push_text("Threads投稿失敗 ❌\n" + str(e))

def main():
    init_db()

    scheduler = BlockingScheduler(timezone=TZ)

    # 0:00 JST
    scheduler.add_job(job_midnight, "cron", hour=0, minute=0)

    # 投稿時刻
    hh, mm = POST_TIME.split(":")
    scheduler.add_job(job_post, "cron", hour=int(hh), minute=int(mm))

    push_text("worker起動OK（予約稼働中）")
    scheduler.start()

if __name__ == "__main__":
    main()
