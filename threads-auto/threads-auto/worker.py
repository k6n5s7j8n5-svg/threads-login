import os
import base64
import re
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

STATE_PATH = "threads_state.json"

def restore_storage():
    b64 = os.getenv("THREADS_STATE_B64")
    if not b64:
        print("THREADS_STATE_B64 not found")
        return False

    data = base64.b64decode(b64)
    with open(STATE_PATH, "wb") as f:
        f.write(data)
    return True

def post_to_threads(text: str):
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
            ],
        )

        context = browser.new_context(storage_state=STATE_PATH)
        page = context.new_page()

        # まず投稿画面へ直行（UI文言依存を排除）
        page.goto("https://www.threads.net/compose/post", wait_until="domcontentloaded")

        # もしログイン切れてたらログインに飛ばされる
        page.wait_for_timeout(3000)
        print("Current URL:", page.url)
        if "login" in page.url:
            print("Not logged in (storage_state invalid). Re-generate THREADS_STATE_B64.")
            browser.close()
            return

        try:
            # Threadsはtextareaじゃなく role=textbox のことが多い
            box = page.get_by_role("textbox").first
            box.wait_for(state="visible", timeout=60000)
            box.fill(text)

            # Post / 投稿 ボタン（どっちでも拾う）
            btn = page.get_by_role("button", name=re.compile(r"(Post|投稿)"))
            btn.wait_for(state="visible", timeout=60000)
            btn.click()

            page.wait_for_timeout(5000)
            print("Posted OK (maybe).")

        except PWTimeout as e:
            print("Timeout:", e)
            print("URL at timeout:", page.url)

        finally:
            browser.close()

if __name__ == "__main__":
    post_to_threads("テスト投稿 from Railway")
    
