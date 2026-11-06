"""Style visuel de FINANCIA : dix thèmes (huit sombres, deux clairs), panneaux à bordure fine et ombre douce,
typographie dense, variations toujours en vert et rouge, graphiques sobres."""

from __future__ import annotations

import base64
import html

import plotly.graph_objects as go
import streamlit as st

import marque

# Vert et rouge des chiffres : identiques dans tous les thèmes (hausse / baisse, gain / perte).
VERT, ROUGE = "#1FC16B", "#F2454F"
VERT_TEXTE, ROUGE_TEXTE = "#22C55E", "#F2454F"

NOM_APPLI = "FINANCIA"


# ------------------------------------------------------------------ thèmes
def rgba(hex_couleur: str, alpha: float) -> str:
    h = hex_couleur.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _melange(a: str, b: str, t: float) -> str:
    """Couleur intermédiaire entre a et b (t = 0 → a, t = 1 → b)."""
    ca = [int(a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb))


def _theme(fond, panneau, panneau_2, bord, texte, texte_2, accent, accent_2, palette, bouton_texte,
           clair=False, **forcer) -> dict:
    """Construit un thème complet à partir de quelques couleurs de base (les autres en sont déduites)."""
    t = dict(
        FOND=fond, PANNEAU=panneau, PANNEAU_2=panneau_2, BORD=bord, TEXTE=texte, TEXTE_2=texte_2,
        ACCENT=accent, ACCENT_2=accent_2, CLAIR=clair, PRIMAIRE=accent,
        BOUTON_FOND=f"linear-gradient(135deg, {accent} 0%, {accent_2} 100%)",
        BOUTON_SURVOL=f"linear-gradient(135deg, {_melange(accent, '#FFFFFF', 0.12)} 0%, "
                      f"{_melange(accent_2, '#FFFFFF', 0.12)} 100%)",
        BOUTON_TEXTE=bouton_texte,
        ACTIF_FOND=rgba(accent, 0.16 if not clair else 0.12), ACTIF_TEXTE=texte,
        SIDEBAR=_melange(fond, "#000000", 0.35) if not clair else panneau,
        SURVOL=_melange(panneau_2, texte, 0.06), PISTE=_melange(panneau_2, texte, 0.09),
        MENU=_melange(panneau_2, texte, 0.02) if not clair else panneau,
        GRILLE=rgba(texte, 0.06), REPERE=_melange(fond, texte, 0.28),
        LUEUR=rgba(accent, 0.09 if not clair else 0.10), LUEUR_2=rgba(accent_2, 0.04),
        REFLET="rgba(255,255,255,0.025)" if not clair else "rgba(255,255,255,0.9)",
        OMBRE=("inset 0 1px 0 rgba(255,255,255,0.035), 0 18px 40px -26px rgba(0,0,0,0.95)" if not clair else
               "0 1px 2px rgba(15,23,42,0.05), 0 14px 34px -22px rgba(15,23,42,0.22)"),
        VERT_TEXTE="#22C55E" if not clair else "#15803D", ROUGE_TEXTE="#F2454F" if not clair else "#DC2626",
        HALO=rgba(accent, 0.13), RAYON="16px", NAV_BARRE=True,
        PALETTE=list(palette),
        ENVELOPPES={"PEA": palette[0], "CTO": palette[1], "Compte-titres": palette[1], "PEA-PME": palette[6],
                    "Assurance vie": palette[4], "PER": palette[3]},
    )
    t.update(BLEU=palette[0], ORANGE=palette[2], VIOLET=palette[3], TURQUOISE=palette[4], ROSE=palette[5],
             INDIGO=palette[6], GRIS=texte_2)
    t.update(forcer)
    return t


THEMES = {
    "FINANCIA": _theme(
        marque.INK_950, marque.INK_900, "#242320", marque.INK_800, marque.PAPER, marque.INK_500,
        marque.GOLD, "#D6BC8C",
        ["#8FA7C9", "#6FB3A8", "#C9A27A", "#9C8BC9", "#7FB0A0", "#D49BB0", "#7A86B8", "#C9BFA9",
         "#8C877E", "#A3B18A", marque.GOLD], marque.INK_950,
        # L'or reste un point, jamais une surface : boutons couleur papier, halos neutres, état actif or doux.
        BOUTON_FOND=marque.PAPER, BOUTON_SURVOL="#F6F1E7", ACTIF_FOND=marque.GOLD_SOFT, ACTIF_TEXTE=marque.PAPER,
        SIDEBAR="#121110", LUEUR="rgba(236,230,218,0.025)", LUEUR_2="rgba(236,230,218,0.0)",
        HALO="rgba(236,230,218,0.035)", RAYON=marque.RAYON, NAV_BARRE=False),
    "Sombre": _theme(
        "#0A0A0A", "#111111", "#161616", "#232323", "#FFFFFF", "#8B8B8B", VERT, "#7EE2A8",
        ["#4C8DFF", "#1FC16B", "#F5A524", "#A78BFA", "#2DD4BF", "#F472B6", "#6366F1", "#C2A878",
         "#8B8B8B", "#7DD3FC", "#FACC15"], "#000000",
        BOUTON_FOND="#FFFFFF", BOUTON_SURVOL="#E6E6E6", ACTIF_FOND="#262626", LUEUR="rgba(255,255,255,0.035)",
        LUEUR_2="rgba(255,255,255,0.0)", SIDEBAR="#070707",
        ENVELOPPES={"PEA": "#4C8DFF", "CTO": "#64D2FF", "Compte-titres": "#64D2FF", "PEA-PME": "#6366F1",
                    "Assurance vie": "#2DD4BF", "PER": "#A78BFA"}),
    "Minuit": _theme(
        "#070B14", "#0D1321", "#121A2B", "#1E2940", "#EEF2FF", "#8A95B0", "#5B8CFF", "#9DB8FF",
        ["#5B8CFF", "#38BDF8", "#F5A524", "#A78BFA", "#2DD4BF", "#F472B6", "#818CF8", "#94A3B8",
         "#FACC15", "#7DD3FC", "#C084FC"], "#050A18"),
    "Océan": _theme(
        "#041214", "#0A1C1F", "#0F2428", "#1A363B", "#E8FBFA", "#82A9A8", "#2DD4BF", "#7DE8DA",
        ["#2DD4BF", "#38BDF8", "#F5A524", "#818CF8", "#5EEAD4", "#F472B6", "#60A5FA", "#FDE68A",
         "#94A3B8", "#C4B5FD", "#7DD3FC"], "#03201D"),
    "Améthyste": _theme(
        "#0C0814", "#140E20", "#1A1329", "#2B2040", "#F5F0FF", "#9B8FB5", "#A78BFA", "#D8C8FF",
        ["#A78BFA", "#F472B6", "#FBBF24", "#60A5FA", "#2DD4BF", "#E879F9", "#818CF8", "#FDA4AF",
         "#94A3B8", "#C4B5FD", "#67E8F9"], "#130A26"),
    "Bordeaux": _theme(
        "#0F0709", "#180C10", "#201117", "#341C24", "#FBF1F3", "#B0939A", "#D9A5A0", "#F3D2C1",
        ["#D9A5A0", "#C084FC", "#F5A524", "#7DD3FC", "#E8B4BC", "#F9A8D4", "#A78BFA", "#FCD34D",
         "#94A3B8", "#6EE7B7", "#B98AA0"], "#1A0A0D"),
    "Graphite": _theme(
        "#0E1013", "#15181D", "#1B1F25", "#2A2F37", "#F3F5F8", "#8D96A3", "#CBD5E1", "#F8FAFC",
        ["#93C5FD", "#CBD5E1", "#F5A524", "#A78BFA", "#5EEAD4", "#F9A8D4", "#818CF8", "#FDE68A",
         "#64748B", "#7DD3FC", "#D8B4FE"], "#0E1013"),
    "Cuivre": _theme(
        "#0F0B08", "#18120D", "#1F1812", "#33281E", "#FAF3EC", "#A8988A", "#D98B5F", "#F2BE94",
        ["#D98B5F", "#7DD3FC", "#E7C27D", "#A78BFA", "#5EB8A8", "#F0A6CA", "#8FA7C9", "#C9B79C",
         "#94A3B8", "#FCD34D", "#B9A0E8"], "#1A0F08"),
    "Ivoire": _theme(
        "#F7F4EE", "#FFFFFF", "#F3EFE7", "#E6DFD2", "#1C1914", "#776F62", "#A67C2E", "#C9A45C",
        ["#A67C2E", "#3B6EA8", "#C2643A", "#7356B5", "#2A8C80", "#C04F86", "#4F5BA8", "#8A7F6C",
         "#B8941F", "#4AA3C9", "#8E6BBF"], "#FFFFFF", clair=True),
    "Neige": _theme(
        "#F5F6F8", "#FFFFFF", "#F0F2F5", "#E3E6EB", "#0B0D12", "#6B7280", "#111827", "#4B5563",
        ["#2563EB", "#0EA5E9", "#F59E0B", "#7C3AED", "#0D9488", "#DB2777", "#4F46E5", "#64748B",
         "#CA8A04", "#06B6D4", "#9333EA"], "#FFFFFF", clair=True,
        ACTIF_FOND="#FFFFFF", LUEUR="rgba(37,99,235,0.06)", LUEUR_2="rgba(124,58,237,0.04)"),
}
THEME_DEFAUT = "FINANCIA"
ANCIENS_THEMES = {"Noir & or": "FINANCIA"}  # thèmes retirés → remplaçant
THEME_ACTIF = THEME_DEFAUT


def activer_theme(nom: str) -> None:
    """Applique un thème : met à jour les couleurs utilisées par le CSS et les graphiques."""
    global THEME_ACTIF, FOND, PANNEAU, PANNEAU_2, BORD, TEXTE, TEXTE_2, ACCENT, ACCENT_2, BOUTON_FOND
    global BOUTON_SURVOL, BOUTON_TEXTE, ACTIF_FOND, ACTIF_TEXTE, BLEU, ORANGE, VIOLET, INDIGO, TURQUOISE, ROSE
    global GRIS, PALETTE, COULEURS_PATRIMOINE, COULEURS_ENVELOPPES, VERT_TEXTE, ROUGE_TEXTE, CLAIR
    global SIDEBAR, SURVOL, PISTE, MENU, GRILLE, REPERE, LUEUR, LUEUR_2, REFLET, OMBRE
    nom = ANCIENS_THEMES.get(nom, nom)
    THEME_ACTIF = nom if nom in THEMES else THEME_DEFAUT
    t = THEMES[THEME_ACTIF]
    FOND, PANNEAU, PANNEAU_2, BORD = t["FOND"], t["PANNEAU"], t["PANNEAU_2"], t["BORD"]
    TEXTE, TEXTE_2, ACCENT, ACCENT_2, CLAIR = t["TEXTE"], t["TEXTE_2"], t["ACCENT"], t["ACCENT_2"], t["CLAIR"]
    BOUTON_FOND, BOUTON_SURVOL, BOUTON_TEXTE = t["BOUTON_FOND"], t["BOUTON_SURVOL"], t["BOUTON_TEXTE"]
    ACTIF_FOND, ACTIF_TEXTE = t["ACTIF_FOND"], t["ACTIF_TEXTE"]
    BLEU, ORANGE, VIOLET, INDIGO = t["BLEU"], t["ORANGE"], t["VIOLET"], t["INDIGO"]
    TURQUOISE, ROSE, GRIS, PALETTE = t["TURQUOISE"], t["ROSE"], t["GRIS"], list(t["PALETTE"])
    SIDEBAR, SURVOL, PISTE, MENU = t["SIDEBAR"], t["SURVOL"], t["PISTE"], t["MENU"]
    GRILLE, REPERE, LUEUR, LUEUR_2, REFLET, OMBRE = (t["GRILLE"], t["REPERE"], t["LUEUR"], t["LUEUR_2"],
                                                     t["REFLET"], t["OMBRE"])
    VERT_TEXTE, ROUGE_TEXTE = t["VERT_TEXTE"], t["ROUGE_TEXTE"]
    COULEURS_PATRIMOINE = {
        "Bourse (portefeuille)": BLEU, "Placements hors application": INDIGO, "Épargne": VERT,
        "Comptes courants": TURQUOISE, "Immobilier": ORANGE, "Crypto": VIOLET, "Autres actifs": "#AC8E68",
        "Dettes": ROUGE,
    }
    COULEURS_ENVELOPPES = dict(t["ENVELOPPES"])


def theme_streamlit() -> dict:
    """Options de thème Streamlit correspondant au thème actif (tableaux, champs, cases à cocher)."""
    t = THEMES[THEME_ACTIF]
    return {"base": "light" if t["CLAIR"] else "dark", "primaryColor": t["PRIMAIRE"],
            "backgroundColor": t["FOND"], "borderColor": t["BORD"], "baseRadius": "10px",
            "dataframeHeaderBackgroundColor": t["PANNEAU_2"], "secondaryBackgroundColor": t["PANNEAU_2"],
            "textColor": t["TEXTE"]}


def logo_svg(icone_seule: bool = False) -> str:
    """Logo FINANCIA du Brand Kit (version fond sombre ou fond clair selon le thème), en image intégrée."""
    return marque.symbole(CLAIR) if icone_seule else marque.logo(CLAIR)


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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {{
  color-scheme: {"light" if CLAIR else "dark"};
  --fond: {FOND};
  --panneau: {PANNEAU};
  --panneau-2: {PANNEAU_2};
  --bord: {BORD};
  --texte: {TEXTE};
  --texte-2: {TEXTE_2};
  --accent: {ACCENT};
  --accent-2: {ACCENT_2};
  --accent-doux: {rgba(ACCENT, 0.16)};
  --survol: {SURVOL};
  --piste: {PISTE};
  --menu: {MENU};
  --ombre: {OMBRE};
  --reflet: {REFLET};
  --rayon: {THEMES[THEME_ACTIF]['RAYON']};
}}
::selection {{ background: {rgba(ACCENT, 0.30)}; }}

/* Fond : aplat du thème éclairé par deux halos très discrets */
.stApp {{
  font-family: {POLICE}; color: var(--texte);
  background: radial-gradient(1100px 520px at 100% -8%, {LUEUR}, transparent 65%),
              radial-gradient(900px 520px at -10% 105%, {LUEUR_2}, transparent 60%), var(--fond);
  background-attachment: fixed;
  font-feature-settings: "cv11", "ss01"; -webkit-font-smoothing: antialiased;
}}
.stApp, .stApp p, .stApp li, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3,
.stApp h4, [data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] {{ color: var(--texte); }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {{ color: var(--texte-2) !important; }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container, [data-testid="stMainBlockContainer"] {{ padding-top: 2rem; max-width: 1380px; }}
[data-testid="stVerticalBlock"] {{ gap: 0.85rem; }}

h1 {{ font-weight: 750 !important; letter-spacing: -0.035em; font-size: 2rem !important; line-height: 1.15 !important; }}
h2, h3 {{ font-weight: 650 !important; letter-spacing: -0.02em; }}
.stApp strong, .stApp b {{ font-weight: 650; }}

/* Barres de défilement fines */
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--piste); border-radius: 10px; border: 2px solid var(--fond); }}
::-webkit-scrollbar-thumb:hover {{ background: {REPERE}; }}

/* Panneaux : st.container(key="verre_…") — surface légèrement éclairée, ombre douce */
[class*="st-key-verre"] {{
  background: linear-gradient(180deg, var(--reflet), transparent 140px), var(--panneau);
  border: 1px solid var(--bord);
  border-radius: var(--rayon);
  padding: 18px 20px 16px;
  box-shadow: var(--ombre);
}}
/* Titre de panneau : petit point lumineux de la couleur du thème devant le premier texte en gras */
[class*="st-key-verre"] > [data-testid="stElementContainer"]:first-of-type [data-testid="stMarkdownContainer"] > p:first-child > strong:first-child::before,
[class*="st-key-verre"] > [data-testid="stLayoutWrapper"]:first-child [data-testid="stColumn"]:first-child > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:first-of-type [data-testid="stMarkdownContainer"] > p:first-child > strong:first-child::before {{
  content: ""; display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: linear-gradient(135deg, {ACCENT}, {ACCENT_2}); box-shadow: 0 0 0 3px {rgba(ACCENT, 0.16)};
  margin-right: 10px; vertical-align: middle; transform: translateY(-1px);
}}

/* Indicateurs */
[data-testid="stMetric"] {{
  background: linear-gradient(180deg, var(--reflet), transparent), var(--panneau-2);
  border: 1px solid var(--bord); border-radius: 12px; padding: 12px 16px;
  transition: border-color .2s ease;
}}
[data-testid="stMetric"]:hover {{ border-color: {rgba(ACCENT, 0.35)}; }}
[data-testid="stMetricLabel"] p {{ color: var(--texte-2) !important; font-size: 0.78rem; font-weight: 500; letter-spacing: 0.01em; }}
[data-testid="stMetricValue"] {{ font-weight: 700; letter-spacing: -0.02em; color: var(--texte); font-size: 1.45rem;
  font-variant-numeric: tabular-nums; }}

/* Barre latérale */
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {SIDEBAR} 0%, var(--fond) 100%); border-right: 1px solid var(--bord); }}
[data-testid="stSidebarHeader"] {{ padding-top: 1.1rem; }}
[data-testid="stSidebarHeader"] img {{ height: 30px !important; max-width: 100%; }}
[data-testid="stSidebarNavLink"], [data-testid="stSidebarNav"] a {{
  border-radius: 10px !important; margin: 2px 8px; transition: background .15s ease;
}}
[data-testid="stSidebarNavLink"] span {{ font-weight: 550; }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{
  background: {ACTIF_FOND} !important; {'box-shadow: inset 3px 0 0 var(--accent);' if THEMES[THEME_ACTIF]['NAV_BARRE'] else ''}
}}
[data-testid="stSidebarNavLink"][aria-current="page"] span {{ color: var(--texte) !important; font-weight: 650; }}
[data-testid="stSidebarNavLink"]:hover {{ background: var(--survol) !important; }}
[data-testid="stSidebarNavSeparator"] {{ border-color: var(--bord) !important; }}

/* Icônes du menu : celles du Brand Kit */
{marque.css_icones_navigation(TEXTE_2, TEXTE)}

/* Boutons */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button, [data-testid="stPopover"] > div > button {{
  border-radius: 10px !important; padding: 0.42rem 1.05rem;
  border: 1px solid var(--bord) !important; background: var(--panneau-2); color: var(--texte);
  box-shadow: none; font-weight: 600; font-size: 0.88rem;
  transition: background .15s ease, border-color .15s ease, transform .15s ease, box-shadow .15s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stPopover"] > div > button:hover {{
  background: var(--survol); border-color: {rgba(ACCENT, 0.45)} !important;
}}
.stButton > button:active {{ transform: translateY(1px); }}
[data-testid="stBaseButton-primary"], button[kind="primary"] {{
  background: {BOUTON_FOND} !important; color: {BOUTON_TEXTE} !important; border: none !important;
  box-shadow: 0 8px 22px -12px {rgba(ACCENT, 0.75)} !important;
}}
[data-testid="stBaseButton-primary"] *, button[kind="primary"] * {{ color: {BOUTON_TEXTE} !important; }}
[data-testid="stBaseButton-primary"]:hover, button[kind="primary"]:hover {{
  background: {BOUTON_SURVOL} !important; transform: translateY(-1px);
}}
button[kind="primary"]:disabled {{ background: var(--piste) !important; box-shadow: none !important; transform: none; }}
button[kind="primary"]:disabled * {{ color: var(--texte-2) !important; }}

/* Contrôles segmentés et pastilles : barre plate, segment actif en relief */
[data-testid="stButtonGroup"] {{
  background: var(--panneau-2); border: 1px solid var(--bord); border-radius: 12px; padding: 3px;
  width: fit-content; max-width: 100%;
}}
[data-testid="stButtonGroup"] > div, [data-testid="stButtonGroup"] [role="radiogroup"],
[data-testid="stButtonGroup"] [role="group"] {{ flex-wrap: wrap !important; overflow: visible !important; }}
[data-testid="stButtonGroup"] button {{
  border-radius: 9px !important; border: none !important; background: transparent !important;
  color: var(--texte-2) !important; font-weight: 600; font-size: 0.84rem; min-height: 30px;
  transition: background .15s ease, color .15s ease;
}}
[data-testid="stButtonGroup"] button:hover {{ color: var(--texte) !important; }}
[data-testid="stButtonGroup"] button p {{ color: inherit !important; }}
[data-testid="stButtonGroup"] button[kind*="Active"], [data-testid="stButtonGroup"] button[aria-checked="true"] {{
  background: {ACTIF_FOND} !important; color: {ACTIF_TEXTE} !important;
  box-shadow: inset 0 0 0 1px {rgba(ACCENT, 0.28)};
}}

/* Champs de saisie */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"],
[data-baseweb="select"] > div, [data-testid="stNumberInputContainer"], [data-testid="stDateInput"] > div > div {{
  border-radius: 10px !important;
}}
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"] {{
  background: var(--panneau-2) !important; border-color: var(--bord) !important;
  transition: border-color .15s ease, box-shadow .15s ease;
}}
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within, [data-baseweb="select"] > div:focus-within {{
  border-color: {rgba(ACCENT, 0.7)} !important; box-shadow: 0 0 0 3px {rgba(ACCENT, 0.14)};
}}
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea, [data-baseweb="select"] * {{ color: var(--texte) !important; }}
[data-testid="stNumberInputContainer"] {{ overflow: hidden; }}
[data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"] {{ background: var(--menu) !important; }}
[data-testid="stPopoverBody"] {{
  background: var(--menu) !important; border: 1px solid var(--bord); border-radius: 14px; box-shadow: var(--ombre);
}}
[data-testid="stDialog"] [role="dialog"] {{ background: var(--panneau) !important; border: 1px solid var(--bord); border-radius: 18px; }}

/* Onglets : même barre segmentée que les contrôles */
[data-baseweb="tab-list"] {{
  background: var(--panneau-2); border: 1px solid var(--bord); border-radius: 12px; padding: 3px; gap: 2px;
  width: fit-content; max-width: 100%;
}}
[data-baseweb="tab"] {{ border-radius: 9px !important; padding: 7px 22px !important; height: auto !important;
  transition: background .15s ease; }}
[data-baseweb="tab"]:hover {{ background: var(--survol); }}
[data-baseweb="tab"] p {{ color: var(--texte-2) !important; font-weight: 600; font-size: 0.88rem; }}
[data-baseweb="tab"][aria-selected="true"] {{ background: {ACTIF_FOND}; box-shadow: inset 0 0 0 1px {rgba(ACCENT, 0.28)}; }}
[data-baseweb="tab-list"] [aria-selected="true"] p {{ color: {ACTIF_TEXTE} !important; }}
[data-baseweb="tab"][aria-selected="true"] p {{ color: var(--texte) !important; }}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {{ display: none !important; }}

/* Autres éléments */
[data-testid="stExpander"] details {{ border-radius: 12px !important; background: var(--panneau); border: 1px solid var(--bord) !important; }}
[data-testid="stExpander"] summary:hover {{ background: var(--survol); border-radius: 12px; }}
[data-testid="stDataFrame"], [data-testid="stDataFrameResizable"] {{ border-radius: 12px; overflow: hidden; }}
[data-testid="stAlert"] > div {{ border-radius: 12px; }}
[data-testid="stFileUploaderDropzone"] {{ border-radius: 12px; background: var(--panneau-2); border: 1px dashed {REPERE}; }}
[data-testid="stToast"] {{ background: var(--menu) !important; border: 1px solid var(--bord); border-radius: 12px; }}
hr {{ border-color: var(--bord) !important; }}

/* Composants maison */
.hero {{
  position: relative; overflow: hidden;
  background: radial-gradient(560px 240px at 0% 0%, {THEMES[THEME_ACTIF]['HALO']}, transparent 70%),
              linear-gradient(180deg, var(--reflet), transparent 160px), var(--panneau);
  border: 1px solid var(--bord); border-radius: calc(var(--rayon) + 4px);
  padding: 22px 24px 20px; margin-bottom: 12px; box-shadow: var(--ombre);
}}
.hero::before {{
  content: ""; position: absolute; left: 24px; right: 24px; top: 0; height: 1px;
  background: linear-gradient(90deg, transparent, {rgba(ACCENT, 0.7)}, transparent);
}}
.hero-libelle {{ color: var(--texte-2) !important; font-size: 0.74rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.09em; }}
.hero-valeur {{
  font-size: clamp(2rem, 4.5vw, 3rem); font-weight: 750; letter-spacing: -0.04em;
  line-height: 1.1; margin: 6px 0 10px; font-variant-numeric: tabular-nums;
}}
/* Variations : simple texte coloré avec flèche, sans fond */
.pilule {{
  display: inline-flex; align-items: center; gap: 4px; padding: 0 10px 0 0;
  font-size: 0.88rem; font-weight: 650; font-variant-numeric: tabular-nums; background: none;
}}
.pilule.pos {{ color: {VERT_TEXTE} !important; }}
.pilule.neg {{ color: {ROUGE_TEXTE} !important; }}
.pilule.neutre {{ color: var(--texte-2) !important; }}
.hero-pied {{ color: var(--texte-2) !important; font-size: 0.82rem; }}
.puces {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 16px; }}
.puce {{
  display: inline-flex; align-items: center; gap: 8px; background: var(--panneau-2);
  border: 1px solid var(--bord); border-radius: 999px; padding: 5px 13px; font-size: 0.84rem;
}}
.puce b {{ font-weight: 650; font-variant-numeric: tabular-nums; }}
.point {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}

.ligne-budget {{ margin: 0 0 12px; }}
.ligne-budget .entete {{ display: flex; justify-content: space-between; gap: 12px; font-size: 0.9rem; margin-bottom: 6px; }}
.ligne-budget .entete span:last-child {{ color: var(--texte-2) !important; font-variant-numeric: tabular-nums; }}
.barre {{ height: 6px; border-radius: 3px; background: var(--piste); overflow: hidden; }}
.barre > span {{ display: block; height: 100%; border-radius: 3px; }}
.barre .ok {{ background: {VERT}; }}
.barre .attention {{ background: {ORANGE}; }}
.barre .depasse {{ background: {ROUGE}; }}
.note {{ color: var(--texte-2) !important; font-size: 0.8rem; }}

/* Enveloppes (PEA, CTO…) */
.enveloppe {{
  background: linear-gradient(180deg, var(--reflet), transparent), var(--panneau-2);
  border: 1px solid var(--bord); border-radius: 14px;
  padding: 13px 15px; margin-bottom: 8px; transition: border-color .2s ease;
}}
.enveloppe:hover {{ border-color: {rgba(ACCENT, 0.35)}; }}
.enveloppe-nom {{ font-weight: 600; font-size: 0.78rem; color: var(--texte-2) !important;
  text-transform: uppercase; letter-spacing: 0.06em; }}
.enveloppe-valeur {{ font-size: 1.5rem; font-weight: 750; letter-spacing: -0.03em; margin: 2px 0 4px;
  font-variant-numeric: tabular-nums; }}
.enveloppe .pilule {{ margin-top: 6px; }}

/* Places boursières */
.places {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; margin: 6px 0 10px; }}
.place {{ background: var(--panneau-2); border: 1px solid var(--bord); border-radius: 12px; padding: 10px 12px; font-size: 0.82rem; }}
.place-tete {{ display: flex; align-items: center; gap: 8px; font-size: 0.9rem; }}
.place-tete b {{ flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.place-point {{ width: 7px; height: 7px; border-radius: 50%; background: {REPERE}; flex: none; }}
.place-etat {{ font-size: 0.75rem; font-weight: 600; color: var(--texte-2) !important; }}
.place.ouvert .place-point, .place-puce.ouvert .place-point {{ background: {VERT}; box-shadow: 0 0 0 3px {rgba(VERT, 0.18)}; }}
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

/* Encadré de version (menu latéral) */
.version-appli {{ display: flex; align-items: center; gap: 10px; margin-top: 10px; padding: 10px 12px;
  border: 1px solid var(--bord); border-radius: 12px; background: var(--panneau-2); }}
.version-appli img {{ width: 26px; height: 26px; flex: none; }}
.version-appli .nom {{ font-weight: 750; font-size: 0.78rem; letter-spacing: 0.14em; }}
.version-appli .note {{ margin: 0; font-size: 0.74rem; }}

/* Sélecteur de thème */
.apercu-theme {{ border-radius: 14px; padding: 10px; margin-bottom: 6px; position: relative; overflow: hidden; }}
.apercu-theme.actif {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.apercu-theme .barre-apercu {{ height: 6px; border-radius: 3px; margin: 8px 0 6px; }}
.apercu-theme .ligne-apercu {{ display: flex; justify-content: space-between; align-items: baseline; gap: 6px; }}
.apercu-theme .nom-apercu {{ font-weight: 650; font-size: 0.86rem; }}
.apercu-theme .valeur-apercu {{ font-weight: 750; font-size: 1.05rem; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }}
.apercu-theme .pastilles {{ display: flex; gap: 4px; margin-top: 8px; }}
.apercu-theme .pastilles span {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
.st-key-grille_themes [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap; row-gap: 0.75rem; }}
.st-key-grille_themes [data-testid="stColumn"] {{ min-width: min(150px, 100%); }}

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


def logo() -> None:
    """Logo FINANCIA en haut du menu latéral (pictogramme seul quand le menu est replié)."""
    st.logo(logo_svg(), size="large", icon_image=logo_svg(icone_seule=True))



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
                     spikecolor=REPERE, spikethickness=1, spikedash="dot", spikemode="across",
                     automargin=True)  # Plotly incline seul les étiquettes trop serrées
    fig.update_yaxes(gridcolor=GRILLE, zeroline=False, title=None, separatethousands=True,
                     side="right", automargin=True)
    return fig


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
