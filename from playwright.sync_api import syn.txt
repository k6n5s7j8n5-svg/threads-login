from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto("https://www.threads.net/")
    print("ログインしてホーム画面が出たら Enter を押して")
    input()

    context.storage_state(path="threads_state.json")
    print("保存完了: threads_state.json")
    browser.close()