"""Mes finances : application personnelle de suivi du patrimoine, du budget et des investissements.

Lancement :  streamlit run app.py
"""

import importlib.abc
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path


# --- Certificats HTTPS dans un dossier sans accent ---------------------------
# libcurl (utilisé par yfinance) ne sait pas lire un fichier dont le chemin contient
# des caractères accentués (ex. « APPLICATIONS CRÉE ») : toutes les requêtes vers
# Yahoo Finance échouaient alors en SSLError. On copie le fichier dans un dossier ASCII.
def _certificats_ascii() -> None:
    import certifi
    source = Path(certifi.where())
    if str(source).isascii():
        return
    for dossier in (os.environ.get("LOCALAPPDATA"), tempfile.gettempdir(), os.environ.get("PROGRAMDATA"), "C:\\"):
        if not dossier:
            continue
        cible = Path(dossier) / "MesFinances" / "cacert.pem"
        if not str(cible).isascii():
            continue
        try:
            cible.parent.mkdir(parents=True, exist_ok=True)
            if not cible.exists() or cible.stat().st_size != source.stat().st_size:
                shutil.copyfile(source, cible)
        except OSError:
            continue
        os.environ["SSL_CERT_FILE"] = os.environ["CURL_CA_BUNDLE"] = str(cible)
        for module in ("curl_cffi.curl", "curl_cffi.aio"):  # déjà importés lors d'une exécution précédente
            if module in sys.modules:
                sys.modules[module].DEFAULT_CACERT = str(cible)
        return


_certificats_ascii()

import streamlit as st
from streamlit import config as _config

# --- Modules de l'application lus depuis les fichiers .py de ce dossier ---------
# MesFinances.exe embarque une copie figée de ces modules : sans ce chargeur,
# les modifications apportées aux fichiers .py seraient ignorées.
DOSSIER = Path(__file__).resolve().parent
MODULES_LOCAUX = {f.stem for f in DOSSIER.glob("*.py") if f.stem != "app"}


class _SourcesLocales(importlib.abc.MetaPathFinder):
    def find_spec(self, nom, path=None, target=None):
        if nom in MODULES_LOCAUX:
            return importlib.util.spec_from_file_location(nom, DOSSIER / f"{nom}.py")
        return None


if not any(isinstance(f, _SourcesLocales) for f in sys.meta_path):
    sys.meta_path.insert(0, _SourcesLocales())

# Bibliothèques ajoutées après la construction de l'exe (ex. pypdf pour les relevés PDF).
BIBLIOTHEQUES = str(DOSSIER / "bibliotheques")
if Path(BIBLIOTHEQUES).is_dir() and BIBLIOTHEQUES not in sys.path:
    sys.path.append(BIBLIOTHEQUES)

# --- Thème sombre (le lanceur de l'exe impose un thème clair en ligne de commande)
import db as _db_theme  # noqa: E402  (chargés via _SourcesLocales)
import style as _style_theme  # noqa: E402

try:
    _db_theme.initialiser()
    _nom_theme = _db_theme.lire_parametre("theme")
except Exception:
    _nom_theme = None
_style_theme.activer_theme(_nom_theme or _style_theme.THEME_DEFAUT)  # Paramètres › Thème
THEME = _style_theme.theme_streamlit()
if any(_config.get_option(f"theme.{k}") != v for k, v in THEME.items()):
    for k, v in THEME.items():
        _config.set_option(f"theme.{k}", v, "app.py")
    st.rerun()  # le thème est transmis au navigateur au début de chaque exécution

import db
import style
import vue_bourse
import vue_budget
import vue_parametres
import vue_marche
import vue_patrimoine

st.set_page_config(page_title="Mes finances", page_icon="💶", layout="wide")
db.initialiser()
style.appliquer()

PAGES = {
    "patrimoine": st.Page(vue_patrimoine.page, title="Mon patrimoine", icon=":material/account_balance:",
                          url_path="patrimoine", default=True),
    "budget": st.Page(vue_budget.page, title="Budget", icon=":material/savings:", url_path="budget"),
    "portefeuille": st.Page(vue_bourse.page_portefeuille, title="Portefeuille", icon=":material/donut_large:",
                            url_path="portefeuille"),
    "transactions": st.Page(vue_bourse.page_transactions, title="Transactions", icon=":material/swap_horiz:",
                            url_path="transactions"),
    "marches": st.Page(vue_marche.page, title="Marchés", icon=":material/show_chart:", url_path="marches"),
    "parametres": st.Page(vue_parametres.page, title="Paramètres", icon=":material/settings:",
                          url_path="parametres"),
}
vue_marche.PAGES.update(PAGES)
navigation = st.navigation(list(PAGES.values()))
with st.sidebar:
    style.note("Cours Yahoo Finance actualisés chaque minute (différé de 0 à 20 min selon la place).")
    vue_parametres.bandeau_mise_a_jour()  # nouvelle version disponible → bouton « Mettre à jour »
navigation.run()
