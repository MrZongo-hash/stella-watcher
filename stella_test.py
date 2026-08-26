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
# Für den späteren Betrieb:
#
# ORT_NAME = "Köln"
# ORT_VALUE = "315000"
# ------------------------------------------------------------

ORT_NAME = "Köln"
ORT_VALUE = "315000"


# ============================================================
# DATEIEN
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
# SMTP
# ============================================================

SMTP_SERVER = "mx.freenet.de"
SMTP_PORT = 587


# ============================================================
# SONDERPÄDAGOGIK
# ============================================================
#
# WICHTIG:
# Die Prüfung erfolgt ausschließlich im Feld
#
# "Fachleiter/-in an einem Zentrum für schulpraktische
# Lehrerausbildung (w/m/d)"
#
# Wir suchen NICHT mehr im kompletten Datensatz nach
# "Sonderpädagogik".
# ============================================================

SONDERPAEDAGOGIK_KEYWORDS = [
    "sonderpädagogische förderung",
    "sonderpädagogischen förderung",
    "sonderpädagogik",
    "sonderpädagogischen",
    "lehramt für sonderpädagogische förderung",
    "lehramt für sonderpädagogik",
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

                print(
                    "Merkliste ist leer – starte mit 0 bekannten Stellen."
                )

                return {}

            data = json.loads(content)

            if isinstance(data, dict):

                # ------------------------------------------------
                # Vorhandene IDs normalisieren
                # ------------------------------------------------

                normalized = {}

                for key, value in data.items():

                    normalized_key = normalize_id(key)

                    normalized[normalized_key] = value

                return normalized

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
# ID NORMALISIEREN
# ============================================================

def normalize_id(value):

    if value is None:
        return ""

    value = str(value)

    value = value.strip()

    value = re.sub(
        r"\s+",
        "",
        value
    )

    return value.upper()


# ============================================================
# AKTENZEICHEN SUCHEN
# ============================================================

def extract_aktenzeichen(text):

    patterns = [

        r"\b\d+\.[A-Z]+-FL\d+[A-Z]?\b",

        r"\b\d+\.[A-Z]-FL\d+[A-Z]?\b",

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            return normalize_id(
                match.group(0)
            )

    return None


# ============================================================
# SONDERPÄDAGOGIK-FELD PRÜFEN
# ============================================================

def is_sonderpaedagogik(fachleiter_feld):

    if not fachleiter_feld:
        return False

    text_lower = fachleiter_feld.lower()

    for keyword in SONDERPAEDAGOGIK_KEYWORDS:

        if keyword in text_lower:

            return True

    return False


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
# SUCHE
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

        # ----------------------------------------------------
        # Nur Fachleiter-Zeilen
        # ----------------------------------------------------

        if (
            "fachleiter/-in an einem zentrum für schulpraktische"
            not in text_lower
        ):

            continue

        # Kopfzeile ignorieren
        if "stellenbezeichnung" in text_lower:

            continue

        # ----------------------------------------------------
        # Fachleiter-Feld separat bestimmen
        # ----------------------------------------------------

        fachleiter_feld = ""

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        for line in lines:

            if (
                line.lower()
                == "fachleiter/-in an einem zentrum für schulpraktische lehrerausbildung (w/m/d)"
            ):

                fachleiter_feld = line

                break

        # ----------------------------------------------------
        # In der Regel steht die Fachinformation direkt
        # danach. Wir nehmen deshalb zusätzlich die folgende
        # Zeile.
        # ----------------------------------------------------

        fachleiter_index = -1

        for index, line in enumerate(lines):

            if (
                line.lower()
                == "fachleiter/-in an einem zentrum für schulpraktische lehrerausbildung (w/m/d)"
            ):

                fachleiter_index = index

                break

        if fachleiter_index >= 0:

            fachleiter_details = ""

            if fachleiter_index + 1 < len(lines):

                fachleiter_details = lines[
                    fachleiter_index + 1
                ]

            if fachleiter_details:

                fachleiter_feld = (
                    fachleiter_feld
                    + "\n"
                    + fachleiter_details
                )

        # ----------------------------------------------------
        # Aktenzeichen
        # ----------------------------------------------------

        aktenzeichen = extract_aktenzeichen(
            text
        )

        if not aktenzeichen:

            print(
                "WARNUNG: Kein Aktenzeichen gefunden."
            )

            continue

        # ----------------------------------------------------
        # Detail-Link
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
                    "Weitere Hinweise"
                    in link_text
                    and href
                ):

                    detail_url = href

                    break

            except Exception:

                pass

        results.append({

            "text": text,

            "fachleiter_feld": fachleiter_feld,

            "aktenzeichen": aktenzeichen,

            "detail_url": detail_url

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
# INFORMATIONEN AUS ERGEBNISZEILE EXTRAHIEREN
# ============================================================

def extract_information(result_text):

    lines = [
        line.strip()
        for line in result_text.splitlines()
        if line.strip()
    ]

    # --------------------------------------------------------
    # Stellenbezeichnung
    # --------------------------------------------------------

    stellenbezeichnung = (
        "Fachleiter/-in an einem Zentrum für schulpraktische "
        "Lehrerausbildung (w/m/d)"
    )

    # --------------------------------------------------------
    # Ausschreibung
    # --------------------------------------------------------

    ausschreibung = ""

    for i, line in enumerate(lines):

        if (
            line.lower()
            == stellenbezeichnung.lower()
        ):

            if i + 1 < len(lines):

                ausschreibung = lines[i + 1]

            break

    # --------------------------------------------------------
    # Fach
    # --------------------------------------------------------

    fach = ""

    fach_match = re.search(
        r"(?:im Fach|im Fachbereich)\s+([^,]+?)(?:\s+am Seminar|\s+-\s+Aktenzeichen)",
        result_text,
        re.IGNORECASE
    )

    if fach_match:

        fach = fach_match.group(1).strip()

    else:

        # Zweiter Versuch
        fach_match = re.search(
            r"Fachleiter/innen?\s+im Fach\s+(.+?)\s+am Seminar",
            result_text,
            re.IGNORECASE
        )

        if fach_match:

            fach = fach_match.group(1).strip()

    # --------------------------------------------------------
    # Lehramt / Seminar
    # --------------------------------------------------------

    lehramt = ""

    seminar_match = re.search(
        r"am Seminar für das (Lehramt[^,\-]+)",
        result_text,
        re.IGNORECASE
    )

    if seminar_match:

        lehramt = seminar_match.group(1).strip()

    # --------------------------------------------------------
    # Ort
    # --------------------------------------------------------

    ort = ORT_NAME

    # --------------------------------------------------------
    # ZfsL
    # --------------------------------------------------------

    zfs_l = ""

    zfs_match = re.search(
        r"(Zentrum für schulpraktische Lehrerausbildung[^\t\n]*)",
        result_text,
        re.IGNORECASE
    )

    if zfs_match:

        zfs_l = zfs_match.group(1).strip()

    # --------------------------------------------------------
    # Vergütung
    # --------------------------------------------------------

    verguetung = ""

    verguetung_patterns = [

        r"(Zulage gemäß § 55.*?BesG NRW)",

        r"(A\s*14\s*-\s*A\s*15\s*LBesO)",

        r"(A\s*\d+\s*-\s*A\s*\d+\s*LBesO)",

    ]

    for pattern in verguetung_patterns:

        match = re.search(
            pattern,
            result_text,
            re.IGNORECASE
        )

        if match:

            verguetung = match.group(1).strip()

            break

    # --------------------------------------------------------
    # Voraussetzungen
    # --------------------------------------------------------

    voraussetzungen = ""

    marker = (
        "Befähigung für das Lehramt"
    )

    start = result_text.find(
        marker
    )

    if start >= 0:

        remaining = result_text[
            start:
        ]

        # Tätigkeit beginnt meistens danach
        end_markers = [
            "Teilzeitbeschäftigung",
            "Weitere Hinweise"
        ]

        end_positions = []

        for end_marker in end_markers:

            position = remaining.find(
                end_marker
            )

            if position > 0:

                end_positions.append(
                    position
                )

        if end_positions:

            voraussetzungen = remaining[
                :min(end_positions)
            ].strip()

    # --------------------------------------------------------
    # Tätigkeit
    # --------------------------------------------------------

    taetigkeit = ""

    start = result_text.find(
        "Teilzeitbeschäftigung"
    )

    if start >= 0:

        remaining = result_text[
            start:
        ]

        end = remaining.find(
            "Weitere Hinweise"
        )

        if end > 0:

            taetigkeit = remaining[
                :end
            ].strip()

        else:

            taetigkeit = remaining.strip()

    # --------------------------------------------------------
    # Bewerbungsfrist
    # --------------------------------------------------------
    #
    # WICHTIG:
    # Wir suchen hier bewusst nach einem Datum am Ende
    # der Ergebniszeile.
    #
    # Das verhindert, dass z.B. "ab 01.10.2011" aus den
    # Lehramtsvoraussetzungen als Bewerbungsfrist
    # übernommen wird.
    # --------------------------------------------------------

    dates = re.findall(
        r"\b\d{2}\.\d{2}\.\d{4}\b",
        result_text
    )

    bewerbungsfrist = ""

    if dates:

        # Normalerweise ist das letzte Datum die Frist.
        bewerbungsfrist = dates[-1]

    # --------------------------------------------------------
    # Kontakt
    # --------------------------------------------------------

    kontakt = ""

    kontakt_match = re.search(
        r"(Bezirksregierung.*?)(?:\n|$)",
        result_text,
        re.IGNORECASE
    )

    if kontakt_match:

        kontakt = kontakt_match.group(1).strip()

    email = ""

    email_match = re.search(
        r"[\w\.-]+@[\w\.-]+\.\w+",
        result_text
    )

    if email_match:

        email = email_match.group(0)

    # --------------------------------------------------------
    # Telefonnummer
    # --------------------------------------------------------

    telefon = ""

    telefon_match = re.search(
        r"\b0\d{2,5}[-\s]\d{3,8}\b",
        result_text
    )

    if telefon_match:

        telefon = telefon_match.group(0)

    return {

        "stellenbezeichnung":
            stellenbezeichnung,

        "ausschreibung":
            ausschreibung,

        "fach":
            fach,

        "lehramt":
            lehramt,

        "ort":
            ort,

        "zfs_l":
            zfs_l,

        "verguetung":
            verguetung,

        "voraussetzungen":
            voraussetzungen,

        "taetigkeit":
            taetigkeit,

        "bewerbungsfrist":
            bewerbungsfrist,

        "kontakt":
            kontakt,

        "email":
            email,

        "telefon":
            telefon

    }


# ============================================================
# E-MAIL TEXT ERZEUGEN
# ============================================================

def build_email(new_jobs):

    now = datetime.now().strftime(
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
        f"Prüfzeitpunkt: {now}"
    )

    lines.append("")

    lines.append(
        "=" * 68
    )

    lines.append("")

    for index, job in enumerate(
        new_jobs,
        start=1
    ):

        info = job["info"]

        lines.append(
            f"STELLE {index} VON {len(new_jobs)}"
        )

        lines.append(
            "=" * 68
        )

        # ----------------------------------------------------
        # Kopf
        # ----------------------------------------------------

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
            info["stellenbezeichnung"]
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

        lines.append(
            info["ausschreibung"]
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
            info["zfs_l"]
        )

        lines.append(
            info["lehramt"]
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
            info["verguetung"]
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
            info["voraussetzungen"]
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
            info["taetigkeit"]
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
            info["bewerbungsfrist"]
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
            info["kontakt"]
        )

        if info["telefon"]:

            lines.append(
                info["telefon"]
            )

        if info["email"]:

            lines.append(
                f"E-Mail: {info['email']}"
            )

        lines.append("")

        # ----------------------------------------------------
        # STELLA
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

        lines.append("")

    lines.append(
        "=" * 68
    )

    lines.append(
        "STELLA Monitor"
    )

    return "\n".join(lines)


# ============================================================
# E-MAIL SENDEN
# ============================================================

def send_email(new_jobs):

    if not new_jobs:

        print(
            "Keine E-Mail notwendig."
        )

        return True

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
        f"Fachleiter-Stelle(n) – {ORT_NAME}"
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
        SMTP_SERVER,
        SMTP_PORT,
        timeout=30
    )

    try:

        print("EHLO...")

        code, response = server.ehlo()

        print(
            code,
            response
        )

        print("STARTTLS...")

        code, response = server.starttls()

        print(
            code,
            response
        )

        print("EHLO nach TLS...")

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

        username_encoded = (
            base64.b64encode(
                sender.encode("utf-8")
            )
            .decode("ascii")
        )

        password_encoded = (
            base64.b64encode(
                password.encode("utf-8")
            )
            .decode("ascii")
        )

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

            print()
            print(
                "Bekannte Aktenzeichen:"
            )

            for known_id in seen:

                print(
                    f"  - {known_id}"
                )

        # ----------------------------------------------------
        # STELLA
        # ----------------------------------------------------

        open_stella(page)

        search_stella(page)

        # ----------------------------------------------------
        # ERGEBNIS
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
        # NEUE STELLEN
        # ----------------------------------------------------

        new_jobs = []

        # Wichtig:
        # updated_seen wird erst nach erfolgreichem
        # Mailversand wirklich gespeichert.

        updated_seen = dict(
            seen
        )

        # ----------------------------------------------------
        # ALLE ERGEBNISSE PRÜFEN
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
                f"Prüfe Ausschreibung {index}/{len(results)}"
            )

            print(
                "----------------------------------------"
            )

            fachleiter_feld = result[
                "fachleiter_feld"
            ]

            job_id = normalize_id(
                result["aktenzeichen"]
            )

            print(
                "Aktenzeichen:",
                job_id
            )

            # ------------------------------------------------
            # SONDERPÄDAGOGIK
            # ------------------------------------------------

            if not is_sonderpaedagogik(
                fachleiter_feld
            ):

                print(
                    "→ Keine Sonderpädagogik-Stelle"
                )

                continue

            print(
                "→ SONDERPÄDAGOGIK-STELLE GEFUNDEN"
            )

            # ------------------------------------------------
            # GANZ WICHTIG:
            # BEREITS BEKANNT?
            # ------------------------------------------------

            print(
                "→ Prüfe gegen Merkliste..."
            )

            if job_id in seen:

                print(
                    f"→ BEREITS BEKANNT: {job_id}"
                )

                print(
                    "→ Wird NICHT erneut gemeldet."
                )

                continue

            print(
                f"→ NEUE STELLE: {job_id}"
            )

            # ------------------------------------------------
            # DETAILSEITE
            # ------------------------------------------------

            detail = None

            detail_url = result[
                "detail_url"
            ]

            if detail_url:

                detail = read_detail_page(
                    context,
                    detail_url
                )

            # ------------------------------------------------
            # STELLA-LINK
            # ------------------------------------------------

            if detail:

                stella_url = detail[
                    "url"
                ]

            else:

                stella_url = page.url

            # ------------------------------------------------
            # INFORMATIONEN
            # ------------------------------------------------

            info = extract_information(
                result["text"]
            )

            # ------------------------------------------------
            # NEUE STELLE SAMMELN
            # ------------------------------------------------

            timestamp = datetime.now().isoformat(
                timespec="seconds"
            )

            new_job = {

                "id":
                    job_id,

                "url":
                    stella_url,

                "gefunden_am":
                    timestamp,

                "info":
                    info

            }

            new_jobs.append(
                new_job
            )

            # Noch NICHT endgültig speichern.
            updated_seen[job_id] = {

                "url":
                    stella_url,

                "erstmals_gefunden":
                    timestamp

            }

            print(
                "→ NEUE STELLE ZUR SAMMLUNG HINZUGEFÜGT"
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
        # NEUE STELLEN
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
            # MAIL VERSENDEN
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

                # Wichtig:
                # Fehler weiterwerfen!
                #
                # Dadurch wird die Merkliste NICHT
                # aktualisiert und die Stelle wird beim
                # nächsten Lauf erneut gemeldet.

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
                        f"{len(new_jobs)} Stelle(n) als gemeldet gespeichert."
                    )

                else:

                    raise RuntimeError(
                        "Merkliste konnte nach erfolgreichem "
                        "Mailversand nicht gespeichert werden."
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
