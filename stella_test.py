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
# ZIELORT
# ============================================================

ORT_NAME = "Köln"
ORT_VALUE = "315000"

# ============================================================
# DATEIEN
# ============================================================

SEEN_FILE = "stella_bereits_gemeldet.json"
STATUS_FILE = "stella_letzter_check.txt"

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

            data = json.load(f)

            if isinstance(data, dict):

                if data:
                    print(
                        f"Merkliste geladen: {len(data)} bekannte Stellen."
                    )
                else:
                    print(
                        "Merkliste ist leer – starte mit 0 bekannten Stellen."
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
# STATUSDATEI SCHREIBEN
# ============================================================

def save_status(new_count):

    now = datetime.now()

    status_text = (
        "STELLA Monitor\n\n"
        "Letzter erfolgreicher Check:\n"
        f"{now.strftime('%d.%m.%Y %H:%M:%S')}\n\n"
        "Ort:\n"
        f"{ORT_NAME}\n\n"
        "Neue passende Stellen:\n"
        f"{new_count}\n\n"
        "Status:\n"
        "ERFOLGREICH\n"
    )

    try:

        with open(
            STATUS_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(status_text)

        print()
        print(
            "Statusdatei erfolgreich aktualisiert."
        )

        return True

    except Exception as e:

        print(
            "FEHLER beim Schreiben der Statusdatei:",
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

            return match.group(0)

    return None


# ============================================================
# STABILE ID
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

    page.locator(
        "#artStelle"
    ).select_option("404")

    page.locator(
        "#institution"
    ).select_option("92")

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
# DETAILSEITE
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
# FACH AUS AUSSCHREIBUNG EXTRAHIEREN
# ============================================================

def extract_fach(text):

    patterns = [

        r"Fach\s+([A-Za-zÄÖÜäöüß /&\-]+)",

        r"Fachleiter/?innen? im Fach\s+([A-Za-zÄÖÜäöüß /&\-]+)",

        r"Fachleitung im Fach\s+([A-Za-zÄÖÜäöüß /&\-]+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            fach = match.group(1).strip()

            fach = re.split(
                r"\s+am Seminar|\s+an einem Seminar|,",
                fach,
                flags=re.IGNORECASE
            )[0]

            return fach.strip()

    return "Nicht eindeutig erkannt"


# ============================================================
# LEHRAMT / SEMINAR EXTRAHIEREN
# ============================================================

def extract_lehramt(text):

    patterns = [

        r"am Seminar für das Lehramt für sonderpädagogische Förderung",

        r"am Seminar für das Lehramt für sonderpädagogische Förderung",

    ]

    for pattern in patterns:

        if re.search(
            pattern,
            text,
            re.IGNORECASE
        ):

            return "Lehramt für sonderpädagogische Förderung"

    return "Lehramt für sonderpädagogische Förderung"


# ============================================================
# STELLA-INFORMATIONEN AUS ERGEBNISZEILE
# ============================================================

def parse_result_information(text):

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    fach = extract_fach(text)

    lehramt = extract_lehramt(text)

    stellenbezeichnung = (
        "Fachleiter/-in an einem Zentrum für "
        "schulpraktische Lehrerausbildung (w/m/d)"
    )

    ausschreibung = ""

    for line in lines:

        lower = line.lower()

        if (
            "fachleitung" in lower
            or "fachleiter/innen im fach" in lower
            or "fachleiterinnen und fachleiter" in lower
        ):

            if "aktenzeichen" in lower:

                ausschreibung = line
                break

    if not ausschreibung:

        for line in lines:

            if (
                "seminar für das lehramt für "
                "sonderpädagogische förderung"
                in line.lower()
            ):

                ausschreibung = line
                break

    if not ausschreibung:
        ausschreibung = text[:500].strip()

    # --------------------------------------------------------
    # Ort
    # --------------------------------------------------------

    ort = ORT_NAME

    # --------------------------------------------------------
    # Seminar
    # --------------------------------------------------------

    seminar = (
        f"Zentrum für schulpraktische Lehrerausbildung "
        f"{ORT_NAME}"
    )

    # --------------------------------------------------------
    # Vergütung
    # --------------------------------------------------------

    verguetung = ""

    for line in lines:

        if (
            "zulage gemäß" in line.lower()
            or "besoldungsgesetz" in line.lower()
            or "lb es o" in line.lower()
            or "lb eso" in line.lower()
        ):

            verguetung = line
            break

    # --------------------------------------------------------
    # Voraussetzungen
    # --------------------------------------------------------

    voraussetzungen = ""

    for line in lines:

        if (
            "befähigung für das lehramt" in line.lower()
        ):

            voraussetzungen = line
            break

    # --------------------------------------------------------
    # Tätigkeit
    # --------------------------------------------------------

    taetigkeit = ""

    for line in lines:

        lower = line.lower()

        if (
            "teilzeitbeschäftigung ist grundsätzlich möglich"
            in lower
        ):

            taetigkeit = line
            break

    # --------------------------------------------------------
    # Bewerbungsfrist
    # --------------------------------------------------------

    bewerbungsfrist = ""

    date_pattern = r"\b\d{2}\.\d{2}\.\d{4}\b"

    dates = re.findall(
        date_pattern,
        text
    )

    # In der Ergebniszeile ist normalerweise das letzte Datum
    # die Bewerbungsfrist.

    if dates:

        bewerbungsfrist = dates[-1]

    # --------------------------------------------------------
    # Kontakt
    # --------------------------------------------------------

    kontakt = ""

    for line in lines:

        if (
            "bezirksregierung" in line.lower()
            and (
                "dez47" in line.lower()
                or "postfach" in line.lower()
                or "am bonneshof" in line.lower()
            )
        ):

            kontakt = line
            break

    if not kontakt:

        for line in lines:

            if "dez47.fachleitung" in line.lower():

                kontakt = line
                break

    return {
        "fach": fach,
        "lehramt": lehramt,
        "stellenbezeichnung": stellenbezeichnung,
        "ausschreibung": ausschreibung,
        "ort": ort,
        "seminar": seminar,
        "verguetung": verguetung,
        "voraussetzungen": voraussetzungen,
        "taetigkeit": taetigkeit,
        "bewerbungsfrist": bewerbungsfrist,
        "kontakt": kontakt,
    }


# ============================================================
# E-MAIL TEXT ERZEUGEN
# ============================================================

def build_email(new_jobs):

    now = datetime.now()

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
        f"Prüfzeitpunkt: {now.strftime('%d.%m.%Y %H:%M:%S')}"
    )

    lines.append("")
    lines.append(
        "=" * 68
    )

    for index, job in enumerate(
        new_jobs,
        start=1
    ):

        info = job["info"]

        lines.append("")
        lines.append(
            f"STELLE {index} VON {len(new_jobs)}"
        )

        lines.append(
            "=" * 68
        )

        lines.append(
            f"Fach: {info['fach']}"
        )

        lines.append(
            f"Lehramt / Seminar: {info['lehramt']}"
        )

        lines.append(
            f"Aktenzeichen: {job['id']}"
        )

        lines.append("")

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
            info["stellenbezeichnung"]
        )

        lines.append("")

        lines.append(
            "-" * 68
        )

        lines.append(
            "AUSSCHREIBUNG"
        )

        lines.append(
            "-" * 68
        )

        lines.append(
            info["ausschreibung"]
        )

        lines.append("")

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

        lines.append(
            info["lehramt"]
        )

        lines.append("")

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
            info["verguetung"]
            if info["verguetung"]
            else "Keine Angabe erkannt."
        )

        lines.append("")

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
            info["voraussetzungen"]
            if info["voraussetzungen"]
            else "Keine Angabe erkannt."
        )

        lines.append("")

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
            info["taetigkeit"]
            if info["taetigkeit"]
            else "Keine Angabe erkannt."
        )

        lines.append("")

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
            info["bewerbungsfrist"]
            if info["bewerbungsfrist"]
            else "Keine Angabe erkannt."
        )

        lines.append("")

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
            info["kontakt"]
            if info["kontakt"]
            else "Keine Kontaktangabe erkannt."
        )

        # ----------------------------------------------------
        # E-Mail-Adresse separat hervorheben
        # ----------------------------------------------------

        email_match = re.search(
            r"[\w\.-]+@[\w\.-]+\.\w+",
            info["kontakt"]
        )

        if email_match:

            lines.append(
                f"E-Mail: {email_match.group(0)}"
            )

        lines.append("")

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

    return "\n".join(lines)


# ============================================================
# E-MAIL VERSENDEN
# ============================================================

def send_email(new_jobs):

    sender = os.environ["FREENET_EMAIL"]
    password = os.environ["FREENET_PASSWORD"]
    recipient = os.environ["MAIL_TO"]

    email_body = build_email(
        new_jobs
    )

    msg = EmailMessage()

    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = (
        f"STELLA: {len(new_jobs)} neue "
        f"Sonderpädagogik-Fachleiterstelle(n) in {ORT_NAME}"
    )

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

        print("EHLO...")

        code, response = server.ehlo()

        print(code, response)

        print("STARTTLS...")

        code, response = server.starttls()

        print(code, response)

        print("EHLO nach TLS...")

        code, response = server.ehlo()

        print(code, response)

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

        print(
            "Benutzername senden..."
        )

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

        print(
            "Passwort senden..."
        )

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

        print(
            "Login erfolgreich."
        )

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

        server.quit()


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
        # MERKLISTE
        # ----------------------------------------------------

        seen = load_seen()

        print(
            f"Bereits bekannte Stellen: {len(seen)}"
        )

        if seen:

            print(
                "Bekannte Aktenzeichen:"
            )

            for job_id in seen:

                print(
                    f"  - {job_id}"
                )

        # ----------------------------------------------------
        # STELLA
        # ----------------------------------------------------

        open_stella(page)

        search_stella(page)

        # ----------------------------------------------------
        # ERGEBNISSE
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

        results = get_result_rows(page)

        print()
        print(
            "Gefundene Fachleiter-Ausschreibungen:",
            len(results)
        )

        # ----------------------------------------------------
        # PRÜFUNG
        # ----------------------------------------------------

        new_jobs = []

        updated_seen = dict(
            seen
        )

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

            result_text = result["text"]

            job_id = create_job_id(
                result_text
            )

            print(
                "Aktenzeichen:",
                job_id
            )

            # ------------------------------------------------
            # NUR DAS FACHLEITER-FELD PRÜFEN
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

            print(
                "→ Prüfe gegen Merkliste..."
            )

            # ------------------------------------------------
            # BEREITS BEKANNT
            # ------------------------------------------------

            if job_id in seen:

                print(
                    f"→ BEREITS BEKANNT: {job_id}"
                )

                print(
                    "→ Wird NICHT erneut gemeldet."
                )

                continue

            # ------------------------------------------------
            # NEUE STELLE
            # ------------------------------------------------

            print(
                "→ NEUE STELLE GEFUNDEN!"
            )

            detail_url = None

            rows = page.locator("tr")

            for r in range(
                rows.count()
            ):

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
            # DETAILSEITE
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
            # INFORMATIONEN
            # ------------------------------------------------

            info = parse_result_information(
                result_text
            )

            timestamp = datetime.now().isoformat(
                timespec="seconds"
            )

            job_data = {

                "id": job_id,

                "url": detail_page_url,

                "gefunden_am": timestamp,

                "text": detail_text,

                "info": info,
            }

            new_jobs.append(
                job_data
            )

            # ------------------------------------------------
            # NOCH NICHT SPEICHERN
            # ------------------------------------------------
            #
            # Die Stelle wird erst nach erfolgreichem
            # E-Mail-Versand in die Merkliste aufgenommen.
            #

            updated_seen[job_id] = {

                "url": detail_page_url,

                "erstmals_gefunden": timestamp
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
        # NEUE STELLEN
        # ====================================================

        if new_jobs:

            print()
            print(
                f"{len(new_jobs)} neue Stelle(n) gefunden."
            )

            print(
                "Alle Stellen werden in EINER E-Mail zusammengefasst."
            )

            # ------------------------------------------------
            # E-MAIL
            # ------------------------------------------------

            mail_success = False

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

                raise

            # ------------------------------------------------
            # NUR NACH ERFOLGREICHER MAIL SPEICHERN
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
                        "Merkliste konnte nicht gespeichert werden."
                    )

        # ====================================================
        # KEINE NEUEN STELLEN
        # ====================================================

        else:

            print()
            print(
                "Keine neuen passenden Stellen gefunden."
            )

        # ====================================================
        # ERFOLGREICHER CHECK
        # ====================================================
        #
        # Die Statusdatei wird NUR erreicht, wenn das gesamte
        # Programm bis hierhin erfolgreich durchgelaufen ist.
        #

        save_status(
            len(new_jobs)
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
