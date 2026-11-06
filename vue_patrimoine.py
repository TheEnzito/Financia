"""Page « Mon patrimoine » : vue d'ensemble, projections et gestion des comptes."""

from __future__ import annotations

import html
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculs
import db
import donnees
import style
import vue_bourse
from style import fmt, fmt_pct, fmt_signe

PERIODES = {"1 h": pd.Timedelta(hours=1), "1 j": pd.Timedelta(days=1),
            "1 sem.": pd.Timedelta(weeks=1), "2 sem.": pd.Timedelta(weeks=2),
            "1 mois": pd.DateOffset(months=1), "3 mois": pd.DateOffset(months=3),
            "4 mois": pd.DateOffset(months=4), "6 mois": pd.DateOffset(months=6),
            "1 an": pd.DateOffset(years=1), "2 ans": pd.DateOffset(years=2),
            "3 ans": pd.DateOffset(years=3), "5 ans": pd.DateOffset(years=5), "Tout": None}
# Périodes courtes : cours intra-journée (période Yahoo, intervalle Yahoo, pas de la courbe).
INTRADAY = {"1 h": ("5d", "1m", "1min"), "1 j": ("5d", "5m", "5min"),
            "1 sem.": ("1mo", "30m", "30min"), "2 sem.": ("1mo", "1h", "1h")}
FORMAT_DATES = {"1 h": "%H:%M", "1 j": "%H:%M", "1 sem.": "%d/%m %Hh", "2 sem.": "%d/%m",
                "1 mois": "%d/%m", "3 mois": "%d/%m", "4 mois": "%d/%m"}


def serie_periode(choix: str, p: dict | None, pat: dict) -> tuple[pd.Series, pd.Timestamp]:
    """Série du patrimoine sur la période choisie et début théorique de la période."""
    hist = pat["hist"]
    maintenant = pd.Timestamp.now()
    decalage = PERIODES[choix]
    if choix in INTRADAY:
        periode, intervalle, pas = INTRADAY[choix]
        serie = donnees.patrimoine_intraday(p, pat, decalage, periode, intervalle, pas)
        return serie, maintenant - decalage
    serie = hist["total"].copy()
    serie.index = serie.index[:-1].append(pd.DatetimeIndex([maintenant]))  # dernier point = maintenant
    if decalage is None:
        return serie, serie.index[0]
    debut = maintenant.normalize() - decalage
    return serie[serie.index >= debut], debut


def page() -> None:
    p = donnees.charger_portefeuille()
    pat = donnees.charger_patrimoine(p)
    base = donnees.devise_base()
    st.title("Mon patrimoine")
    donnees.avertir_introuvables(p)
    vue, auto, proj, comptes = st.tabs(["Vue d'ensemble", "Projection automatique", "Projection personnalisée",
                                        "Mes comptes"])
    with vue:
        vue_ensemble(p, pat, base)
    with auto:
        projection_automatique(p, pat, base)
    with proj:
        projections(p, pat, base)
    with comptes:
        gestion_comptes(pat, base)


# ===================================================================== VUE
def vue_ensemble(p: dict | None, pat: dict, base: str) -> None:
    hist = pat["hist"]
    if hist.empty:
        style.hero("Patrimoine net", fmt(0, base), style.pilule("Aucun actif enregistré", None))
        st.info("Ajoutez vos comptes (épargne, compte courant, immobilier…) dans l'onglet **Mes comptes**, "
                "et vos achats d'actions dans **Transactions**. Votre patrimoine se calculera tout seul, "
                "avec les cours de bourse en direct.")
        return

    total = float(hist["total"].iloc[-1])
    veille = float(hist["total"].iloc[-2]) if len(hist) > 1 else total
    variation = total - veille
    composition = hist.drop(columns="total").iloc[-1]
    composition = composition[composition.abs() > 0.005].sort_values(ascending=False)
    puces = [(style.couleur_patrimoine(c), c, fmt(v, base, 0)) for c, v in composition.items()]
    style.hero("Patrimoine net", fmt(total, base),
               style.pilule(f"{fmt_signe(variation, base, 0)} ({fmt_pct(variation / abs(veille) * 100 if veille else None)})",
                            variation),
               "depuis hier", puces)

    # Courbe façon cours de bourse
    with style.verre("courbe_patrimoine"):
        g, d = st.columns([3, 2], vertical_alignment="center")
        g.markdown("**Évolution**")
        choix = d.segmented_control("Période", list(PERIODES), default="1 an",
                                    label_visibility="collapsed", key="periode_patrimoine") or "1 an"
        with st.spinner("Chargement des cours…"):
            serie, debut = serie_periode(choix, p, pat)
        if len(serie) == 1:  # une seule valeur : on trace un palier sur la période
            serie = pd.Series([serie.iloc[0]] * 2, index=pd.DatetimeIndex([debut, serie.index[0]]))
        ecart = float(serie.iloc[-1] - serie.iloc[0])
        pct = ecart / abs(serie.iloc[0]) * 100 if serie.iloc[0] else None
        precision = 2 if choix in ("1 h", "1 j") else 0
        complement = ""
        if serie.index[0] > debut + pd.Timedelta(days=1):
            complement = f" · historique disponible depuis le {serie.index[0]:%d/%m/%Y}"
        g.markdown(f"{style.pilule(f'{fmt_signe(ecart, base, precision)} ({fmt_pct(pct)})', ecart)}"
                   f' <span class="note">{"depuis le début" if choix == "Tout" else "sur " + choix}'
                   f'{complement}</span>', unsafe_allow_html=True)
        fig = style.courbe_cours(serie.index, serie.values, "Patrimoine", ecart >= 0, 340)
        fig.update_xaxes(range=[min(debut, serie.index[0]), serie.index[-1]],
                         tickformat=FORMAT_DATES.get(choix, "%m/%Y"),
                         hoverformat="%d/%m/%Y %H:%M" if choix in INTRADAY else "%d/%m/%Y")
        st.plotly_chart(fig, config={"displayModeBar": False}, key="graphe_patrimoine")
        c1, c2, c3 = st.columns(3)
        c1.metric("Plus haut", fmt(serie.max(), base, 0))
        c2.metric("Plus bas", fmt(serie.min(), base, 0))
        c3.metric("Moyenne", fmt(serie.mean(), base, 0))
        style.note("La courbe inclut l'argent que vous ajoutez : elle montre l'évolution de votre richesse, "
                   "pas seulement la performance de vos placements (voir Portefeuille pour celle-ci).")

    # Composition
    g, d = st.columns([3, 2])
    with g, style.verre("composition_temps"):
        st.markdown("**Composition dans le temps**")
        actifs = [c for c in hist.columns if c not in ("total", "Dettes")]
        fig = go.Figure()
        for c in actifs:
            couleur = style.couleur_patrimoine(c)
            fig.add_scatter(x=hist.index, y=hist[c], name=c, stackgroup="actifs", mode="lines",
                            line=dict(width=0.6, color=couleur), fillcolor=style.rgba(couleur, 0.45))
        if "Dettes" in hist.columns:
            fig.add_scatter(x=hist.index, y=hist["Dettes"], name="Dettes", mode="lines",
                            line=dict(color=style.ROUGE, width=1.5, dash="dot"))
        fig.add_scatter(x=hist.index, y=hist["total"], name="Patrimoine net", mode="lines",
                        line=dict(color=style.TEXTE, width=1.8))
        st.plotly_chart(style.graphique(fig, 330), config={"displayModeBar": False}, key="graphe_compo_temps")
    with d, style.verre("repartition"):
        st.markdown("**Répartition actuelle**")
        positifs = composition[composition > 0]
        fig = go.Figure(go.Pie(labels=positifs.index, values=positifs.values, hole=0.66, sort=False,
                               marker=dict(colors=[style.couleur_patrimoine(c) for c in positifs.index],
                                           line=dict(color=style.PANNEAU, width=3)),
                               texttemplate="%{percent:.2%}",
                               hovertemplate="%{label}<br>%{value:,.0f} · %{percent:.2%}<extra></extra>"))
        fig.add_annotation(text=f"<b>{fmt(positifs.sum(), base, 0)}</b><br><span style='font-size:11px'>d'actifs</span>",
                           showarrow=False, font=dict(size=15))
        st.plotly_chart(style.graphique(fig, 330, legende=True).update_layout(hovermode=False),
                        config={"displayModeBar": False}, key="graphe_repartition")

    if p or db.especes_actuelles():
        with style.verre("mes_actions"):
            st.markdown("**Mes portefeuilles (PEA, CTO…)**")
            vue_bourse.camemberts_portefeuilles(p, "graphe_portefeuilles_patrimoine")

    projection_revenus(p, pat, base)

    # Revenus des placements
    with style.verre("revenus_placements"):
        st.markdown("**Revenus de vos placements**")
        journal = p["journal"] if p else pd.DataFrame(columns=["date", "nature", "montant_base"])
        un_an = pd.Timestamp.today() - pd.DateOffset(years=1)
        recent = journal[journal["date"] >= un_an] if not journal.empty else journal
        div_12 = float(recent.loc[recent["nature"] == "Dividendes", "montant_base"].sum()) if not recent.empty else 0.0
        pv_12 = float(recent.loc[recent["nature"] == "Plus-values réalisées", "montant_base"].sum()) if not recent.empty else 0.0
        attendus = p["dividendes_attendus"] if p else 0.0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Dividendes reçus (12 mois)", fmt(div_12, base, 0))
        c2.metric("Plus-values réalisées (12 mois)", fmt(pv_12, base, 0))
        c3.metric("Dividendes attendus (12 mois)", fmt(attendus, base, 0),
                  help="Estimation en direct : dividende annuel annoncé de chaque titre (Yahoo Finance) "
                       "× nombre de titres détenus. Les ETF capitalisants ne versent rien.")
        c4.metric("Revenu passif mensuel estimé", fmt(attendus / 12, base, 0))
        mensuel = calculs.revenus_mensuels(journal, 24)
        if mensuel.values.sum() != 0:
            fig = go.Figure()
            fig.add_bar(x=mensuel.index, y=mensuel["Dividendes"], name="Dividendes", marker_color=style.VERT)
            fig.add_bar(x=mensuel.index, y=mensuel["Plus-values réalisées"], name="Plus-values réalisées",
                        marker_color=style.BLEU)
            st.plotly_chart(style.graphique(fig, 260).update_layout(barmode="relative"),
                            config={"displayModeBar": False}, key="graphe_revenus")
        else:
            style.note("Aucun dividende ni vente enregistré pour l'instant.")

    # Ce mois-ci
    mvts = db.lister_budget()
    synthese = calculs.synthese_mensuelle(mvts)
    ligne = synthese[synthese["mois"] == pd.Timestamp.today().strftime("%Y-%m")]
    if not ligne.empty:
        r = ligne.iloc[0]
        st.markdown("#### Ce mois-ci")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Revenus", fmt(r["revenus"], base, 0))
        c2.metric("Dépenses", fmt(r["depenses"], base, 0))
        c3.metric("Épargne", fmt(r["epargne"], base, 0))
        c4.metric("Taux d'épargne", fmt_pct(r["taux_epargne_pct"], signe=False, dec=2))


# ======================================= PROJECTION DIVIDENDES + INTÉRÊTS
def projection_revenus(p: dict | None, pat: dict, base: str) -> None:
    """Patrimoine projeté avec les seuls revenus « connus » : dividendes annoncés de vos titres
    et intérêts de vos comptes rémunérés (livrets…). Hausse des cours en option, nulle par défaut."""
    hist, actuels = pat["hist"], pat["actuels"]
    total0 = float(hist["total"].iloc[-1])
    bourse0 = float(pat["valeur_bourse"])
    attendus = float(p["dividendes_attendus"]) if p else 0.0
    rendement = attendus / bourse0 if bourse0 > 0 else 0.0
    remuneres = actuels[(actuels["categorie"] != "Dettes") & (actuels["taux_annuel"] > 0)
                        & (actuels["solde"] > 0)] if not actuels.empty else actuels
    comptes = [(r.nom, float(r.solde), float(r.taux_annuel)) for r in remuneres.itertuples(index=False)]
    interets0 = sum(s * t / 100 for _, s, t in comptes)
    autres = total0 - bourse0 - sum(s for _, s, _ in comptes)

    with style.verre("projection_revenus"):
        st.markdown("**Projection : dividendes et intérêts**")
        c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1], vertical_alignment="bottom")
        horizons = {"5 ans": 5, "10 ans": 10, "15 ans": 15, "20 ans": 20, "30 ans": 30}
        horizon = c1.segmented_control("Horizon", list(horizons), default="10 ans", key="horizon_revenus") or "10 ans"
        annees = horizons[horizon]
        reinvestir = c2.toggle("Dividendes réinvestis", value=True, key="reinvestir_revenus",
                               help="Sinon, ils s'accumulent en liquidités sans rapporter.")
        versement = c3.number_input(f"Versement mensuel en bourse ({base})", min_value=0.0, value=0.0, step=50.0,
                                    key="versement_revenus")
        hausse = c4.number_input("Hausse des cours (%/an)", -10.0, 15.0, 0.0, 0.5, key="hausse_revenus",
                                 help="0 % = scénario « sûr » : seuls les dividendes et les intérêts comptent.")

        proj = calculs.projeter_revenus(bourse0, rendement, comptes, autres, annees, reinvestir,
                                        hausse / 100, versement)
        fin = proj.iloc[-1]
        style.hero(f"Patrimoine estimé dans {annees} ans", fmt(fin["total"], base, 0),
                   style.pilule(f"{fmt_signe(fin['total'] - total0, base, 0)} par rapport à aujourd'hui",
                                fin["total"] - total0),
                   "sans hausse des cours" if hausse == 0 else f"avec {fmt_pct(hausse)} de hausse des cours par an",
                   [(style.ORANGE, "Dividendes cumulés", fmt(fin["dividendes_cumules"], base, 0)),
                    (style.VERT, "Intérêts cumulés", fmt(fin["interets_cumules"], base, 0)),
                    (style.BLEU, "Revenu passif aujourd'hui", f"{fmt((attendus + interets0) / 12, base, 0)} / mois"),
                    (style.VIOLET, f"Revenu passif dans {annees} ans", f"{fmt(fin['revenu_annuel'] / 12, base, 0)} / mois")])

        # Courbe : historique récent puis patrimoine projeté, décomposé en couches empilées.
        socle = total0 + proj["verse_cumule"]
        cours = (proj["total"] - socle - proj["interets_cumules"] - proj["dividendes_cumules"]).clip(lower=0)
        fig = go.Figure()
        passe = hist["total"][hist.index >= hist.index[-1] - pd.DateOffset(years=1)]
        fig.add_scatter(x=passe.index, y=passe.values, name="Historique", mode="lines",
                        line=dict(color=style.TEXTE, width=2))
        couches = [("Patrimoine actuel" + (" + versements" if versement else ""), socle, style.GRIS),
                   ("Intérêts (livrets…)", proj["interets_cumules"], style.VERT),
                   ("Dividendes", proj["dividendes_cumules"], style.ORANGE)]
        if hausse:
            couches.append(("Hausse des cours", cours, style.BLEU))
        for nom, y, couleur in couches:
            fig.add_scatter(x=proj.index, y=y, name=nom, mode="lines", stackgroup="projection",
                            line=dict(width=0.8, color=couleur), fillcolor=style.rgba(couleur, 0.35))
        fig.add_scatter(x=proj.index, y=proj["total"], name="Patrimoine projeté", mode="lines",
                        line=dict(color=style.BLEU, width=2.6, shape="spline"))
        fig.add_vline(x=pd.Timestamp.today().strftime("%Y-%m-%d"), line=dict(color=style.GRIS, width=1, dash="dot"))
        bas = min(float(passe.min()) if not passe.empty else total0, total0)
        fig.update_yaxes(range=[bas * 0.9 if bas > 0 else bas * 1.1, float(proj["total"].max()) * 1.04])
        st.plotly_chart(style.graphique(fig, 380), config={"displayModeBar": False}, key="graphe_proj_revenus")

        g, d = st.columns([3, 2])
        with g:
            st.markdown("**Revenus passifs perçus chaque année**")
            annee = (np.arange(len(proj) - 1) // 12) + 1
            par_an = proj.iloc[1:].groupby(annee)[["dividendes_mois", "interets_mois"]].sum()
            fig = go.Figure()
            fig.add_bar(x=[f"An {a}" for a in par_an.index], y=par_an["dividendes_mois"], name="Dividendes",
                        marker_color=style.ORANGE)
            fig.add_bar(x=[f"An {a}" for a in par_an.index], y=par_an["interets_mois"], name="Intérêts",
                        marker_color=style.VERT)
            st.plotly_chart(style.graphique(fig, 260).update_layout(barmode="stack"),
                            config={"displayModeBar": False}, key="graphe_revenus_annuels")
        with d:
            st.markdown("**D'où viennent ces revenus aujourd'hui**")
            lignes = []
            if p:
                pos = p["positions"]
                for r in pos[pos["dividendes_attendus_base"] > 0].sort_values(
                        "dividendes_attendus_base", ascending=False).itertuples(index=False):
                    lignes.append((f"{r.ticker} ({r.enveloppe})", "Dividende", r.dividendes_attendus_base))
            lignes += [(nom, f"Intérêts {fmt(t, dec=2)} %", s * t / 100) for nom, s, t in comptes]
            if lignes:
                st.dataframe(pd.DataFrame(lignes, columns=["Source", "Nature", "Par an"]), hide_index=True,
                             column_config={"Par an": st.column_config.NumberColumn(f"Par an ({base})", format="%.0f")},
                             height=min(38 + 35 * len(lignes), 260))
            else:
                style.note("Aucun dividende annoncé ni compte rémunéré pour l'instant.")
        sans_taux = actuels[(actuels["categorie"] == "Épargne") & (actuels["taux_annuel"] <= 0)] \
            if not actuels.empty else actuels
        avertissement = ""
        if not sans_taux.empty:
            avertissement = (" Sans taux : " + ", ".join(sans_taux["nom"]) +
                             " (renseignez-le dans l'onglet Mes comptes).")
        style.note("Dividendes au niveau annoncé aujourd'hui par chaque entreprise (Yahoo Finance), intérêts aux taux "
                   "de vos comptes, capitalisés chaque année. Montants avant impôts ; les taux des livrets et les "
                   "dividendes peuvent changer." + avertissement)


# =================================================== PROJECTION AUTOMATIQUE
def hypotheses_automatiques(p: dict | None, pat: dict) -> dict:
    """Tout ce que la projection automatique déduit de vos données, sans réglage."""
    hist, actuels = pat["hist"], pat["actuels"]
    mvts = db.lister_budget()
    total0 = float(hist["total"].iloc[-1]) if not hist.empty else 0.0
    bourse0 = float(pat["valeur_bourse"])
    dividendes = float(p["dividendes_attendus"]) if p else 0.0
    remuneres = actuels[(actuels["categorie"] != "Dettes") & (actuels["taux_annuel"] > 0) & (actuels["solde"] > 0)] \
        if not actuels.empty else actuels
    comptes = [(r.nom, float(r.solde), float(r.taux_annuel)) for r in remuneres.itertuples(index=False)]
    epargne_mois = max(calculs.moyenne_mois_complets(mvts, "epargne"), 0.0)
    vers_bourse = calculs.versement_mensuel_moyen(p["tx"]) if p else 0.0
    # Loyers et autres revenus récurrents hors salaire, sur les 12 derniers mois.
    un_an = pd.Timestamp.today().normalize() - pd.DateOffset(months=12)
    revenus = mvts[(mvts["type"] == "REVENU") & (mvts["date"] >= un_an)] if not mvts.empty else mvts
    nb_mois = max(1, revenus["date"].dt.strftime("%Y-%m").nunique()) if not revenus.empty else 1
    loyers = float(revenus.loc[revenus["categorie"].str.contains("locati|loyer", case=False, na=False),
                               "montant"].sum()) / nb_mois if not revenus.empty else 0.0
    twr = calculs.twr_annualise(p["hist"]) if p and not p["hist"].empty and p["anciennete_jours"] > 365 else None
    return {
        "total0": total0, "bourse0": bourse0, "dividendes": dividendes,
        "rendement": dividendes / bourse0 if bourse0 > 0 else 0.0, "comptes": comptes,
        "interets": sum(s * t / 100 for _, s, t in comptes),
        "autres": total0 - bourse0 - sum(s for _, s, _ in comptes),
        "epargne_mois": epargne_mois, "vers_bourse": min(vers_bourse, epargne_mois) if epargne_mois else vers_bourse,
        "vers_livrets": max(epargne_mois - vers_bourse, 0.0), "loyers": loyers,
        "twr": max(min(twr, 0.12), -0.05) if twr is not None else None,  # performance passée, bornée
        "mois_budget": int(mvts["date"].dt.strftime("%Y-%m").nunique()) if not mvts.empty else 0,
    }


def projection_automatique(p: dict | None, pat: dict, base: str) -> None:
    """Projection sans aucun réglage : uniquement vos livrets, vos dividendes, votre épargne réelle,
    vos versements habituels et vos loyers. Cours de bourse supposés stables (scénario prudent)."""
    if pat["hist"].empty:
        st.info("Ajoutez d'abord vos comptes (Mes comptes) et vos placements pour obtenir une projection.")
        return
    h = hypotheses_automatiques(p, pat)
    annees = 20
    args = dict(bourse=h["bourse0"], rendement_dividende=h["rendement"], comptes_remuneres=h["comptes"],
                autres=h["autres"], annees=annees, reinvestir=True, versement_mensuel=h["vers_bourse"],
                versement_epargne=h["vers_livrets"])
    proj = calculs.projeter_revenus(hausse_cours=0.0, **args)
    proj_perf = calculs.projeter_revenus(hausse_cours=h["twr"], **args) if h["twr"] else None

    dix = proj.iloc[10 * 12]
    style.hero("Votre patrimoine dans 10 ans (scénario prudent)", fmt(dix["total"], base, 0),
               style.pilule(f"{fmt_signe(dix['total'] - h['total0'], base, 0)} par rapport à aujourd'hui",
                            dix["total"] - h["total0"]),
               "cours de bourse supposés stables",
               [(style.BLEU, f"Dans {a} an{'s' if a > 1 else ''}", fmt(proj.iloc[a * 12]["total"], base, 0))
                for a in (1, 5, 20)]
               + [(style.VERT, "Revenus passifs dans 10 ans", f"{fmt(dix['revenu_annuel'] / 12, base, 0)} / mois")])

    with style.verre("hypotheses_auto"):
        st.markdown("**Ce que l'application a pris en compte (calculé automatiquement)**")
        lignes = [
            ("Épargne mensuelle moyenne", fmt(h["epargne_mois"], base, 0),
             f"moyenne des {min(h['mois_budget'], 6)} derniers mois complets du Budget (revenus − dépenses)"
             if h["mois_budget"] else "aucun mois de budget saisi : comptée à 0"),
            ("… dont placée en bourse", fmt(h["vers_bourse"], base, 0),
             "vos achats nets moyens des 12 derniers mois (Transactions)"),
            ("… dont versée sur vos livrets", fmt(h["vers_livrets"], base, 0), "le reste de votre épargne"),
            ("Dividendes annoncés", f"{fmt(h['dividendes'], base, 0)} / an",
             f"rendement de {fmt_pct(h['rendement'] * 100, signe=False)} sur {fmt(h['bourse0'], base, 0)} "
             "de titres, réinvestis"),
            ("Intérêts de vos livrets", f"{fmt(h['interets'], base, 0)} / an",
             " · ".join(f"{n} {fmt(t, dec=2)} %" for n, _, t in h["comptes"]) or "aucun compte rémunéré"),
            ("Loyers perçus", f"{fmt(h['loyers'], base, 0)} / mois",
             "moyenne mensuelle sur les 12 derniers mois saisis (déjà comprise dans votre épargne)"
             if h["loyers"] else "aucun loyer enregistré"),
            ("Cours de bourse", "stables", "scénario prudent : seuls les revenus réels font grandir le patrimoine"),
        ]
        # Liste plutôt que tableau : les explications passent à la ligne, même en fenêtre étroite.
        st.markdown("".join(
            f'<div style="display:flex;flex-wrap:wrap;gap:4px 12px;align-items:baseline;padding:7px 0;'
            f'border-bottom:1px solid {style.BORD}"><span style="min-width:210px">{html.escape(e)}</span>'
            f'<b style="min-width:110px">{html.escape(v)}</b><span class="note" style="flex:1;min-width:200px">'
            f'{html.escape(o)}</span></div>' for e, v, o in lignes), unsafe_allow_html=True)
        sans_taux = pat["actuels"][(pat["actuels"]["categorie"] == "Épargne") & (pat["actuels"]["taux_annuel"] <= 0)] \
            if not pat["actuels"].empty else pat["actuels"]
        if not sans_taux.empty:
            st.warning("Taux non renseigné pour : " + ", ".join(sans_taux["nom"]) +
                       ". Indiquez-le dans l'onglet Mes comptes pour inclure ses intérêts.")

    with style.verre("courbe_auto"):
        st.markdown("**Évolution prévue sur 20 ans**")
        fig = go.Figure()
        for nom, col, couleur in [("Bourse", "bourse", style.BLEU), ("Livrets", "epargne", style.VERT),
                                  ("Autres actifs", "autres", style.GRIS), ("Liquidités", "liquidites", style.TURQUOISE)]:
            if proj[col].abs().sum() > 0:
                fig.add_scatter(x=proj.index, y=proj[col], name=nom, stackgroup="auto", mode="lines",
                                line=dict(width=0.6, color=couleur), fillcolor=style.rgba(couleur, 0.35))
        fig.add_scatter(x=proj.index, y=proj["total"], name="Patrimoine (prudent)", mode="lines",
                        line=dict(color=style.TEXTE, width=2.2))
        if proj_perf is not None:
            fig.add_scatter(x=proj_perf.index, y=proj_perf["total"], mode="lines", line=dict(color=style.ORANGE,
                            width=1.6, dash="dot"),
                            name=f"Si les cours suivent votre performance passée ({fmt_pct(h['twr'] * 100)} / an)")
        st.plotly_chart(style.graphique(fig, 380), config={"displayModeBar": False}, key="graphe_projection_auto")

    with style.verre("jalons_auto"):
        st.markdown("**Étape par étape**")
        jalons = []
        for a in (1, 2, 3, 5, 10, 15, 20):
            r = proj.iloc[a * 12]
            jalons.append({"Dans": f"{a} an{'s' if a > 1 else ''}", "Date": proj.index[a * 12].strftime("%m/%Y"),
                           "Patrimoine": fmt(r["total"], base, 0),
                           "Revenus passifs / mois": fmt(r["revenu_annuel"] / 12, base, 0),
                           "Dividendes cumulés": fmt(r["dividendes_cumules"], base, 0),
                           "Intérêts cumulés": fmt(r["interets_cumules"], base, 0),
                           "Versé de votre poche": fmt(r["verse_cumule"], base, 0)})
        st.dataframe(pd.DataFrame(jalons), hide_index=True, width="stretch")
        style.note("Projection indicative, avant impôts, calculée uniquement à partir de vos données. Pour tester "
                   "d'autres hypothèses (hausse des cours, inflation…), utilisez l'onglet Projection personnalisée.")


# ============================================================== PROJECTIONS
def projections(p: dict | None, pat: dict, base: str) -> None:
    hist, actuels = pat["hist"], pat["actuels"]
    if hist.empty:
        st.info("Ajoutez d'abord vos comptes ou vos placements pour lancer une projection.")
        return

    par_cat = actuels.groupby("categorie")["valeur"].sum() if not actuels.empty else pd.Series(dtype=float)
    total = float(hist["total"].iloc[-1])
    P0 = pat["valeur_bourse"] + float(par_cat.get("Placements hors application", 0)) + float(par_cat.get("Crypto", 0))
    E0 = float(par_cat.get("Épargne", 0))
    A0 = total - P0 - E0

    epargnes = actuels[actuels["categorie"] == "Épargne"] if not actuels.empty else actuels
    taux_epargne = (float(np.average(epargnes["taux_annuel"], weights=epargnes["solde"]))
                    if not epargnes.empty and epargnes["solde"].sum() > 0 else 0.0)
    rdt_div = (p["dividendes_attendus"] / pat["valeur_bourse"] * 100) if p and pat["valeur_bourse"] > 0 else 0.0
    vers_bourse = calculs.versement_mensuel_moyen(p["tx"]) if p else 0.0
    mvts = db.lister_budget()
    epargne_mensuelle = calculs.moyenne_mois_complets(mvts, "epargne")
    depenses_mensuelles = calculs.moyenne_mois_complets(mvts, "depenses")
    twr = calculs.twr_annualise(p["hist"]) if p and not p["hist"].empty and p["anciennete_jours"] > 365 else None

    with style.verre("hypotheses"):
        st.markdown("**Vos hypothèses**")
        c1, c2, c3 = st.columns(3)
        annees = c1.slider("Horizon (années)", 1, 40, 15)
        v_bourse = c1.number_input(f"Versement mensuel en placements ({base})", min_value=0.0,
                                   value=float(round(vers_bourse)), step=50.0,
                                   help="Par défaut : votre moyenne d'achats nets des 12 derniers mois.")
        v_epargne = c1.number_input(f"Versement mensuel sur l'épargne ({base})", min_value=0.0,
                                    value=float(round(max(0.0, epargne_mensuelle - vers_bourse))), step=50.0,
                                    help="Par défaut : votre épargne mensuelle moyenne (Budget) moins vos placements.")
        hausse = c2.number_input("Hausse annuelle des cours (%)", -10.0, 20.0, 5.0, 0.5,
                                 help="Progression moyenne des cours, hors dividendes.")
        if twr is not None:
            c2.caption(f"Votre performance historique (TWR) : {fmt_pct(twr * 100)} par an, dividendes compris.")
        dividende = c2.number_input("Rendement du dividende (%)", 0.0, 15.0, float(min(round(rdt_div, 2), 15.0)), 0.1,
                                    help="Par défaut : dividendes annoncés de vos titres ÷ valeur actuelle, en direct.")
        remuneration = c2.number_input("Rémunération de l'épargne (%)", 0.0, 10.0, float(min(round(taux_epargne, 2), 10.0)), 0.1,
                                       help="Par défaut : moyenne des taux de vos comptes d'épargne.")
        mode = c3.radio("Dividendes", ["reinvestis", "epargne", "depenses"],
                        format_func={"reinvestis": "Réinvestis", "epargne": "Versés sur l'épargne",
                                     "depenses": "Dépensés (revenu)"}.get)
        ecart = c3.number_input("Écart des scénarios (± points)", 0.0, 10.0, 3.0, 0.5,
                                help="Le scénario prudent retire ces points à la hausse des cours, l'optimiste les ajoute.")
        reel = c3.toggle("En euros d'aujourd'hui", help="Retire l'inflation pour afficher un pouvoir d'achat réel.")
        inflation = c3.number_input("Inflation (%)", 0.0, 10.0, 2.0, 0.1) / 100 if reel else 0.0

    args = dict(placements=P0, epargne=E0, autres=A0, versement_placements=v_bourse, versement_epargne=v_epargne,
                rendement_dividende=dividende / 100, taux_epargne=remuneration / 100, annees=annees,
                dividendes=mode, inflation=inflation)
    central = calculs.projeter(hausse_annuelle=hausse / 100, **args)
    prudent = calculs.projeter(hausse_annuelle=(hausse - ecart) / 100, **args)
    optimiste = calculs.projeter(hausse_annuelle=(hausse + ecart) / 100, **args)
    fin = central.iloc[-1]
    gains = fin["total"] - total - fin["verse_cumule"]

    style.hero(f"Patrimoine estimé dans {annees} ans", fmt(fin["total"], base, 0),
               style.pilule(f"{fmt_signe(fin['total'] - total, base, 0)} par rapport à aujourd'hui", fin["total"] - total),
               f"entre {fmt(prudent['total'].iloc[-1], base, 0)} et {fmt(optimiste['total'].iloc[-1], base, 0)} selon le scénario",
               [(style.BLEU, "Versé de votre poche", fmt(fin["verse_cumule"], base, 0)),
                (style.VERT, "Gains (intérêts, hausses, dividendes)", fmt(gains, base, 0)),
                (style.ORANGE, "Dividendes par an à l'horizon", fmt(fin["dividendes_annuels"], base, 0)),
                (style.VIOLET, "soit par mois", fmt(fin["dividendes_annuels"] / 12, base, 0))])

    with style.verre("graphe_projection"):
        st.markdown("**Votre patrimoine, du passé à l'avenir**")
        passe = hist["total"][hist.index >= hist.index[-1] - pd.DateOffset(years=3)]
        fig = go.Figure()
        fig.add_scatter(x=optimiste.index, y=optimiste["total"], name="Optimiste", mode="lines",
                        line=dict(color=style.rgba(style.BLEU, 0.35), width=1))
        fig.add_scatter(x=prudent.index, y=prudent["total"], name="Prudent", mode="lines", fill="tonexty",
                        fillcolor=style.rgba(style.BLEU, 0.12), line=dict(color=style.rgba(style.BLEU, 0.35), width=1))
        fig.add_scatter(x=central.index, y=central["total"], name="Scénario central", mode="lines",
                        line=dict(color=style.BLEU, width=3, shape="spline"))
        fig.add_scatter(x=passe.index, y=passe.values, name="Historique", mode="lines",
                        line=dict(color=style.TEXTE, width=2.2))
        fig.add_scatter(x=central.index, y=central["verse_cumule"] + total, name="Sans aucun rendement",
                        mode="lines", line=dict(color=style.GRIS, width=1.4, dash="dot"))
        fig.add_vline(x=pd.Timestamp.today().strftime("%Y-%m-%d"), line=dict(color=style.GRIS, width=1, dash="dot"))
        st.plotly_chart(style.graphique(fig, 420), config={"displayModeBar": False}, key="graphe_proj")

    g, d = st.columns([3, 2])
    with g, style.verre("dividendes_futurs"):
        st.markdown("**Dividendes perçus chaque année**")
        par_an = central["dividendes_mois"].iloc[1:].groupby((np.arange(len(central) - 1) // 12) + 1).sum()
        fig = go.Figure(go.Bar(x=[f"An {a}" for a in par_an.index], y=par_an.values, marker_color=style.VERT,
                               name="Dividendes"))
        if depenses_mensuelles > 0:
            fig.add_hline(y=depenses_mensuelles * 12, line=dict(color=style.ORANGE, dash="dot", width=1.5))
            couverture = fin["dividendes_annuels"] / (depenses_mensuelles * 12) * 100
            style.note(f"Ligne orange : vos dépenses annuelles moyennes ({fmt(depenses_mensuelles * 12, base, 0)}). "
                       f"À l'horizon, vos dividendes en couvriraient {fmt(couverture, dec=2)} %.")
        st.plotly_chart(style.graphique(fig, 300, legende=False), config={"displayModeBar": False}, key="graphe_div_futurs")

    with d, style.verre("independance"):
        st.markdown("**Indépendance financière**")
        if depenses_mensuelles > 0:
            cible = depenses_mensuelles * 12 * 25
            st.metric("Capital visé (règle des 4 %)", fmt(cible, base, 0),
                      help="25 fois vos dépenses annuelles : un capital dont on peut retirer 4 % par an "
                           "sur une longue durée, selon les études historiques.")
            for nom, scen in [("Prudent", prudent), ("Central", central), ("Optimiste", optimiste)]:
                atteinte = calculs.premiere_date(scen, scen["placements"] + scen["epargne"] >= cible)
                texte = style.fmt_mois(atteinte) if atteinte is not None else f"au-delà de {annees} ans"
                st.markdown(f"{nom} : **{texte}**")
            style.note("Calculé sur vos placements et votre épargne, hors immobilier et comptes courants.")
        else:
            style.note("Saisissez quelques mois de dépenses dans Budget pour estimer le capital dont vous auriez besoin.")

    with style.verre("jalons"):
        st.markdown("**Étapes clés (scénario central)**")
        jalons = [a for a in (1, 2, 3, 5, 10, 15, 20, 25, 30, 40) if a <= annees]
        lignes = []
        for a in jalons:
            r, rp, ro = central.iloc[a * 12], prudent.iloc[a * 12], optimiste.iloc[a * 12]
            lignes.append({"Dans": f"{a} an{'s' if a > 1 else ''}", "Date": central.index[a * 12].strftime("%m/%Y"),
                           "Patrimoine": r["total"], "Prudent": rp["total"], "Optimiste": ro["total"],
                           "Placements": r["placements"], "Épargne": r["epargne"],
                           "Dividendes / mois": r["dividendes_annuels"] / 12})
        st.dataframe(pd.DataFrame(lignes), hide_index=True, column_config={
            c: st.column_config.NumberColumn(c, format="%.0f") for c in
            ["Patrimoine", "Prudent", "Optimiste", "Placements", "Épargne", "Dividendes / mois"]})
        style.note("Projection indicative, pas une prévision : les marchés peuvent baisser plusieurs années de suite. "
                   "Les montants sont avant impôts.")


# ================================================================== COMPTES
def gestion_comptes(pat: dict, base: str) -> None:
    actuels = pat["actuels"]
    version = st.session_state.get("version_soldes", 0)

    with style.verre("mise_a_jour_soldes"):
        st.markdown("**Mettre à jour mes soldes**")
        if pat["valeur_bourse"]:
            style.note(f"Votre portefeuille boursier ({fmt(pat['valeur_bourse'], base, 0)}) est calculé "
                       "automatiquement à partir de vos transactions et des cours en direct.")
        if actuels.empty:
            st.caption("Aucun compte pour l'instant : ajoutez-en un ci-dessous.")
        else:
            table = actuels[["id", "nom", "categorie", "solde", "date"]].copy()
            table["nouveau"] = np.nan
            edite = st.data_editor(
                table, hide_index=True, key=f"editeur_soldes_{version}",
                disabled=["id", "nom", "categorie", "solde", "date"],
                column_config={
                    "id": None, "nom": "Compte", "categorie": "Catégorie",
                    "solde": st.column_config.NumberColumn(f"Dernier solde ({base})", format="%.2f"),
                    "date": st.column_config.DateColumn("Relevé du", format="DD/MM/YYYY"),
                    "nouveau": st.column_config.NumberColumn(f"Nouveau solde ({base})", format="%.2f",
                                                             help="Laissez vide si inchangé"),
                })
            c1, c2 = st.columns([1, 2], vertical_alignment="bottom")
            jour = c1.date_input("Date du relevé", date.today(), format="DD/MM/YYYY", key="date_releve")
            if c2.button("Enregistrer les nouveaux soldes", type="primary"):
                a_saisir = edite.dropna(subset=["nouveau"])
                for r in a_saisir.itertuples(index=False):
                    db.enregistrer_solde(r.id, jour, r.nouveau)
                st.session_state["version_soldes"] = version + 1
                st.toast(f"{len(a_saisir)} solde(s) enregistré(s).")
                st.rerun()
            style.note("Pour les dettes (crédit, prêt), saisissez le capital restant dû en positif : "
                       "il est déduit automatiquement.")

    g, d = st.columns(2)
    with g, style.verre("ajout_compte"):
        st.markdown("**Ajouter un compte ou un actif**")
        with st.form("form_compte", clear_on_submit=True, border=False):
            nom = st.text_input("Nom", placeholder="ex. Livret A, Assurance vie, Appartement, Crédit auto")
            categorie = st.selectbox("Catégorie", db.CATEGORIES_PATRIMOINE, index=1)
            c1, c2 = st.columns(2)
            solde = c1.number_input(f"Solde actuel ({base})", min_value=0.0, step=100.0)
            taux = c2.number_input("Taux annuel (%)", min_value=0.0, max_value=30.0, step=0.1,
                                   help="Rémunération (épargne) ou taux d'intérêt (dette). Utilisé dans les projections.")
            if st.form_submit_button("Ajouter le compte", type="primary"):
                if not nom.strip():
                    st.error("Donnez un nom au compte.")
                else:
                    compte_id = db.ajouter_compte(nom, categorie, taux)
                    db.enregistrer_solde(compte_id, date.today(), solde)
                    st.rerun()

    with d, style.verre("modifier_compte"):
        st.markdown("**Modifier ou supprimer un compte**")
        if actuels.empty:
            st.caption("Aucun compte.")
        else:
            choix = st.selectbox("Compte", actuels["id"].tolist(),
                                 format_func=lambda i: actuels.loc[actuels["id"] == i, "nom"].iloc[0])
            ligne = actuels[actuels["id"] == choix].iloc[0]
            nom = st.text_input("Nom", ligne["nom"], key=f"nom_{choix}")
            categorie = st.selectbox("Catégorie", db.CATEGORIES_PATRIMOINE, key=f"cat_{choix}",
                                     index=db.CATEGORIES_PATRIMOINE.index(ligne["categorie"])
                                     if ligne["categorie"] in db.CATEGORIES_PATRIMOINE else 0)
            taux = st.number_input("Taux annuel (%)", 0.0, 30.0, float(ligne["taux_annuel"]), 0.1, key=f"taux_{choix}")
            c1, c2 = st.columns(2)
            if c1.button("Enregistrer", key="maj_compte"):
                db.modifier_compte(choix, nom, categorie, taux)
                st.rerun()
            confirmer = c2.checkbox("Confirmer la suppression", key=f"conf_{choix}")
            if c2.button("Supprimer le compte", disabled=not confirmer, key="suppr_compte"):
                db.supprimer_compte(choix)
                st.rerun()

    soldes = pat["soldes"]
    if not soldes.empty:
        with st.expander("Historique des relevés"):
            vue = soldes.sort_values("date", ascending=False)
            st.dataframe(vue[["date", "nom", "categorie", "montant"]], hide_index=True, column_config={
                "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"), "nom": "Compte",
                "categorie": "Catégorie", "montant": st.column_config.NumberColumn("Solde", format="%.2f")})
            ids = st.multiselect("Relevés à supprimer", vue["id"].tolist(),
                                 format_func=lambda i: "{:%d/%m/%Y} : {} ({})".format(
                                     *vue.loc[vue["id"] == i, ["date", "nom", "montant"]].iloc[0]))
            if st.button("Supprimer la sélection", disabled=not ids, key="suppr_releves"):
                db.supprimer_soldes(ids)
                st.rerun()
