from playwright.sync_api import sync_playwright
import json
import os
import re
from datetime import datetime


# ============================================================
# KONFIGURATION
# ============================================================

BASE = "https://www.schulministerium.nrw.de"

# ------------------------------------------------------------
# TESTORT
# ------------------------------------------------------------
# Zum Testen: Kleve
# Später für den normalen Betrieb auf Köln ändern:
#
# KÖLN: 315000
# KLEVE: 154036
# ------------------------------------------------------------

ORT_NAME = "Kleve"
ORT_VALUE = "154036"

# ------------------------------------------------------------
# Datei, in der bereits gemeldete Stellen gespeichert werden
# ------------------------------------------------------------

SEEN_FILE = "stella_bereits_gemeldet.json"


# ============================================================
# START-URL
# ============================================================

START_URL = (
    BASE
    + "/BiPo/Stella/online"
    + "?action=18.747518507714723"
    + "&block=50"
    + "&suchid=18143"
    + "&stellenart=4_0"
)


# ============================================================
# SCHLÜSSELWÖRTER FÜR SONDERPÄDAGOGIK
# ============================================================

SONDERPAEDAGOGIK_KEYWORDS = [
    "sonderpädagogische förderung",
    "sonderpädagogik",
    "sonderpädagogischen förderung",
    "lehramt für sonderpädagogische förderung",
    "lehramt für sonderpädagogik",
]


# ============================================================
# DATEI MIT BEREITS GEMELDETEN STELLEN LADEN
# ============================================================

def load_seen():
    if not os.path.exists(SEEN_FILE):
        return {}

    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        print("Fehler beim Laden der Merkliste:", e)
        return {}


# ============================================================
# DATEI MIT BEREITS GEMELDETEN STELLEN SPEICHERN
# ============================================================

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(
            seen,
            f,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# PRÜFEN, OB EINE STELLE ZU SONDERPÄDAGOGIK PASST
# ============================================================

def is_sonderpaedagogik(text):

    text_lower = text.lower()

    for keyword in SONDERPAEDAGOGIK_KEYWORDS:
        if keyword in text_lower:
            return True

    return False


# ============================================================
# EINE STABILE ID FÜR EINE STELLE ERZEUGEN
# ============================================================

def create_job_id(text):

    # Zuerst versuchen wir das Aktenzeichen zu finden.
    #
    # Beispiele:
    # 47.Z-FL4110A
    # 47.Z-FL4206A
    # 47.Z-FL4237A

    match = re.search(
        r"\b\d+\.[A-Z]-FL\d+[A-Z]?\b",
        text
    )

    if match:
        return match.group(0)

    # Falls kein Aktenzeichen gefunden wird,
    # verwenden wir den gesamten Text als Grundlage.

    normalized = " ".join(text.split())

    return normalized[:500]


# ============================================================
# STELLA ÖFFNEN UND SUCHE DURCHFÜHREN
# ============================================================

def search_stella(page):

    print("Öffne STELLA...")

    page.goto(
        START_URL,
        wait_until="networkidle",
        timeout=60000
    )

    print("Startseite geladen.")

    # --------------------------------------------------------
    # Zur Suchmaschine
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Fachleiter-Bereich
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Suchkriterien
    # --------------------------------------------------------

    # Fachleiter/-in
    page.locator("#artStelle").select_option("404")

    # Studienseminar
    page.locator("#institution").select_option("92")

    # Ort
    page.locator("#ort").select_option(ORT_VALUE)

    print(
        f"Suche: Fachleiter + Studienseminar + {ORT_NAME}"
    )

    # --------------------------------------------------------
    # Suche starten
    # --------------------------------------------------------

    page.locator(
        "input[name='button_suchen']"
    ).click()

    page.wait_for_load_state(
        "networkidle",
        timeout=60000
    )

    print("Suche abgeschlossen.")

    return page


# ============================================================
# STELLEN AUF DER ERGEBNISSEITE AUSLESEN
# ============================================================

def get_job_links(page):

    jobs = []

    links = page.locator("a")

    for i in range(links.count()):

        a = links.nth(i)

        try:
            text = a.inner_text().strip()
            href = a.get_attribute("href")

            if not text or not href:
                continue

            # Wir interessieren uns für
            # "Weitere Hinweise"-Links.
            #
            # Bei STELLA führen diese zu den Detailinformationen
            # der jeweiligen Stelle.

            if "Weitere Hinweise" in text:

                jobs.append({
                    "text": text,
                    "href": href
                })

        except Exception:
            pass

    return jobs


# ============================================================
# ABSOLUTEN LINK ERZEUGEN
# ============================================================

def make_absolute_url(href):

    if href.startswith("http"):
        return href

    if href.startswith("/"):
        return BASE + href

    return BASE + "/" + href


# ============================================================
# STELLENDETAILS AUSLESEN
# ============================================================

def read_job_detail(context, href):

    page = context.new_page()

    try:

        url = make_absolute_url(href)

        page.goto(
            url,
            wait_until="networkidle",
            timeout=60000
        )

        text = page.locator("body").inner_text()

        return {
            "url": page.url,
            "text": text
        }

    except Exception as e:

        print(
            "Fehler beim Lesen der Stelle:",
            e
        )

        return None

    finally:

        page.close()


# ============================================================
# HAUPTPROGRAMM
# ============================================================

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=True
    )

    context = browser.new_context()

    page = context.new_page()

    # --------------------------------------------------------
    # Bereits bekannte Stellen laden
    # --------------------------------------------------------

    seen = load_seen()

    print()
    print("========================================")
    print("BEREITS BEKANNTE STELLEN")
    print("========================================")

    print(
        "Anzahl:",
        len(seen)
    )

    # --------------------------------------------------------
    # STELLA SUCHE
    # --------------------------------------------------------

    search_stella(page)

    # --------------------------------------------------------
    # Ergebnisübersicht
    # --------------------------------------------------------

    print()
    print("========================================")
    print(f"ERGEBNISSE FÜR {ORT_NAME.upper()}")
    print("========================================")

    print(
        "URL:",
        page.url
    )

    # --------------------------------------------------------
    # Stellenlinks finden
    # --------------------------------------------------------

    jobs = get_job_links(page)

    print()
    print(
        "Gefundene Ausschreibungen:",
        len(jobs)
    )

    # --------------------------------------------------------
    # Jede Ausschreibung untersuchen
    # --------------------------------------------------------

    new_jobs = []

    for index, job in enumerate(jobs, start=1):

        print()
        print("----------------------------------------")
        print(
            f"Prüfe Ausschreibung {index}/{len(jobs)}"
        )
        print("----------------------------------------")

        detail = read_job_detail(
            context,
            job["href"]
        )

        if not detail:
            continue

        text = detail["text"]

        # ----------------------------------------------------
        # Sonderpädagogik-Filter
        # ----------------------------------------------------

        if not is_sonderpaedagogik(text):

            print(
                "→ Keine Sonderpädagogik-Stelle"
            )

            continue

        print(
            "→ SONDERPÄDAGOGIK-STELLE GEFUNDEN"
        )

        # ----------------------------------------------------
        # ID erzeugen
        # ----------------------------------------------------

        job_id = create_job_id(text)

        print(
            "ID:",
            job_id
        )

        # ----------------------------------------------------
        # Bereits gemeldet?
        # ----------------------------------------------------

        if job_id in seen:

            print(
                "→ Bereits bekannt – keine erneute Meldung"
            )

            continue

        # ----------------------------------------------------
        # Neue Stelle
        # ----------------------------------------------------

        print(
            "→ NEUE STELLE!"
        )

        job_data = {
            "id": job_id,
            "url": detail["url"],
            "gefunden_am": datetime.now().isoformat(
                timespec="seconds"
            ),
            "text": text
        }

        new_jobs.append(job_data)

        # ----------------------------------------------------
        # Sofort in Merkliste eintragen
        # ----------------------------------------------------
        #
        # Dadurch wird die Stelle nicht bei einem weiteren
        # Durchlauf erneut als neu erkannt.

        seen[job_id] = {
            "url": detail["url"],
            "erstmals_gefunden": job_data["gefunden_am"]
        }

        save_seen(seen)

    # ========================================================
    # ERGEBNIS
    # ========================================================

    print()
    print()
    print("========================================")
    print("NEUE SONDERPÄDAGOGIK-STELLEN")
    print("========================================")

    if not new_jobs:

        print()
        print(
            "Keine neuen passenden Stellen gefunden."
        )

    else:

        print()
        print(
            f"{len(new_jobs)} neue Stelle(n) gefunden!"
        )

        for i, job in enumerate(
            new_jobs,
            start=1
        ):

            print()
            print("########################################")
            print(
                f"NEUE STELLE {i}"
            )
            print("########################################")

            print()
            print(
                "ID:",
                job["id"]
            )

            print()
            print(
                "URL:",
                job["url"]
            )

            print()
            print(
                "KOMPLETTER AUSSCHREIBUNGSTEXT:"
            )

            print("----------------------------------------")
            print(job["text"])
            print("----------------------------------------")

    # ========================================================
    # ENDE
    # ========================================================

    print()
    print("========================================")
    print("CHECK BEENDET")
    print("========================================")

    browser.close()
