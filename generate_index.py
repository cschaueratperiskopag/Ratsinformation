#!/usr/bin/env python3
"""Erzeugt docs/index.html als Dashboard mit Links zu allen Reports."""
import os, re
from datetime import datetime

REPORT_DIR = "docs/reports"

def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    files = sorted(
        [f for f in os.listdir(REPORT_DIR)
         if re.match(r"bericht_\d{4}-\d{2}-\d{2}\.html", f)],
        reverse=True,
    )
    rows = ""
    for f in files[:52]:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", f)
        if m:
            d = datetime.strptime(m.group(1), "%Y-%m-%d")
            rows += '<li><a href="reports/{}">{}</a></li>\n'.format(
                f, d.strftime("%A, %d.%m.%Y"))

    placeholder = '<li style="color:#999">Noch keine Berichte. Erster Scan laeuft automatisch.</li>'

    html = """<!DOCTYPE html>
<html lang="de"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>RIS-Monitor Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#f5f7fa;color:#333;padding:2em}
.c{max-width:800px;margin:0 auto}
h1{color:#1a365d;margin-bottom:.2em}
.sub{color:#666;margin-bottom:1.5em}
.card{background:#fff;border-radius:10px;padding:1.5em 2em;box-shadow:0 2px 8px rgba(0,0,0,.08);margin-bottom:1.5em}
.card h2{color:#2b6cb0;margin-bottom:.8em;font-size:1.15em}
.latest a{background:#2b6cb0;color:#fff;padding:.6em 1.2em;border-radius:6px;text-decoration:none;display:inline-block}
.latest a:hover{background:#1a4e8a}
ul{list-style:none;padding:0}
li{padding:.45em 0;border-bottom:1px solid #f0f0f0}
li a{color:#2b6cb0;text-decoration:none}
li a:hover{text-decoration:underline}
footer{margin-top:2em;text-align:center;color:#aaa;font-size:.85em}
</style></head><body><div class="c">
<h1>RIS-Monitor</h1>
<p class="sub">Automatische Ueberwachung kommunaler Ratsinformationssysteme</p>
<div class="card latest"><h2>Aktuellster Bericht</h2>
<a href="reports/latest.html">Letzten Scan oeffnen &rarr;</a></div>
<div class="card"><h2>Alle Berichte</h2><ul>
""" + (rows if rows else placeholder) + """
</ul></div>
<footer>RIS-Monitor | Scans: Montag + Mittwoch frueh | GitHub Actions</footer>
</div></body></html>"""

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as fh:
        fh.write(html)
    print("Index geschrieben: docs/index.html")

if __name__ == "__main__":
    main()
