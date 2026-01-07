# tests/approve_flow.py
import os
from playwright.sync_api import Page, expect

def test_approve_flow(page: Page):
    base = os.getenv("BASE_URL", "http://127.0.0.1:8004")
    page.goto(f"{base}/", wait_until="domcontentloaded")

    # Detail page
    first_link = page.locator("#list a").first
    expect(first_link).to_be_visible()
    first_link.click()

    # Detail→Approve
    btn = page.locator("button#approve")
    expect(btn).to_be_visible()
    btn.click()

    # Approved status
    status = page.locator("#status")
    expect(status).to_contain_text("Approved", timeout=5000)
