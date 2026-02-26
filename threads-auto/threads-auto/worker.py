import os
import base64
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

STATE_PATH = Path("threads_state.json")
SCREENSHOT_DIR = Path("screens")
SCREENSHOT_DIR.mkdir(exist_ok=True)

THREADS_COMPOSE_URL = "https://www.threads.com/compose/post"

def restore_storage_state() -> None:
    b64 = os.getenv("THREADS_STATE_B64", "").strip()
    if not b64:
        raise RuntimeError("THREADS_STATE_B64 is missing. Set it in Railway Variables.")

    data = base64.b64decode(b64)
    STATE_PATH.write_bytes(data)

def get_post_text() -> str:
    text = os.getenv("POST_TEXT", "").strip()
    if not text:
        raise RuntimeError("POST_TEXT is missing. Set it in Railway Variables.")
    # Threadsの上限は変動しうるので長すぎると失敗する。念のため。
    return text[:480]

def launch_args() -> list[str]:
    return [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--no-zygote",
        "--single-process",
    ]

def take_screenshot(page, name: str) -> None:
    ts = int(time.time())
    path = SCREENSHOT_DIR / f"{ts}_{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        print(f"[screenshot] saved: {path}")
    except Exception as e:
        print(f"[screenshot] failed: {e}")

def post_once(text: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=launch_args())
        context = p.chromium.new_context(
            storage_state=str(STATE_PATH),
            viewport={"width": 1280, "height": 720},
            user_agent=os.getenv("UA_OVERRIDE") or None,
        )
        page = context.new_page()

        try:
            print("[goto] opening compose...")
            page.goto(THREADS_COMPOSE_URL, wait_until="domcontentloaded", timeout=180000)
            print("[url]", page.url)

            # ログイン切れだと /login などへ飛ぶ
            if "login" in page.url or "accounts" in page.url:
                take_screenshot(page, "login_redirect")
                raise RuntimeError("Login state seems expired. Re-generate THREADS_STATE_B64.")

            # エディタ（contenteditable）を探す
            editor = page.locator('div[contenteditable="true"]').first
            editor.wait_for(state="visible", timeout=120000)

            editor.click()
            editor.fill(text)

            # 投稿ボタン（文言は言語で変わるので、役割寄りに探す）
            # ThreadsはUI変更があるので複数候補で拾う
            candidates = [
                'button:has-text("投稿")',
                'button:has-text("Post")',
                'div[role="button"]:has-text("投稿")',
                'div[role="button"]:has-text("Post")',
            ]
            post_btn = None
            for sel in candidates:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    post_btn = loc
                    break

            if post_btn is None:
                take_screenshot(page, "post_button_not_found")
                raise RuntimeError("Post button not found (UI changed).")

            # クリック
            post_btn.click()

            # 投稿完了の判定：URL遷移 or エディタが空になる等、複数で待つ
            # 重い環境向けにゆるく待つ
            page.wait_for_timeout(2500)

            print("[ok] clicked post. (No strict confirmation to avoid long waits)")
            take_screenshot(page, "after_post")

        except PWTimeoutError as e:
            take_screenshot(page, "timeout")
            raise RuntimeError(f"Playwright timeout: {e}") from e
        finally:
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

def main():
    restore_storage_state()
    text = get_post_text()

    retries = int(os.getenv("RETRIES", "2"))
    backoff = int(os.getenv("BACKOFF_SEC", "6"))

    last_err = None
    for i in range(retries + 1):
        try:
            print(f"[try] {i+1}/{retries+1}")
            post_once(text)
            print("[done] success")
            return
        except Exception as e:
            last_err = e
            print("[error]", repr(e))
            if i < retries:
                time.sleep(backoff * (i + 1))

    raise SystemExit(f"Failed after retries: {last_err}")

if __name__ == "__main__":
    main()
