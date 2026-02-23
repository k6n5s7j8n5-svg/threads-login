from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page()
    page.goto("https://example.com")
    print("TITLE:", page.title())
    browser.close()
