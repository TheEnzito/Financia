"""Identité visuelle FINANCIA (Brand Kit) : logo, symbole, icône d'application, icônes de navigation et couleurs.

Les dessins viennent du Brand Kit (dossier financia-brand-kit). Ils sont intégrés ici en texte pour être livrés par le
bouton « Mettre à jour » (qui ne transporte que des fichiers .py, .json…).

Règles du logo : ne jamais recolorer le point doré, ni ajouter d'ombre ou de contour. Taille minimale : symbole 20 px,
logo horizontal 96 px de large. L'or reste un point, jamais une surface.
"""

from __future__ import annotations

import base64

# ------------------------------------------------------------------ couleurs (tokens)
INK_950 = "#161514"   # fond principal
INK_900 = "#1E1D1B"   # surfaces, cartes
INK_800 = "#2A2926"   # bordures, séparateurs
INK_500 = "#8C877E"   # texte secondaire
PAPER = "#ECE6DA"     # texte principal, traits du logo
GOLD = "#BFA06A"      # accent doré, à utiliser avec parcimonie
GOLD_SOFT = "rgba(191,160,106,0.14)"  # fonds d'état actif
TRAIT_CLAIR = "#1A1918"  # traits du logo sur fond clair
RAYON = "12px"

# ------------------------------------------------------------------ logo
_SYMBOLE = ("M17 55 C17.5 44 18.6 31 20.4 19 C21.4 12.4 25 10.2 32 10.4 C37 10.6 41.5 11.1 45.4 12 M19.6 34.5 "
            "C25.5 33.2 31 32.4 36.6 32.6 C44.6 33 45.6 43.4 38.8 44.6 C32.6 45.6 30.2 38.4 34.6 33.8 C38 30.4 "
            "43.4 30 48.4 31.4")
_POINT = f'<circle cx="54.6" cy="19.6" r="5.2" fill="{GOLD}"/>'
_MOT = ("M0.50 24.00 Q0.85 11.99 0.00 0.00 Q6.53 -0.30 13.00 0.60 M0.30 11.50 Q5.18 11.85 10.00 11.00 M22.50 0.40 "
        "Q22.10 12.21 22.90 24.00 M32.00 24.00 Q32.80 12.01 32.40 0.00 Q40.01 11.54 46.60 23.70 Q47.40 11.86 47.00 0.00 "
        "M56.50 24.00 Q61.07 12.19 64.50 0.00 Q69.07 11.81 72.50 24.00 M60.10 15.50 Q64.62 15.95 69.10 15.20 M82.00 "
        "24.00 Q82.80 12.01 82.40 0.00 Q90.01 11.54 96.60 23.70 Q97.40 11.86 97.00 0.00 M121.50 4.2 C119.00 1 116.00 0 "
        "114.10 0.2 C109.10 0.8 106.60 6 106.70 12.2 C106.80 18.6 109.90 23.9 114.90 23.8 C117.90 23.7 120.10 22.2 "
        "121.70 19.6 M131.00 0.40 Q130.60 12.21 131.40 24.00 M140.50 24.00 Q145.07 12.19 148.50 0.00 Q153.07 11.81 "
        "156.50 24.00 M144.10 15.50 Q148.62 15.95 153.10 15.20")


def _trait(d: str, couleur: str, epaisseur: float) -> str:
    return (f'<path d="{d}" fill="none" stroke="{couleur}" stroke-width="{epaisseur}" stroke-linecap="round" '
            'stroke-linejoin="round"/>')


def _data_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def logo(clair: bool = False) -> str:
    """Logo horizontal (symbole + FINANCIA), version fond sombre ou fond clair."""
    trait = TRAIT_CLAIR if clair else PAPER
    return _data_uri('<svg xmlns="http://www.w3.org/2000/svg" viewBox="10 4 236 58" width="472" height="116">'
                     + _trait(_SYMBOLE, trait, 5.4) + _POINT
                     + f'<g transform="translate(84 20)">{_trait(_MOT, trait, 3.6)}</g></svg>')


def symbole(clair: bool = False) -> str:
    """Symbole seul (F + point doré)."""
    trait = TRAIT_CLAIR if clair else PAPER
    return _data_uri('<svg xmlns="http://www.w3.org/2000/svg" viewBox="8 4 56 56" width="56" height="56">'
                     + _trait(_SYMBOLE, trait, 5.4) + _POINT + "</svg>")


def icone_appli() -> str:
    """Icône d'application (symbole sur carré sombre arrondi) : onglet du navigateur."""
    return _data_uri('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="512" height="512">'
                     f'<rect width="64" height="64" rx="14" fill="{INK_950}"/>'
                     '<g transform="translate(5 3.5) scale(0.86)">' + _trait(_SYMBOLE, PAPER, 6) + _POINT + "</g></svg>")


# ------------------------------------------------------------------ icônes (24 × 24, trait 2,4)
# Chaque icône : (tracés du trait, accent doré). L'icône « marches » est dessinée dans le même style que le kit.
_ICONES = {
    "patrimoine": (
        '<path d="M4.2 20.4 C4 16.6 4.1 13.6 4.6 11.2 C7 9 9.4 6.8 12 4.6 C14.6 6.7 17 8.9 19.4 11.1 C19.8 14.2 '
        '19.9 17.2 19.6 20.2 C14.4 20.7 9.2 20.8 4.2 20.4 Z"/><path d="M10 20.4 C9.9 17.8 10.3 15.4 12.1 15.3 C13.9 '
        '15.2 14.1 17.6 14 20.4"/>',
        '<circle cx="18.6" cy="4.4" r="2.1"/>'),
    "budget": (
        '<path d="M11.6 3.8 C6.9 4 3.6 7.7 3.7 12.4 C3.8 17 7.5 20.5 12.1 20.4 C16.6 20.3 20.2 16.8 20.3 12.4 '
        'L11.8 12.3 Z"/>',
        '<path d="M14.6 2.6 C18.4 2.9 21.2 5.9 21.4 9.6 L14.5 9.7 Z"/>'),
    "portefeuilles": (
        '<path d="M6.6 5.8 C10 3.4 13.6 3 16.4 5.4"/><path d="M4.4 8.2 C4.3 6.6 5.3 5.7 7 5.6 L17.8 5.4 C19.2 5.4 '
        '20 6.3 20 7.6 L20.2 17 C20.2 18.6 19.2 19.4 17.6 19.4 L7 19.6 C5.3 19.6 4.4 18.6 4.4 17 Z"/><path '
        'd="M20.2 10.4 L15.7 10.5 C14.2 10.6 13.5 11.5 13.6 12.6 C13.7 13.7 14.4 14.4 15.8 14.4 L20.2 14.3"/>',
        '<circle cx="16.1" cy="12.45" r="1.35"/>'),
    "transactions": (
        '<path d="M4.2 9.4 C7.4 6.2 13.2 5.4 19 8.2"/><path d="M15.6 4.9 L19.2 8.2 L15.9 10.9"/><path d="M19.8 14.8 '
        'C16.6 18 10.8 18.8 5 16"/><path d="M8.4 19.3 L4.8 16 L8.1 13.3"/>',
        '<circle cx="12" cy="12.1" r="1.7"/>'),
    "marches": (
        '<path d="M3.8 17.6 C6.2 14.8 8 12.6 10 13.8 C12 15 13.4 12.8 15.2 10.2 C16.2 8.8 17 8 17.8 7.6"/>'
        '<path d="M3.6 20.6 C9 20.2 14.6 20.8 20.4 20.4"/>',
        '<circle cx="20" cy="6.4" r="2.1"/>'),
    "parametres": (
        '<path d="M3.6 6.6 C8.4 6.2 14 6.9 20.4 6.4"/><path d="M3.6 12.2 C9 11.8 14.6 12.5 20.4 12"/><path d="M3.6 '
        '17.7 C8.6 17.3 14.2 18 20.4 17.5"/><circle cx="15.2" cy="6.55" r="2.3" fill="{c}"/><circle cx="13" '
        'cy="17.65" r="2.3" fill="{c}"/>',
        '<circle cx="8" cy="12.05" r="2.5"/>'),
}


def icone(nom: str, couleur: str) -> str:
    """Icône du kit en image intégrée, trait de la couleur donnée, accent toujours doré."""
    traits, accent = _ICONES[nom]
    return _data_uri('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none">'
                     f'<g fill="none" stroke="{couleur}" stroke-width="2.4" stroke-linecap="round" '
                     f'stroke-linejoin="round">{traits.replace("{c}", couleur)}</g>'
                     f'<g fill="{GOLD}" stroke="none">{accent}</g></svg>')


# Page de l'application (fin de l'adresse du lien de navigation) → icône du kit
ICONES_PAGES = {"/": "patrimoine", "/budget": "budget", "/portefeuille": "portefeuilles",
                "/transactions": "transactions", "/marches": "marches", "/parametres": "parametres"}


def css_icones_navigation(couleur_repos: str, couleur_active: str) -> str:
    """Remplace les icônes du menu latéral par celles du kit (trait gris au repos, clair sur la page active)."""
    regles = []
    for fin, nom in ICONES_PAGES.items():
        lien = f'[data-testid="stSidebarNavLink"][href$="{fin}"]'
        regles.append(f'{lien} [data-testid="stIconMaterial"] {{ background-image: url("{icone(nom, couleur_repos)}"); }}')
        regles.append(f'{lien}[aria-current="page"] [data-testid="stIconMaterial"], {lien}:hover [data-testid="stIconMaterial"] '
                      f'{{ background-image: url("{icone(nom, couleur_active)}"); }}')
    regles.append('[data-testid="stSidebarNavLink"] [data-testid="stIconMaterial"] { font-size: 0 !important; '
                  'color: transparent !important; width: 20px; height: 20px; min-width: 20px; '
                  'background-size: 20px 20px; background-repeat: no-repeat; background-position: center; }')
    return "\n".join(regles)
