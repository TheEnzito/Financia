"""Page « Budget » : plan mensuel simple, analyse des dépenses, saisie des mouvements."""

from __future__ import annotations

import calendar
import html
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import calculs
import db
import donnees
import releves
import style
from style import fmt, fmt_pct, fmt_signe


def page() -> None:
    st.title("Budget")
    base = donnees.devise_base()
    mvts = db.lister_budget()
    _courant, precedent = mois_courant_et_precedent()
    plan, dernier, tendances, mouvements = st.tabs(
        ["Mon plan", f"Mois dernier ({libelle_mois(precedent).split()[0]})", "Où va mon argent", "Mouvements"])
    with plan:
        onglet_plan(mvts, base)
    with dernier:
        onglet_mois_dernier(mvts, base)
    with tendances:
        onglet_tendances(mvts, base)
    with mouvements:
        onglet_mouvements(mvts, base)


TYPES_MOUVEMENT = {"DEPENSE": "Dépense", "REVENU": "Revenu", "VIREMENT": "Virement entre mes comptes"}
CAT_VIREMENT = "Virement entre mes comptes"  # catégorie qui fait d'une opération importée un virement


def type_affiche(categorie: str, montant: float) -> str:
    if categorie == CAT_VIREMENT:
        return "Virement"
    return "Revenu" if montant > 0 else "Dépense"


def mes_comptes() -> list[str]:
    """Vos comptes (Mon patrimoine › Mes comptes) et enveloppes boursières, pour les virements."""
    noms = db.lister_comptes()["nom"].tolist() + db.lister_enveloppes()
    return list(dict.fromkeys(noms + ["Compte courant", "Autre compte"]))


# ------------------------------------------------------------ saisie rapide
def formulaire_mouvement(prefixe: str, base: str) -> None:
    c1, c2, c3, c4 = st.columns([1.1, 1.2, 1, 1])
    type_ = c1.segmented_control("Type", list(TYPES_MOUVEMENT), default="DEPENSE", key=f"{prefixe}_type",
                                 format_func=TYPES_MOUVEMENT.get) or "DEPENSE"
    if type_ == "VIREMENT":
        # Virement entre deux de vos comptes : ni dépense ni revenu, il ne compte pas dans le budget.
        comptes = mes_comptes()
        d1, d2 = c2.columns(2)
        depuis = d1.selectbox("Depuis", comptes, key=f"{prefixe}_depuis")
        vers = d2.selectbox("Vers", [c for c in comptes if c != depuis] or comptes, key=f"{prefixe}_vers")
        categorie = f"{depuis} → {vers}"
    else:
        cle = "categories" if type_ == "DEPENSE" else "categories_revenus"
        categories = [c.strip() for c in db.lire_parametre(cle).split(",") if c.strip()]
        categorie = c2.selectbox("Catégorie", categories, key=f"{prefixe}_cat")
    montant = c3.number_input(f"Montant ({base})", min_value=0.0, step=1.0, format="%.2f", key=f"{prefixe}_montant")
    jour = c4.date_input("Date", date.today(), format="DD/MM/YYYY", key=f"{prefixe}_date")
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    description = c1.text_input("Description (facultatif)", key=f"{prefixe}_desc")
    if c2.button("Ajouter", type="primary", key=f"{prefixe}_ok"):
        if montant <= 0:
            st.error("Le montant doit être supérieur à zéro.")
        else:
            db.ajouter_mouvement(jour, type_, categorie, montant, description)
            st.toast(f"{TYPES_MOUVEMENT[type_]} de {fmt(montant, base)} ajouté"
                     + (" (hors budget)." if type_ == "VIREMENT" else "."))
            st.rerun()


# ============================================================ FLUX (Sankey)
# Une couleur pastel par étage : revenus → budget → groupes → catégories.
COULEURS_FLUX = {"revenus": "#A5B4FC", "budget": "#FDBA74", "Besoins": "#C4B5FD", "Envies": "#7DD3FC",
                 "Épargne": "#F9A8D4", "Non réparti": "#9CA3AF", "Déficit": "#FCA5A5"}


PASTELS_GROUPES = ["#86EFAC", "#FDE68A", "#FCA5A5", "#A5F3FC", "#D8B4FE", "#FDBA74", "#BEF264", "#F0ABFC"]
def _couleurs_barres() -> dict:  # lues au moment de l'affichage : elles suivent le thème choisi
    return {"Besoins": style.BLEU, "Envies": style.VIOLET, "Épargne": style.VERT}


def couleur_groupe(groupe: str) -> str:
    """Couleur pastel du flux d'un groupe (fixe pour les groupes de départ, stable pour les autres)."""
    if groupe in COULEURS_FLUX:
        return COULEURS_FLUX[groupe]
    return PASTELS_GROUPES[sum(map(ord, groupe)) % len(PASTELS_GROUPES)]


def couleur_barre(groupe: str) -> str:
    return _couleurs_barres().get(groupe) or style.PALETTE[sum(map(ord, groupe)) % len(style.PALETTE)]


def barres_groupes(valeurs_pct: dict[str, float], cle: str, plan_pct: dict[str, float] | None = None,
                   nom: str = "Mon plan") -> None:
    """Barres par groupe en % du revenu, avec le repère 50/30/20 pour les groupes de départ."""
    # Barres horizontales : les noms (même longs) restent lisibles quelle que soit la largeur de la colonne.
    groupes = list(valeurs_pct)[::-1]  # premier groupe en haut
    maxi = max([valeurs_pct[g] for g in groupes] + list((plan_pct or {}).values()) + [50.0]) * 1.08
    fig = go.Figure()
    fig.add_bar(y=groupes, x=[valeurs_pct[g] for g in groupes], name=nom, orientation="h",
                marker_color=[couleur_barre(g) for g in groupes], width=0.6,
                hovertemplate="%{y} : %{x:.2f} %<extra></extra>")
    # Pourcentages dans une colonne réservée à droite : jamais recouverts par un repère ou un losange.
    for g in groupes:
        fig.add_annotation(x=1.0, xref="paper", xanchor="right", y=g, yref="y", showarrow=False,
                           text=f"<b>{fmt_pct(valeurs_pct[g], signe=False, dec=2)}</b>",
                           font=dict(color=style.TEXTE, size=12))
    if plan_pct:
        fig.add_scatter(y=groupes, x=[plan_pct.get(g, 0) for g in groupes], name="Mon plan", mode="markers",
                        marker=dict(symbol="diamond", size=11, color=style.ORANGE),
                        hovertemplate="Plan %{y} : %{x:.2f} %<extra></extra>")
    repere = {g: v * 100 for g, v in calculs.REGLE_50_30_20.items() if g in groupes}
    if repere:
        fig.add_scatter(y=list(repere), x=list(repere.values()), name="Repère 50/30/20", mode="markers",
                        marker=dict(symbol="line-ns", size=26, line=dict(width=3, color=style.TEXTE)),
                        hovertemplate="Repère %{y} : %{x:.0f} %<extra></extra>")
    fig = style.graphique(fig, max(190, 46 * len(groupes) + 90))
    fig.update_xaxes(ticksuffix=" %", range=[0, maxi], showgrid=True, gridcolor=style.GRILLE,
                     domain=[0, 0.8], automargin=True)
    largeur_noms = 7 * max((len(g) for g in groupes), default=6) + 12  # place réservée aux noms, en pixels
    fig.update_yaxes(side="left", gridcolor="rgba(0,0,0,0)", automargin=True, tickfont=dict(color=style.TEXTE))
    fig.update_layout(hovermode="closest", bargap=0.35, margin=dict(l=largeur_noms, r=8, t=34, b=4),
                      legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0, font=dict(size=11)))
    st.plotly_chart(fig, config={"displayModeBar": False}, key=cle)


def _sankey(sources: dict[str, float], branches: list[tuple[str, str, float]], base: str,
            centre: str = "Budget") -> go.Figure | None:
    """sources : {libellé: montant} à gauche ; branches : (groupe, catégorie, montant).
    Une branche dont la catégorie est vide s'arrête au niveau du groupe."""
    sources = dict(sorted(((k, v) for k, v in sources.items() if v > 0),
                          key=lambda kv: (kv[0] == "Déficit", -kv[1])))
    branches = [b for b in branches if b[2] > 0]
    if not sources or not branches:
        return None
    labels, couleurs, src, dst, val, coul_liens = [], [], [], [], [], []
    colonnes: list[int] = []
    montants: list[float] = []

    def noeud(libelle: str, montant: float, couleur: str, colonne: int) -> int:
        # Deux lignes (nom, puis montant) : étiquettes deux fois moins larges, donc sans collision entre colonnes.
        labels.append(f"{libelle}<br>{fmt(montant, base, 0)}")
        couleurs.append(couleur)
        colonnes.append(colonne)
        montants.append(montant)
        return len(labels) - 1

    def lien(a: int, b: int, montant: float, couleur: str) -> None:
        src.append(a), dst.append(b), val.append(montant), coul_liens.append(style.rgba(couleur, 0.55))

    entree = sum(sources.values())
    for nom, montant in sources.items():
        couleur = COULEURS_FLUX["Déficit"] if nom == "Déficit" else COULEURS_FLUX["revenus"]
        noeud(nom, montant, couleur, 0)
    i_centre = noeud(centre, entree, COULEURS_FLUX["budget"] if style.THEME_ACTIF == style.THEME_DEFAUT
                     else style.ACCENT, 1)
    for i in range(len(sources)):
        lien(i, i_centre, montants[i], couleurs[i])

    totaux = {}
    for g, _, m in branches:
        totaux[g] = totaux.get(g, 0) + m
    ordre = sorted(totaux, key=lambda g: (g == "Non réparti", -totaux[g]))
    for groupe in ordre:
        lignes = sorted([b for b in branches if b[0] == groupe], key=lambda b: -b[2])
        if not lignes:
            continue
        couleur = couleur_groupe(groupe)
        total = sum(m for _, _, m in lignes)
        categories = [b for b in lignes if b[1]]
        if len(categories) == 1 and len(lignes) == 1:
            # Une seule catégorie dans le groupe : un seul nœud (« Besoins · Logement »), pas deux étiquettes voisines.
            cat = categories[0][1]
            i_groupe = noeud(groupe if cat == groupe else f"{groupe} · {cat}", total, couleur, 2)
            lien(i_centre, i_groupe, total, couleur)
            continue
        i_groupe = noeud(groupe, total, couleur, 2)
        lien(i_centre, i_groupe, total, couleur)
        for _, categorie, montant in lignes:
            if categorie:
                lien(i_groupe, noeud(categorie, montant, couleur, 3), montant, couleur)

    # Positions fixes : chaque colonne empile ses nœuds dans l'ordre de création, de sorte que
    # les catégories restent groupées sous leur groupe (pas de flux qui se croisent).
    nb_col = max(colonnes) + 1
    xs = [0.001 + c * 0.998 / (nb_col - 1) for c in colonnes]
    ys = [0.0] * len(labels)
    marge = 0.035
    # Hauteur adaptée à la colonne la plus chargée : chaque étiquette dispose d'au moins ~36 px.
    plus_chargee = max(colonnes.count(c) for c in range(nb_col))
    hauteur = max(460, 42 * plus_chargee + 60)
    ecart_min = 36 / (hauteur - 24)  # écart minimal entre deux centres de nœuds (étiquette sur deux lignes)
    for c in range(nb_col):
        idx = [i for i, col in enumerate(colonnes) if col == c]
        total_col = sum(montants[i] for i in idx) or 1
        echelle = (1 - marge * (len(idx) - 1)) / total_col
        haut = 0.0
        for i in idx:
            h = montants[i] * echelle
            ys[i] = haut + h / 2
            haut += h + marge
        # Garde-fou : deux étiquettes voisines ne se superposent jamais.
        for k in range(1, len(idx)):
            ys[idx[k]] = max(ys[idx[k]], ys[idx[k - 1]] + ecart_min)
        if idx and ys[idx[-1]] > 0.999:  # trop bas : on remonte la colonne, puis on la resserre si besoin
            decalage = min(ys[idx[-1]] - 0.999, ys[idx[0]] - 0.001)
            for i in idx:
                ys[i] -= decalage
            if ys[idx[-1]] > 0.999:
                premier, dernier = ys[idx[0]], ys[idx[-1]]
                for i in idx:
                    ys[i] = premier + (ys[i] - premier) * (0.999 - premier) / (dernier - premier)
        for i in idx:
            ys[i] = min(max(ys[i], 0.001), 0.999)
    fig = go.Figure(go.Sankey(
        arrangement="fixed", valueformat=",.0f", valuesuffix=f" {base}",
        textfont=dict(family=style.POLICE, color=style.TEXTE, size=12.5),
        node=dict(label=labels, color=couleurs, pad=14, thickness=12, line=dict(width=0), x=xs, y=ys,
                  hovertemplate="%{label}<extra></extra>"),
        link=dict(source=src, target=dst, value=val, color=coul_liens,
                  hovertemplate="%{source.label} → %{target.label}<extra></extra>"),
    ))
    fig.update_layout(height=hauteur, margin=dict(l=8, r=8, t=12, b=12),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", separators=", ",
                      font=dict(family=style.POLICE, color=style.TEXTE),
                      hoverlabel=dict(bgcolor=style.PANNEAU_2, font=dict(color=style.TEXTE)))
    return fig


def libelle_mois(mois: str) -> str:
    return style.fmt_mois(pd.Timestamp(mois + "-01")).capitalize()


def mois_courant_et_precedent() -> tuple[str, str]:
    aujourd_hui = pd.Timestamp.today()
    return aujourd_hui.strftime("%Y-%m"), (aujourd_hui - pd.DateOffset(months=1)).strftime("%Y-%m")


def groupe_categorie(categorie: str, groupe_de: dict) -> str:
    if categorie in groupe_de:
        return groupe_de[categorie]
    defaut = db.GROUPE_PAR_DEFAUT.get(categorie)
    return defaut if defaut in db.lister_groupes() else db.groupe_par_defaut()


def flux_reel(mvts: pd.DataFrame, groupe_de: dict, mois: str) -> tuple[dict, list]:
    """Sources (revenus) et branches (groupe, catégorie, montant) du flux réel d'un mois."""
    sel = mvts[mvts["date"].dt.strftime("%Y-%m") == mois] if not mvts.empty else mvts
    sources = sel[sel["type"] == "REVENU"].groupby("categorie")["montant"].sum().to_dict() if not sel.empty else {}
    depenses = sel[sel["type"] == "DEPENSE"].groupby("categorie")["montant"].sum() if not sel.empty else pd.Series(dtype=float)
    branches = [(groupe_categorie(c, groupe_de), c, float(m)) for c, m in depenses.items()]
    solde = sum(sources.values()) - float(depenses.sum())
    if solde > 0.5:
        branches.append(("Épargne", "Reste du mois", solde))
    elif solde < -0.5:
        sources["Déficit"] = -solde
    return sources, branches


def chiffres_mois(mvts: pd.DataFrame, mois: str) -> dict:
    """Revenus, dépenses, épargne, taux d'épargne, virements et dépenses par catégorie d'un mois."""
    sel = mvts[mvts["date"].dt.strftime("%Y-%m") == mois] if not mvts.empty else mvts
    rev = float(sel.loc[sel["type"] == "REVENU", "montant"].sum()) if not sel.empty else 0.0
    dep = float(sel.loc[sel["type"] == "DEPENSE", "montant"].sum()) if not sel.empty else 0.0
    vir = float(sel.loc[sel["type"] == "VIREMENT", "montant"].sum()) if not sel.empty else 0.0
    par_cat = (sel[sel["type"] == "DEPENSE"].groupby("categorie")["montant"].sum()
               if not sel.empty else pd.Series(dtype=float))
    return {"revenus": rev, "depenses": dep, "epargne": rev - dep, "virements": vir, "operations": sel,
            "taux": (rev - dep) / rev * 100 if rev > 0 else None, "par_categorie": par_cat}


def flux_plan(mvts: pd.DataFrame, plan: pd.DataFrame, revenu: float) -> tuple[dict, list]:
    """Sources et branches du flux prévu par le plan (revenu prévu réparti selon vos revenus habituels)."""
    sources = {"Revenu mensuel": revenu}
    recents = mvts[(mvts["type"] == "REVENU") &
                   (mvts["date"] >= pd.Timestamp.today().normalize() - pd.DateOffset(months=6))] \
        if not mvts.empty else mvts
    if revenu > 0 and not recents.empty:
        parts = recents.groupby("categorie")["montant"].sum()
        sources = (parts / parts.sum() * revenu).to_dict()
    branches = [(r.groupe, r.categorie, float(r.montant)) for r in plan.itertuples(index=False)]
    reste = revenu - sum(m for _, _, m in branches)
    if reste > 0.5:
        branches.append(("Non réparti", "", reste))
    elif reste < -0.5:
        sources["Déficit"] = -reste
    return sources, branches


def comparaison_mois(mvts: pd.DataFrame, plan: pd.DataFrame, revenu: float, base: str) -> None:
    """Réel du mois dernier (N-1) face au plan prévu pour ce mois (N) : deux flux côte à côte,
    puis l'écart par catégorie. Montre où le plan corrige (ou non) les habitudes du mois passé."""
    groupe_de = dict(zip(plan["categorie"], plan["groupe"]))
    courant, precedent = mois_courant_et_precedent()
    reel = chiffres_mois(mvts, precedent)
    # Même périmètre des deux côtés : ce qui est rangé dans le groupe « Épargne » n'est pas une dépense.
    reel_dep = float(sum(m for c, m in reel["par_categorie"].items() if groupe_categorie(c, groupe_de) != "Épargne"))
    reel.update(depenses=reel_dep, epargne=reel["revenus"] - reel_dep,
                taux=(reel["revenus"] - reel_dep) / reel["revenus"] * 100 if reel["revenus"] > 0 else None)
    prevu_cat = plan.set_index("categorie")["montant"].astype(float)
    prevu_dep = float(prevu_cat[[groupe_categorie(c, groupe_de) != "Épargne" for c in prevu_cat.index]].sum())
    prevu = {"revenus": revenu, "depenses": prevu_dep, "epargne": revenu - prevu_dep,
             "taux": (revenu - prevu_dep) / revenu * 100 if revenu > 0 else None}
    nom_n1 = libelle_mois(precedent).split()[0].lower()

    c1, c2, c3, c4 = st.columns(4)
    for col, nom, cle, inverse in [(c1, "Revenus prévus", "revenus", False), (c2, "Dépenses prévues", "depenses", True),
                                   (c3, "Épargne prévue", "epargne", False)]:
        col.metric(f"{nom} ({libelle_mois(courant).split()[0].lower()})", fmt(prevu[cle], base, 0),
                   f"{fmt_signe(prevu[cle] - reel[cle], base, 0)} vs réel {nom_n1}",
                   delta_color="inverse" if inverse else "normal")
    c4.metric("Taux d'épargne prévu", fmt_pct(prevu["taux"], signe=False, dec=2),
              f"{prevu['taux'] - reel['taux']:+.2f} pts vs réel {nom_n1}".replace("-", "−").replace(".", ",")
              if prevu["taux"] is not None and reel["taux"] is not None else None)

    g, d = st.columns(2)
    with g:
        st.markdown(f"**Réel : {libelle_mois(precedent).lower()} (mois N-1)**")
        sources, branches = flux_reel(mvts, groupe_de, precedent)
        fig = _sankey(sources, branches, base)
        if fig is None:
            st.info("Aucun revenu ni dépense enregistré le mois dernier : importez son relevé dans Mouvements.")
        else:
            st.plotly_chart(fig.update_layout(height=min(fig.layout.height or 460, 520)),
                            config={"displayModeBar": False}, key="sankey_comparaison_reel")
    with d:
        st.markdown(f"**Plan prévu : {libelle_mois(courant).lower()} (mois N)**")
        sources, branches = flux_plan(mvts, plan, revenu)
        fig = _sankey(sources, branches, base)
        if fig is None:
            st.info("Indiquez votre revenu et vos budgets dans Mon plan pour voir le flux prévu.")
        else:
            st.plotly_chart(fig.update_layout(height=min(fig.layout.height or 460, 520)),
                            config={"displayModeBar": False}, key="sankey_comparaison_plan")

    # Écart par catégorie : réel du mois N-1 vs budget prévu du mois N
    cats = [c for c in dict.fromkeys(list(prevu_cat.index) + list(reel["par_categorie"].index))
            if prevu_cat.get(c, 0) > 0 or reel["par_categorie"].get(c, 0) > 0]
    cats.sort(key=lambda c: -max(prevu_cat.get(c, 0), reel["par_categorie"].get(c, 0)))
    if cats:
        st.markdown("**Par catégorie : réel du mois dernier face au budget de ce mois**")
        fig = go.Figure()
        fig.add_bar(x=cats, y=[reel["par_categorie"].get(c, 0) for c in cats], name=f"Réel {nom_n1}",
                    marker_color=style.GRIS)
        fig.add_bar(x=cats, y=[prevu_cat.get(c, 0) for c in cats], name=f"Plan {libelle_mois(courant).split()[0].lower()}",
                    marker_color=style.BLEU)
        st.plotly_chart(style.graphique(fig, 300).update_layout(barmode="group", hovermode="x unified"),
                        config={"displayModeBar": False}, key="barres_comparaison")
        ecarts = [(c, reel["par_categorie"].get(c, 0) - prevu_cat.get(c, 0)) for c in cats]
        a_reduire = sorted([e for e in ecarts if e[1] > 0.5], key=lambda x: -x[1])[:3]
        if a_reduire:
            style.note("Pour tenir le plan ce mois-ci, par rapport au mois dernier, il faut dépenser moins en : "
                       + " · ".join(f"{c} (−{fmt(e, base, 0)})" for c, e in a_reduire) + ".")
        else:
            style.note("Le mois dernier, toutes les catégories sont restées dans le budget prévu pour ce mois.")


def flux_budget(mvts: pd.DataFrame, plan: pd.DataFrame, revenu: float, base: str) -> None:
    with style.verre("flux_budget"):
        c1, c2, c3 = st.columns([1.6, 1.8, 1], vertical_alignment="center")
        c1.markdown("**Le chemin de mon argent**")
        mode = c2.segmented_control("Mode", ["Plan prévu", "Mois réel", "Comparaison"], default="Plan prévu",
                                    key="mode_flux", label_visibility="collapsed") or "Plan prévu"
        groupe_de = dict(zip(plan["categorie"], plan["groupe"]))
        if mode == "Comparaison":
            c3.caption("Réel N-1 vs plan N")
            comparaison_mois(mvts, plan, revenu, base)
            return

        if mode == "Plan prévu":
            sources, branches = flux_plan(mvts, plan, revenu)
            note = ("Montants de votre plan. Les sources de revenus reprennent la répartition de vos revenus "
                    "des 6 derniers mois.")
        else:
            aujourd_hui = pd.Timestamp.today()
            mois_dispo = sorted(set(mvts["date"].dt.strftime("%Y-%m")) | {aujourd_hui.strftime("%Y-%m")},
                                reverse=True) if not mvts.empty else [aujourd_hui.strftime("%Y-%m")]
            mois = c3.selectbox("Mois du flux", mois_dispo, label_visibility="collapsed", key="mois_flux",
                                format_func=lambda m: style.fmt_mois(pd.Timestamp(m + "-01")).capitalize())
            sources, branches = flux_reel(mvts, groupe_de, mois)
            note = "Revenus et dépenses saisis pour ce mois ; ce qui n'est pas dépensé apparaît en épargne."

        fig = _sankey(sources, branches, base)
        if fig is None:
            st.info("Indiquez votre revenu et vos budgets ci-dessous pour voir le flux." if mode == "Plan prévu"
                    else "Aucun revenu ni dépense saisi pour ce mois.")
        else:
            st.plotly_chart(fig, config={"displayModeBar": False}, key=f"sankey_{mode}")
            style.note(note + " Survolez un flux pour le détail.")


# ================================================================ GROUPES
def _creer_groupe() -> None:
    nom = (st.session_state.get("nouveau_groupe") or "").strip()
    if not nom:
        st.session_state["_msg_groupe"] = "Donnez un nom au groupe."
    elif nom.lower() in (g.lower() for g in db.lister_groupes()):
        st.session_state["_msg_groupe"] = f"Le groupe « {nom} » existe déjà."
    else:
        db.ajouter_groupe(nom)
        st.session_state["nouveau_groupe"] = ""
        st.session_state["_msg_groupe"] = f"Groupe « {nom} » créé : choisissez-le pour vos catégories dans le tableau."
        st.session_state["version_plan"] = st.session_state.get("version_plan", 0) + 1


def _renommer_groupe(ancien: str) -> None:
    nouveau = (st.session_state.get(f"renommer_groupe_{ancien}") or "").strip()
    if nouveau and nouveau != ancien:
        if nouveau.lower() in (g.lower() for g in db.lister_groupes()):
            st.session_state["_msg_groupe"] = f"Le groupe « {nouveau} » existe déjà."
            return
        db.renommer_groupe(ancien, nouveau)
        st.session_state["_msg_groupe"] = f"« {ancien} » renommé en « {nouveau} »."
        st.session_state["version_plan"] = st.session_state.get("version_plan", 0) + 1


def _supprimer_groupe(nom: str) -> None:
    remplacement = st.session_state.get(f"remplacer_groupe_{nom}")
    if remplacement:
        db.supprimer_groupe(nom, remplacement)
        st.session_state["_msg_groupe"] = f"Groupe « {nom} » supprimé (catégories déplacées dans « {remplacement} »)."
        st.session_state["version_plan"] = st.session_state.get("version_plan", 0) + 1


def _deplacer_groupe(nom: str, decalage: int) -> None:
    db.deplacer_groupe(nom, decalage)
    st.session_state["version_plan"] = st.session_state.get("version_plan", 0) + 1


def gestion_groupes(plan: pd.DataFrame, groupes: list[str], base: str) -> None:
    """Création, renommage, ordre et suppression des groupes de dépenses (Besoins, Envies, Épargne…)."""
    if msg := st.session_state.pop("_msg_groupe", None):
        st.toast(msg)
    with st.popover(f"Gérer les groupes ({len(groupes)})", width="stretch"):
        st.markdown("**Groupes de dépenses**")
        style.note("Rangez vos catégories dans des groupes (ex. Besoins, Envies, Épargne, Enfants, Projets…). "
                   "Le groupe « Épargne » est réservé à l'argent mis de côté.")
        g1, g2 = st.columns([3, 1], vertical_alignment="bottom")
        g1.text_input("Nouveau groupe", key="nouveau_groupe", placeholder="ex. Enfants, Projets, Animaux")
        g2.button("Créer", on_click=_creer_groupe, type="primary", width="stretch")
        st.divider()
        for i, g in enumerate(groupes):
            lignes = plan[plan["groupe"] == g]
            entete = (f'<span class="point" style="background:{couleur_barre(g)}"></span> <b>{html.escape(g)}</b> · '
                      f'{len(lignes)} catégorie(s) · {fmt(float(lignes["montant"].sum()), base, 0)} / mois')
            c1, c2, c3 = st.columns([6, 1, 1], vertical_alignment="center")
            c1.markdown(entete, unsafe_allow_html=True)
            c2.button("↑", key=f"monter_groupe_{g}", disabled=i == 0, on_click=_deplacer_groupe, args=(g, -1),
                      help="Monter")
            c3.button("↓", key=f"descendre_groupe_{g}", disabled=i == len(groupes) - 1, on_click=_deplacer_groupe,
                      args=(g, 1), help="Descendre")
            if g == db.GROUPE_EPARGNE:
                continue
            with st.expander(f"Modifier « {g} »"):
                r1, r2 = st.columns([3, 1], vertical_alignment="bottom")
                r1.text_input("Nouveau nom", value=g, key=f"renommer_groupe_{g}")
                r2.button("Renommer", key=f"btn_renommer_groupe_{g}", on_click=_renommer_groupe, args=(g,),
                          width="stretch")
                autres = [x for x in groupes if x != g]
                s1, s2 = st.columns([3, 1], vertical_alignment="bottom")
                s1.selectbox("Déplacer ses catégories vers", autres, key=f"remplacer_groupe_{g}",
                             index=autres.index(db.groupe_par_defaut()) if db.groupe_par_defaut() in autres else 0)
                s2.button("Supprimer", key=f"btn_supprimer_groupe_{g}", on_click=_supprimer_groupe, args=(g,),
                          width="stretch")


# ================================================================== PLAN
def onglet_plan(mvts: pd.DataFrame, base: str) -> None:
    plan = db.lire_plan()
    version = st.session_state.get("version_plan", 0)
    moy_revenus = calculs.moyenne_mois_complets(mvts, "revenus")
    revenu_enregistre = float(db.lire_parametre("revenu_prevu") or 0)
    flux_budget(mvts, plan, revenu_enregistre or moy_revenus, base)

    g, d = st.columns([3, 2])
    with g, style.verre("plan_edition"):
        st.markdown("**Répartir mon revenu**")
        revenu = st.number_input(f"Revenu mensuel net prévu ({base})", min_value=0.0, step=50.0,
                                 value=float(revenu_enregistre or round(moy_revenus)), key="revenu_prevu_saisie")
        if revenu != revenu_enregistre:
            db.ecrire_parametre("revenu_prevu", str(revenu))
        if moy_revenus:
            style.note(f"Vos revenus des 6 derniers mois : {fmt(moy_revenus, base, 0)} en moyenne.")
        groupes = db.lister_groupes()
        gestion_groupes(plan, groupes, base)
        edite = st.data_editor(
            plan, key=f"editeur_plan_{version}", num_rows="dynamic", hide_index=True,
            column_config={
                "categorie": st.column_config.TextColumn("Catégorie", required=True),
                "groupe": st.column_config.SelectboxColumn("Groupe", options=groupes, required=True,
                                                           default=db.groupe_par_defaut()),
                "montant": st.column_config.NumberColumn(f"Budget mensuel ({base})", min_value=0, step=10,
                                                         format="%.0f", default=0),
            })
        edite = edite.dropna(subset=["categorie"])
        edite["montant"] = pd.to_numeric(edite["montant"], errors="coerce").fillna(0.0)
        c1, c2 = st.columns(2)
        if c1.button("Enregistrer le plan", type="primary"):
            db.enregistrer_plan(edite)
            st.session_state["version_plan"] = version + 1
            st.toast("Plan enregistré.")
            st.rerun()
        if c2.button("Proposer une répartition 50/30/20",
                     help="50 % pour les besoins, 30 % pour les envies, 20 % pour l'épargne, "
                          "répartis selon vos dépenses habituelles."):
            piv = calculs.depenses_mois_categorie(mvts, 7)
            moyennes = piv.iloc[:-1].mean().to_dict() if not piv.empty and piv.shape[1] else {}
            db.enregistrer_plan(calculs.proposer_50_30_20(edite, revenu, moyennes))
            st.session_state["version_plan"] = version + 1
            st.rerun()
        style.note("Ajoutez ou supprimez des lignes directement dans le tableau. Les catégories servent aussi "
                   "pour la saisie de vos dépenses.")

    with d, style.verre("plan_resume"):
        alloue = float(edite["montant"].sum())
        reste = revenu - alloue
        style.hero("Reste à répartir", fmt(reste, base, 0),
                   style.pilule(f"{fmt_pct(alloue / revenu * 100 if revenu else None, signe=False, dec=2)} du revenu réparti",
                                None if reste >= 0 else -1),
                   "", None)
        if reste < 0:
            st.warning(f"Votre plan dépasse votre revenu de {fmt(-reste, base, 0)}.")
        par_groupe = edite.groupby("groupe")["montant"].sum().reindex(groupes).fillna(0)
        if revenu > 0:
            barres_groupes({g: float(v) / revenu * 100 for g, v in par_groupe.items()}, "graphe_groupes")
            st.markdown('<div class="puces">' + "".join(
                f'<span class="puce"><span class="point" style="background:{couleur_barre(g)}"></span>'
                f'{html.escape(g)} <b>{fmt(v, base, 0)}</b></span>' for g, v in par_groupe.items()) + "</div>",
                unsafe_allow_html=True)

    # Suivi du mois
    with style.verre("suivi_mois"):
        aujourd_hui = pd.Timestamp.today()
        mois_dispo = sorted(set(mvts["date"].dt.strftime("%Y-%m")) | {aujourd_hui.strftime("%Y-%m")}, reverse=True) \
            if not mvts.empty else [aujourd_hui.strftime("%Y-%m")]
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.markdown("**Suivi du mois**")
        mois = c2.selectbox("Mois", mois_dispo, label_visibility="collapsed",
                            format_func=lambda m: style.fmt_mois(pd.Timestamp(m + "-01")).capitalize())
        suivi = calculs.suivi_plan(db.lire_plan(), mvts, mois)
        prevu, depense = float(suivi["prevu"].sum()), float(suivi["depense"].sum())
        annee, num = int(mois[:4]), int(mois[5:])
        nb_jours = calendar.monthrange(annee, num)[1]
        en_cours = mois == aujourd_hui.strftime("%Y-%m")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Budget du mois", fmt(prevu, base, 0))
        c2.metric("Dépensé", fmt(depense, base, 0))
        c3.metric("Reste", fmt(prevu - depense, base, 0))
        if en_cours and depense > 0:
            rythme = depense / aujourd_hui.day * nb_jours
            c4.metric("À ce rythme, fin de mois", fmt(rythme, base, 0),
                      fmt(rythme - prevu, base, 0) + " vs budget" if prevu else None, delta_color="inverse")
        else:
            c4.metric("Jours restants", nb_jours - aujourd_hui.day if en_cours else 0)
        lignes = suivi[(suivi["prevu"] > 0) | (suivi["depense"] > 0)].sort_values("prevu", ascending=False)
        if lignes.empty:
            style.note("Fixez vos budgets ci-dessus et saisissez vos dépenses pour suivre votre mois.")
        else:
            colonnes = st.columns(2)
            for i, r in enumerate(lignes.itertuples(index=False)):
                colonnes[i % 2].markdown(style.ligne_budget(r.categorie, r.depense, r.prevu, base),
                                         unsafe_allow_html=True)

    with st.expander("Ajouter une dépense ou un revenu"):
        formulaire_mouvement("plan", base)


# ============================================================ MOIS DERNIER
def onglet_mois_dernier(mvts: pd.DataFrame, base: str) -> None:
    """Dépenses réelles du mois précédent (ou d'un mois passé), présentées comme « Mon plan »."""
    plan = db.lire_plan()
    groupe_de = dict(zip(plan["categorie"], plan["groupe"]))
    courant, precedent = mois_courant_et_precedent()
    passes = sorted({m for m in (mvts["date"].dt.strftime("%Y-%m") if not mvts.empty else []) if m < courant}
                    | {precedent}, reverse=True)
    c1, c2 = st.columns([2.4, 1.1], vertical_alignment="center")
    mois = c2.selectbox("Mois", passes, index=passes.index(precedent), key="mois_dernier",
                        label_visibility="collapsed", format_func=libelle_mois)
    m = chiffres_mois(mvts, mois)
    avant = chiffres_mois(mvts, (pd.Timestamp(mois + "-01") - pd.DateOffset(months=1)).strftime("%Y-%m"))
    c1.markdown(f"#### {libelle_mois(mois)} : vos dépenses réelles")
    nom_mois = libelle_mois(mois).lower()
    de_mois = ("d'" if nom_mois[0] in "aeiouyéèâ" else "de ") + nom_mois  # « d'octobre », « de novembre »
    if m["operations"].empty:
        st.info(f"Aucune opération en {libelle_mois(mois).lower()}. Importez le relevé de ce mois dans "
                "**Mouvements**, ou saisissez vos dépenses.")
        return

    prevu = float(plan["montant"].sum())
    ecart = m["depenses"] - prevu
    pied = (f"{fmt(abs(ecart), base, 0)} {'au-dessus' if ecart > 0 else 'en dessous'} de votre plan "
            f"({fmt(prevu, base, 0)})" if prevu else "aucun plan défini dans Mon plan")
    hausse = m["depenses"] - avant["depenses"]
    # Plus de dépenses = rouge (flèche vers le haut), moins = vert.
    variation = (f'<span class="pilule {"neg" if hausse > 0 else "pos"}">{"▲" if hausse > 0 else "▼"} '
                 f'{fmt_signe(hausse, base, 0)} vs mois précédent</span>' if avant["depenses"] else "")
    style.hero(f"Dépenses {de_mois}", fmt(m["depenses"], base, 0), variation,
               pied,
               [(style.VERT, "Revenus", fmt(m["revenus"], base, 0)),
                (style.BLEU, "Épargne", fmt(m["epargne"], base, 0)),
                (style.VIOLET, "Taux d'épargne", fmt_pct(m["taux"], signe=False, dec=2)),
                (style.GRIS, "Virements entre vos comptes (hors budget)", fmt(m["virements"], base, 0))])

    # Le chemin de l'argent ce mois-là
    with style.verre("flux_mois_dernier"):
        st.markdown(f"**Le chemin de mon argent en {libelle_mois(mois).lower()}**")
        sources, branches = flux_reel(mvts, groupe_de, mois)
        fig = _sankey(sources, branches, base)
        if fig is not None:
            st.plotly_chart(fig, config={"displayModeBar": False}, key="sankey_mois_dernier")
        style.note("Ce qui n'a pas été dépensé apparaît en « Reste du mois » (épargne).")

    g, d = st.columns([3, 2])
    with g, style.verre("suivi_mois_dernier"):
        st.markdown("**Dépensé par rapport au plan, catégorie par catégorie**")
        suivi = calculs.suivi_plan(plan, mvts, mois)
        lignes = suivi[(suivi["prevu"] > 0) | (suivi["depense"] > 0)].sort_values("depense", ascending=False)
        colonnes = st.columns(2)
        for i, r in enumerate(lignes.itertuples(index=False)):
            colonnes[i % 2].markdown(style.ligne_budget(r.categorie, r.depense, r.prevu, base), unsafe_allow_html=True)
        depasses = lignes[(lignes["prevu"] > 0) & (lignes["depense"] > lignes["prevu"])]
        if not depasses.empty:
            style.note("Au-dessus du budget : " + ", ".join(
                f"{r.categorie} (+{fmt(r.depense - r.prevu, base, 0)})" for r in depasses.itertuples(index=False)))
    with d, style.verre("groupes_mois_dernier"):
        groupes = db.lister_groupes()
        st.markdown("**Par groupe de dépenses**")
        if m["revenus"] > 0:
            reel = {gr: 0.0 for gr in groupes}
            for c, montant in m["par_categorie"].items():
                gr = groupe_categorie(c, groupe_de)
                reel[gr if gr in reel else db.groupe_par_defaut()] += float(montant)
            reel[db.GROUPE_EPARGNE] += max(m["epargne"], 0.0)
            prevu_gr = plan.groupby("groupe")["montant"].sum().reindex(groupes).fillna(0)
            revenu_plan = float(db.lire_parametre("revenu_prevu") or 0) or m["revenus"]
            barres_groupes({g: reel[g] / m["revenus"] * 100 for g in groupes}, "groupes_mois_dernier",
                           {g: float(v) / revenu_plan * 100 for g, v in prevu_gr.items()} if prevu_gr.sum() > 0 else None,
                           nom="Réel")
            style.note("En % des revenus du mois. L'épargne inclut ce qui n'a pas été dépensé.")
        else:
            style.note("Aucun revenu enregistré ce mois-là : impossible de calculer les proportions.")

    with style.verre("top_depenses_mois_dernier"):
        st.markdown("**Plus grosses dépenses du mois**")
        ops = m["operations"]
        top = ops[ops["type"] == "DEPENSE"].sort_values("montant", ascending=False).head(10)
        st.dataframe(top[["date", "categorie", "description", "montant"]], hide_index=True, column_config={
            "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"), "categorie": "Catégorie",
            "description": "Libellé", "montant": st.column_config.NumberColumn(f"Montant ({base})", format="%.2f")})


# ============================================================ TENDANCES
def onglet_tendances(mvts: pd.DataFrame, base: str) -> None:
    c1, c2 = st.columns([3, 1], vertical_alignment="center")
    nb = {"6 mois": 6, "12 mois": 12, "24 mois": 24}
    choix = c2.segmented_control("Période", list(nb), default="12 mois", label_visibility="collapsed",
                                 key="periode_tendances") or "12 mois"
    piv = calculs.depenses_mois_categorie(mvts, nb[choix])
    if piv.empty or piv.shape[1] == 0 or piv.values.sum() == 0:
        st.info("Aucune dépense sur cette période. Saisissez vos dépenses dans **Mouvements**, "
                "ou importez un relevé bancaire en CSV.")
        return

    total = piv.sum(axis=1)
    complets = total.iloc[:-1]
    moyenne = float(complets.mean()) if len(complets) else float(total.mean())
    dernier = float(complets.iloc[-1]) if len(complets) else 0.0
    tendance = calculs.tendance_globale(piv)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ce mois-ci (en cours)", fmt(total.iloc[-1], base, 0))
    m2.metric("Dernier mois complet", fmt(dernier, base, 0),
              fmt_pct((dernier / moyenne - 1) * 100 if moyenne else None) + " vs moyenne" if moyenne else None,
              delta_color="inverse")
    m3.metric("Moyenne mensuelle", fmt(moyenne, base, 0))
    libelle = "–" if tendance is None else ("En hausse" if tendance > 3 else ("En baisse" if tendance < -3 else "Stable"))
    m4.metric("Tendance sur 3 mois", libelle, fmt_pct(tendance) if tendance is not None else None,
              delta_color="inverse", help="3 derniers mois complets comparés aux 3 précédents.")

    with style.verre("depenses_par_mois"):
        st.markdown("**Dépenses par mois et par catégorie**")
        principales = list(piv.columns[:8])
        affiche = piv[principales].copy()
        if piv.shape[1] > 8:
            affiche["Autres"] = piv[piv.columns[8:]].sum(axis=1)
        fig = go.Figure()
        for i, c in enumerate(affiche.columns):
            fig.add_bar(x=affiche.index, y=affiche[c], name=c, marker_color=style.PALETTE[i % len(style.PALETTE)])
        fig.add_scatter(x=total.index, y=total.rolling(3, min_periods=1).mean(), name="Moyenne sur 3 mois",
                        mode="lines", line=dict(color=style.TEXTE, width=2, shape="spline"))
        st.plotly_chart(style.graphique(fig, 380).update_layout(barmode="stack", bargap=0.35),
                        config={"displayModeBar": False}, key="graphe_dep_mois")

    g, d = st.columns(2)
    with g, style.verre("ou_va_argent"):
        st.markdown(f"**Où va votre argent ({choix})**")
        cumul = piv.sum().sort_values(ascending=False)
        cumul = cumul[cumul > 0]
        fig = go.Figure(go.Treemap(
            labels=cumul.index, parents=[""] * len(cumul), values=cumul.values,
            marker=dict(colors=[style.PALETTE[i % len(style.PALETTE)] for i in range(len(cumul))],
                        cornerradius=12, line=dict(color=style.PANNEAU, width=3)),
            texttemplate="<b>%{label}</b><br>%{value:,.0f}<br>%{percentRoot:.2%}",
            hovertemplate="%{label} : %{value:,.0f}<extra></extra>"))
        st.plotly_chart(style.graphique(fig, 340, legende=False).update_layout(margin=dict(l=0, r=0, t=0, b=0)),
                        config={"displayModeBar": False}, key="graphe_treemap")

    with d, style.verre("evolution_categorie"):
        st.markdown("**Évolution d'une catégorie**")
        cat = st.selectbox("Catégorie", list(piv.columns), label_visibility="collapsed", key="cat_evolution")
        serie = piv[cat]
        moy_cat = float(serie.iloc[:-1].mean()) if len(serie) > 1 else float(serie.mean())
        fig = go.Figure()
        fig.add_bar(x=serie.index, y=serie.values, name=cat, marker_color=style.BLEU)
        fig.add_hline(y=moy_cat, line=dict(color=style.ORANGE, dash="dot", width=1.5))
        st.plotly_chart(style.graphique(fig, 290, legende=False), config={"displayModeBar": False},
                        key="graphe_evol_cat")
        style.note(f"Ligne orange : moyenne de {fmt(moy_cat, base, 0)} par mois (mois complets).")

    with style.verre("tableau_tendances"):
        st.markdown("**Tendance par catégorie**")
        t = calculs.tendances_categories(piv)
        st.dataframe(
            t[["categorie", "historique", "moyenne", "dernier_mois", "ecart_pct", "mois_en_cours", "tendance"]],
            hide_index=True, column_config={
                "categorie": "Catégorie",
                "historique": st.column_config.LineChartColumn("Évolution", y_min=0),
                "moyenne": st.column_config.NumberColumn("Moyenne / mois", format="%.0f"),
                "dernier_mois": st.column_config.NumberColumn("Dernier mois", format="%.0f"),
                "ecart_pct": st.column_config.NumberColumn("Écart à la moyenne", format="%+.2f %%"),
                "mois_en_cours": st.column_config.NumberColumn("Mois en cours", format="%.0f"),
                "tendance": "Tendance",
            })
        style.note("La tendance compare la pente des mois complets à la moyenne : au-delà de 3 % par mois, "
                   "la catégorie est considérée en hausse ou en baisse.")

    with style.verre("revenus_depenses"):
        st.markdown("**Revenus, dépenses et épargne**")
        synthese = calculs.synthese_mensuelle(mvts)
        synthese = synthese[synthese["mois"].isin(piv.index)]
        fig = go.Figure()
        fig.add_bar(x=synthese["mois"], y=synthese["revenus"], name="Revenus", marker_color=style.VERT)
        fig.add_bar(x=synthese["mois"], y=synthese["depenses"], name="Dépenses", marker_color=style.ORANGE)
        fig.add_scatter(x=synthese["mois"], y=synthese["epargne"], name="Épargne", mode="lines+markers",
                        line=dict(color=style.BLEU, width=2.5, shape="spline"))
        st.plotly_chart(style.graphique(fig, 320).update_layout(barmode="group"),
                        config={"displayModeBar": False}, key="graphe_rev_dep")


# ===================================================== IMPORT DE RELEVÉS
def _classer(idx: int, categorie: str | None, importer: bool, similaires: list[int], suivant: int) -> None:
    """Enregistre le choix de la fenêtre de classement puis passe à l'opération suivante."""
    etat = st.session_state["classement"]
    for j in [idx] + similaires:
        etat["choix"][j] = (categorie, importer)
    etat["i"] = suivant


def _aller(position: int) -> None:
    st.session_state["classement"]["i"] = position


def _fermer_classement() -> None:
    etat = st.session_state["classement"]
    etat["ouvert"] = False
    etat["version"] += 1  # le tableau d'aperçu reprend les choix de la fenêtre


@st.dialog("Classer les opérations du relevé", width="large", on_dismiss=_fermer_classement)
def _fenetre_classement(ops: pd.DataFrame, a_classer: list[int], proposees: list[str],
                        cat_dep: list[str], cat_rev: list[str], base: str) -> None:
    etat = st.session_state["classement"]
    seulement = st.toggle("Seulement les opérations non reconnues (« Autre ») et les virements à vérifier",
                          key="classement_inconnues", value=etat["seulement_inconnues"])
    etat["seulement_inconnues"] = seulement
    liste = [i for i in a_classer
             if not seulement or proposees[i] in ("Autre", "Autres", "Divers") or ops.at[i, "interne"]]
    if not liste:
        st.success("Toutes les opérations sont reconnues.")
        if st.button("Terminer", type="primary", on_click=_fermer_classement, width="stretch"):
            st.rerun()
        return
    pos = min(etat["i"], len(liste) - 1)
    idx = liste[pos]
    op = ops.loc[idx]
    montant = float(op["montant"])
    revenu = montant > 0
    st.progress((pos + 1) / len(liste), text=f"Opération {pos + 1} sur {len(liste)}")

    couleur = style.VERT_TEXTE if revenu else style.TEXTE
    st.markdown(
        f'<div class="enveloppe"><div class="enveloppe-nom">{op["date"]:%d/%m/%Y} · '
        f'{"Revenu" if revenu else "Dépense"}</div>'
        f'<div class="enveloppe-valeur" style="color:{couleur} !important">{"+" if revenu else "−"}'
        f'{fmt(abs(montant), base)}</div>'
        f'<div style="font-size:0.95rem">{html.escape(str(op["libelle"]))}</div></div>', unsafe_allow_html=True)
    if ops.at[idx, "interne"]:
        st.info("Ce virement semble aller d'un de vos comptes à un autre : il est proposé comme « Virement entre "
                "mes comptes » (hors budget). Choisissez une autre catégorie s'il s'agit en réalité d'une dépense "
                "ou d'un revenu.")

    categories = (cat_rev if revenu else cat_dep) + [CAT_VIREMENT]
    actuelle = etat["choix"].get(idx, (proposees[idx], True))[0]
    st.caption(f"Catégorie proposée : {proposees[idx]}" + (" (règle apprise ou mot-clé reconnu)"
                                                         if proposees[idx] not in ("Autre", "Autres") else ""))
    choix = st.pills("Ce que c'est", categories, default=actuelle if actuelle in categories else None,
                     key=f"classement_choix_{idx}")
    autres = [c for c in dict.fromkeys(cat_dep + cat_rev) if c not in categories]
    if choix == CAT_VIREMENT:
        st.caption("Virement entre vos comptes : enregistré, mais exclu des dépenses, des revenus et du budget.")
    with st.expander("Une catégorie de l'autre type" + (" (dépenses)" if revenu else " (revenus)")):
        hors = st.selectbox("Catégorie", ["—"] + autres, key=f"classement_hors_{idx}", label_visibility="collapsed")
    if hors and hors != "—":
        choix = hors

    cle = releves.cle_libelle(op["libelle"])
    similaires = [j for j in a_classer if j != idx and cle and releves.cle_libelle(ops.at[j, "libelle"]) == cle
                  and (ops.at[j, "montant"] > 0) == revenu]
    appliquer = False
    if similaires:
        appliquer = st.checkbox(f"Appliquer aussi aux {len(similaires)} autre(s) opération(s) du même commerçant "
                                f"(« {cle} »)", value=True, key=f"classement_similaires_{idx}")
    # Opération suivante : on saute celles déjà classées (dont les « similaires » classées d'un coup).
    deja_vues = set(etat["choix"]) | (set(similaires) if appliquer else set())
    suivant = next((j for j in range(pos + 1, len(liste)) if liste[j] not in deja_vues), len(liste))
    fin = suivant >= len(liste)
    c1, c2, c3, c4 = st.columns(4)
    c1.button("← Précédent", disabled=pos == 0, on_click=_aller, args=(pos - 1,), width="stretch")
    c2.button("Ne pas importer", on_click=_classer, width="stretch",
              args=(idx, actuelle, False, similaires if appliquer else [], suivant))
    if c3.button("Terminer plus tard", on_click=_fermer_classement, width="stretch"):
        st.rerun()
    if c4.button("Valider ✓" if fin else "Valider →", type="primary", disabled=not choix, width="stretch",
                 on_click=_classer, args=(idx, choix, True, similaires if appliquer else [], suivant)):
        if fin:
            _fermer_classement()
            st.rerun()
    style.note("Vos choix sont retenus : la prochaine fois, ces commerçants seront classés automatiquement.")


def import_releve(mvts: pd.DataFrame, base: str) -> None:
    """Lecture d'un relevé bancaire, aperçu modifiable (catégories proposées), puis import."""
    version = st.session_state.get("version_import_releve", 0)
    with style.verre("import_releve"):
        st.markdown("**Importer un relevé bancaire**")
        formats = ", ".join(f.upper() for f in releves.FORMATS if f != "txt")
        style.note(f"Formats acceptés : {formats}. Exportez le relevé depuis votre espace bancaire en ligne "
                   "(rubrique « Exporter » ou « Télécharger les opérations »). Les catégories sont proposées "
                   "automatiquement et l'application retient vos corrections pour les prochains imports.")
        fichier = st.file_uploader("Relevé", type=releves.FORMATS + (["pdf"] if "pdf" not in releves.FORMATS else []),
                                   key=f"fichier_releve_{version}", label_visibility="collapsed")
        if fichier is None:
            return
        try:
            ops, detail = releves.lire_releve(fichier.name, fichier.getvalue())
        except Exception as e:
            st.error(f"Lecture impossible : {e}")
            return
        if ops.empty:
            st.warning("Aucune opération reconnue dans ce fichier. Vérifiez qu'il contient bien une date, un "
                       "libellé et un montant (ou des colonnes Débit / Crédit) pour chaque opération.")
            return

        titulaire = ops.attrs.get("titulaire", "")
        cat_dep = [c.strip() for c in db.lire_parametre("categories").split(",") if c.strip()]
        cat_rev = [c.strip() for c in db.lire_parametre("categories_revenus").split(",") if c.strip()]
        regles = db.lire_regles_budget()
        ops["type"] = ops["montant"].map(lambda m: "Revenu" if m > 0 else "Dépense")
        ops["categorie"] = [releves.categoriser(l, m, regles, cat_dep, cat_rev)
                            for l, m in zip(ops["libelle"], ops["montant"])]
        existants = set()
        if not mvts.empty:
            existants = {(d.strftime("%Y-%m-%d"), t, round(float(m), 2), releves.cle_libelle(desc))
                         for d, t, m, desc in zip(mvts["date"], mvts["type"], mvts["montant"],
                                                  mvts["description"].fillna(""))}
        # Virements entre vos propres comptes : importés comme « virements » (hors budget).
        ops["interne"] = [c == CAT_VIREMENT or releves.virement_interne(l, titulaire)
                          for l, c in zip(ops["libelle"], ops["categorie"])]
        ops.loc[ops["interne"], "categorie"] = CAT_VIREMENT
        ops["deja"] = [any((d.strftime("%Y-%m-%d"), t, round(abs(m), 2), releves.cle_libelle(l)) in existants
                           for t in ("VIREMENT", "REVENU" if m > 0 else "DEPENSE"))
                       for d, m, l in zip(ops["date"], ops["montant"], ops["libelle"])]
        ops["importer"] = ~ops["deja"]
        ops["statut"] = ["Déjà importé" if d else ("Virement détecté" if i else "")
                         for d, i in zip(ops["deja"], ops["interne"])]
        proposees = ops["categorie"].tolist()

        # Fenêtre de classement ligne par ligne : ouverte d'office à la lecture d'un nouveau relevé.
        etat = st.session_state.get("classement")
        if not etat or etat.get("fichier") != fichier.file_id:
            etat = {"fichier": fichier.file_id, "i": 0, "choix": {}, "ouvert": True, "version": 0,
                    "seulement_inconnues": False}
            st.session_state["classement"] = etat
        for i, (cat, importer) in etat["choix"].items():
            if i in ops.index:
                ops.at[i, "categorie"], ops.at[i, "importer"] = cat, importer
        ops["type"] = [type_affiche(c, m) for c, m in zip(ops["categorie"], ops["montant"])]
        a_classer = [i for i in ops.index if not ops.at[i, "deja"]]
        b1, b2 = st.columns([1, 3], vertical_alignment="center")
        if b1.button("Classer ligne par ligne", key="ouvrir_classement", width="stretch"):
            etat["ouvert"] = True
        faites = sum(1 for i in a_classer if i in etat["choix"])
        b2.caption(f"{faites} / {len(a_classer)} opérations classées dans la fenêtre de classement. "
                   "Vous pouvez aussi corriger directement dans le tableau ci-dessous.")
        if etat["ouvert"] and a_classer:
            _fenetre_classement(ops, a_classer, proposees, cat_dep, cat_rev, base)

        debut, fin = ops["date"].min(), ops["date"].max()
        st.success(f"{len(ops)} opérations lues du {debut:%d/%m/%Y} au {fin:%d/%m/%Y} · format : {detail}"
                   + (f" · {int(ops['deja'].sum())} déjà présentes (décochées)" if ops["deja"].any() else "")
                   + (f" · {int(ops['interne'].sum())} virement(s) entre vos comptes détecté(s), importés hors "
                      "budget" if ops["interne"].any() else ""))
        edite = st.data_editor(
            ops[["importer", "date", "libelle", "montant", "type", "categorie", "statut"]],
            hide_index=True, key=f"apercu_releve_{version}_{fichier.file_id}_{etat['version']}",
            disabled=["date", "montant", "type", "statut"], height=min(38 + 35 * len(ops), 520),
            column_config={
                "importer": st.column_config.CheckboxColumn("Importer", width="small"),
                "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                "libelle": st.column_config.TextColumn("Libellé", width="large"),
                "montant": st.column_config.NumberColumn(f"Montant ({base})", format="%+.2f"),
                "type": "Type",
                "categorie": st.column_config.SelectboxColumn(
                    "Catégorie", options=list(dict.fromkeys(cat_dep + cat_rev + [CAT_VIREMENT])), required=True,
                    help=f"« {CAT_VIREMENT} » : argent passé d'un de vos comptes à un autre, hors budget."),
                "statut": "",
            })
        choisies = edite[edite["importer"]]
        virements = choisies["categorie"] == CAT_VIREMENT
        budget = choisies[~virements]
        depenses = float(-budget.loc[budget["montant"] < 0, "montant"].sum())
        revenus = float(budget.loc[budget["montant"] > 0, "montant"].sum())
        c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1.4], vertical_alignment="bottom")
        c1.metric("Dépenses", fmt(depenses, base, 0))
        c2.metric("Revenus", fmt(revenus, base, 0))
        c3.metric("Solde", fmt(revenus - depenses, base, 0))
        c4.metric("Virements", fmt(float(choisies.loc[virements, "montant"].abs().sum()), base, 0),
                  help="Entre vos comptes : hors budget, ni dépense ni revenu.")
        if c5.button(f"Importer {len(choisies)} opération(s)", type="primary", disabled=choisies.empty,
                     width="stretch", key="btn_import_releve"):
            lignes, appris = [], 0
            for i, r in choisies.iterrows():
                sens = "REVENU" if r["montant"] > 0 else "DEPENSE"
                type_ = "VIREMENT" if r["categorie"] == CAT_VIREMENT else sens
                lignes.append((r["date"], type_, r["categorie"], r["montant"], r["libelle"]))
                if r["categorie"] != proposees[i]:  # correction : on la retient pour la prochaine fois
                    db.apprendre_regle_budget(sens, releves.cle_libelle(r["libelle"]), r["categorie"])
                    appris += 1
            n = db.ajouter_mouvements(lignes)
            st.session_state["version_import_releve"] = version + 1
            st.toast(f"{n} opération(s) importée(s)" + (f", {appris} correction(s) mémorisée(s)." if appris else "."))
            st.rerun()


# ============================================================ MOUVEMENTS
def onglet_mouvements(mvts: pd.DataFrame, base: str) -> None:
    import_releve(mvts, base)
    with style.verre("saisie_mouvement"):
        st.markdown("**Nouveau mouvement**")
        formulaire_mouvement("mouvements", base)

    if mvts.empty:
        st.caption("Aucun mouvement pour l'instant.")
    else:
        with style.verre("liste_mouvements"):
            c1, c2 = st.columns([3, 1], vertical_alignment="center")
            c1.markdown("**Historique**")
            annees = sorted(mvts["date"].dt.year.unique(), reverse=True)
            annee = c2.selectbox("Année", annees, label_visibility="collapsed")
            sel = mvts[mvts["date"].dt.year == annee]
            st.dataframe(sel.assign(type=sel["type"].map(TYPES_MOUVEMENT).fillna(sel["type"])),
                         hide_index=True, column_config={
                "id": None, "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                "type": "Type", "categorie": "Catégorie",
                "montant": st.column_config.NumberColumn(f"Montant ({base})", format="%.2f"),
                "description": "Description"})
            with st.expander("Supprimer des mouvements"):
                ids = st.multiselect("Mouvements à supprimer", sel["id"].tolist(),
                                     format_func=lambda i: "{:%d/%m/%Y} : {} {:.2f}".format(
                                         *sel.loc[sel["id"] == i, ["date", "categorie", "montant"]].iloc[0]))
                if st.button("Supprimer la sélection", disabled=not ids, key="suppr_budget"):
                    db.supprimer_mouvements(ids)
                    st.rerun()

    with style.verre("import_budget"):
        st.markdown("**Import et export**")
        c1, c2 = st.columns(2)
        if not mvts.empty:
            c1.download_button("Exporter en CSV", mvts.drop(columns=["id"]).to_csv(index=False).encode("utf-8"),
                               "budget.csv", "text/csv")
        fichier = c2.file_uploader("Importer un CSV", type="csv", key="import_budget",
                                   help="Colonnes : date, type (DEPENSE/REVENU), categorie, montant, description")
        if fichier is not None and c2.button("Importer ce fichier", key="btn_import_budget"):
            try:
                n = db.importer_budget_csv(pd.read_csv(fichier, sep=None, engine="python"))
                st.success(f"{n} mouvements importés.")
                st.rerun()
            except Exception as e:
                st.error(f"Import impossible : {e}")
