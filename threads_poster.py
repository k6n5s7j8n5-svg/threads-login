import base64
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

STATE_PATH = Path("/app/threads_state.json")
THREADS_URL = "https://www.threads.net/compose/post"

def restore_state_from_env():
    b64 = os.getenv("THREADS_STATE_B64", "")
    if not b64:
        raise RuntimeError("THREADS_STATE_B64 is missing")
    data = base64.b64decode(b64)
    STATE_PATH.write_bytes(data)

def post_to_threads(text: str):
    restore_state_from_env()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        context = browser.new_context(storage_state=str(STATE_PATH))
        page = context.new_page()

        page.goto(THREADS_URL, wait_until="domcontentloaded", timeout=180000)

        # editor (contenteditable)
        editor = page.locator("div[contenteditable='true']").first
        editor.wait_for(state="visible", timeout=120000)
        editor.click()
        editor.fill(text)

        # Post button (JP/EN)
        page.locator("button:has-text('投稿'), button:has-text('Post')").first.click()
        page.wait_for_timeout(4000)

        browser.close()
