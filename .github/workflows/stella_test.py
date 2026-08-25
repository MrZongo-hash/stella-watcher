from playwright.sync_api import sync_playwright

URL = "https://www.schulministerium.nrw.de/BiPo/Stella/online?action=18.747518507714723&block=50&suchid=18143&stellenart=4_0"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    print("Öffne STELLA...")
    page.goto(URL, wait_until="networkidle", timeout=60000)

    print("Titel:", page.title())
    print("URL:", page.url)

    text = page.locator("body").inner_text()

    print("\n--- STELLA-INHALT ---")
    print(text[:10000])
    print("--- ENDE ---")

    browser.close()
