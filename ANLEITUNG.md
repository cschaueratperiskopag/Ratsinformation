# RIS-Monitor auf GitHub - Komplettanleitung

## Was passiert?
GitHub fuehrt **jeden Montag und Mittwoch um ca. 06-07 Uhr** automatisch
den RIS-Scanner aus. Die Ergebnisse erscheinen als Website.
**Keine Installation noetig.**

---

## EINRICHTUNG (einmalig)

### Schritt 1 - GitHub-Konto erstellen
1. https://github.com > "Sign up"
2. E-Mail, Passwort, Benutzername waehlen

### Schritt 2 - Repository anlegen
1. Oben rechts **+** > **New repository**
2. Name: `ris-monitor`, Sichtbarkeit: **Private**
3. **Create repository**

### Schritt 3 - Dateien hochladen
1. Klicke **"uploading an existing file"**
2. Ziehe den **gesamten Inhalt des Ordners** hinein
   (WICHTIG: inkl. verstecktem `.github`-Ordner!)
   - Windows: Explorer > Ansicht > "Ausgeblendete Elemente"
   - macOS: Finder > Cmd+Shift+.
3. **Commit changes**

### Schritt 4 - GitHub Pages aktivieren
1. **Settings** > **Pages**
2. Source: **Deploy from a branch**
3. Branch: **main** / Ordner: **/docs** > **Save**
4. Euer Link: `https://BENUTZERNAME.github.io/ris-monitor/`

### Schritt 5 - Actions aktivieren
Tab **Actions** > gruenen Enable-Button klicken

### Schritt 6 - Team einladen
**Settings** > **Collaborators** > **Add people**

---

## TÄGLICHE NUTZUNG

### Schlagwoerter aendern
1. `config.json` auf GitHub anklicken
2. Stift-Symbol klicken
3. In der Liste `"keywords"` Woerter aendern/hinzufuegen/loeschen
4. **Commit changes**

Beispiel - neues Wort hinzufuegen:
```
"keywords": [
    "Bebauungsplan",
    "Kita",
    "Mein neues Schlagwort"     <-- hier einfach eine Zeile ergaenzen
]
```

### Neue Kommune hinzufuegen
1. `config.json` auf GitHub oeffnen > Stift-Symbol
2. Unter `"extra_kommunen"` einen neuen Eintrag ergaenzen:
```
{
    "key": "potsdam",
    "name": "Landeshauptstadt Potsdam",
    "system": "allris",
    "base_url": "https://egov.potsdam.de/bi"
}
```
3. **Commit changes**

Woher bekomme ich die base_url?
> Googeln: "[Stadtname] Ratsinformationssystem" oder "[Stadtname] Buergerinfo"
> Die URL der Seite kopieren (meist endet sie auf /bi oder /buergerinfo)

Welches "system" hat die Kommune?
> Die meisten nutzen "allris". Wenn es nicht klappt, bitte melden.

### Nur bestimmte Kommunen scannen
In `config.json` die Liste `"kommunen_aktiv"` befuellen:
```
"kommunen_aktiv": ["schoenefeld", "berlin_mitte", "leipzig"]
```
Leer lassen = alle werden gescannt.

### Manuellen Scan starten
Tab **Actions** > "RIS-Monitor Scan" > **Run workflow**

---

## FAQ

**Kostet das etwas?** Nein, GitHub-Gratiskontingent reicht.

**Privat?** Bei "Private" nur fuer Eingeladene sichtbar.

**Scan laeuft nicht?** Actions-Tab pruefen, ob aktiviert.
