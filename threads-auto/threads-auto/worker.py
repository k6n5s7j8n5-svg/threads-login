import os
import base64
from playwright.sync_api import sync_playwright

def restore_storage():
    b64 = os.getenv("THREADS_STATE_B64")
    if not b64:
        print("THREADS_STATE_B64 not found")
        return

    data = base64.b64decode(b64)
    with open("threads_state.json", "wb") as f:
        f.write(data)

def post_to_threads(text):
    restore_storage()

    with sync_playwright() as p:
        browser = playwright.chromium.launch(
    headless=True,
    args=[
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu"
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
