import os
import base64
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

STATE_PATH = Path("threads_state.json")
THREADS_URL = "https://www.threads.com/compose/post"


def restore_state():
    b64 = os.getenv("THREADS_STATE_B64")
    if not b64:
        raise RuntimeError("THREADS_STATE_B64 missing")
    STATE_PATH.write_bytes(base64.b64decode(b64))


def get_text():
    text = os.getenv("POST_TEXT")
    if not text:
        raise RuntimeError("POST_TEXT missing")
    return text


def post(text):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        context = browser.new_context(storage_state=str(STATE_PATH))
        page = context.new_page()

        page.goto(THREADS_URL, wait_until="domcontentloaded", timeout=180000)

        editor = page.locator('div[contenteditable="true"]').first
        editor.wait_for(state="visible", timeout=60000)
        editor.click()
        editor.fill(text)

        page.locator('button:has-text("投稿"), button:has-text("Post")').first.click()

        page.wait_for_timeout(3000)

        browser.close()


if __name__ == "__main__":
    restore_state()
    text = get_text()
    post(text)
