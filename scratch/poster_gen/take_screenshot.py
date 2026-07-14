from playwright.sync_api import sync_playwright
import os

html_path = "file://" + os.path.abspath("poster.html")
out_path = "/Users/nicksng/.gemini/antigravity-ide/brain/d5a704cb-df05-4e0d-b5f0-5303be3a20c2/EGD_Telegram_QR_ABA_Style.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    # High resolution scale factor (4x) for crisp printing
    context = browser.new_context(device_scale_factor=4)
    page = context.new_page()
    page.goto(html_path)
    
    # Wait for the JS QR code to render (the SVG)
    page.wait_for_selector("#qr-code-container svg")
    
    # Target the white card specifically so we don't get the background gradient unless they want it
    # We will screenshot the whole card with a transparent background!
    # Wait, the poster-card has rounded corners and a shadow. Screenshotting the element itself includes the shadow.
    element = page.locator(".poster-card")
    element.screenshot(path=out_path, omit_background=True)
    
    browser.close()

print(f"Saved super high-res PNG to {out_path}")
