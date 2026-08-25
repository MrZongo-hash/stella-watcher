from playwright.sync_api import sync_playwright

URL = "https://www.schulministerium.nrw.de/BiPo/Stella/online?action=18.747518507714723&block=50&suchid=18143&stellenart=4_0"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    print("Öffne STELLA...")
    page.goto(URL, wait_until="networkidle", timeout=60000)

    print("Startseite:", page.url)

    # Alle Links anzeigen, damit wir den richtigen Einstieg finden
    print("\n--- LINKS AUF DER STARTSEITE ---")
    for link in page.locator("a").all():
        try:
            text = link.inner_text().strip().replace("\n", " ")
            href = link.get_attribute("href")
            if text:
                print(f"TEXT: {text} | HREF: {href}")
        except:
            pass

    print("\n--- KLICKE AUF STELLENAUSSCHREIBUNGEN ---")

    # Prüfen, ob der Link vorhanden ist
    link = page.get_by_text("Stellenausschreibungen", exact=False).first

    if link.count() == 0:
        print("FEHLER: Link nicht gefunden!")
    else:
        print("Link gefunden.")

        # Öffnet der Link ein neues Fenster?
        with context.expect_page(timeout=15000) as new_page_info:
            link.click()

        new_page = new_page_info.value
        new_page.wait_for_load_state("networkidle", timeout=60000)

        print("\n--- NEUE STELLA-SEITE ---")
        print("URL:", new_page.url)
        print("Titel:", new_page.title())

        text = new_page.locator("body").inner_text()

        print("\n--- STELLA-ERGEBNIS ---")
        print(text[:20000])
        print("--- ENDE ---")

    browser.close()
