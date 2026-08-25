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

    # Zum Suchmaschinen-Bereich
    link = page.get_by_text(
        "zu den Stellen im System Stella NRW",
        exact=False
    ).first

    print("Klicke auf: zu den Stellen im System Stella NRW")
    link.click()
    page.wait_for_load_state("networkidle", timeout=60000)

    print("Suchmaschinen-Seite:", page.url)

    # Alle Links dieser Seite ausgeben
    print("\n--- LINKS DER SUCHMASCHINE ---")

    for link in page.locator("a").all():
        try:
            text = link.inner_text().strip().replace("\n", " ")
            href = link.get_attribute("href")

            if text:
                print(f"TEXT: {text}")
                print(f"HREF: {href}")
                print()
        except:
            pass

    # Den Fachleiter-Bereich anklicken
    fachleiter = page.get_by_text(
        "Stellen an Zentren für schulpraktische Lehrerausbildung/Fachleiterausschreibung",
        exact=False
    ).first

    print("--- FACHLEITER-BEREICH ---")
    print("Gefunden:", fachleiter.count())

    if fachleiter.count() > 0:
        print("HREF:", fachleiter.get_attribute("href"))

        fachleiter.click()
        page.wait_for_load_state("networkidle", timeout=60000)

        print("\n--- FACHLEITER-SUCHE ---")
        print("URL:", page.url)
        print("Titel:", page.title())

        text = page.locator("body").inner_text()

        print("\n--- INHALT ---")
        print(text[:30000])
        print("--- ENDE ---")

    else:
        print("Fachleiter-Bereich nicht gefunden!")

    browser.close()
