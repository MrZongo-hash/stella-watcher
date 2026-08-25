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

    # --------------------------------------------------
    # 1. STELLA öffnen
    # --------------------------------------------------

    page.goto(
        START_URL,
        wait_until="networkidle",
        timeout=60000
    )

    print("Startseite geladen.")

    # --------------------------------------------------
    # 2. Zur Suchmaschine
    # --------------------------------------------------

    link = page.get_by_text(
        "zu den Stellen im System Stella NRW",
        exact=False
    ).first

    link.click()

    page.wait_for_load_state(
        "networkidle",
        timeout=60000
    )

    print("Suchmaschine geöffnet.")

    # --------------------------------------------------
    # 3. Fachleiter-Bereich
    # --------------------------------------------------

    fachleiter = page.get_by_text(
        "Stellen an Zentren für schulpraktische Lehrerausbildung/Fachleiterausschreibung",
        exact=False
    ).first

    fachleiter.click()

    page.wait_for_load_state(
        "networkidle",
        timeout=60000
    )

    print("Fachleiter-Suche geöffnet.")
    print("URL:", page.url)

    # --------------------------------------------------
    # 4. Suchkriterien
    # --------------------------------------------------

    # Fachleiter/-in
    page.locator("#artStelle").select_option("404")

    # Studienseminar
    page.locator("#institution").select_option("92")

    # KLEVE
    page.locator("#ort").select_option("154036")

    print("Suche: Fachleiter + Studienseminar + Kleve")

    # --------------------------------------------------
    # 5. Suche starten
    # --------------------------------------------------

    page.locator("input[name='button_suchen']").click()

    page.wait_for_load_state(
        "networkidle",
        timeout=60000
    )

    print("\n========================================")
    print("ERGEBNISSE FÜR KLEVE")
    print("========================================")

    print("URL:", page.url)
    print("Titel:", page.title())

    # --------------------------------------------------
    # 6. Alle Links im Ergebnis untersuchen
    # --------------------------------------------------

    print("\n========================================")
    print("LINKS IM ERGEBNIS")
    print("========================================")

    links = page.locator("a")

    print("Anzahl Links:", links.count())

    for i in range(links.count()):
        a = links.nth(i)

        try:
            text = a.inner_text().strip().replace("\n", " ")
            href = a.get_attribute("href")

            if text:
                print(f"\nLINK {i}")
                print("TEXT:", text)
                print("HREF:", href)

        except Exception:
            pass

    # --------------------------------------------------
    # 7. Kompletter Seiteninhalt
    # --------------------------------------------------

    print("\n========================================")
    print("KOMPLETTER STELLA-INHALT")
    print("========================================")

    text = page.locator("body").inner_text()

    print(text[:50000])

    print("\n========================================")
    print("TEST BEENDET")
    print("========================================")

    browser.close()
