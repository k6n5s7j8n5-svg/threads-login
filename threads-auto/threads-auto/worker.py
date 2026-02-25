import os
import base64
from playwright.sync_api import sync_playwright

def restore_storage():
    b64 = os.getenv("THREADS_STATE_B64")
    if not b64:
        print("THREADS_STATE_B64 not found")
        return False

    data = base64.b64decode(b64)
    with open("threads_state.json", "wb") as f:
        f.write(data)
    return True

def post_to_threads(text):
    if not restore_storage():
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
            ],
        )

        context = browser.new_context(storage_state="threads_state.json")
        page = context.new_page()

        page.goto("https://www.threads.net/")
        page.wait_for_timeout(5000)

        page.click("text=Start a thread")
        page.fill("textarea", text)
        page.click("text=Post")

        page.wait_for_timeout(3000)
        browser.close()

if __name__ == "__main__":
    post_to_threads("テスト投稿 from Railway")
