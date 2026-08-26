from playwright.sync_api import sync_playwright
import json
import os
import re
import base64
import smtplib
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
# Später für Köln:
#
# ORT_NAME = "Köln"
# ORT_VALUE = "315000"
# ------------------------------------------------------------

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
        print("Merkliste ist leer – starte mit 0 bekannten Stellen.")
        return {}

    try:

        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            content = f.read().strip()

            if not content:
                print("Merkliste ist leer – starte mit 0 bekannten Stellen.")
                return {}

            data = json.loads(content)

            if isinstance(data, dict):

                print(
                    f"Merkliste geladen – {len(data)} bekannte Stellen."
                )

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

        r"\b\d+\.[A-Z]-FL\d+[A-Z]?\b",

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
# STABILE ID
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

    # --------------------------------------------------------
    # Fachleiter/-in
    # --------------------------------------------------------

    page.locator(
        "#artStelle"
    ).select_option("404")

    # --------------------------------------------------------
    # Studienseminar
    # --------------------------------------------------------

    page.locator(
        "#institution"
    ).select_option("92")

    # --------------------------------------------------------
    # Ort
    # --------------------------------------------------------

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
# ERGEBNISZEILEN AUSLESEN
# ============================================================

def get_result_rows(page):

    """
    Liest die Ausschreibungen aus der Ergebnisliste.

    WICHTIG:
    Die Sonderpädagogik-Prüfung erfolgt später ausschließlich
    anhand des Feldes:

    "Fachleiter/-in an einem Zentrum für schulpraktische
    Lehrerausbildung (w/m/d)"

    und NICHT anhand anderer Tabellenfelder.
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

        if (
            "fachleiter" not in text_lower
            and "fachleiter/-in" not in text_lower
        ):
            continue

        if "stellenbezeichnung" in text_lower:
            continue

        # ----------------------------------------------------
        # Zellen auslesen
        # ----------------------------------------------------

        cells = row.locator("td")

        cell_texts = []

        for c in range(cells.count()):

            try:

                cell_text = cells.nth(c).inner_text().strip()

            except Exception:

                cell_text = ""

            cell_texts.append(cell_text)

        # ----------------------------------------------------
        # Fachleiter-Feld ermitteln
        # ----------------------------------------------------

        fachleiter_field = ""

        for cell_text in cell_texts:

            if (
                "fachleiter/-in an einem zentrum für schulpraktische"
                in cell_text.lower()
            ):

                fachleiter_field = cell_text
                break

        # Falls das Feld nicht gefunden wurde,
        # Ausschreibung ignorieren.

        if not fachleiter_field:

            continue

        results.append({
            "text": text,
            "cells": cell_texts,
            "fachleiter_field": fachleiter_field,
            "row_index": i
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
# DETAIL-LINK AUS ERGEBNISZEILE
# ============================================================

def find_detail_url(page, job_id):

    rows = page.locator("tr")

    for r in range(rows.count()):

        row = rows.nth(r)

        try:

            row_text = row.inner_text().strip()

        except Exception:

            continue

        if job_id.lower() not in row_text.lower():
            continue

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

                    return href

            except Exception:

                pass

    return None


# ============================================================
# FACH AUS DEM FACHLEITER-FELD ERMITTELN
# ============================================================

def extract_subject(fachleiter_field):

    text = " ".join(
        fachleiter_field.split()
    )

    patterns = [

        r"Eine Fachleitung im Fach (.+?) am Seminar",

        r"Fachleiter/innen im Fach (.+?) am Seminar",

        r"Fachleiter/in(?:nen)? im Fach (.+?) am Seminar",

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            subject = match.group(1).strip()

            subject = re.sub(
                r"\s*-\s*Aktenzeichen:.*$",
                "",
                subject,
                flags=re.IGNORECASE
            )

            return subject

    return "Nicht angegeben"


# ============================================================
# LEHRAMT / SEMINAR ERMITTELN
# ============================================================

def extract_seminar_info(fachleiter_field):

    text = " ".join(
        fachleiter_field.split()
    )

    match = re.search(
        r"am Seminar für das (Lehramt.+?)(?:\s*-\s*Aktenzeichen:|$)",
        text,
        re.IGNORECASE
    )

    if match:

        return match.group(1).strip()

    return "Nicht angegeben"


# ============================================================
# AKTENZEICHEN AUS FACHLEITER-FELD
# ============================================================

def extract_job_title(fachleiter_field):

    lines = [
        line.strip()
        for line in fachleiter_field.splitlines()
        if line.strip()
    ]

    if not lines:
        return "Fachleiter/-in an einem Zentrum für schulpraktische Lehrerausbildung (w/m/d)"

    return lines[0]


# ============================================================
# ZELLE NACH POSITION SUCHEN
# ============================================================

def find_cell_containing(cells, keywords):

    for cell in cells:

        cell_lower = cell.lower()

        if all(
            keyword.lower() in cell_lower
            for keyword in keywords
        ):

            return cell.strip()

    return ""


# ============================================================
# STELLENINFORMATIONEN AUS TABELLE EXTRAHIEREN
# ============================================================

def extract_job_information(result):

    cells = result["cells"]

    fachleiter_field = result["fachleiter_field"]

    # --------------------------------------------------------
    # Fach
    # --------------------------------------------------------

    fach = extract_subject(
        fachleiter_field
    )

    # --------------------------------------------------------
    # Seminar / Lehramt
    # --------------------------------------------------------

    seminar = extract_seminar_info(
        fachleiter_field
    )

    # --------------------------------------------------------
    # Stellenbezeichnung
    # --------------------------------------------------------

    stellenbezeichnung = extract_job_title(
        fachleiter_field
    )

    # --------------------------------------------------------
    # Ort
    # --------------------------------------------------------

    ort = find_cell_containing(
        cells,
        [ORT_NAME]
    )

    if not ort:
        ort = ORT_NAME

    # --------------------------------------------------------
    # Besoldung / Zulage
    # --------------------------------------------------------

    besoldung = ""

    for cell in cells:

        lower = cell.lower()

        if (
            "zulage" in lower
            or "besoldung" in lower
            or "lbeso" in lower
        ):

            besoldung = cell.strip()
            break

    if not besoldung:
        besoldung = "Nicht angegeben"

    # --------------------------------------------------------
    # Voraussetzungen
    # --------------------------------------------------------

    voraussetzungen = ""

    for cell in cells:

        lower = cell.lower()

        if (
            "befähigung für das lehramt" in lower
            or "beendigung der beamtenrechtlichen probezeit" in lower
        ):

            voraussetzungen = cell.strip()
            break

    if not voraussetzungen:
        voraussetzungen = "Nicht angegeben"

    # --------------------------------------------------------
    # Tätigkeit / gewünschte Erfahrungen
    # --------------------------------------------------------

    taetigkeit = ""

    for cell in cells:

        lower = cell.lower()

        if (
            "teilzeitbeschäftigung" in lower
            or "die tätigkeit umfasst" in lower
            or "gewünscht sind" in lower
        ):

            taetigkeit = cell.strip()
            break

    if not taetigkeit:
        taetigkeit = "Nicht angegeben"

    # --------------------------------------------------------
    # Bewerbungsfrist
    # --------------------------------------------------------

    frist = ""

    date_pattern = r"\b\d{2}\.\d{2}\.\d{4}\b"

    for cell in cells:

        dates = re.findall(
            date_pattern,
            cell
        )

        if dates:

            # Die letzte Datumsangabe der betreffenden
            # Zelle ist normalerweise die Bewerbungsfrist.
            frist = dates[-1]
            break

    if not frist:
        frist = "Nicht angegeben"

    # --------------------------------------------------------
    # Bewerbung / Kontakt
    # --------------------------------------------------------

    kontakt = ""

    for cell in cells:

        lower = cell.lower()

        if (
            "dez47.fachleitung" in lower
            or "bezirksregierung düsseldorf" in lower
        ):

            kontakt = cell.strip()
            break

    if not kontakt:
        kontakt = "Nicht angegeben"

    return {
        "fach": fach,
        "seminar": seminar,
        "stellenbezeichnung": stellenbezeichnung,
        "ort": ort,
        "besoldung": besoldung,
        "voraussetzungen": voraussetzungen,
        "taetigkeit": taetigkeit,
        "frist": frist,
        "kontakt": kontakt
    }


# ============================================================
# TEXT AUFBEREITEN
# ============================================================

def clean_text(text):

    if not text:
        return ""

    # Mehrfache Leerzeichen reduzieren
    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    # Mehrfache Leerzeilen reduzieren
    text = re.sub(
        r"\n\s*\n+",
        "\n",
        text
    )

    return text.strip()


# ============================================================
# KONTAKT AUFBEREITEN
# ============================================================

def format_contact(contact):

    contact = clean_text(
        contact
    )

    # E-Mail-Adresse separat erkennen
    email_match = re.search(
        r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
        contact
    )

    email_address = (
        email_match.group(0)
        if email_match
        else None
    )

    # Faxnummern entfernen
    contact = re.sub(
        r"Fax:\s*[0-9\-/ ]+",
        "",
        contact,
        flags=re.IGNORECASE
    )

    contact = re.sub(
        r"\s{2,}",
        " ",
        contact
    )

    contact = contact.strip(
        " -\t"
    )

    if email_address:

        return (
            f"{contact}\n"
            f"E-Mail: {email_address}"
        )

    return contact


# ============================================================
# E-MAIL TEXT ERSTELLEN
# ============================================================

def build_email(new_jobs):

    now = datetime.now()

    timestamp = now.strftime(
        "%d.%m.%Y %H:%M:%S"
    )

    lines = []

    lines.append(
        "Neue STELLA-Ausschreibungen"
    )

    lines.append("")
    lines.append(
        f"Ort: {ORT_NAME}"
    )
    lines.append(
        f"Anzahl neue Stellen: {len(new_jobs)}"
    )
    lines.append(
        f"Prüfzeitpunkt: {timestamp}"
    )

    lines.append("")
    lines.append(
        "=" * 68
    )

    for index, job in enumerate(
        new_jobs,
        start=1
    ):

        info = job["information"]

        lines.append("")

        lines.append(
            f"STELLE {index} VON {len(new_jobs)}"
        )

        lines.append(
            "=" * 68
        )

        # ----------------------------------------------------
        # Basisdaten
        # ----------------------------------------------------

        lines.append(
            f"Fach: {info['fach']}"
        )

        lines.append(
            f"Lehramt / Seminar: {info['seminar']}"
        )

        lines.append(
            f"Aktenzeichen: {job['id']}"
        )

        lines.append("")

        # ----------------------------------------------------
        # Stellenbezeichnung
        # ----------------------------------------------------

        lines.append(
            "-" * 68
        )

        lines.append(
            "STELLENBEZEICHNUNG"
        )

        lines.append(
            "-" * 68
        )

        lines.append(
            clean_text(
                info["stellenbezeichnung"]
            )
        )

        lines.append("")

        # ----------------------------------------------------
        # Ausschreibung
        # ----------------------------------------------------

        lines.append(
            "-" * 68
        )

        lines.append(
            "AUSSCHREIBUNG"
        )

        lines.append(
            "-" * 68
        )

        fachleiter_field = clean_text(
            job["fachleiter_field"]
        )

        # Die erste Zeile ist die allgemeine
        # Stellenbezeichnung. Diese wurde bereits oben
        # ausgegeben.
        fachleiter_lines = [
            line.strip()
            for line in fachleiter_field.splitlines()
            if line.strip()
        ]

        if len(fachleiter_lines) > 1:

            lines.append(
                " ".join(
                    fachleiter_lines[1:]
                )
            )

        else:

            lines.append(
                fachleiter_field
            )

        lines.append("")

        # ----------------------------------------------------
        # Ort / Seminar
        # ----------------------------------------------------

        lines.append(
            "-" * 68
        )

        lines.append(
            "ORT / SEMINAR"
        )

        lines.append(
            "-" * 68
        )

        lines.append(
            info["ort"]
        )

        lines.append(
            info["seminar"]
        )

        lines.append("")

        # ----------------------------------------------------
        # Vergütung
        # ----------------------------------------------------

        lines.append(
            "-" * 68
        )

        lines.append(
            "VERGÜTUNG"
        )

        lines.append(
            "-" * 68
        )

        lines.append(
            clean_text(
                info["besoldung"]
            )
        )

        lines.append("")

        # ----------------------------------------------------
        # Voraussetzungen
        # ----------------------------------------------------

        lines.append(
            "-" * 68
        )

        lines.append(
            "VORAUSSETZUNGEN"
        )

        lines.append(
            "-" * 68
        )

        lines.append(
            clean_text(
                info["voraussetzungen"]
            )
        )

        lines.append("")

        # ----------------------------------------------------
        # Tätigkeit
        # ----------------------------------------------------

        lines.append(
            "-" * 68
        )

        lines.append(
            "TÄTIGKEIT / ERWÜNSCHTE ERFAHRUNGEN"
        )

        lines.append(
            "-" * 68
        )

        lines.append(
            clean_text(
                info["taetigkeit"]
            )
        )

        lines.append("")

        # ----------------------------------------------------
        # Bewerbungsfrist
        # ----------------------------------------------------

        lines.append(
            "-" * 68
        )

        lines.append(
            "BEWERBUNGSFRIST"
        )

        lines.append(
            "-" * 68
        )

        lines.append(
            info["frist"]
        )

        lines.append("")

        # ----------------------------------------------------
        # Kontakt
        # ----------------------------------------------------

        lines.append(
            "-" * 68
        )

        lines.append(
            "BEWERBUNG / KONTAKT"
        )

        lines.append(
            "-" * 68
        )

        lines.append(
            format_contact(
                info["kontakt"]
            )
        )

        lines.append("")

        # ----------------------------------------------------
        # STELLA-LINK
        # ----------------------------------------------------

        lines.append(
            "-" * 68
        )

        lines.append(
            "STELLA"
        )

        lines.append(
            "-" * 68
        )

        lines.append(
            job["url"]
        )

        lines.append("")

    lines.append(
        "=" * 68
    )

    lines.append(
        "STELLA Monitor"
    )

    return "\n".join(
        lines
    )


# ============================================================
# E-MAIL SENDEN
# ============================================================

def send_email(new_jobs):

    sender = os.environ["FREENET_EMAIL"]
    password = os.environ["FREENET_PASSWORD"]
    recipient = os.environ["MAIL_TO"]

    email_body = build_email(
        new_jobs
    )

    subject = (
        f"STELLA: {len(new_jobs)} neue "
        f"Fachleiter-Stelle(n) – {ORT_NAME}"
    )

    msg = EmailMessage()

    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject

    msg.set_content(
        email_body
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
        f"Neue Stellen in dieser Mail: {len(new_jobs)}"
    )

    server = smtplib.SMTP(
        "mx.freenet.de",
        587,
        timeout=30
    )

    try:

        # ----------------------------------------------------
        # EHLO
        # ----------------------------------------------------

        print("EHLO...")

        code, response = server.ehlo()

        print(
            code,
            response
        )

        # ----------------------------------------------------
        # STARTTLS
        # ----------------------------------------------------

        print("STARTTLS...")

        code, response = server.starttls()

        print(
            code,
            response
        )

        # ----------------------------------------------------
        # EHLO nach TLS
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
                "AUTH LOGIN konnte nicht gestartet werden: "
                f"{code} {response}"
            )

        # ----------------------------------------------------
        # Benutzername
        # ----------------------------------------------------

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
                "Benutzername wurde abgelehnt: "
                f"{code} {response}"
            )

        # ----------------------------------------------------
        # Passwort
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
                "Authentifizierung fehlgeschlagen: "
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
                f"MAIL FROM abgelehnt: {code} {response}"
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
        print(
            "========================================"
        )
        print(
            "E-MAIL ERFOLGREICH VERSENDET."
        )
        print(
            f"{len(new_jobs)} Stelle(n) in einer einzigen E-Mail."
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

        # ----------------------------------------------------
        # Merkliste laden
        # ----------------------------------------------------

        seen = load_seen()

        print(
            f"Bereits bekannte Stellen: {len(seen)}"
        )

        # ----------------------------------------------------
        # STELLA öffnen
        # ----------------------------------------------------

        open_stella(page)

        search_stella(page)

        # ----------------------------------------------------
        # Ergebnisse
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Neue Stellen sammeln
        # ----------------------------------------------------

        new_jobs = []

        # ----------------------------------------------------
        # Merkliste zunächst NICHT verändern
        # ----------------------------------------------------

        updated_seen = dict(
            seen
        )

        # ----------------------------------------------------
        # Ergebnisse prüfen
        # ----------------------------------------------------

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
            # WICHTIG:
            #
            # Die Sonderpädagogik-Prüfung erfolgt ausschließlich
            # im Fachleiter-Feld.
            # ------------------------------------------------

            fachleiter_field = result[
                "fachleiter_field"
            ]

            if not is_sonderpaedagogik(
                fachleiter_field
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
                fachleiter_field
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
                    "→ Bereits bekannt – keine neue Meldung"
                )

                continue

            # ------------------------------------------------
            # Detailseite
            # ------------------------------------------------

            detail_url = find_detail_url(
                page,
                job_id
            )

            detail_page_url = page.url

            if detail_url:

                detail = read_detail_page(
                    context,
                    detail_url
                )

                if detail:

                    detail_page_url = detail[
                        "url"
                    ]

            # ------------------------------------------------
            # Stelleninformationen extrahieren
            # ------------------------------------------------

            information = extract_job_information(
                result
            )

            # ------------------------------------------------
            # Neue Stelle
            # ------------------------------------------------

            print(
                "→ NEUE STELLE ZUR SAMMLUNG HINZUGEFÜGT"
            )

            timestamp = datetime.now().isoformat(
                timespec="seconds"
            )

            job_data = {

                "id": job_id,

                "url": detail_page_url,

                "gefunden_am": timestamp,

                "fachleiter_field":
                    fachleiter_field,

                "information":
                    information
            }

            new_jobs.append(
                job_data
            )

            # Noch NICHT dauerhaft speichern.
            #
            # Das geschieht erst NACH erfolgreichem
            # E-Mail-Versand.

            updated_seen[job_id] = {

                "url": detail_page_url,

                "erstmals_gefunden":
                    timestamp
            }

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
            f"Neue passende Stellen: {len(new_jobs)}"
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
        # NEUE STELLEN → EINE MAIL
        # ====================================================

        else:

            print()
            print(
                f"{len(new_jobs)} neue Stelle(n) gefunden."
            )

            print(
                "Alle Stellen werden in EINER E-Mail zusammengefasst."
            )

            # ------------------------------------------------
            # E-Mail senden
            # ------------------------------------------------

            mail_success = send_email(
                new_jobs
            )

            # ------------------------------------------------
            # NUR BEI ERFOLGREICHEM VERSAND SPEICHERN
            # ------------------------------------------------

            if mail_success:

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
                        "E-Mail wurde versendet, "
                        "aber die Merkliste konnte nicht "
                        "gespeichert werden."
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
