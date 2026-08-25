from playwright.sync_api import sync_playwright

BASE = "https://www.schulministerium.nrw.de"
START_URL = BASE + "/BiPo/Stella/online?action=18.747518507714723&block=50&suchid=18143&stellenart=4_0"
STELLA_URL = BASE + "/BiPo/Stella/online?action=584.5405792950158"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # Eine gemeinsame Sitzung verwenden
    context = browser.new_context()
    page = context.new_page()

    print("Öffne STELLA-Startseite...")
    page.goto(START_URL, wait_until="networkidle", timeout=60000)

    print("Startseite geladen.")
    print("Cookies:", len(context.cookies()))

    print("\nNavigiere zu den Stellen...")
    page.goto(STELLA_URL, wait_until="networkidle", timeout=60000)

    print("\n--- STELLA STELLENLISTE ---")
    print("URL:", page.url)
    print("Titel:", page.title())

    text = page.locator("body").inner_text()

    print("\n--- INHALT ---")
    print(text[:30000])
    print("--- ENDE ---")

    browser.close()
