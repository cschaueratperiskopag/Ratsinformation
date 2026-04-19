#!/usr/bin/env python3
"""
RIS-Monitor v1.0 - Schlagwort-Scanner fuer kommunale Ratsinformationssysteme

Nutzung:
    python ris_monitor.py                              # Volllauf
    python ris_monitor.py -k "Kita,Haushalt,B-Plan"    # Eigene Keywords
    python ris_monitor.py -d 14 -o bericht.html        # 14 Tage, HTML
    python ris_monitor.py --kommune schoenefeld         # Nur eine Kommune
    python ris_monitor.py --list-kommunen               # Alle Kommunen zeigen

Voraussetzungen:  pip install requests beautifulsoup4 lxml
"""

import requests, json, re, logging, argparse, time, smtplib
import html as htmlmod
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional
from abc import ABC, abstractmethod
from urllib.parse import urljoin
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ris")


# ============================================================================
# DATENMODELLE
# ============================================================================

@dataclass
class RISDocument:
    """Ein gefundenes Dokument / Tagesordnungspunkt."""
    kommune: str
    gremium: str
    datum: str
    titel: str
    url: str
    doc_type: str = ""
    beschluss: str = ""
    matched_keywords: list = field(default_factory=list)
    raw_text: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class KommuneConfig:
    """Konfiguration einer Kommune."""
    name: str
    key: str
    system: str       # allris | oparl | ris_muenchen
    base_url: str
    oparl_url: str = ""
    notes: str = ""


# ============================================================================
# KONFIGURATION
# ============================================================================

DEFAULT_KEYWORDS = [
    "Bebauungsplan", "B-Plan", "Bauleitplanung", "Flaechennutzungsplan",
    "Bauvorhaben", "Baugenehmigung", "Aufstellungsbeschluss",
    "Satzungsbeschluss", "Strassenbau", "Radweg", "Verkehrsplanung",
    "Kita", "Kindertagesstaette", "Schule", "Schulbau",
    "Klimaschutz", "Photovoltaik", "Windkraft", "Nachhaltigkeit",
    "Haushalt", "Haushaltsplan", "Nachtragshaushalt",
    "Grundsteuer", "Gewerbesteuer",
    "Gewerbegebiet", "Ansiedlung", "Wirtschaftsfoerderung",
    "Flughafen", "BER", "Wohnen", "Sozialwohnung",
    "Breitband", "Glasfaser", "Digitalisierung",
]

EMAIL_CONFIG = {
    "enabled": False,
    "smtp_host": "smtp.example.com",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_pass": "",
    "from_addr": "ris@example.com",
    "to_addrs": ["you@example.com"],
    "subject_prefix": "[RIS-Monitor]",
}


# ============================================================================
# KOMMUNEN-KONFIGURATION
# ============================================================================
# Hinweis: URLs muessen beim ersten Einsatz verifiziert werden!
# Manche Kommunen aendern URLs oder wechseln das System.

KOMMUNEN = {
    # --- Brandenburg ---
    "schoenefeld": KommuneConfig(
        name="Gemeinde Schoenefeld",
        key="schoenefeld",
        system="allris",
        base_url="https://www.ratsinfo-online.net/schoenefeld-bi",
        notes="ALLRIS Buergerinfo, Gemeinde am Flughafen BER",
    ),
    "wandlitz": KommuneConfig(
        name="Gemeinde Wandlitz",
        key="wandlitz",
        system="allris",
        base_url="https://ris.wandlitz.de/bi",
    ),
    "koenigs_wusterhausen": KommuneConfig(
        name="Stadt Koenigs Wusterhausen",
        key="koenigs_wusterhausen",
        system="allris",
        base_url="https://www.ratsinfo-online.net/koenigswusterhausen-bi",
    ),

    # --- Berlin (alle 12 Bezirke, nutzen ALLRIS) ---
    "berlin_mitte": KommuneConfig(
        name="Berlin Mitte", key="berlin_mitte", system="allris",
        base_url="https://www.berlin.de/ba-mitte/politik-und-verwaltung/bezirksverordnetenversammlung/online",
    ),
    "berlin_friedrichshain_kreuzberg": KommuneConfig(
        name="Berlin Friedrichshain-Kreuzberg",
        key="berlin_friedrichshain_kreuzberg", system="allris",
        base_url="https://www.berlin.de/ba-friedrichshain-kreuzberg/politik-und-verwaltung/bezirksverordnetenversammlung/online",
    ),
    "berlin_pankow": KommuneConfig(
        name="Berlin Pankow", key="berlin_pankow", system="allris",
        base_url="https://www.berlin.de/ba-pankow/politik-und-verwaltung/bezirksverordnetenversammlung/online",
    ),
    "berlin_charlottenburg_wilmersdorf": KommuneConfig(
        name="Berlin Charlottenburg-Wilmersdorf",
        key="berlin_charlottenburg_wilmersdorf", system="allris",
        base_url="https://www.berlin.de/ba-charlottenburg-wilmersdorf/politik/bezirksverordnetenversammlung/online",
    ),
    "berlin_spandau": KommuneConfig(
        name="Berlin Spandau", key="berlin_spandau", system="allris",
        base_url="https://bvv-spandau.berlin.de",
    ),
    "berlin_steglitz_zehlendorf": KommuneConfig(
        name="Berlin Steglitz-Zehlendorf",
        key="berlin_steglitz_zehlendorf", system="allris",
        base_url="https://www.berlin.de/ba-steglitz-zehlendorf/politik-und-verwaltung/bezirksverordnetenversammlung/online",
    ),
    "berlin_tempelhof_schoeneberg": KommuneConfig(
        name="Berlin Tempelhof-Schoeneberg",
        key="berlin_tempelhof_schoeneberg", system="allris",
        base_url="https://www.berlin.de/ba-tempelhof-schoeneberg/politik-und-verwaltung/bezirksverordnetenversammlung/online",
    ),
    "berlin_neukoelln": KommuneConfig(
        name="Berlin Neukoelln", key="berlin_neukoelln", system="allris",
        base_url="https://www.berlin.de/ba-neukoelln/politik-und-verwaltung/bezirksverordnetenversammlung/online",
    ),
    "berlin_treptow_koepenick": KommuneConfig(
        name="Berlin Treptow-Koepenick",
        key="berlin_treptow_koepenick", system="allris",
        base_url="https://www.berlin.de/ba-treptow-koepenick/politik-und-verwaltung/bezirksverordnetenversammlung/online",
    ),
    "berlin_marzahn_hellersdorf": KommuneConfig(
        name="Berlin Marzahn-Hellersdorf",
        key="berlin_marzahn_hellersdorf", system="allris",
        base_url="https://www.berlin.de/ba-marzahn-hellersdorf/politik-und-verwaltung/bezirksverordnetenversammlung/online",
    ),
    "berlin_lichtenberg": KommuneConfig(
        name="Berlin Lichtenberg", key="berlin_lichtenberg", system="allris",
        base_url="https://www.berlin.de/ba-lichtenberg/politik-und-verwaltung/bezirksverordnetenversammlung/online",
    ),
    "berlin_reinickendorf": KommuneConfig(
        name="Berlin Reinickendorf", key="berlin_reinickendorf", system="allris",
        base_url="https://www.berlin.de/ba-reinickendorf/politik-und-verwaltung/bezirksverordnetenversammlung/online",
    ),

    # --- Sachsen-Anhalt ---
    "magdeburg": KommuneConfig(
        name="Landeshauptstadt Magdeburg",
        key="magdeburg", system="allris",
        base_url="https://ratsinfo.magdeburg.de/bi",
    ),

    # --- Hessen ---
    "bad_vilbel": KommuneConfig(
        name="Stadt Bad Vilbel",
        key="bad_vilbel", system="allris",
        base_url="https://www.bad-vilbel.de/allris/bi",
        notes="URL verifizieren - evtl. anderes System",
    ),

    # --- Sachsen ---
    "leipzig": KommuneConfig(
        name="Stadt Leipzig",
        key="leipzig", system="allris",
        base_url="https://ratsinformation.leipzig.de/allris_leipzig_public",
        oparl_url="https://ratsinformation.leipzig.de/allris_leipzig_public/oparl/v1.0/system",
        notes="ALLRIS mit OParl-API - bevorzugt OParl!",
    ),

    # --- Bayern ---
    "muenchen": KommuneConfig(
        name="Landeshauptstadt Muenchen",
        key="muenchen", system="ris_muenchen",
        base_url="https://risi.muenchen.de",
        notes="Eigenes RIS der Stadt Muenchen",
    ),
    "fuerstenfeldbruck": KommuneConfig(
        name="Stadt Fuerstenfeldbruck",
        key="fuerstenfeldbruck", system="allris",
        base_url="https://sessionnet.krz.de/fuerstenfeldbruck/bi",
        notes="Vermutlich Session/Buergerinfo - URL verifizieren",
    ),

    # --- Baden-Wuerttemberg ---
    "lenningen": KommuneConfig(
        name="Gemeinde Lenningen",
        key="lenningen", system="allris",
        base_url="https://www.lenningen.de/buergerinfo",
        notes="Kleine Gemeinde - evtl. kein ALLRIS",
    ),
}


# ============================================================================
# SCRAPER BASISKLASSE
# ============================================================================


# ============================================================================
# KONFIGURATION AUS config.json LADEN
# ============================================================================

import pathlib as _pathlib

def _load_config():
    """Laedt config.json aus dem gleichen Ordner wie das Skript."""
    p = _pathlib.Path(__file__).parent / "config.json"
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            logger.info(f"config.json geladen")
            return cfg
        except Exception as e:
            logger.warning(f"config.json fehlerhaft: {e}")
    return {}

_CONFIG_CACHE = None
def get_config():
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        _CONFIG_CACHE = _load_config()
    return _CONFIG_CACHE

def get_keywords_from_config():
    cfg = get_config()
    if "keywords" in cfg and cfg["keywords"]:
        return cfg["keywords"]
    return DEFAULT_KEYWORDS

def get_kommunen_to_scan():
    """Baut die Kommunen-Liste: Basis + Ergaenzungen aus config.json."""
    cfg = get_config()
    result = dict(KOMMUNEN)

    # Neue Kommunen aus config.json hinzufuegen
    for entry in cfg.get("extra_kommunen", []):
        key = entry.get("key", "")
        if not key:
            continue
        result[key] = KommuneConfig(
            name=entry.get("name", key),
            key=key,
            system=entry.get("system", "allris"),
            base_url=entry.get("base_url", ""),
            oparl_url=entry.get("oparl_url", ""),
            notes=entry.get("notes", "Aus config.json"),
        )

    # Nur bestimmte Kommunen aktivieren (optional)
    enabled = cfg.get("kommunen_aktiv", [])
    if enabled:
        result = {k: v for k, v in result.items() if k in enabled}

    return result


class RISScraper(ABC):
    """Abstrakte Basisklasse fuer alle RIS-Scraper."""

    def __init__(self, config: KommuneConfig, keywords: list, days: int = 30):
        self.config = config
        self.keywords = [kw.lower() for kw in keywords]
        self.days = days
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "RIS-Monitor/1.0 (kontakt@example.com)",
            "Accept-Language": "de-DE,de;q=0.9",
        })
        self.results: list = []

    @abstractmethod
    def fetch_sitzungen(self) -> list:
        """Sitzungen der letzten N Tage abrufen."""
        ...

    @abstractmethod
    def fetch_tagesordnung(self, sitzung: dict) -> list:
        """Tagesordnungspunkte einer Sitzung abrufen."""
        ...

    def match_keywords(self, text: str) -> list:
        """Prueft ob Schlagwoerter im Text vorkommen."""
        text_lower = text.lower()
        return [kw for kw in self.keywords if kw in text_lower]

    def run(self) -> list:
        """Hauptmethode: Sitzungen abrufen, TOPs scannen, Treffer sammeln."""
        logger.info(f"Scanne {self.config.name} ({self.config.system})")
        self.results = []
        try:
            sitzungen = self.fetch_sitzungen()
            logger.info(f"  {len(sitzungen)} Sitzung(en) gefunden")
            for sitzung in sitzungen:
                try:
                    tops = self.fetch_tagesordnung(sitzung)
                    for top in tops:
                        full_text = " ".join([
                            top.get("titel", ""),
                            top.get("beschluss", ""),
                            top.get("raw_text", ""),
                        ])
                        matches = self.match_keywords(full_text)
                        if matches:
                            doc = RISDocument(
                                kommune=self.config.name,
                                gremium=sitzung.get("gremium", ""),
                                datum=sitzung.get("datum", ""),
                                titel=top.get("titel", ""),
                                url=top.get("url", sitzung.get("url", "")),
                                doc_type=top.get("doc_type", "top"),
                                beschluss=top.get("beschluss", ""),
                                matched_keywords=matches,
                                raw_text=top.get("raw_text", "")[:500],
                            )
                            self.results.append(doc)
                    time.sleep(0.5)  # Hoefliche Pause
                except Exception as e:
                    logger.warning(f"  Sitzungsfehler: {e}")
        except Exception as e:
            logger.error(f"  Fehler bei {self.config.name}: {e}")
        logger.info(f"  -> {len(self.results)} Treffer")
        return self.results


# ============================================================================
# ALLRIS SCRAPER
# ============================================================================

class ALLRISScraper(RISScraper):
    """
    Scraper fuer ALLRIS-basierte Ratsinformationssysteme.

    ALLRIS URL-Schema (Buergerinfo):
        Sitzungskalender:  /si010_e.asp?YY=YYYY&MM=MM&DD=DD
        Sitzungsdetail:    /si020.asp?SILFDNR=<id>
        Vorlagendetail:    /vo020.asp?VOLFDNR=<id>
        Textrecherche:     /si017.asp  (POST: suchbegriff=...)
    """

    def fetch_sitzungen(self) -> list:
        sitzungen = []
        start = datetime.now() - timedelta(days=self.days)
        url = f"{self.config.base_url}/si010_e.asp"

        try:
            resp = self.session.get(
                url,
                params={"YY": start.year, "MM": start.month, "DD": start.day},
                timeout=15,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            for link in soup.find_all("a", href=re.compile(r"si020", re.I)):
                href = link.get("href", "")
                text = link.get_text(strip=True)
                sitzung_url = urljoin(self.config.base_url + "/", href)

                datum = ""
                parent_row = link.find_parent("tr")
                if parent_row:
                    for cell in parent_row.find_all("td"):
                        m = re.search(r"\d{2}\.\d{2}\.\d{4}", cell.get_text())
                        if m:
                            datum = m.group()
                            break

                sitzungen.append({
                    "gremium": text,
                    "datum": datum,
                    "url": sitzung_url,
                })

        except requests.RequestException as e:
            logger.warning(f"  Kalender nicht erreichbar ({e})")
            logger.info("  Versuche Textrecherche als Fallback...")
            sitzungen = self._textrecherche_fallback()

        return sitzungen

    def fetch_tagesordnung(self, sitzung: dict) -> list:
        tops = []
        try:
            resp = self.session.get(sitzung["url"], timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            for table in soup.find_all(
                "table", class_=re.compile(r"t[kl]1|smc_table")
            ):
                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        titel = cells[1].get_text(strip=True)
                        top_link = row.find(
                            "a", href=re.compile(r"(vo020|to020|si021)", re.I)
                        )
                        top_url = ""
                        if top_link:
                            top_url = urljoin(
                                self.config.base_url + "/", top_link["href"]
                            )

                        beschluss = ""
                        if len(cells) > 3:
                            beschluss = cells[-1].get_text(strip=True)

                        tops.append({
                            "titel": titel,
                            "url": top_url or sitzung["url"],
                            "beschluss": beschluss,
                            "doc_type": "top",
                            "raw_text": row.get_text(" ", strip=True),
                        })

            if not tops:
                page_text = soup.get_text(" ", strip=True)
                tops.append({
                    "titel": f"Gesamtseite: {sitzung.get('gremium', '')}",
                    "url": sitzung["url"],
                    "beschluss": "",
                    "doc_type": "sitzung",
                    "raw_text": page_text[:2000],
                })

        except requests.RequestException as e:
            logger.warning(f"  Tagesordnung nicht abrufbar: {e}")

        return tops

    def _textrecherche_fallback(self) -> list:
        """ALLRIS Volltextsuche als Fallback."""
        sitzungen = []
        search_url = f"{self.config.base_url}/si017.asp"
        for keyword in self.keywords[:5]:
            try:
                resp = self.session.post(
                    search_url,
                    data={"suchbegriff": keyword},
                    timeout=15,
                )
                if resp.ok:
                    soup = BeautifulSoup(resp.text, "lxml")
                    for link in soup.find_all(
                        "a", href=re.compile(r"si020|vo020")
                    ):
                        sitzungen.append({
                            "gremium": link.get_text(strip=True),
                            "datum": "",
                            "url": urljoin(
                                self.config.base_url + "/", link["href"]
                            ),
                        })
                time.sleep(1)
            except Exception:
                pass
        return sitzungen


# ============================================================================
# OPARL SCRAPER
# ============================================================================

class OParlScraper(RISScraper):
    """Scraper fuer Kommunen mit OParl-JSON-API (https://oparl.org)."""

    def _get_json(self, url, params=None):
        try:
            r = self.session.get(url, params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"  OParl GET {url}: {e}")
            return None

    def fetch_sitzungen(self) -> list:
        sitzungen = []
        if not self.config.oparl_url:
            return sitzungen
        try:
            system = self._get_json(self.config.oparl_url)
            if not system:
                return sitzungen

            bodies = system.get("body", [])
            if isinstance(bodies, str):
                bodies_data = self._get_json(bodies)
                bodies = bodies_data.get("data", []) if bodies_data else []

            for body_ref in bodies[:3]:
                body = (
                    body_ref
                    if isinstance(body_ref, dict)
                    else (self._get_json(body_ref) or {})
                )
                meetings_url = body.get("meeting", "")
                if not meetings_url:
                    continue

                start_date = (
                    datetime.now() - timedelta(days=self.days)
                ).strftime("%Y-%m-%d")
                page = self._get_json(
                    meetings_url, params={"modified_since": start_date}
                )
                if not page:
                    continue

                for meeting in page.get("data", page.get("member", [])):
                    if isinstance(meeting, str):
                        meeting = self._get_json(meeting) or {}
                    sitzungen.append({
                        "gremium": meeting.get("name", ""),
                        "datum": meeting.get("start", "")[:10],
                        "url": meeting.get("web", meeting.get("id", "")),
                        "oparl_data": meeting,
                    })
        except Exception as e:
            logger.error(f"  OParl-Fehler: {e}")
        return sitzungen

    def fetch_tagesordnung(self, sitzung: dict) -> list:
        tops = []
        meeting = sitzung.get("oparl_data", {})
        for item in meeting.get("agendaItem", []):
            if isinstance(item, str):
                item = self._get_json(item) or {}
            tops.append({
                "titel": item.get("name", item.get("number", "")),
                "url": item.get("web", sitzung["url"]),
                "beschluss": item.get("result", ""),
                "doc_type": "top",
                "raw_text": json.dumps(item, ensure_ascii=False)[:1000],
            })
        return tops


# ============================================================================
# RIS MUENCHEN SCRAPER
# ============================================================================

class RISMuenchenScraper(RISScraper):
    """Scraper fuer das RIS der LH Muenchen (Eigenloesung)."""

    def fetch_sitzungen(self) -> list:
        sitzungen = []
        start = (datetime.now() - timedelta(days=self.days)).strftime("%d.%m.%Y")
        end = datetime.now().strftime("%d.%m.%Y")
        try:
            resp = self.session.get(
                f"{self.config.base_url}/risi/sitzung/suche",
                params={"datumVon": start, "datumBis": end},
                timeout=15,
            )
            if resp.ok:
                soup = BeautifulSoup(resp.text, "lxml")
                for link in soup.find_all(
                    "a", href=re.compile(r"/risi/sitzung/detail")
                ):
                    parent = link.find_parent("tr")
                    datum = ""
                    if parent:
                        m = re.search(
                            r"\d{2}\.\d{2}\.\d{4}", parent.get_text()
                        )
                        if m:
                            datum = m.group()
                    sitzungen.append({
                        "gremium": link.get_text(strip=True),
                        "datum": datum,
                        "url": urljoin(self.config.base_url, link["href"]),
                    })
        except Exception as e:
            logger.warning(f"  RIS Muenchen: {e}")

        # Fallback: Vorlagen-Suche
        if not sitzungen:
            for kw in self.keywords[:3]:
                try:
                    resp = self.session.get(
                        f"{self.config.base_url}/risi/sitzungsvorlage/suche",
                        params={"suchbegriff": kw},
                        timeout=15,
                    )
                    if resp.ok:
                        soup = BeautifulSoup(resp.text, "lxml")
                        for link in soup.find_all(
                            "a",
                            href=re.compile(r"/risi/sitzungsvorlage/detail"),
                        ):
                            sitzungen.append({
                                "gremium": "Vorlagensuche",
                                "datum": "",
                                "url": urljoin(
                                    self.config.base_url, link["href"]
                                ),
                            })
                    time.sleep(1)
                except Exception:
                    pass
        return sitzungen

    def fetch_tagesordnung(self, sitzung: dict) -> list:
        try:
            resp = self.session.get(sitzung["url"], timeout=15)
            if resp.ok:
                soup = BeautifulSoup(resp.text, "lxml")
                return [{
                    "titel": sitzung.get("gremium", ""),
                    "url": sitzung["url"],
                    "beschluss": "",
                    "doc_type": "sitzung",
                    "raw_text": soup.get_text(" ", strip=True)[:2000],
                }]
        except Exception:
            pass
        return []


# ============================================================================
# FACTORY
# ============================================================================

def create_scraper(config, keywords, days):
    """Erstellt den passenden Scraper fuer die Kommune."""
    if config.oparl_url:
        return OParlScraper(config, keywords, days)
    if config.system == "ris_muenchen":
        return RISMuenchenScraper(config, keywords, days)
    return ALLRISScraper(config, keywords, days)


# ============================================================================
# REPORT-GENERIERUNG
# ============================================================================

def generate_html_report(results, keywords, days):
    """Erzeugt einen formatierten HTML-Bericht."""
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    start = (datetime.now() - timedelta(days=days)).strftime("%d.%m.%Y")

    by_kommune = {}
    for doc in results:
        by_kommune.setdefault(doc.kommune, []).append(doc)

    rows = ""
    for kommune, docs in sorted(by_kommune.items()):
        rows += (
            f'<tr class="kh"><td colspan="5"><strong>'
            f'{htmlmod.escape(kommune)}</strong> - '
            f'{len(docs)} Treffer</td></tr>'
        )
        for doc in docs:
            badges = " ".join(
                f'<span class="b">{htmlmod.escape(kw)}</span>'
                for kw in doc.matched_keywords
            )
            rows += (
                f'<tr>'
                f'<td>{htmlmod.escape(doc.datum)}</td>'
                f'<td>{htmlmod.escape(doc.gremium)}</td>'
                f'<td><a href="{htmlmod.escape(doc.url)}" target="_blank">'
                f'{htmlmod.escape(doc.titel[:120])}</a></td>'
                f'<td>{badges}</td>'
                f'<td>{htmlmod.escape(doc.beschluss[:100])}</td>'
                f'</tr>'
            )

    if not results:
        rows = (
            '<tr><td colspan="5" style="text-align:center;padding:2em;'
            'color:#888">Keine Treffer im Zeitraum.</td></tr>'
        )

    kw_html = " ".join(
        f'<span class="b">{htmlmod.escape(k)}</span>' for k in keywords[:30]
    )

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RIS-Monitor Wochenbericht</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box }}
body {{ font-family:'Segoe UI',system-ui,sans-serif; background:#f5f7fa; color:#333; padding:2em }}
.c {{ max-width:1200px; margin:0 auto }}
h1 {{ color:#1a365d; margin-bottom:.3em }}
.meta {{ color:#666; margin-bottom:1.5em; font-size:.95em }}
.sum {{ display:flex; gap:1em; margin-bottom:1.5em; flex-wrap:wrap }}
.st {{ background:#fff; border-radius:8px; padding:1em 1.5em; box-shadow:0 1px 3px rgba(0,0,0,.1); min-width:150px }}
.st .n {{ font-size:1.8em; font-weight:700; color:#2b6cb0 }}
.st .l {{ font-size:.85em; color:#888 }}
table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.1) }}
th {{ background:#2b6cb0; color:#fff; padding:.8em 1em; text-align:left; font-weight:600 }}
td {{ padding:.6em 1em; border-bottom:1px solid #eee; font-size:.9em }}
tr:hover {{ background:#f7fafc }}
.kh {{ background:#ebf4ff !important }}
.kh td {{ padding:.8em 1em }}
a {{ color:#2b6cb0; text-decoration:none }}
a:hover {{ text-decoration:underline }}
.b {{ display:inline-block; background:#ebf4ff; color:#2b6cb0; padding:.15em .5em; border-radius:4px; font-size:.8em; margin:.1em }}
.kw {{ background:#fff; border-radius:8px; padding:1em 1.5em; margin-bottom:1.5em; box-shadow:0 1px 3px rgba(0,0,0,.1) }}
.kw h3 {{ margin-bottom:.5em; color:#555; font-size:.95em }}
footer {{ margin-top:2em; color:#999; font-size:.85em; text-align:center }}
</style>
</head>
<body>
<div class="c">
<h1>RIS-Monitor - Wochenbericht</h1>
<p class="meta">Zeitraum: {start} - {now}</p>
<div class="sum">
  <div class="st"><div class="n">{len(results)}</div><div class="l">Treffer</div></div>
  <div class="st"><div class="n">{len(by_kommune)}</div><div class="l">Kommunen mit Treffern</div></div>
  <div class="st"><div class="n">{len(KOMMUNEN)}</div><div class="l">Kommunen gescannt</div></div>
</div>
<div class="kw">
  <h3>Schlagwoerter ({len(keywords)}):</h3>
  <p>{kw_html}</p>
</div>
<table>
<thead><tr><th>Datum</th><th>Gremium</th><th>Thema / Vorlage</th><th>Schlagwoerter</th><th>Beschluss</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<footer>RIS-Monitor v1.0 | Datenquellen: ALLRIS, OParl, RIS Muenchen</footer>
</div>
</body>
</html>"""


def generate_json_report(results, keywords):
    """JSON-Export."""
    return json.dumps({
        "meta": {
            "generated": datetime.now().isoformat(),
            "keywords": keywords,
            "total_hits": len(results),
        },
        "results": [doc.to_dict() for doc in results],
    }, ensure_ascii=False, indent=2)


def generate_text_report(results):
    """Einfacher Text-Report fuer die Konsole."""
    lines = [
        "=" * 70,
        "RIS-MONITOR WOCHENBERICHT",
        f"Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        f"Treffer: {len(results)}",
        "=" * 70, "",
    ]
    by_kommune = {}
    for doc in results:
        by_kommune.setdefault(doc.kommune, []).append(doc)

    for kommune, docs in sorted(by_kommune.items()):
        lines.append(f"\n  {kommune} ({len(docs)} Treffer)")
        lines.append("-" * 50)
        for doc in docs:
            lines.append(f"  [{doc.datum}] {doc.gremium}")
            lines.append(f"  {doc.titel[:100]}")
            lines.append(f"  Keywords: {', '.join(doc.matched_keywords)}")
            if doc.beschluss:
                lines.append(f"  Beschluss: {doc.beschluss[:80]}")
            lines.append(f"  -> {doc.url}")
            lines.append("")

    if not results:
        lines.append("Keine Treffer im Zeitraum gefunden.")
    return "\n".join(lines)


def send_email_report(html_report, count):
    """Versendet den Report per E-Mail."""
    if not EMAIL_CONFIG.get("enabled"):
        logger.info("E-Mail-Versand deaktiviert")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"{EMAIL_CONFIG['subject_prefix']} {count} Treffer - "
        f"{datetime.now().strftime('%d.%m.%Y')}"
    )
    msg["From"] = EMAIL_CONFIG["from_addr"]
    msg["To"] = ", ".join(EMAIL_CONFIG["to_addrs"])
    msg.attach(MIMEText(html_report, "html"))
    try:
        with smtplib.SMTP(
            EMAIL_CONFIG["smtp_host"], EMAIL_CONFIG["smtp_port"]
        ) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_CONFIG["smtp_user"], EMAIL_CONFIG["smtp_pass"])
            smtp.send_message(msg)
        logger.info("E-Mail erfolgreich versendet")
    except Exception as e:
        logger.error(f"E-Mail-Fehler: {e}")


# ============================================================================
# HAUPTPROGRAMM
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="RIS-Monitor: Schlagwort-Scanner fuer Ratsinformationssysteme",
        epilog="Beispiel: python ris_monitor.py -k 'Kita,Haushalt' -d 14 -o bericht.html",
    )
    parser.add_argument("-k", "--keywords", type=str,
        help="Kommagetrennte Schlagwoerter (ueberschreibt Standard)")
    parser.add_argument("-d", "--days", type=int, default=7,
        help="Zeitraum in Tagen (Standard: 7)")
    parser.add_argument("-o", "--output", type=str, default="report.html",
        help="Ausgabedatei (.html, .json, .txt)")
    parser.add_argument("--kommune", type=str, action="append",
        help="Nur bestimmte Kommunen (wiederholbar)")
    parser.add_argument("--list-kommunen", action="store_true",
        help="Alle konfigurierten Kommunen auflisten")
    parser.add_argument("--email", action="store_true",
        help="Report per E-Mail senden")

    args = parser.parse_args()

    if args.list_kommunen:
        alle = get_kommunen_to_scan()
        print(f"\n{'Schluessel':<42} {'System':<14} Name")
        print("-" * 80)
        for key, cfg in sorted(alle.items()):
            oparl_flag = " [OParl]" if cfg.oparl_url else ""
            print(f"  {key:<40} {cfg.system:<12} {cfg.name}{oparl_flag}")
        print(f"\nGesamt: {len(alle)} Kommunen")
        return

    # Schlagwoerter: aus config.json, CLI ueberschreibt
    keywords = get_keywords_from_config()
    if args.keywords:
        keywords = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]

    # Kommunen: aus config.json (inkl. extra_kommunen), CLI ueberschreibt
    kommunen_to_scan = get_kommunen_to_scan()
    if args.kommune:
        kommunen_to_scan = {
            k: v for k, v in kommunen_to_scan.items() if k in args.kommune
        }
    if not kommunen_to_scan:
        print("Keine Kommunen gefunden.")
        print("Verfuegbar: " + ", ".join(sorted(get_kommunen_to_scan().keys())))
        return

    # Scan durchfuehren
    all_results = []
    for key, config in kommunen_to_scan.items():
        scraper = create_scraper(config, keywords, args.days)
        all_results.extend(scraper.run())

    # Report erstellen
    output_file = args.output
    if output_file.endswith(".json"):
        report = generate_json_report(all_results, keywords)
    elif output_file.endswith(".txt"):
        report = generate_text_report(all_results)
    else:
        report = generate_html_report(all_results, keywords, args.days)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info(f"Report gespeichert: {output_file}")

    # Konsolenausgabe
    print(generate_text_report(all_results))

    # E-Mail
    if args.email:
        html_report = generate_html_report(all_results, keywords, args.days)
        send_email_report(html_report, len(all_results))


if __name__ == "__main__":
    main()
