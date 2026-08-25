from playwright.sync_api import sync_playwright

BASE = "https://www.schulministerium.nrw.de"
START_URL = BASE + "/BiPo/Stella/online?action=18.747518507714723&block=50&suchid=18143&stellenart=4_0"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    print("Öffne STELLA...")
    page.goto(START_URL, wait_until="networkidle", timeout=60000)

    print("Startseite geladen.")
    
    print("\n--- COOKIES ---")
    for cookie in context.cookies():
        print(
            "Name:", cookie["name"],
            "| Domain:", cookie["domain"],
            "| Path:", cookie["path"]
        )

    print("\n--- STELLA-LINK ---")
    link = page.get_by_text(
        "zu den Stellen im System Stella NRW",
        exact=False
    ).first

    print("Anzahl gefundener Links:", link.count())

    if link.count() == 0:
        print("FEHLER: Stellen-Link nicht gefunden!")
    else:
        print("Link gefunden.")
        print("HREF:", link.get_attribute("href"))
        print("TARGET:", link.get_attribute("target"))

        print("\nKlicke den Link wie ein normaler Benutzer...")

        link.click()

        # Kurz warten, damit STELLA reagieren kann
        page.wait_for_timeout(5000)

        print("\n--- NACH DEM KLICK ---")
        print("URL:", page.url)
        print("Titel:", page.title())

        print("\n--- SEITENINHALT ---")
        text = page.locator("body").inner_text()
        print(text[:30000])
        print("--- ENDE ---")

    browser.close()
