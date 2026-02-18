from flask import Flask, request
import os

app = Flask(__name__)

SAVE_FILE = "threads_post.txt"

@app.route("/", methods=["GET"])
def home():
    return "OK"

@app.route("/callback", methods=["POST"])
def callback():
    data = request.json

    # LINEからのWebhookはここに入る
    events = data.get("events", [])

    for event in events:
        if event.get("type") == "message":
            message = event.get("message", {})
            if message.get("type") == "text":
                text = message.get("text")

                # 送られてきた文章をファイルに保存
                with open(SAVE_FILE, "w", encoding="utf-8") as f:
                    f.write(text)

    return "OK"

