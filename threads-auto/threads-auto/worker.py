import os
import base64
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

    print("storage_state restored:", STATE_PATH)
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

        context = browser.new_context(
            storage_state=STATE_PATH,
            viewport={"width": 1280, "height": 720},
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
        )

        # タイムアウト長め（Threads重い対策）
        context.set_default_timeout(180000)          # 180秒
        context.set_default_navigation_timeout(180000)

        page = context.new_page()

        try:
            print("goto compose...")
            page.goto("https://www.threads.com/compose/post", wait_until="domcontentloaded")

            # 投稿ボックス（textareaではないことが多い）
            textbox = page.locator('div[role="textbox"]').first
            textbox.wait_for(state="visible", timeout=180000)
            textbox.click()
            textbox.fill(text)

            # Postボタン（文言が変わる可能性あるので複数候補）
            post_btn = page.locator('button:has-text("Post"), button:has-text("投稿")').first
            post_btn.wait_for(state="visible", timeout=180000)
            post_btn.click()

            # 投稿完了っぽい状態まで少し待つ
            page.wait_for_timeout(5000)
            print("post click done ✅")

        except PWTimeout as e:
            print("TIMEOUT:", str(e))
            print("Current URL:", page.url)
            # デバッグ用（ログに出る）
            print("Title:", page.title())

        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    post_to_threads("テスト投稿 from Railway")
