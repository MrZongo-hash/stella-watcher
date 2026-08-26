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

# ------------------------------------------------------------
# TESTORT
# ------------------------------------------------------------
# Zunächst Kleve zum Testen.
#
# Später:
# ORT_NAME = "Köln"
# ORT_VALUE = "315000"
# ------------------------------------------------------------

ORT_NAME = "Kleve"
ORT_VALUE = "154036"


# Datei mit bereits gemeldeten Stellen
SEEN_FILE = "stella_bereits_gemeldet.json"


# ============================================================
# E-MAIL / FREEnet
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

        if (
            "fachleiter" not in text_lower
            and "fachleiter/-in" not in text_lower
        ):
            continue

        if "stellenbezeichnung" in text_lower:
            continue

        results.append({
            "text": text
        })

    return results


# ============================================================
# DETAILSEITE ÖFFNEN
# ============================================================

def read_detail_page(context, href):

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
# E-MAIL VERSENDEN
# ============================================================

def send_email(job):

    sender = os.environ["FREENET_EMAIL"]
    password = os.environ["FREENET_PASSWORD"]
    recipient = os.environ["MAIL_TO"]

    print()
    print("========================================")
    print("VERSENDE E-MAIL")
    print("========================================")

    msg = EmailMessage()

    msg["From"] = sender
    msg["To"] = recipient

    msg["Subject"] = (
        "Neue STELLA-Stelle – "
        f"Fachleitung Sonderpädagogik – {ORT_NAME}"
    )

    email_text = (
        "Eine neue passende Ausschreibung wurde gefunden.\n\n"
        "========================================\n"
        "STELLA MONITOR\n"
        "========================================\n\n"

        f"Ort: {ORT_NAME}\n"
        f"Aktenzeichen: {job['id']}\n"
        f"Gefunden am: {job['gefunden_am']}\n\n"

        "DETAILSEITE:\n"
        f"{job['url']}\n\n"

        "========================================\n"
        "AUSSCHREIBUNGSTEXT\n"
        "========================================\n\n"

        f"{job['text']}\n"
    )

    msg.set_content(email_text)

    server = smtplib.SMTP(
        SMTP_SERVER,
        SMTP_PORT,
        timeout=30
    )

    try:

        print("EHLO...")
        code, response = server.ehlo()
        print(code, response)

        print("STARTTLS...")
        code, response = server.starttls()
        print(code, response)

        print("EHLO nach TLS...")
        code, response = server.ehlo()
        print(code, response)

        # ----------------------------------------------------
        # AUTH LOGIN
        # ----------------------------------------------------

        print("Login...")

        code, response = server.docmd(
            "AUTH",
            "LOGIN"
        )

        print(code, response)

        if code != 334:

            raise RuntimeError(
                "AUTH LOGIN konnte nicht gestartet werden: "
                f"{code} {response}"
            )

        username_encoded = base64.b64encode(
            sender.encode("utf-8")
        ).decode("ascii")

        password_encoded = base64.b64encode(
            password.encode("utf-8")
        ).decode("ascii")

        print("Benutzername senden...")

        code, response = server.docmd(
            "",
            username_encoded
        )

        print(code, response)

        if code != 334:

            raise RuntimeError(
                "Benutzername wurde abgelehnt: "
                f"{code} {response}"
            )

        print("Passwort senden...")

        code, response = server.docmd(
            "",
            password_encoded
        )

        print(code, response)

        if code != 235:

            raise RuntimeError(
                "Authentifizierung fehlgeschlagen: "
                f"{code} {response}"
            )

        print("Login erfolgreich.")

        # ----------------------------------------------------
        # MAIL FROM
        # ----------------------------------------------------

        code, response = server.mail(sender)

        print(
            "MAIL FROM:",
            code,
            response
        )

        if code != 250:

            raise RuntimeError(
                f"MAIL FROM abgelehnt: {code} {response}"
            )

        # ----------------------------------------------------
        # RCPT TO
        # ----------------------------------------------------

        code, response = server.rcpt(recipient)

        print(
            "RCPT TO:",
            code,
            response
        )

        if code != 250:

            raise RuntimeError(
                f"RCPT TO abgelehnt: {code} {response}"
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
                f"DATA abgelehnt: {code} {response}"
            )

        print()
        print("E-MAIL ERFOLGREICH VERSENDET.")

        return True

    finally:

        print("Schließe SMTP-Verbindung...")

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

        # ----------------------------------------------------
        # Merkliste
        # ----------------------------------------------------

        seen = load_seen()

        print()
        print("========================================")
        print("STELLA MONITOR")
        print("========================================")

        print(
            "Ort:",
            ORT_NAME
        )

        print(
            "Bereits bekannte Stellen:",
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

        results = get_result_rows(page)

        print()
        print(
            "Gefundene Fachleiter-Ausschreibungen:",
            len(results)
        )

        # ----------------------------------------------------
        # Neue Stellen
        # ----------------------------------------------------

        new_jobs = []

        for index, result in enumerate(
            results,
            start=1
        ):

            print()
            print("----------------------------------------")
            print(
                f"Prüfe Ausschreibung "
                f"{index}/{len(results)}"
            )
            print("----------------------------------------")

            result_text = result["text"]

            # ------------------------------------------------
            # Sonderpädagogik
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
                    "→ Bereits bekannt – "
                    "keine E-Mail"
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

                    row_text = (
                        row.inner_text()
                        .strip()
                    )

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
            # Detailseite laden
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

            timestamp = datetime.now().isoformat(
                timespec="seconds"
            )

            job_data = {

                "id": job_id,

                "url": detail_page_url,

                "gefunden_am": timestamp,

                "text": detail_text
            }

            print()
            print(
                "→ NEUE STELLE GEFUNDEN!"
            )

            # ------------------------------------------------
            # E-MAIL SENDEN
            # ------------------------------------------------

            try:

                mail_success = send_email(
                    job_data
                )

            except Exception as e:

                print()
                print(
                    "FEHLER BEIM E-MAIL-VERSAND:"
                )

                print(
                    type(e).__name__ + ":",
                    e
                )

                # WICHTIG:
                # Nicht als bekannt speichern!
                # Beim nächsten Lauf wird erneut versucht,
                # die Mail zu senden.

                raise

            # ------------------------------------------------
            # Erst NACH erfolgreicher Mail speichern
            # ------------------------------------------------

            if mail_success:

                seen[job_id] = {

                    "url": detail_page_url,

                    "erstmals_gefunden": timestamp
                }

                if save_seen(seen):

                    print(
                        "→ Stelle erfolgreich "
                        "als gemeldet gespeichert."
                    )

                else:

                    raise RuntimeError(
                        "E-Mail wurde gesendet, "
                        "aber die Merkliste konnte "
                        "nicht gespeichert werden."
                    )

                new_jobs.append(
                    job_data
                )

        # ----------------------------------------------------
        # ABSCHLUSS
        # ----------------------------------------------------

        print()
        print()
        print("========================================")
        print("CHECK BEENDET")
        print("========================================")

        if not new_jobs:

            print(
                "Keine neuen passenden Stellen."
            )

        else:

            print(
                f"{len(new_jobs)} neue Stelle(n) "
                "gemeldet."
            )

    except Exception as e:

        print()
        print("========================================")
        print("FEHLER BEIM AUSFÜHREN DES MONITORS")
        print("========================================")

        print(
            type(e).__name__ + ":",
            e
        )

        raise

    finally:

        browser.close()

        print()
        print("Browser geschlossen.")
