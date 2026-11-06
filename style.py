"""Style visuel sombre et épuré, façon application de courtage : fond noir, panneaux plats
à bordure fine, typographie dense, variations en vert et rouge, graphiques sobres."""

from __future__ import annotations

import html

import plotly.graph_objects as go
import streamlit as st

# Vert et rouge des chiffres : identiques dans tous les thèmes (hausse / baisse, gain / perte).
VERT, ROUGE = "#1FC16B", "#F2454F"
VERT_TEXTE, ROUGE_TEXTE = "#22C55E", "#F2454F"

# ------------------------------------------------------------------ thèmes
THEMES = {
    "Sombre": dict(
        FOND="#0A0A0A", PANNEAU="#111111", PANNEAU_2="#161616", BORD="#232323",
        TEXTE="#FFFFFF", TEXTE_2="#8B8B8B",
        ACCENT=VERT,                         # point « en direct » des titres de panneau
        BOUTON_FOND="#FFFFFF", BOUTON_SURVOL="#E6E6E6", BOUTON_TEXTE="#000000",
        ACTIF_FOND="#262626", ACTIF_TEXTE="#FFFFFF",
        PRIMAIRE="#1FC16B",                  # couleur Streamlit (cases, curseurs, sélection)
        BLEU="#4C8DFF", ORANGE="#F5A524", VIOLET="#A78BFA", INDIGO="#6366F1", TURQUOISE="#2DD4BF",
        ROSE="#F472B6", GRIS="#8B8B8B",
        PALETTE=["#4C8DFF", "#1FC16B", "#F5A524", "#A78BFA", "#2DD4BF", "#F472B6", "#6366F1", "#C2A878",
                 "#8B8B8B", "#7DD3FC", "#FACC15"],
        ENVELOPPES={"PEA": "#4C8DFF", "CTO": "#64D2FF", "Compte-titres": "#64D2FF", "PEA-PME": "#6366F1",
                    "Assurance vie": "#2DD4BF", "PER": "#A78BFA"},
    ),
    "Noir & or": dict(
        FOND="#0B0A08", PANNEAU="#12100C", PANNEAU_2="#1A1711", BORD="#2E2819",
        TEXTE="#F4EFE4", TEXTE_2="#A39A86",
        ACCENT="#C9A45C",
        BOUTON_FOND="linear-gradient(180deg, #E1C27E 0%, #C09A4E 100%)", BOUTON_SURVOL="#E8CD8F",
        BOUTON_TEXTE="#0B0A08",
        ACTIF_FOND="#2E2819", ACTIF_TEXTE="#E3C88A",
        PRIMAIRE="#C9A45C",
        BLEU="#C9A45C", ORANGE="#D9A441", VIOLET="#9C8BC9", INDIGO="#7A86B8", TURQUOISE="#6FB3A8",
        ROSE="#D49BB0", GRIS="#8A8274",
        PALETTE=["#C9A45C", "#8FA7C9", "#B07D62", "#9C8BC9", "#6FB3A8", "#D49BB0", "#7A86B8", "#E3C88A",
                 "#8A8274", "#A3B18A", "#D9A441"],
        ENVELOPPES={"PEA": "#C9A45C", "CTO": "#8FA7C9", "Compte-titres": "#8FA7C9", "PEA-PME": "#B07D62",
                    "Assurance vie": "#6FB3A8", "PER": "#9C8BC9"},
    ),
}
THEME_DEFAUT = "Sombre"
THEME_ACTIF = THEME_DEFAUT


def activer_theme(nom: str) -> None:
    """Applique un thème : met à jour les couleurs utilisées par le CSS et les graphiques."""
    global THEME_ACTIF, FOND, PANNEAU, PANNEAU_2, BORD, TEXTE, TEXTE_2, ACCENT, BOUTON_FOND, BOUTON_SURVOL
    global BOUTON_TEXTE, ACTIF_FOND, ACTIF_TEXTE, BLEU, ORANGE, VIOLET, INDIGO, TURQUOISE, ROSE, GRIS, PALETTE
    global COULEURS_PATRIMOINE, COULEURS_ENVELOPPES
    THEME_ACTIF = nom if nom in THEMES else THEME_DEFAUT
    t = THEMES[THEME_ACTIF]
    FOND, PANNEAU, PANNEAU_2, BORD = t["FOND"], t["PANNEAU"], t["PANNEAU_2"], t["BORD"]
    TEXTE, TEXTE_2, ACCENT = t["TEXTE"], t["TEXTE_2"], t["ACCENT"]
    BOUTON_FOND, BOUTON_SURVOL, BOUTON_TEXTE = t["BOUTON_FOND"], t["BOUTON_SURVOL"], t["BOUTON_TEXTE"]
    ACTIF_FOND, ACTIF_TEXTE = t["ACTIF_FOND"], t["ACTIF_TEXTE"]
    BLEU, ORANGE, VIOLET, INDIGO = t["BLEU"], t["ORANGE"], t["VIOLET"], t["INDIGO"]
    TURQUOISE, ROSE, GRIS, PALETTE = t["TURQUOISE"], t["ROSE"], t["GRIS"], list(t["PALETTE"])
    COULEURS_PATRIMOINE = {
        "Bourse (portefeuille)": BLEU, "Placements hors application": INDIGO, "Épargne": VERT,
        "Comptes courants": TURQUOISE, "Immobilier": ORANGE, "Crypto": VIOLET, "Autres actifs": "#AC8E68",
        "Dettes": ROUGE,
    }
    COULEURS_ENVELOPPES = dict(t["ENVELOPPES"])


def theme_streamlit() -> dict:
    """Options de thème Streamlit correspondant au thème actif (tableaux, champs, cases à cocher)."""
    t = THEMES[THEME_ACTIF]
    return {"base": "dark", "primaryColor": t["PRIMAIRE"], "backgroundColor": t["FOND"],
            "borderColor": t["BORD"], "baseRadius": "8px", "dataframeHeaderBackgroundColor": t["PANNEAU"],
            "secondaryBackgroundColor": t["PANNEAU_2"], "textColor": t["TEXTE"]}


activer_theme(THEME_DEFAUT)


def couleur_enveloppe(enveloppe: str) -> str:
    """Couleur fixe d'une enveloppe (les noms libres reçoivent une couleur stable de la palette)."""
    if enveloppe in COULEURS_ENVELOPPES:
        return COULEURS_ENVELOPPES[enveloppe]
    return PALETTE[sum(map(ord, enveloppe)) % len(PALETTE)]


def couleur_patrimoine(categorie: str) -> str:
    """Couleur d'une catégorie de patrimoine, y compris « Bourse · <enveloppe> »."""
    if categorie in COULEURS_PATRIMOINE:
        return COULEURS_PATRIMOINE[categorie]
    if categorie.startswith("Bourse · "):
        return couleur_enveloppe(categorie.split(" · ", 1)[1])
    return GRIS


POLICE = ('"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, '
          '"Helvetica Neue", Arial, sans-serif')

def _css() -> str:
    """Feuille de style du thème actif."""
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root {{
  color-scheme: dark;
  --fond: {FOND};
  --panneau: {PANNEAU};
  --panneau-2: {PANNEAU_2};
  --bord: {BORD};
  --texte: {TEXTE};
  --texte-2: {TEXTE_2};
  --rayon: 12px;
}}

.stApp {{ font-family: {POLICE}; color: var(--texte); background: var(--fond); }}
.stApp, .stApp p, .stApp li, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3,
.stApp h4, [data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] {{ color: var(--texte); }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {{ color: var(--texte-2) !important; }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container, [data-testid="stMainBlockContainer"] {{ padding-top: 1.6rem; max-width: 1360px; }}
[data-testid="stVerticalBlock"] {{ gap: 0.75rem; }}

h1 {{ font-weight: 700 !important; letter-spacing: -0.02em; font-size: 1.75rem !important; }}
h2, h3 {{ font-weight: 650 !important; letter-spacing: -0.01em; }}
.stApp strong, .stApp b {{ font-weight: 650; }}

/* Panneaux : st.container(key="verre_…") — aplats sombres à bordure fine */
[class*="st-key-verre"] {{
  background: var(--panneau);
  border: 1px solid var(--bord);
  border-radius: var(--rayon);
  padding: 16px 18px 14px;
}}
/* Titre de panneau : petit point vert « en direct » devant le premier texte en gras */
[class*="st-key-verre"] > [data-testid="stElementContainer"]:first-of-type [data-testid="stMarkdownContainer"] > p:first-child > strong:first-child::before,
[class*="st-key-verre"] > [data-testid="stLayoutWrapper"]:first-child [data-testid="stColumn"]:first-child > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:first-of-type [data-testid="stMarkdownContainer"] > p:first-child > strong:first-child::before {{
  content: ""; display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: {ACCENT}; margin-right: 8px; vertical-align: middle; transform: translateY(-1px);
}}

/* Indicateurs */
[data-testid="stMetric"] {{
  background: var(--panneau-2); border: 1px solid var(--bord); border-radius: 10px; padding: 10px 14px;
}}
[data-testid="stMetricLabel"] p {{ color: var(--texte-2) !important; font-size: 0.8rem; }}
[data-testid="stMetricValue"] {{ font-weight: 650; letter-spacing: -0.01em; color: var(--texte); font-size: 1.45rem; }}

/* Barre latérale */
[data-testid="stSidebar"] {{ background: #070707; border-right: 1px solid var(--bord); }}
[data-testid="stSidebarNavLink"], [data-testid="stSidebarNav"] a {{ border-radius: 8px !important; margin: 1px 6px; }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: var(--panneau-2) !important; }}
[data-testid="stSidebarNavLink"]:hover {{ background: #161616 !important; }}

/* Boutons : sombres et plats ; bouton principal blanc, texte noir */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button, [data-testid="stPopover"] > div > button {{
  border-radius: 8px !important; padding: 0.4rem 1rem;
  border: 1px solid var(--bord) !important; background: var(--panneau-2); color: var(--texte);
  box-shadow: none; font-weight: 600; font-size: 0.88rem;
}}
.stButton > button:hover, [data-testid="stPopover"] > div > button:hover {{ background: #1E1E1E; border-color: #2C2C2C !important; }}
[data-testid="stBaseButton-primary"], button[kind="primary"] {{
  background: {BOUTON_FOND} !important; color: {BOUTON_TEXTE} !important; border: none !important; box-shadow: none !important;
}}
[data-testid="stBaseButton-primary"] *, button[kind="primary"] * {{ color: {BOUTON_TEXTE} !important; }}
[data-testid="stBaseButton-primary"]:hover, button[kind="primary"]:hover {{ background: {BOUTON_SURVOL} !important; }}
button[kind="primary"]:disabled {{ background: #2A2A2A !important; }}
button[kind="primary"]:disabled * {{ color: #6B6B6B !important; }}

/* Contrôles segmentés et pastilles : barre plate, segment actif plus clair */
[data-testid="stButtonGroup"] {{ background: var(--panneau-2); border-radius: 8px; padding: 3px; width: fit-content; max-width: 100%; }}
[data-testid="stButtonGroup"] > div, [data-testid="stButtonGroup"] [role="radiogroup"],
[data-testid="stButtonGroup"] [role="group"] {{ flex-wrap: wrap !important; overflow: visible !important; }}
[data-testid="stButtonGroup"] button {{
  border-radius: 6px !important; border: none !important; background: transparent !important;
  color: var(--texte-2) !important; font-weight: 600; font-size: 0.84rem; min-height: 30px;
}}
[data-testid="stButtonGroup"] button p {{ color: inherit !important; }}
[data-testid="stButtonGroup"] button[kind*="Active"], [data-testid="stButtonGroup"] button[aria-checked="true"] {{
  background: {ACTIF_FOND} !important; color: {ACTIF_TEXTE} !important;
}}

/* Champs de saisie */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"],
[data-baseweb="select"] > div, [data-testid="stNumberInputContainer"], [data-testid="stDateInput"] > div > div {{
  border-radius: 8px !important;
}}
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"] {{
  background: var(--panneau-2) !important; border-color: var(--bord) !important;
}}
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea, [data-baseweb="select"] * {{ color: var(--texte) !important; }}
[data-testid="stNumberInputContainer"] {{ overflow: hidden; }}
[data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"] {{ background: #161616 !important; }}
[data-testid="stPopoverBody"] {{ background: #121212 !important; border: 1px solid var(--bord); border-radius: 10px; }}

/* Onglets : même barre segmentée que les contrôles */
[data-baseweb="tab-list"] {{
  background: var(--panneau-2); border-radius: 8px; padding: 3px; gap: 2px; width: fit-content; max-width: 100%;
}}
[data-baseweb="tab"] {{ border-radius: 6px !important; padding: 6px 22px !important; height: auto !important; }}
[data-baseweb="tab"] p {{ color: var(--texte-2) !important; font-weight: 600; font-size: 0.88rem; }}
[data-baseweb="tab"][aria-selected="true"] {{ background: {ACTIF_FOND}; }}
[data-baseweb="tab-list"] [aria-selected="true"] p {{ color: {ACTIF_TEXTE} !important; }}
[data-baseweb="tab"][aria-selected="true"] p {{ color: var(--texte) !important; }}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {{ display: none !important; }}

/* Autres éléments */
[data-testid="stExpander"] details {{ border-radius: 10px !important; background: var(--panneau); border: 1px solid var(--bord) !important; }}
[data-testid="stDataFrame"], [data-testid="stDataFrameResizable"] {{ border-radius: 8px; overflow: hidden; }}
[data-testid="stAlert"] > div {{ border-radius: 10px; }}
[data-testid="stFileUploaderDropzone"] {{ border-radius: 10px; background: var(--panneau-2); }}
hr {{ border-color: var(--bord) !important; }}

/* Composants maison */
.hero {{
  background: var(--panneau); border: 1px solid var(--bord); border-radius: var(--rayon);
  padding: 18px 20px 16px; margin-bottom: 12px;
}}
.hero-libelle {{ color: var(--texte-2) !important; font-size: 0.85rem; font-weight: 500; }}
.hero-valeur {{
  font-size: clamp(2rem, 4.5vw, 2.8rem); font-weight: 700; letter-spacing: -0.03em;
  line-height: 1.1; margin: 2px 0 8px; font-variant-numeric: tabular-nums;
}}
/* Variations : simple texte coloré avec flèche, sans fond */
.pilule {{
  display: inline-flex; align-items: center; gap: 4px; padding: 0 10px 0 0;
  font-size: 0.88rem; font-weight: 600; font-variant-numeric: tabular-nums; background: none;
}}
.pilule.pos {{ color: {VERT_TEXTE} !important; }}
.pilule.neg {{ color: {ROUGE_TEXTE} !important; }}
.pilule.neutre {{ color: var(--texte-2) !important; }}
.hero-pied {{ color: var(--texte-2) !important; font-size: 0.82rem; }}
.puces {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 14px; }}
.puce {{
  display: inline-flex; align-items: center; gap: 8px; background: var(--panneau-2);
  border: 1px solid var(--bord); border-radius: 8px; padding: 5px 12px; font-size: 0.84rem;
}}
.puce b {{ font-weight: 650; font-variant-numeric: tabular-nums; }}
.point {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}

.ligne-budget {{ margin: 0 0 12px; }}
.ligne-budget .entete {{ display: flex; justify-content: space-between; gap: 12px; font-size: 0.9rem; margin-bottom: 5px; }}
.ligne-budget .entete span:last-child {{ color: var(--texte-2) !important; font-variant-numeric: tabular-nums; }}
.barre {{ height: 6px; border-radius: 3px; background: #1F1F1F; overflow: hidden; }}
.barre > span {{ display: block; height: 100%; border-radius: 3px; }}
.barre .ok {{ background: {VERT}; }}
.barre .attention {{ background: {ORANGE}; }}
.barre .depasse {{ background: {ROUGE}; }}
.note {{ color: var(--texte-2) !important; font-size: 0.8rem; }}

/* Enveloppes (PEA, CTO…) */
.enveloppe {{
  background: var(--panneau-2); border: 1px solid var(--bord); border-radius: 10px;
  padding: 12px 14px; margin-bottom: 8px;
}}
.enveloppe-nom {{ font-weight: 600; font-size: 0.85rem; color: var(--texte-2) !important; }}
.enveloppe-valeur {{ font-size: 1.5rem; font-weight: 700; letter-spacing: -0.02em; margin: 2px 0 4px;
  font-variant-numeric: tabular-nums; }}
.enveloppe .pilule {{ margin-top: 6px; }}

/* Places boursières */
.places {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; margin: 6px 0 10px; }}
.place {{ background: var(--panneau-2); border: 1px solid var(--bord); border-radius: 10px; padding: 10px 12px; font-size: 0.82rem; }}
.place-tete {{ display: flex; align-items: center; gap: 8px; font-size: 0.9rem; }}
.place-tete b {{ flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.place-point {{ width: 7px; height: 7px; border-radius: 50%; background: #4A4A4A; flex: none; }}
.place-etat {{ font-size: 0.75rem; font-weight: 600; color: var(--texte-2) !important; }}
.place.ouvert .place-point, .place-puce.ouvert .place-point {{ background: {VERT}; }}
.place.ouvert .place-etat {{ color: {VERT_TEXTE} !important; }}
.place.pause .place-point, .place.férié .place-point,
.place-puce.pause .place-point, .place-puce.férié .place-point {{ background: {ORANGE}; }}
.place.pause .place-etat, .place.férié .place-etat {{ color: {ORANGE} !important; }}
.places-puces {{ margin: 4px 0 10px; }}
.place-puce {{ font-size: 0.82rem; padding: 4px 10px; }}
.place-puce .note {{ font-size: 0.78rem; }}
.place-heures, .place-evt {{ color: var(--texte-2) !important; margin-top: 4px; }}
.place-indice {{ display: block; margin-top: 4px; font-variant-numeric: tabular-nums; }}
.place-indice .pos {{ color: {VERT_TEXTE} !important; }}
.place-indice .neg {{ color: {ROUGE_TEXTE} !important; }}
.place-indice .neutre {{ color: var(--texte-2) !important; }}

/* ---------- Garde-fous anti-chevauchement ---------- */
/* Panneaux : marge basse suffisante pour que la dernière ligne ne touche jamais le bord. */
[class*="st-key-verre"] {{ padding-bottom: 20px !important; }}
/* Streamlit colle parfois le dernier paragraphe au bloc suivant (marge négative) : on l'annule. */
[data-testid="stMarkdownContainer"] > :last-child, [data-testid="stMarkdownContainer"] p:last-child {{ margin-bottom: 0 !important; }}
/* Streamlit met une marge négative (−1rem) sous chaque bloc de texte : le bloc réserve alors moins de place que son
   contenu, qui déborde sur l'élément suivant ou sur le bord du panneau. On la neutralise partout. */
[data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
[data-testid="stElementContainer"], [data-testid="stColumn"], [data-testid="stVerticalBlock"] {{ min-width: 0; }}
/* Les textes longs passent à la ligne au lieu de déborder sur le voisin. */
[data-testid="stMarkdownContainer"], .note, .hero, .enveloppe, .place, .puce {{ overflow-wrap: break-word; }}
.note {{ display: block; line-height: 1.45; margin: 4px 0 2px; }}
.puces {{ align-items: stretch; }}
.puce {{ max-width: 100%; flex-wrap: wrap; row-gap: 2px; line-height: 1.35; }}
.hero-valeur, .enveloppe-valeur {{ overflow-wrap: anywhere; }}
/* Boutons et libellés d'indicateurs : retour à la ligne plutôt que texte coupé ou superposé. */
.stButton > button, .stDownloadButton > button, [data-testid="stPopover"] > div > button {{ height: auto; min-height: 2.25rem; }}
.stButton > button p, [data-testid="stPopover"] > div > button p, [data-testid="stPopoverButton"] p {{
  white-space: normal !important; overflow-wrap: anywhere; text-align: center; line-height: 1.25;
}}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {{ white-space: normal !important; overflow: visible !important; }}
[data-testid="stMetricValue"] {{ font-size: clamp(1.05rem, 2.1vw, 1.45rem) !important; line-height: 1.2; }}
[data-testid="stMetricValue"] > div {{ overflow: visible !important; white-space: normal !important; overflow-wrap: anywhere; }}
[data-testid="stMetricDelta"] {{ flex-wrap: wrap; }}
/* Graphiques : jamais plus larges que leur colonne. */
[data-testid="stPlotlyChart"] {{ overflow: hidden; }}

/* ---------- Adaptation à la largeur de la fenêtre ---------- */
/* Les colonnes qui portent un graphique, un panneau ou des indicateurs passent à la ligne
   plutôt que de s'écraser quand la fenêtre se rétrécit. */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stPlotlyChart"]),
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [class*="st-key-verre"]),
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) {{ flex-wrap: wrap; row-gap: 0.75rem; }}
[data-testid="stColumn"]:has([data-testid="stPlotlyChart"]) {{ min-width: min(300px, 100%); }}
[data-testid="stColumn"]:has(> [data-testid="stVerticalBlock"] > [class*="st-key-verre"]) {{ min-width: min(360px, 100%); }}
[data-testid="stColumn"]:has([data-testid="stMetric"]) {{ min-width: min(160px, 100%); }}
[data-testid="stPlotlyChart"], [data-testid="stPlotlyChart"] > div {{ width: 100% !important; }}
.puces {{ row-gap: 6px; }}
@media (max-width: 1100px) {{
  .block-container, [data-testid="stMainBlockContainer"] {{ padding-left: 1.2rem; padding-right: 1.2rem; }}
  [data-testid="stMetricValue"] {{ font-size: 1.25rem; }}
  .hero-valeur {{ font-size: clamp(1.7rem, 6vw, 2.4rem); }}
}}
@media (max-width: 700px) {{
  .block-container, [data-testid="stMainBlockContainer"] {{ padding: 1rem 0.6rem 3rem; }}
  h1 {{ font-size: 1.4rem !important; }}
  [class*="st-key-verre"], .hero {{ padding: 12px 12px 10px; }}
  [data-baseweb="tab-list"] {{ width: 100%; overflow-x: auto; flex-wrap: nowrap; }}
  [data-baseweb="tab"] {{ padding: 6px 12px !important; white-space: nowrap; }}
  .places {{ grid-template-columns: 1fr; }}
  .puce {{ font-size: 0.8rem; padding: 4px 9px; }}
}}

@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; animation: none !important; }} }}
</style>
"""


def appliquer() -> None:
    st.markdown(_css(), unsafe_allow_html=True)


def verre(nom: str):
    """Panneau translucide arrondi (à utiliser avec `with`)."""
    return st.container(key=f"verre_{nom}")


# ------------------------------------------------------------- formatage
SYMBOLES = {"EUR": "€", "USD": "$", "GBP": "£", "CHF": "CHF", "JPY": "¥", "PLN": "zł"}


def fmt(x, devise: str | None = None, dec: int = 2) -> str:
    try:
        if x is None or x != x:
            return "–"
    except TypeError:
        return "–"
    s = f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")
    return f"{s} {SYMBOLES.get(devise, devise)}" if devise else s


MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def fmt_mois(d) -> str:
    return f"{MOIS[d.month - 1]} {d.year}"


def fmt_pct(x, signe: bool = True, dec: int = 2) -> str:
    if x is None or x != x:
        return "–"
    return (f"{x:+.{dec}f}" if signe else f"{x:.{dec}f}").replace(".", ",") + " %"


def fmt_signe(x, devise: str | None = None, dec: int = 0) -> str:
    if x is None or x != x:
        return "–"
    return ("+" if x >= 0 else "−") + fmt(abs(x), devise, dec)


# ------------------------------------------------------------- composants
def pilule(texte: str, valeur: float | None) -> str:
    classe = "neutre" if valeur is None or valeur == 0 else ("pos" if valeur > 0 else "neg")
    fleche = "" if classe == "neutre" else ("▲ " if valeur > 0 else "▼ ")
    return f'<span class="pilule {classe}">{fleche}{html.escape(texte)}</span>'


def hero(libelle: str, valeur: str, variation_html: str = "", pied: str = "",
         puces: list[tuple[str, str, str]] | None = None) -> None:
    """puces : liste de (couleur, libellé, valeur)."""
    puces_html = ""
    if puces:
        puces_html = '<div class="puces">' + "".join(
            f'<span class="puce"><span class="point" style="background:{c}"></span>'
            f'{html.escape(l)} <b>{html.escape(v)}</b></span>' for c, l, v in puces) + "</div>"
    st.markdown(
        f'<div class="hero"><div class="hero-libelle">{html.escape(libelle)}</div>'
        f'<div class="hero-valeur">{html.escape(valeur)}</div>'
        f'<div>{variation_html}<span class="hero-pied">{html.escape(pied)}</span></div>'
        f'{puces_html}</div>', unsafe_allow_html=True)


def ligne_budget(categorie: str, depense: float, prevu: float, devise: str) -> str:
    if prevu > 0:
        ratio = depense / prevu
        classe = "ok" if ratio < 0.8 else ("attention" if ratio <= 1 else "depasse")
        largeur = min(ratio, 1) * 100
        droite = f"{fmt(depense, devise, 0)} sur {fmt(prevu, devise, 0)}"
        if ratio > 1:
            droite += f" (dépassé de {fmt(depense - prevu, devise, 0)})"
        else:
            droite += f" (reste {fmt(prevu - depense, devise, 0)})"
    else:
        classe, largeur = ("depasse", 100) if depense > 0 else ("ok", 0)
        droite = f"{fmt(depense, devise, 0)} hors budget" if depense > 0 else "aucun budget"
    return (f'<div class="ligne-budget"><div class="entete"><span>{html.escape(categorie)}</span>'
            f'<span>{html.escape(droite)}</span></div>'
            f'<div class="barre"><span class="{classe}" style="width:{largeur:.1f}%"></span></div></div>')


def couleur_gain(v) -> str:
    """Style CSS d'une cellule : vert si positif (favorable), rouge si négatif, gris si nul ou absent."""
    try:
        if v is None or v != v or abs(float(v)) < 1e-9:
            return f"color: {TEXTE_2}"
    except (TypeError, ValueError):
        return ""
    return f"color: {VERT_TEXTE}; font-weight: 600" if float(v) > 0 else f"color: {ROUGE_TEXTE}; font-weight: 600"


SELECTION_CLIC = "single-cell"  # un clic n'importe où sur la ligne la sélectionne (pas de case à cocher)


def ligne_selectionnee(evenement) -> int | None:
    """Position de la ligne cliquée dans un st.dataframe (sélection par cellule ou par ligne)."""
    sel = getattr(evenement, "selection", None) if evenement is not None else None
    if not sel:
        return None
    if sel.get("cells"):
        return int(sel["cells"][0][0])
    if sel.get("rows"):
        return int(sel["rows"][0])
    return None


def fleche(v) -> str:
    """Petit triangle de tendance : ▲ hausse, ▼ baisse, rien si nul."""
    try:
        if v is None or v != v or abs(float(v)) < 1e-9:
            return ""
    except (TypeError, ValueError):
        return ""
    return "▲ " if float(v) > 0 else "▼ "


def tableau_gains(df, colonnes_signees: list[str], formats: dict, cours_et_pru: tuple[str, str] | None = None):
    """Styler pandas : texte des colonnes de gains en vert ▲ / rouge ▼, cours en vert ▲ s'il dépasse le PRU
    (rouge ▼ sinon), formats français. Les colonnes concernées ne doivent pas avoir de format dans
    column_config, sinon Streamlit l'applique à la place de cet affichage."""
    df = df.copy()
    formats = dict(formats)
    signees = [c for c in colonnes_signees if c in df.columns]
    for c in signees:
        base_fmt = formats.get(c, lambda v: f"{v}")
        formats[c] = (lambda f: (lambda v: "–" if v is None or v != v else fleche(v) + f(v)))(base_fmt)
    ecarts = None
    if cours_et_pru and all(c in df.columns for c in cours_et_pru):
        cours, pru = cours_et_pru
        ecarts = (df[cours] - df[pru]).tolist()
        f_cours = formats.pop(cours, lambda v: f"{v}")
        df[cours] = [("–" if v != v else fleche(e) + f_cours(v)) for v, e in zip(df[cours], ecarts)]
    s = df.style.map(couleur_gain, subset=signees)
    if ecarts is not None:
        couleurs = [couleur_gain(e) for e in ecarts]
        s = s.apply(lambda col: couleurs, axis=0, subset=[cours_et_pru[0]])
    return s.format({k: f for k, f in formats.items() if k in df.columns}, na_rep="–")


def note(texte: str) -> None:
    st.markdown(f'<div class="note">{html.escape(texte)}</div>', unsafe_allow_html=True)


# ------------------------------------------------------------- graphiques
def graphique(fig: go.Figure, hauteur: int = 360, legende: bool = True) -> go.Figure:
    fig.update_layout(
        # Marge haute réservée à la légende (placée au-dessus) : elle ne chevauche ni les courbes ni l'axe.
        height=hauteur, margin=dict(l=4, r=4, t=40 if legende else 16, b=4),
        font=dict(family=POLICE, color=TEXTE_2, size=12),
        colorway=PALETTE,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        hoverlabel=dict(bgcolor=PANNEAU_2, bordercolor=BORD, font=dict(family=POLICE, color=TEXTE, size=12)),
        showlegend=legende,
        legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0, xanchor="left", bgcolor="rgba(0,0,0,0)",
                    title=None, font=dict(color=TEXTE, size=11), itemsizing="constant"),
        uniformtext=dict(minsize=9, mode="hide"),  # texte trop serré pour sa barre : masqué plutôt que superposé
        separators=", ",  # virgule décimale et espace des milliers, à la française
        barcornerradius=3, bargap=0.3,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=BORD, title=None, ticks="", showspikes=True,
                     spikecolor="#3A3A3A", spikethickness=1, spikedash="dot", spikemode="across",
                     automargin=True)  # Plotly incline seul les étiquettes trop serrées
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)", zeroline=False, title=None, separatethousands=True,
                     side="right", automargin=True)
    return fig


def rgba(hex_couleur: str, alpha: float) -> str:
    h = hex_couleur.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def courbe_cours(x, y, nom: str = "", hausse: bool = True, hauteur: int = 340) -> go.Figure:
    """Courbe façon application Bourse : verte si hausse, rouge si baisse, aire dégradée."""
    couleur = VERT if hausse else ROUGE
    y = list(y)
    ymin, ymax = (min(y), max(y)) if y else (0.0, 1.0)
    marge = (ymax - ymin) * 0.10 or abs(ymax) * 0.02 or 1
    plancher = ymin - marge
    fig = go.Figure()
    fig.add_scatter(x=x, y=[plancher] * len(y), mode="lines", line=dict(width=0),
                    hoverinfo="skip", showlegend=False)
    trace = dict(x=x, y=y, name=nom, mode="lines", fill="tonexty",
                 line=dict(color=couleur, width=2, shape="linear"))
    try:
        fig.add_scatter(**trace, fillgradient=dict(
            type="vertical", colorscale=[[0, rgba(couleur, 0.0)], [1, rgba(couleur, 0.30)]]))
    except ValueError:  # Plotly trop ancien : aire unie
        fig.add_scatter(**trace, fillcolor=rgba(couleur, 0.16))
    fig.update_yaxes(range=[plancher, ymax + marge])
    return graphique(fig, hauteur, legende=False)
