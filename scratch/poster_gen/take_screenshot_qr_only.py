from playwright.sync_api import sync_playwright
import os

html_path = "file://" + os.path.abspath("poster.html")
out_path = "/Users/nicksng/.gemini/antigravity-ide/brain/d5a704cb-df05-4e0d-b5f0-5303be3a20c2/EGD_Telegram_QR_ABA_Style_Only.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(device_scale_factor=4)
    page = context.new_page()
    page.goto(html_path)
    
    # Wait for the JS QR code to render
    page.wait_for_selector("#qr-code-container svg")
    
    # Target ONLY the QR Code container
    element = page.locator("#qr-code-container")
    element.screenshot(path=out_path, omit_background=True)
    
    browser.close()

print(f"Saved super high-res PNG to {out_path}")
