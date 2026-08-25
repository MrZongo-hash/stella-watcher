```python
from playwright.sync_api import sync_playwright
import json
import os
import re
from datetime import datetime


# ============================================================
# KONFIGURATION
# ============================================================

BASE = "https://www.schulministerium.nrw.de"


# ============================================================
# TESTORT
# ============================================================
# Zunächst Kleve zum Testen.
#
# Wenn alles funktioniert:
#
# ORT_NAME = "Köln"
# ORT_VALUE = "315000"
# ============================================================

ORT_NAME = "Kleve"
ORT_VALUE = "154036"


# Datei mit bereits gemeldeten Stellen
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
# SCHLÜSSELWÖRTER
# ============================================================

SONDERPAEDAGOGIK_KEYWORDS = [
    "sonderpädagogische förderung",
    "sonderpädagogischen förderung",
    "sonderpädagogik",
    "sonderpädagogischen",
    "lehramt für sonderpädagogische förderung",
    "lehramt für sonderpädagogik",
    "seminar für das lehramt für sonderpädagogische förderung",
    "seminar für das lehramt für sonderpädagogik",
]


# ============================================================
# MERKLISTE LADEN
# ============================================================

def load_seen():

    if not os.path.exists(SEEN_FILE):
        return {}

    try:

        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

            if isinstance(data, dict):
                return data

            return {}

    except Exception as e:

        print(
            "Fehler beim Laden der Merkliste:",
            e
        )

        return {}


# ============================================================
# MERKLISTE SPEICHERN
# ============================================================

def save_seen(seen):

    try:

        with open(
            SEEN_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                seen,
                f,
                ensure_ascii=False,
                indent=2
            )

        return True

    except Exception as e:

        print(
            "FEHLER beim Speichern der Merkliste:",
            e
        )

        return False


# ============================================================
# SONDERPÄDAGOGIK ERKENNEN
# ============================================================

def is_sonderpaedagogik(text):

    text_lower = text.lower()

    for keyword in SONDERPAEDAGOGIK_KEYWORDS:

        if keyword in text_lower:
            return True

    return False


# ============================================================
# AKTENZEICHEN SUCHEN
# ============================================================

def extract_aktenzeichen(text):

    patterns = [

        # z.B. 47.Z-FL4206A
        r"\b\d+\.[A-Z]-FL\d+[A-Z]?\b",

        # etwas großzügiger
        r"\b\d+\.[A-Z]+-FL\d+[A-Z]?\b",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(0)

    return None


# ============================================================
# STABILE ID ERZEUGEN
# ============================================================

def create_job_id(text):

    aktenzeichen = extract_aktenzeichen(text)

    if aktenzeichen:

        return aktenzeichen.upper()

    # Falls aus irgendeinem Grund kein Aktenzeichen
    # gefunden wird, erzeugen wir eine Ersatz-ID.

    normalized = " ".join(
        text.split()
    )

    return (
        "NO_AKTENZEICHEN_"
        + normalized[:300]
    )


# ============================================================
# STELLA ÖFFNEN
# ============================================================

def open_stella(page):

    print("Öffne STELLA...")

    page.goto(
        START_URL,
        wait_until="networkidle",
        timeout=60000
    )

    print("Startseite geladen.")

    # --------------------------------------------------------
    # Suchmaschine
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
    # Fachleiter
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


# ============================================================
# SUCHE DURCHFÜHREN
# ============================================================

def search_stella(page):

    # Fachleiter/-in
    page.locator(
        "#artStelle"
    ).select_option("404")

    # Studienseminar
    page.locator(
        "#institution"
    ).select_option("92")

    # Ort
    page.locator(
        "#ort"
    ).select_option(ORT_VALUE)

    print()
    print(
        f"Suche: Fachleiter + Studienseminar + {ORT_NAME}"
    )

    page.locator(
        "input[name='button_suchen']"
    ).click()

    page.wait_for_load_state(
        "networkidle",
        timeout=60000
    )

    print("Suche abgeschlossen.")


# ============================================================
# ERGEBNISSE AUSLESEN
# ============================================================

def get_result_rows(page):

    """
    Liest die Ausschreibungen aus der Ergebnis-Tabelle.

    Wir suchen dabei nicht nach 'Weitere Hinweise',
    sondern nach Tabellenzeilen, damit die komplette
    Ausschreibung zusammenbleibt.
    """

    rows = page.locator("tr")

    results = []

    count = rows.count()

    print()
    print(
        "Gefundene Tabellenzeilen:",
        count
    )

    for i in range(count):

        row = rows.nth(i)

        try:

            text = row.inner_text().strip()

        except Exception:

            continue

        if not text:
            continue

        text_lower = text.lower()

        # ----------------------------------------------------
        # Nur relevante Ausschreibungszeilen
        # ----------------------------------------------------

        if (
            "fachleiter" not in text_lower
            and "fachleiter/-in" not in text_lower
        ):
            continue

        # Kopfzeile ignorieren
        if "stellenbezeichnung" in text_lower:
            continue

        results.append({
            "text": text
        })

    return results


# ============================================================
# DETAILSEITE ÖFFNEN
# ============================================================

def read_detail_page(
    context,
    href
):

    page = context.new_page()

    try:

        if href.startswith("http"):

            url = href

        elif href.startswith("/"):

            url = BASE + href

        else:

            url = BASE + "/" + href

        page.goto(
            url,
            wait_until="networkidle",
            timeout=60000
        )

        text = page.locator(
            "body"
        ).inner_text()

        return {
            "url": page.url,
            "text": text
        }

    except Exception as e:

        print(
            "Fehler beim Öffnen der Detailseite:",
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

    try:

        # ----------------------------------------------------
        # Merkliste
        # ----------------------------------------------------

        seen = load_seen()

        print()
        print("========================================")
        print("BEREITS BEKANNTE STELLEN")
        print("========================================")

        print(
            "Anzahl:",
            len(seen)
        )

        # ----------------------------------------------------
        # STELLA
        # ----------------------------------------------------

        open_stella(page)

        search_stella(page)

        # ----------------------------------------------------
        # Ergebnis
        # ----------------------------------------------------

        print()
        print("========================================")
        print(
            f"ERGEBNISSE FÜR {ORT_NAME.upper()}"
        )
        print("========================================")

        print(
            "URL:",
            page.url
        )

        # ----------------------------------------------------
        # Ausschreibungen auslesen
        # ----------------------------------------------------

        results = get_result_rows(page)

        print()
        print(
            "Gefundene Ausschreibungen:",
            len(results)
        )

        # ----------------------------------------------------
        # Ergebnisse prüfen
        # ----------------------------------------------------

        new_jobs = []

        # Kopie der Merkliste.
        # Änderungen werden erst nach erfolgreicher
        # Verarbeitung dauerhaft gespeichert.
        updated_seen = dict(seen)

        for index, result in enumerate(
            results,
            start=1
        ):

            print()
            print("----------------------------------------")
            print(
                f"Prüfe Ausschreibung {index}/{len(results)}"
            )
            print("----------------------------------------")

            result_text = result["text"]

            # ------------------------------------------------
            # Sonderpädagogik prüfen
            # ------------------------------------------------

            if not is_sonderpaedagogik(
                result_text
            ):

                print(
                    "→ Keine Sonderpädagogik-Stelle"
                )

                continue

            print(
                "→ SONDERPÄDAGOGIK-STELLE GEFUNDEN"
            )

            # ------------------------------------------------
            # ID
            # ------------------------------------------------

            job_id = create_job_id(
                result_text
            )

            print(
                "ID:",
                job_id
            )

            # ------------------------------------------------
            # Bereits bekannt?
            # ------------------------------------------------

            if job_id in seen:

                print(
                    "→ Bereits bekannt – keine erneute Meldung"
                )

                continue

            # ------------------------------------------------
            # Detailseite suchen
            # ------------------------------------------------

            detail_url = None

            rows = page.locator("tr")

            for r in range(rows.count()):

                row = rows.nth(r)

                try:

                    row_text = row.inner_text().strip()

                except Exception:

                    continue

                if job_id.lower() in row_text.lower():

                    anchors = row.locator("a")

                    for a_index in range(
                        anchors.count()
                    ):

                        a = anchors.nth(
                            a_index
                        )

                        try:

                            link_text = (
                                a.inner_text()
                                .strip()
                            )

                            href = (
                                a.get_attribute(
                                    "href"
                                )
                            )

                            if (
                                "Weitere Hinweise"
                                in link_text
                                and href
                            ):

                                detail_url = href

                                break

                        except Exception:

                            pass

                if detail_url:
                    break

            # ------------------------------------------------
            # Detailtext laden
            # ------------------------------------------------

            detail_text = result_text

            detail_page_url = page.url

            if detail_url:

                detail = read_detail_page(
                    context,
                    detail_url
                )

                if detail:

                    detail_text = detail["text"]

                    detail_page_url = detail["url"]

            # ------------------------------------------------
            # Neue Stelle
            # ------------------------------------------------

            print(
                "→ NEUE STELLE!"
            )

            timestamp = datetime.now().isoformat(
                timespec="seconds"
            )

            job_data = {

                "id": job_id,

                "url": detail_page_url,

                "gefunden_am": timestamp,

                "text": detail_text
            }

            new_jobs.append(
                job_data
            )

            # Noch NICHT dauerhaft speichern.
            updated_seen[job_id] = {

                "url": detail_page_url,

                "erstmals_gefunden": timestamp
            }

        # ----------------------------------------------------
        # Neue Stellen dauerhaft speichern
        # ----------------------------------------------------
        #
        # Für den jetzigen Test speichern wir die gefundenen
        # neuen Stellen am Ende des erfolgreichen Durchlaufs.
        #
        # Später beim E-Mail-Versand ändern wir das so,
        # dass erst nach erfolgreichem Versand gespeichert wird.
        # ----------------------------------------------------

        if new_jobs:

            if save_seen(updated_seen):

                print()
                print(
                    "Merkliste erfolgreich aktualisiert."
                )

            else:

                print()
                print(
                    "WARNUNG: Merkliste konnte nicht gespeichert werden."
                )

        # ----------------------------------------------------
        # AUSGABE
        # ----------------------------------------------------

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

                print(
                    job["text"]
                )

                print("----------------------------------------")

    except Exception as e:

        print()
        print("========================================")
        print("FEHLER BEIM AUSFÜHREN DES MONITORS")
        print("========================================")
        print(e)

        raise

    finally:

        browser.close()

        print()
        print("========================================")
        print("CHECK BEENDET")
        print("========================================")
```
