from playwright.sync_api import sync_playwright

BASE = "https://www.schulministerium.nrw.de"
START_URL = BASE + "/BiPo/Stella/online?action=18.747518507714723&block=50&suchid=18143&stellenart=4_0"


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    print("Öffne STELLA...")
    page.goto(START_URL, wait_until="networkidle", timeout=60000)

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

    print("\n--- FACHLEITER-SUCHMASKE ---")
    print("URL:", page.url)

    # Alle Select-Felder untersuchen
    print("\n--- AUSWAHLMENÜS (SELECT) ---")

    selects = page.locator("select")

    print("Anzahl Selects:", selects.count())

    for i in range(selects.count()):
        select = selects.nth(i)

        print(f"\nSELECT {i}")
        print("Name:", select.get_attribute("name"))
        print("ID:", select.get_attribute("id"))

        options = select.locator("option")

        for j in range(options.count()):
            option = options.nth(j)

            text = option.inner_text().strip()
            value = option.get_attribute("value")

            print(f"  OPTION {j}: {text} | VALUE: {value}")

    # Alle Eingabefelder untersuchen
    print("\n--- INPUT-FELDER ---")

    inputs = page.locator("input")

    print("Anzahl Inputs:", inputs.count())

    for i in range(inputs.count()):
        inp = inputs.nth(i)

        print(
            f"INPUT {i}: "
            f"type={inp.get_attribute('type')} | "
            f"name={inp.get_attribute('name')} | "
            f"id={inp.get_attribute('id')} | "
            f"value={inp.get_attribute('value')}"
        )

    # Buttons
    print("\n--- BUTTONS ---")

    buttons = page.locator("button, input[type='submit'], input[type='button']")

    print("Anzahl Buttons:", buttons.count())

    for i in range(buttons.count()):
        button = buttons.nth(i)

        print(
            f"BUTTON {i}: "
            f"text={button.inner_text().strip()} | "
            f"type={button.get_attribute('type')} | "
            f"name={button.get_attribute('name')} | "
            f"value={button.get_attribute('value')}"
        )

    print("\n--- TEST ENDE ---")

    browser.close()
