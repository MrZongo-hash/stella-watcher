from playwright.sync_api import sync_playwright
import json
import os
import re
import smtplib
import base64
from email.message import EmailMessage
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
# Später für Köln:
#
# ORT_NAME = "Köln"
# ORT_VALUE = "315000"
# ============================================================

ORT_NAME = "Kleve"
ORT_VALUE = "154036"


# Datei mit bereits gemeldeten Stellen
SEEN_FILE = "stella_bereits_gemeldet.json"


# ============================================================
# FREENET SMTP
# ============================================================

SMTP_SERVER = "mx.freenet.de"
SMTP_PORT = 587


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
# SCHLÜSSELWÖRTER SONDERPÄDAGOGIK
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

            content = f.read().strip()

            # ------------------------------------------------
            # Leere Datei
            # ------------------------------------------------

            if not content:

                print(
                    "Merkliste ist leer – "
                    "starte mit 0 bekannten Stellen."
                )

                return {}

            data = json.loads(content)

            if isinstance(data, dict):

                return data

            print(
                "WARNUNG: Merkliste enthält kein "
                "gültiges JSON-Objekt."
            )

            return {}

    except Exception as e:

        print(
            "Fehler beim Laden der Merkliste:",
            e
        )

        print(
            "Starte vorsichtshalber mit "
            "leerer Merkliste."
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

        # Beispiel:
        # 47.Z-FL4110A
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
# STABILE ID
# ============================================================

def create_job_id(text):

    aktenzeichen = extract_aktenzeichen(
        text
    )

    if aktenzeichen:

        return aktenzeichen.upper()

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

    print(
        "Öffne STELLA..."
    )

    page.goto(
        START_URL,
        wait_until="networkidle",
        timeout=60000
    )

    print(
        "Startseite geladen."
    )

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

    print(
        "Suchmaschine geöffnet."
    )

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

    print(
        "Fachleiter-Suche geöffnet."
    )


# ============================================================
# SUCHE DURCHFÜHREN
# ============================================================

def search_stella(page):

    # --------------------------------------------------------
    # Stellenart: Fachleiter/-in
    # --------------------------------------------------------

    page.locator(
        "#artStelle"
    ).select_option("404")

    # --------------------------------------------------------
    # Institution: Studienseminar
    # --------------------------------------------------------

    page.locator(
        "#institution"
    ).select_option("92")

    # --------------------------------------------------------
    # Ort
    # --------------------------------------------------------

    page.locator(
        "#ort"
    ).select_option(
        ORT_VALUE
    )

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

    print(
        "Suche abgeschlossen."
    )


# ============================================================
# ERGEBNISSE AUSLESEN
# ============================================================

def get_result_rows(page):

    """
    Liest die eigentlichen Ausschreibungszeilen
    aus der Ergebnis-Tabelle.

    Wichtig:
    Wir speichern hier den kompletten Text der
    Ergebniszeile. Dieser enthält die eigentlichen
    Informationen zur Stelle.
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
        # Nur Fachleiter-Ausschreibungen
        # ----------------------------------------------------

        if (
            "fachleiter" not in text_lower
            and "fachleiter/-in" not in text_lower
        ):

            continue

        # ----------------------------------------------------
        # Kopfzeile ignorieren
        # ----------------------------------------------------

        if "stellenbezeichnung" in text_lower:

            continue

        # ----------------------------------------------------
        # Links der Ergebniszeile sichern
        # ----------------------------------------------------

        links = []

        anchors = row.locator("a")

        for a_index in range(
            anchors.count()
        ):

            anchor = anchors.nth(
                a_index
            )

            try:

                link_text = (
                    anchor.inner_text()
                    .strip()
                )

                href = (
                    anchor.get_attribute(
                        "href"
                    )
                )

                if href:

                    links.append({
                        "text": link_text,
                        "href": href
                    })

            except Exception:

                pass

        results.append({
            "text": text,
            "links": links
        })

    return results


# ============================================================
# DETAILSEITE ÖFFNEN
# ============================================================

def read_detail_page(
    context,
    href
):

    detail_page = context.new_page()

    try:

        if href.startswith(
            "http"
        ):

            url = href

        elif href.startswith(
            "/"
        ):

            url = BASE + href

        else:

            url = BASE + "/" + href

        detail_page.goto(
            url,
            wait_until="networkidle",
            timeout=60000
        )

        text = detail_page.locator(
            "body"
        ).inner_text()

        return {
            "url": detail_page.url,
            "text": text
        }

    except Exception as e:

        print(
            "Fehler beim Öffnen der Detailseite:",
            e
        )

        return None

    finally:

        detail_page.close()


# ============================================================
# PASSENDEN DETAIL-LINK SUCHEN
# ============================================================

def find_detail_link(
    result
):

    for link in result.get(
        "links",
        []
    ):

        link_text = link[
            "text"
        ]

        href = link[
            "href"
        ]

        # ----------------------------------------------------
        # Bevorzugt "Weitere Hinweise"
        # ----------------------------------------------------

        if (
            "Weitere Hinweise"
            in link_text
        ):

            return href

    # --------------------------------------------------------
    # Falls kein "Weitere Hinweise"-Link vorhanden ist,
    # nehmen wir keinen Detail-Link.
    # --------------------------------------------------------

    return None


# ============================================================
# E-MAIL MIT ALLEN NEUEN STELLEN
# ============================================================

def send_email(
    jobs
):

    sender = os.environ[
        "FREENET_EMAIL"
    ]

    password = os.environ[
        "FREENET_PASSWORD"
    ]

    recipient = os.environ[
        "MAIL_TO"
    ]

    number_of_jobs = len(
        jobs
    )

    print()

    print(
        "========================================"
    )

    print(
        "VERSENDE GESAMMELTE E-MAIL"
    )

    print(
        "========================================"
    )

    print(
        "Neue Stellen in dieser Mail:",
        number_of_jobs
    )

    # ========================================================
    # BETREFF
    # ========================================================

    if number_of_jobs == 1:

        subject = (
            "1 neue STELLA-Stelle – "
            "Fachleitung Sonderpädagogik – "
            f"{ORT_NAME}"
        )

    else:

        subject = (
            f"{number_of_jobs} neue STELLA-Stellen – "
            "Fachleitung Sonderpädagogik – "
            f"{ORT_NAME}"
        )

    # ========================================================
    # MAIL-INHALT
    # ========================================================

    lines = []

    lines.append(
        "Neue passende STELLA-Ausschreibungen"
    )

    lines.append(
        ""
    )

    lines.append(
        f"Ort: {ORT_NAME}"
    )

    lines.append(
        f"Anzahl neue Stellen: {number_of_jobs}"
    )

    lines.append(
        f"Prüfzeitpunkt: "
        f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )

    lines.append(
        ""
    )

    lines.append(
        "=" * 70
    )

    # ========================================================
    # ALLE STELLEN
    # ========================================================

    for index, job in enumerate(
        jobs,
        start=1
    ):

        lines.append(
            ""
        )

        lines.append(
            f"STELLE {index} VON {number_of_jobs}"
        )

        lines.append(
            "=" * 70
        )

        lines.append(
            ""
        )

        # ----------------------------------------------------
        # AKTENZEICHEN
        # ----------------------------------------------------

        lines.append(
            f"Aktenzeichen: {job['id']}"
        )

        lines.append(
            ""
        )

        # ----------------------------------------------------
        # WICHTIG:
        # EIGENTLICHE ERGEBNISZEILE
        # ----------------------------------------------------

        lines.append(
            "STELLENINFORMATIONEN AUS DER "
            "STELLA-ERGEBNISLISTE:"
        )

        lines.append(
            "-" * 70
        )

        lines.append(
            job["result_text"]
        )

        lines.append(
            "-" * 70
        )

        lines.append(
            ""
        )

        # ----------------------------------------------------
        # DETAILSEITE
        # ----------------------------------------------------

        if job.get(
            "detail_text"
        ):

            lines.append(
                "WEITERE HINWEISE:"
            )

            lines.append(
                "-" * 70
            )

            lines.append(
                job["detail_text"]
            )

            lines.append(
                "-" * 70
            )

            lines.append(
                ""
            )

        # ----------------------------------------------------
        # LINK
        # ----------------------------------------------------

        lines.append(
            "STELLA-LINK:"
        )

        lines.append(
            job["url"]
        )

        lines.append(
            ""
        )

    # ========================================================
    # ABSCHLUSS
    # ========================================================

    lines.append(
        "=" * 70
    )

    lines.append(
        "STELLA Monitor"
    )

    msg = EmailMessage()

    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject

    msg.set_content(
        "\n".join(lines)
    )

    # ========================================================
    # SMTP VERBINDUNG
    # ========================================================

    server = smtplib.SMTP(
        SMTP_SERVER,
        SMTP_PORT,
        timeout=30
    )

    try:

        # ----------------------------------------------------
        # EHLO
        # ----------------------------------------------------

        print(
            "EHLO..."
        )

        code, response = server.ehlo()

        print(
            code,
            response
        )

        if code != 250:

            raise RuntimeError(
                f"EHLO fehlgeschlagen: "
                f"{code} {response}"
            )

        # ----------------------------------------------------
        # STARTTLS
        # ----------------------------------------------------

        print(
            "STARTTLS..."
        )

        code, response = server.starttls()

        print(
            code,
            response
        )

        if code != 220:

            raise RuntimeError(
                f"STARTTLS fehlgeschlagen: "
                f"{code} {response}"
            )

        # ----------------------------------------------------
        # EHLO NACH TLS
        # ----------------------------------------------------

        print(
            "EHLO nach TLS..."
        )

        code, response = server.ehlo()

        print(
            code,
            response
        )

        # ----------------------------------------------------
        # AUTH LOGIN
        # ----------------------------------------------------

        print(
            "Login..."
        )

        code, response = server.docmd(
            "AUTH",
            "LOGIN"
        )

        print(
            code,
            response
        )

        if code != 334:

            raise RuntimeError(
                "AUTH LOGIN konnte nicht "
                "gestartet werden: "
                f"{code} {response}"
            )

        username_encoded = (
            base64.b64encode(
                sender.encode(
                    "utf-8"
                )
            )
            .decode(
                "ascii"
            )
        )

        password_encoded = (
            base64.b64encode(
                password.encode(
                    "utf-8"
                )
            )
            .decode(
                "ascii"
            )
        )

        # ----------------------------------------------------
        # BENUTZERNAME
        # ----------------------------------------------------

        print(
            "Benutzername senden..."
        )

        code, response = server.docmd(
            "",
            username_encoded
        )

        print(
            code,
            response
        )

        if code != 334:

            raise RuntimeError(
                "Benutzername wurde "
                "abgelehnt: "
                f"{code} {response}"
            )

        # ----------------------------------------------------
        # PASSWORT
        # ----------------------------------------------------

        print(
            "Passwort senden..."
        )

        code, response = server.docmd(
            "",
            password_encoded
        )

        print(
            code,
            response
        )

        if code != 235:

            raise RuntimeError(
                "Authentifizierung "
                "fehlgeschlagen: "
                f"{code} {response}"
            )

        print(
            "Login erfolgreich."
        )

        # ----------------------------------------------------
        # MAIL FROM
        # ----------------------------------------------------

        code, response = server.mail(
            sender
        )

        print(
            "MAIL FROM:",
            code,
            response
        )

        if code != 250:

            raise RuntimeError(
                f"MAIL FROM abgelehnt: "
                f"{code} {response}"
            )

        # ----------------------------------------------------
        # RCPT TO
        # ----------------------------------------------------

        code, response = server.rcpt(
            recipient
        )

        print(
            "RCPT TO:",
            code,
            response
        )

        if code != 250:

            raise RuntimeError(
                f"RCPT TO abgelehnt: "
                f"{code} {response}"
            )

        # ----------------------------------------------------
        # DATA
        # ----------------------------------------------------

        code, response = server.data(
            msg.as_bytes()
        )

        print(
            "DATA:",
            code,
            response
        )

        if code != 250:

            raise RuntimeError(
                f"DATA abgelehnt: "
                f"{code} {response}"
            )

        print()

        print(
            "========================================"
        )

        print(
            "E-MAIL ERFOLGREICH VERSENDET."
        )

        print(
            f"{number_of_jobs} Stelle(n) "
            "in EINER E-Mail."
        )

        print(
            "========================================"
        )

        return True

    finally:

        print(
            "Schließe SMTP-Verbindung..."
        )

        try:

            server.quit()

        except Exception:

            pass


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

        # ====================================================
        # MERKLISTE
        # ====================================================

        seen = load_seen()

        print()

        print(
            "========================================"
        )

        print(
            "STELLA MONITOR"
        )

        print(
            "========================================"
        )

        print(
            "Ort:",
            ORT_NAME
        )

        print(
            "Bereits bekannte Stellen:",
            len(seen)
        )

        # ====================================================
        # STELLA
        # ====================================================

        open_stella(
            page
        )

        search_stella(
            page
        )

        # ====================================================
        # ERGEBNISSE
        # ====================================================

        print()

        print(
            "========================================"
        )

        print(
            f"ERGEBNISSE FÜR {ORT_NAME.upper()}"
        )

        print(
            "========================================"
        )

        print(
            "URL:",
            page.url
        )

        results = get_result_rows(
            page
        )

        print()

        print(
            "Gefundene Fachleiter-Ausschreibungen:",
            len(results)
        )

        # ====================================================
        # NEUE STELLEN SAMMELN
        # ====================================================

        new_jobs = []

        for index, result in enumerate(
            results,
            start=1
        ):

            print()

            print(
                "----------------------------------------"
            )

            print(
                f"Prüfe Ausschreibung "
                f"{index}/{len(results)}"
            )

            print(
                "----------------------------------------"
            )

            result_text = result[
                "text"
            ]

            # ------------------------------------------------
            # DEBUG-AUSGABE
            # ------------------------------------------------

            print()

            print(
                "ERGEBNISZEILE:"
            )

            print(
                "----------------------------------------"
            )

            print(
                result_text
            )

            print(
                "----------------------------------------"
            )

            # ------------------------------------------------
            # SONDERPÄDAGOGIK
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
            # BEREITS BEKANNT?
            # ------------------------------------------------

            if job_id in seen:

                print(
                    "→ Bereits bekannt – "
                    "keine Meldung"
                )

                continue

            # ------------------------------------------------
            # DETAIL-LINK
            # ------------------------------------------------

            detail_url = find_detail_link(
                result
            )

            detail_text = None

            detail_page_url = page.url

            # ------------------------------------------------
            # DETAILSEITE LADEN
            # ------------------------------------------------

            if detail_url:

                detail = read_detail_page(
                    context,
                    detail_url
                )

                if detail:

                    detail_text = detail[
                        "text"
                    ]

                    detail_page_url = detail[
                        "url"
                    ]

            # ------------------------------------------------
            # STELLE ERSTELLEN
            # ------------------------------------------------

            timestamp = datetime.now().isoformat(
                timespec="seconds"
            )

            job_data = {

                "id": job_id,

                # URL zur Detailseite
                "url": detail_page_url,

                # Zeitpunkt
                "gefunden_am": timestamp,

                # DAS IST DIE WICHTIGE INFORMATION:
                # Originale Ergebniszeile aus STELLA
                "result_text": result_text,

                # Zusätzliche Hinweise
                "detail_text": detail_text
            }

            new_jobs.append(
                job_data
            )

            print()

            print(
                "→ NEUE STELLE "
                "ZUR SAMMLUNG HINZUGEFÜGT"
            )

        # ====================================================
        # AUSWERTUNG
        # ====================================================

        print()

        print(
            "========================================"
        )

        print(
            "AUSWERTUNG"
        )

        print(
            "========================================"
        )

        print(
            "Neue passende Stellen:",
            len(new_jobs)
        )

        # ====================================================
        # KEINE NEUEN STELLEN
        # ====================================================

        if not new_jobs:

            print()

            print(
                "Keine neuen passenden Stellen."
            )

            print(
                "Es wird keine E-Mail versendet."
            )

        # ====================================================
        # NEUE STELLEN
        # ====================================================

        else:

            print()

            print(
                f"{len(new_jobs)} neue Stelle(n) "
                "gefunden."
            )

            print(
                "Alle Stellen werden in EINER "
                "E-Mail zusammengefasst."
            )

            # =================================================
            # EINE MAIL FÜR ALLE STELLEN
            # =================================================

            try:

                mail_success = send_email(
                    new_jobs
                )

            except Exception as e:

                print()

                print(
                    "========================================"
                )

                print(
                    "FEHLER BEIM E-MAIL-VERSAND"
                )

                print(
                    "========================================"
                )

                print(
                    type(e).__name__ + ":",
                    e
                )

                # ------------------------------------------------
                # WICHTIG:
                # NICHT ALS BEKANNT SPEICHERN.
                #
                # Beim nächsten Lauf wird erneut versucht,
                # die Mail zu verschicken.
                # ------------------------------------------------

                raise

            # =================================================
            # ERST NACH ERFOLGREICHER MAIL SPEICHERN
            # =================================================

            if mail_success:

                print()

                print(
                    "E-Mail erfolgreich versendet."
                )

                print(
                    "Aktualisiere jetzt "
                    "die Merkliste..."
                )

                for job in new_jobs:

                    seen[
                        job["id"]
                    ] = {

                        "url":
                            job["url"],

                        "erstmals_gefunden":
                            job["gefunden_am"]
                    }

                if save_seen(
                    seen
                ):

                    print()

                    print(
                        "Merkliste erfolgreich "
                        "aktualisiert."
                    )

                    print(
                        f"{len(new_jobs)} Stelle(n) "
                        "als gemeldet gespeichert."
                    )

                else:

                    raise RuntimeError(
                        "E-Mail wurde erfolgreich "
                        "versendet, aber die "
                        "Merkliste konnte nicht "
                        "gespeichert werden."
                    )

        # ====================================================
        # ENDE
        # ====================================================

        print()

        print(
            "========================================"
        )

        print(
            "CHECK BEENDET"
        )

        print(
            "========================================"
        )

    except Exception as e:

        print()

        print(
            "========================================"
        )

        print(
            "FEHLER BEIM AUSFÜHREN "
            "DES MONITORS"
        )

        print(
            "========================================"
        )

        print(
            type(e).__name__ + ":",
            e
        )

        raise

    finally:

        browser.close()

        print()

        print(
            "Browser geschlossen."
        )
