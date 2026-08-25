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

    # Zur Suchmaschine
    link = page.get_by_text(
        "zu den Stellen im System Stella NRW",
        exact=False
    ).first

    link.click()
    page.wait_for_load_state("networkidle", timeout=60000)

    # Fachleiter-Bereich
    fachleiter = page.get_by_text(
        "Stellen an Zentren für schulpraktische Lehrerausbildung/Fachleiterausschreibung",
        exact=False
    ).first

    fachleiter.click()
    page.wait_for_load_state("networkidle", timeout=60000)

    print("Fachleiter-Suche geöffnet.")

    # Fachleiter
    page.locator("#artStelle").select_option("404")

    # Studienseminar
    page.locator("#institution").select_option("92")

    # NUR KÖLN
    page.locator("#ort").select_option("315000")

    print("Suche: Fachleiter + Studienseminar + Köln")

    # Suche starten
    page.locator("input[name='button_suchen']").click()

    page.wait_for_load_state("networkidle", timeout=60000)

    print("\n========================================")
    print("ERGEBNISSE FÜR KÖLN")
    print("========================================")

    print("URL:", page.url)

    text = page.locator("body").inner_text()

    print(text[:50000])

    browser.close()
