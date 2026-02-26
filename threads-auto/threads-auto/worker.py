import os
import base64
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

STATE_PATH = Path("threads_state.json")
THREADS_COMPOSE_URL = "https://www.threads.com/compose/post"


def restore_storage_state() -> None:
    b64 = os.getenv("THREADS_STATE_B64", "").strip()
    if not b64:
        raise RuntimeError("THREADS_STATE_B64 is missing. Set it in Railway Variables.")
    STATE_PATH.write_bytes(base64.b64decode(b64))


def get_post_text() -> str:
    text = os.getenv("POST_TEXT", "").strip()
    if not text:
        raise RuntimeError("POST_TEXT is missing. Set it in Railway Variables.")
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


def post_once(text: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=launch_args())
        context = browser.new_context(storage_state=str(STATE_PATH))
        page = context.new_page()

        try:
            print("[goto] compose page...")
            page.goto(
                THREADS_COMPOSE_URL,
                wait_until="domcontentloaded",
                timeout=180000,
            )
            print("[url]", page.url)

            if "login" in page.url or "accounts" in page.url:
                raise RuntimeError("Login seems required. Recreate THREADS_STATE_B64.")

            editor = page.locator('div[contenteditable="true"]').first
            editor.wait_for(state="visible", timeout=120000)
            editor.click()
            editor.fill(text)

            # ボタン候補（UI変更に備えて複数）
            candidates = [
                'button:has-text("投稿")',
                'button:has-text("Post")',
                'div[role="button"]:has-text("投稿")',
                'div[role="button"]:has-text("Post")',
            ]
            btn = None
            for sel in candidates:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    btn = loc
                    break

            if btn is None:
                raise RuntimeError("Post button not found (UI changed).")

            btn.click()
            page.wait_for_timeout(3000)
            print("[ok] clicked post")

        except PWTimeoutError as e:
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


def main() -> None:
    restore_storage_state()
    text = get_post_text()

    retries = int(os.getenv("RETRIES", "2"))
    backoff = int(os.getenv("BACKOFF_SEC", "6"))

    last_err = None
    for i in range(retries + 1):
        try:
            print(f"[try] {i + 1}/{retries + 1}")
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
