from playwright.sync_api import sync_playwright

BASE = "https://www.schulministerium.nrw.de"

START_URL = (
    BASE
    + "/BiPo/Stella/online"
    + "?action=18.747518507714723"
    + "&block=50"
    + "&suchid=18143"
    + "&stellenart=4_0"
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    print("Öffne STELLA...")

    page.goto(
        START_URL,
        wait_until="networkidle",
        timeout=60000
    )

    # Suchmaschine
    link = page.get_by_text(
        "zu den Stellen im System Stella NRW",
        exact=False
    ).first

    link.click()
    page.wait_for_load_state("networkidle", timeout=60000)

    # Fachleiter
    fachleiter = page.get_by_text(
        "Stellen an Zentren für schulpraktische Lehrerausbildung/Fachleiterausschreibung",
        exact=False
    ).first

    fachleiter.click()
    page.wait_for_load_state("networkidle", timeout=60000)

    # Suchkriterien
    page.locator("#artStelle").select_option("404")
    page.locator("#institution").select_option("92")
    page.locator("#ort").select_option("315000")

    # Suche
    page.locator("input[name='button_suchen']").click()

    page.wait_for_load_state("networkidle", timeout=60000)

    print("\n========================================")
    print("ERGEBNISSE")
    print("========================================")

    print("URL:", page.url)

    # ALLE Links der Ergebnisse
    print("\n--- LINKS IM ERGEBNIS ---")

    for i, a in enumerate(page.locator("a").all()):
        try:
            text = a.inner_text().strip().replace("\n", " ")
            href = a.get_attribute("href")

            if text:
                print(f"\nLINK {i}")
                print("TEXT:", text)
                print("HREF:", href)

        except:
            pass

    print("\n--- KOMPLETTER TEXT ---")

    text = page.locator("body").inner_text()

    print(text[:50000])

    browser.close()
