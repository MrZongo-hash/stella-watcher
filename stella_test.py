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
# Für den späteren produktiven Betrieb:
#
# ORT_NAME = "Köln"
# ORT_VALUE = "315000"
# ============================================================

ORT_NAME = "Kleve"
ORT_VALUE = "154036"


# ============================================================
# DATEI MIT BEREITS GEMELDETEN STELLEN
# ============================================================

SEEN_FILE = "stella_bereits_gemeldet.json"


# ============================================================
# STELLA START-URL
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
#
# Diese Schlüsselwörter werden AUSSCHLIESSLICH im Feld
#
# "Fachleiter/-in an einem Zentrum für schulpraktische
# Lehrerausbildung (w/m/d)"
#
# geprüft.
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

        print(
            "Merkliste ist leer – starte mit 0 bekannten Stellen."
        )

        return {}

    try:

        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            content = f.read().strip()

            if not content:

                print(
                    "Merkliste ist leer – starte mit 0 bekannten Stellen."
                )

                return {}

            data = json.loads(content)

            if isinstance(data, dict):

                return data

            print(
                "Merkliste enthält kein gültiges Dictionary."
            )

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

    """
    Prüft einen Text auf Sonderpädagogik-Schlüsselwörter.

    WICHTIG:
    Diese Funktion bekommt im Hauptprogramm ausschließlich
    den Inhalt des Fachleiter-Feldes übergeben.
    """

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

        # Etwas großzügiger
        r"\b\d+\.[A-Z]+-FL\d+[A-Z]?\b",

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            return match.group(0).upper()

    return None


# ============================================================
# STABILE ID ERZEUGEN
# ============================================================

def create_job_id(text):

    aktenzeichen = extract_aktenzeichen(text)

    if aktenzeichen:

        return aktenzeichen

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
    Liest die Fachleiter-Ausschreibungen aus der
    STELLA-Ergebnisliste.

    Die komplette Tabellenzeile wird gespeichert.

    Zusätzlich wird das konkrete Feld
    "Fachleiter/-in an einem Zentrum für schulpraktische
    Lehrerausbildung (w/m/d)" separat ermittelt.

    NUR dieses Feld wird später für die Prüfung auf
    Sonderpädagogik verwendet.
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

        # Kopfzeile ignorieren

        if "stellenbezeichnung" in text_lower:

            continue

        # ----------------------------------------------------
        # Fachleiter-Feld suchen
        # ----------------------------------------------------

        fachleiter_text = ""

        cells = row.locator(
            "td, th"
        )

        cell_count = cells.count()

        for c in range(cell_count):

            cell = cells.nth(c)

            try:

                cell_text = (
                    cell.inner_text()
                    .strip()
                )

            except Exception:

                continue

            if not cell_text:

                continue

            cell_lower = cell_text.lower()

            # ------------------------------------------------
            # Gesuchtes Feld
            # ------------------------------------------------

            if (
                "fachleiter/-in an einem zentrum "
                "für schulpraktische lehrerausbildung"
                in cell_lower
            ):

                fachleiter_text = cell_text

                break

        # ----------------------------------------------------
        # Fallback
        # ----------------------------------------------------
        #
        # Falls STELLA die Tabellenstruktur so liefert, dass
        # Überschrift und Inhalt nicht in derselben Zelle
        # stehen, suchen wir nach der Zelle mit
        # "Fachleiter/-in".
        #
        # Wichtig:
        # Auch hier wird NICHT die gesamte Tabellenzeile
        # für die Sonderpädagogik-Prüfung verwendet.
        # ----------------------------------------------------

        if not fachleiter_text:

            for c in range(cell_count):

                cell = cells.nth(c)

                try:

                    cell_text = (
                        cell.inner_text()
                        .strip()
                    )

                except Exception:

                    continue

                cell_lower = cell_text.lower()

                if (
                    "fachleiter/-in" in cell_lower
                ):

                    fachleiter_text = cell_text

                    break

        # ----------------------------------------------------
        # Detail-Link suchen
        # ----------------------------------------------------

        detail_url = None

        anchors = row.locator("a")

        for a_index in range(
            anchors.count()
        ):

            a = anchors.nth(
                a_index
            )

            try:

                href = a.get_attribute(
                    "href"
                )

                link_text = (
                    a.inner_text()
                    .strip()
                )

                if (
                    href
                    and "Weitere Hinweise"
                    in link_text
                ):

                    if href.startswith("http"):

                        detail_url = href

                    elif href.startswith("/"):

                        detail_url = BASE + href

                    else:

                        detail_url = BASE + "/" + href

                    break

            except Exception:

                pass

        # ----------------------------------------------------
        # Ergebnis speichern
        # ----------------------------------------------------

        results.append({

            # Komplette Ergebniszeile
            "text": text,

            # NUR dieses Feld wird für die
            # Sonderpädagogik-Erkennung verwendet
            "fachleiter_text": fachleiter_text,

            # Link zu "Weitere Hinweise"
            "detail_url": detail_url,

        })

    return results


# ============================================================
# DETAILSEITE ÖFFNEN
# ============================================================

def read_detail_page(context, href):

    if not href:

        return None

    page = context.new_page()

    try:

        page.goto(
            href,
            wait_until="networkidle",
            timeout=60000
        )

        text = page.locator(
            "body"
        ).inner_text()

        return {

            "url": page.url,

            "text": text,

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
# STELLE AUFBEREITEN
# ============================================================

def prepare_job(result, context):

    result_text = result["text"]

    job_id = create_job_id(
        result_text
    )

    detail_url = result.get(
        "detail_url"
    )

    detail_text = None

    detail_page_url = detail_url

    # --------------------------------------------------------
    # Detailseite zusätzlich laden
    # --------------------------------------------------------

    if detail_url:

        detail = read_detail_page(
            context,
            detail_url
        )

        if detail:

            detail_text = detail["text"]

            detail_page_url = detail["url"]

    timestamp = datetime.now().isoformat(
        timespec="seconds"
    )

    return {

        "id": job_id,

        "url": detail_page_url,

        "gefunden_am": timestamp,

        # Komplette relevante Ergebniszeile
        "stelleninformationen": result_text,

        # Das konkret geprüfte Fachleiter-Feld
        "fachleiter_text": result.get(
            "fachleiter_text",
            ""
        ),

        # Weitere Hinweise separat
        "weitere_hinweise": detail_text,

    }


# ============================================================
# E-MAIL VERSENDEN
# ============================================================

def send_email(new_jobs):

    if not new_jobs:

        print(
            "Keine neuen Stellen – keine E-Mail."
        )

        return True

    # --------------------------------------------------------
    # Zugangsdaten aus GitHub Secrets
    # --------------------------------------------------------

    sender = os.environ["FREENET_EMAIL"]

    password = os.environ["FREENET_PASSWORD"]

    recipient = os.environ["MAIL_TO"]

    # --------------------------------------------------------
    # Betreff
    # --------------------------------------------------------

    if len(new_jobs) == 1:

        subject = (
            f"STELLA: Neue Fachleiterstelle "
            f"Sonderpädagogik – {ORT_NAME}"
        )

    else:

        subject = (
            f"STELLA: {len(new_jobs)} neue "
            f"Fachleiterstellen Sonderpädagogik – "
            f"{ORT_NAME}"
        )

    # --------------------------------------------------------
    # Mailtext
    # --------------------------------------------------------

    now = datetime.now().strftime(
        "%d.%m.%Y %H:%M:%S"
    )

    lines = []

    lines.append(
        "Neue passende STELLA-Ausschreibungen"
    )

    lines.append("")

    lines.append(
        f"Ort: {ORT_NAME}"
    )

    lines.append(
        f"Anzahl neue Stellen: {len(new_jobs)}"
    )

    lines.append(
        f"Prüfzeitpunkt: {now}"
    )

    lines.append("")

    lines.append(
        "=" * 70
    )

    # ========================================================
    # ALLE NEUEN STELLEN
    # ========================================================

    for index, job in enumerate(
        new_jobs,
        start=1
    ):

        lines.append("")

        lines.append(
            f"STELLE {index} VON {len(new_jobs)}"
        )

        lines.append(
            "=" * 70
        )

        lines.append("")

        lines.append(
            f"Aktenzeichen: {job['id']}"
        )

        lines.append("")

        # ----------------------------------------------------
        # Fachleiter-Feld
        # ----------------------------------------------------

        lines.append(
            "FACHLEITER-FELD:"
        )

        lines.append(
            "-" * 70
        )

        lines.append(
            job.get(
                "fachleiter_text",
                ""
            )
        )

        lines.append(
            "-" * 70
        )

        lines.append("")

        # ----------------------------------------------------
        # KOMPLETTE STELLENINFORMATIONEN
        # ----------------------------------------------------

        lines.append(
            "STELLENINFORMATIONEN AUS DER "
            "STELLA-ERGEBNISLISTE:"
        )

        lines.append(
            "-" * 70
        )

        lines.append(
            job["stelleninformationen"]
        )

        lines.append(
            "-" * 70
        )

        lines.append("")

        # ----------------------------------------------------
        # STELLA-LINK
        # ----------------------------------------------------

        lines.append(
            "STELLA-LINK:"
        )

        lines.append(
            job["url"]
        )

        lines.append("")

        # ----------------------------------------------------
        # Weitere Hinweise
        # ----------------------------------------------------
        #
        # Diese sind allgemeiner Standardtext und deshalb
        # nicht mehr der Hauptbestandteil der Mail.
        #
        # Wir nehmen sie trotzdem mit, falls die Detailseite
        # zusätzliche Informationen enthält.
        # ----------------------------------------------------

        if job.get("weitere_hinweise"):

            detail_text = job[
                "weitere_hinweise"
            ]

            marker = "Weitere Hinweise"

            if marker in detail_text:

                detail_text = detail_text[
                    detail_text.find(marker):
                ]

            lines.append(
                "WEITERE HINWEISE:"
            )

            lines.append(
                "-" * 70
            )

            lines.append(
                detail_text.strip()
            )

            lines.append(
                "-" * 70
            )

        lines.append("")

    lines.append(
        "=" * 70
    )

    lines.append(
        "STELLA Monitor"
    )

    body = "\n".join(
        lines
    )

    # ========================================================
    # E-MAIL ERSTELLEN
    # ========================================================

    msg = EmailMessage()

    msg["From"] = sender

    msg["To"] = recipient

    msg["Subject"] = subject

    msg.set_content(
        body
    )

    # ========================================================
    # SMTP
    # ========================================================

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
        f"Neue Stellen in dieser Mail: {len(new_jobs)}"
    )

    server = smtplib.SMTP(
        "mx.freenet.de",
        587,
        timeout=30
    )

    try:

        print("EHLO...")

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

        print("STARTTLS...")

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

        print("Login...")

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
                "gestartet werden."
            )

        username_encoded = base64.b64encode(
            sender.encode("utf-8")
        ).decode("ascii")

        password_encoded = base64.b64encode(
            password.encode("utf-8")
        ).decode("ascii")

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
                "Benutzername wurde abgelehnt."
            )

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
                "Authentifizierung fehlgeschlagen."
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
                "MAIL FROM abgelehnt."
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
                "RCPT TO abgelehnt."
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
                "DATA abgelehnt."
            )

        print(
            "E-Mail erfolgreich versendet."
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
            f"Ort: {ORT_NAME}"
        )

        print(
            f"Bereits bekannte Stellen: {len(seen)}"
        )

        # ====================================================
        # STELLA
        # ====================================================

        open_stella(page)

        search_stella(page)

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

        # Kopie der Merkliste.
        #
        # Diese wird erst nach erfolgreichem
        # Mailversand gespeichert.

        updated_seen = dict(
            seen
        )

        # ====================================================
        # AUSSCHREIBUNGEN PRÜFEN
        # ====================================================

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

            # ------------------------------------------------
            # NUR DAS FACHLEITER-FELD VERWENDEN
            # ------------------------------------------------

            fachleiter_text = result.get(
                "fachleiter_text",
                ""
            )

            if not fachleiter_text:

                print(
                    "→ Fachleiter-Feld konnte "
                    "nicht erkannt werden."
                )

                continue

            print(
                "Fachleiter-Feld:"
            )

            print(
                fachleiter_text
            )

            # ------------------------------------------------
            # SONDERPÄDAGOGIK PRÜFEN
            # ------------------------------------------------
            #
            # Ganz wichtig:
            #
            # Hier wird NICHT result["text"] geprüft.
            #
            # Nur fachleiter_text.
            # ------------------------------------------------

            if not is_sonderpaedagogik(
                fachleiter_text
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
                result["text"]
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
                    "keine erneute Meldung"
                )

                continue

            # ------------------------------------------------
            # NEUE STELLE
            # ------------------------------------------------

            job = prepare_job(
                result,
                context
            )

            new_jobs.append(
                job
            )

            updated_seen[
                job_id
            ] = {

                "url": job["url"],

                "erstmals_gefunden":
                    job["gefunden_am"],

            }

            print(
                "→ NEUE STELLE ZUR SAMMLUNG "
                "HINZUGEFÜGT"
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
            f"Neue passende Stellen: "
            f"{len(new_jobs)}"
        )

        # ====================================================
        # KEINE NEUEN STELLEN
        # ====================================================

        if not new_jobs:

            print()
            print(
                "Keine neuen passenden Stellen gefunden."
            )

        # ====================================================
        # NEUE STELLEN
        # ====================================================

        else:

            print()
            print(
                f"{len(new_jobs)} neue Stelle(n) gefunden."
            )

            print(
                "Alle Stellen werden in EINER "
                "E-Mail zusammengefasst."
            )

            # ------------------------------------------------
            # E-MAIL VERSENDEN
            # ------------------------------------------------

            try:

                mail_success = send_email(
                    new_jobs
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

                # Wichtig:
                #
                # Keine Aktualisierung der Merkliste,
                # wenn der Mailversand fehlschlägt.

                raise

            # ------------------------------------------------
            # NUR NACH ERFOLGREICHEM MAILVERSAND
            # MERKLISTE SPEICHERN
            # ------------------------------------------------

            if mail_success:

                print()
                print(
                    "========================================"
                )

                print(
                    "E-MAIL ERFOLGREICH VERSENDET."
                )

                print(
                    f"{len(new_jobs)} Stelle(n) "
                    "in einer einzigen E-Mail."
                )

                print(
                    "========================================"
                )

                print()
                print(
                    "Aktualisiere jetzt die Merkliste..."
                )

                if save_seen(
                    updated_seen
                ):

                    print(
                        "Merkliste erfolgreich aktualisiert."
                    )

                    print(
                        f"{len(new_jobs)} Stelle(n) "
                        "als gemeldet gespeichert."
                    )

                else:

                    raise RuntimeError(
                        "Merkliste konnte nach "
                        "erfolgreichem Mailversand "
                        "nicht gespeichert werden."
                    )

    except Exception as e:

        print()
        print(
            "========================================"
        )

        print(
            "FEHLER BEIM AUSFÜHREN DES MONITORS"
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
            "========================================"
        )

        print(
            "CHECK BEENDET"
        )

        print(
            "========================================"
        )

        print(
            "Browser geschlossen."
        )
