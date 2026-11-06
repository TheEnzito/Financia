"""Mises à jour de l'application sans réinstallation.

Principe : le code de l'application (fichiers .py de ce dossier, bibliothèques ajoutées, configuration)
est relu au démarrage. Une mise à jour remplace donc simplement ces fichiers.

- `version.json` (local) : version installée et empreinte SHA-256 de chaque fichier.
- `mise_a_jour.json` (local) : adresse de la source des mises à jour (ex. un dépôt GitHub public).
- À la source : le même `version.json` (version publiée) et les fichiers.

Sécurité : téléchargement en HTTPS uniquement, depuis la seule source configurée ; chaque fichier est
vérifié par son empreinte avant d'être installé ; seuls des fichiers de code et de configuration de ce
dossier peuvent être remplacés (jamais l'exécutable ni les bibliothèques compilées) ; les anciens
fichiers sont sauvegardés et restaurés en cas d'échec.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import ssl
import sys
import urllib.request
from datetime import datetime
from pathlib import Path, PurePosixPath

DOSSIER = Path(__file__).resolve().parent
FICHIER_VERSION = DOSSIER / "version.json"
FICHIER_CONFIG = DOSSIER / "mise_a_jour.json"
SAUVEGARDES = DOSSIER / "_sauvegardes"
EXTENSIONS_AUTORISEES = {".py", ".json", ".toml", ".txt", ".md"}
DELAI = 10  # secondes


# ------------------------------------------------------------------ outils
def empreinte(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def version_tuple(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in str(v).strip().lstrip("v").split("."))
    except ValueError:
        return (0,)


def version_locale() -> dict:
    try:
        return json.loads(FICHIER_VERSION.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": "0.0.0", "fichiers": {}}


def lire_source() -> str:
    try:
        return str(json.loads(FICHIER_CONFIG.read_text(encoding="utf-8")).get("source", "")).strip().rstrip("/")
    except (OSError, ValueError):
        return ""


def ecrire_source(url: str) -> None:
    FICHIER_CONFIG.write_text(json.dumps({"source": url.strip().rstrip("/")}, indent=2), encoding="utf-8")


def adresse_brute(source: str) -> str:
    """Accepte l'adresse d'un dépôt GitHub (https://github.com/moi/mesfinances) et la convertit en adresse
    de téléchargement direct (https://raw.githubusercontent.com/moi/mesfinances/main)."""
    s = source.strip().rstrip("/")
    if s.startswith("https://github.com/"):
        parties = s[len("https://github.com/"):].split("/")
        if len(parties) >= 2:
            branche = parties[3] if len(parties) >= 4 and parties[2] == "tree" else "main"
            return f"https://raw.githubusercontent.com/{parties[0]}/{parties[1]}/{branche}"
    return s


def _contexte_ssl() -> ssl.SSLContext:
    # Certificats : copie sans accent préparée au démarrage (SSL_CERT_FILE), sinon certifi, sinon système.
    for chemin in (os.environ.get("SSL_CERT_FILE"),):
        if chemin and Path(chemin).exists():
            return ssl.create_default_context(cafile=chemin)
    try:
        import certifi
        if str(certifi.where()).isascii():
            return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    return ssl.create_default_context()


def _telecharger(url: str) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("La source des mises à jour doit être une adresse https://")
    requete = urllib.request.Request(url, headers={"User-Agent": "MesFinances-mise-a-jour", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(requete, timeout=DELAI, context=_contexte_ssl()) as r:
        return r.read()


def _chemin_sur(relatif: str) -> Path:
    """Chemin cible d'un fichier de la mise à jour, refusé s'il sort du dossier ou n'est pas du code."""
    p = PurePosixPath(relatif)
    if (p.is_absolute() or ".." in p.parts or not p.parts or p.parts[0].startswith("_sauvegardes")
            or any(":" in x or "\\" in x for x in p.parts)):  # lecteur Windows (C:) ou séparateur détourné
        raise ValueError(f"Chemin refusé : {relatif}")
    if p.suffix.lower() not in EXTENSIONS_AUTORISEES:
        raise ValueError(f"Type de fichier refusé : {relatif}")
    cible = (DOSSIER / Path(*p.parts)).resolve()
    if DOSSIER not in cible.parents:
        raise ValueError(f"Chemin refusé : {relatif}")
    return cible


# --------------------------------------------------------------- vérifier
def verifier() -> dict:
    """{"disponible": bool, "locale": "1.0.0", "distante": "1.1.0", "notes": [...], "erreur": str|None}."""
    locale = version_locale()
    source = lire_source()
    res = {"disponible": False, "locale": locale.get("version", "0.0.0"), "distante": None, "notes": [],
           "date": None, "erreur": None, "source": source}
    if not source:
        res["erreur"] = "Aucune source de mises à jour n'est configurée."
        return res
    if not adresse_brute(source).startswith("https://"):
        res["erreur"] = "La source des mises à jour doit être une adresse sécurisée (https://)."
        return res
    try:
        distante = json.loads(_telecharger(adresse_brute(source) + "/version.json").decode("utf-8"))
    except Exception as e:  # pas de connexion, adresse erronée…
        res["erreur"] = f"Impossible de joindre la source des mises à jour ({e.__class__.__name__})."
        return res
    res.update(distante=distante.get("version"), notes=distante.get("notes", []), date=distante.get("date"),
               manifeste=distante)
    res["disponible"] = version_tuple(distante.get("version", "0")) > version_tuple(res["locale"])
    return res


# ---------------------------------------------------------------- installer
def installer(manifeste: dict) -> list[str]:
    """Télécharge et installe les fichiers modifiés de la version publiée. Renvoie la liste des fichiers mis
    à jour. Tout ou rien : en cas d'erreur, rien n'est modifié (ou tout est restauré)."""
    source = adresse_brute(lire_source())
    locaux = version_locale().get("fichiers", {})
    a_installer = {}
    for relatif, attendu in manifeste.get("fichiers", {}).items():
        cible = _chemin_sur(relatif)
        if cible.exists() and empreinte(cible) == attendu:
            continue
        contenu = _telecharger(f"{source}/{relatif}")
        if hashlib.sha256(contenu).hexdigest() != attendu:
            raise ValueError(f"Fichier altéré ou incomplet : {relatif} (empreinte différente). Rien n'a été installé.")
        a_installer[relatif] = contenu

    # Sauvegarde des fichiers remplacés, puis installation
    dossier_sauvegarde = SAUVEGARDES / f"{version_locale().get('version', '0')}_{datetime.now():%Y%m%d-%H%M%S}"
    remplaces = []
    try:
        for relatif, contenu in a_installer.items():
            cible = _chemin_sur(relatif)
            if cible.exists():
                copie = dossier_sauvegarde / relatif
                copie.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cible, copie)
            cible.parent.mkdir(parents=True, exist_ok=True)
            temporaire = cible.with_name(cible.name + ".nouveau")
            temporaire.write_bytes(contenu)
            os.replace(temporaire, cible)
            remplaces.append(relatif)
        FICHIER_VERSION.write_text(json.dumps(manifeste, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        for relatif in remplaces:  # restauration
            copie = dossier_sauvegarde / relatif
            if copie.exists():
                shutil.copy2(copie, _chemin_sur(relatif))
        raise
    return remplaces


def recharger_modules() -> None:
    """Oublie les modules de l'application déjà chargés : la prochaine exécution relit les nouveaux fichiers."""
    for nom in [f.stem for f in DOSSIER.glob("*.py") if f.stem != "app"]:
        sys.modules.pop(nom, None)
