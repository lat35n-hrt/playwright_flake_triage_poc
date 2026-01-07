import os
from playwright.sync_api import sync_playwright
from backend.e2e.flows.approve_flow import run_approve_flow


def main() -> None:
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:8004")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        run_approve_flow(page, base_url=base_url)
        browser.close()

if __name__ == "__main__":
    main()
