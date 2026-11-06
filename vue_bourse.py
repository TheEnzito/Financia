"""Pages « Portefeuille », « Transactions » et « Marchés »."""

from __future__ import annotations

import html
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import bourses
import calculs
import db
import donnees
import style
import vue_marche
from style import fmt, fmt_pct, fmt_signe

SANS_BARRE = {"displayModeBar": False}


# ============================================================ PORTEFEUILLE
def _cours(v) -> str:
    return fmt(v, dec=2 if v != v or abs(v) >= 1 else 6)


FORMATS_POSITIONS = {
    "quantite": lambda v: fmt(v, dec=6).rstrip("0").rstrip(","), "pru": _cours, "cours": _cours,
    "var_jour_pct": fmt_pct, "cout_revient_base": lambda v: fmt(v), "valeur_base": lambda v: fmt(v),
    "pv_latente_base": lambda v: fmt_signe(v, dec=2), "pv_latente_pct": fmt_pct,
    "dividendes_base": lambda v: fmt(v), "gain_total_base": lambda v: fmt_signe(v, dec=2), "xirr_pct": fmt_pct,
    "pv_realisee": lambda v: fmt_signe(v, dec=2), "dividendes": lambda v: fmt(v), "frais": lambda v: fmt(v),
}


def _xirr_lignes(pos: pd.DataFrame, p: dict) -> pd.Series:
    return pd.Series([(p["xirr_titres"].get((e, t)) or float("nan")) * 100
                      for e, t in zip(pos["enveloppe"], pos["ticker"])], index=pos.index)


def _donut(labels: list[str], valeurs: list[float], couleurs: list[str], survols: list[str],
           centre: str, sous_titre: str, cle: str, hauteur: int) -> None:
    """Camembert « anneau » avec le total au centre."""
    fig = go.Figure(go.Pie(
        labels=labels, values=valeurs, hole=0.64, sort=False, direction="clockwise",
        marker=dict(colors=couleurs, line=dict(color=style.PANNEAU, width=2)),
        customdata=survols, hovertemplate="%{customdata}<extra></extra>",
        texttemplate="<b>%{label}</b><br>%{percent:.2%}", textposition="inside",
        insidetextorientation="horizontal"))
    fig.add_annotation(text=f"<b>{centre}</b><br><span style='font-size:11px;color:{style.TEXTE_2}'>{sous_titre}</span>",
                       showarrow=False, font=dict(size=15, color=style.TEXTE, family=style.POLICE))
    fig.update_layout(height=hauteur, margin=dict(l=4, r=4, t=4, b=4), showlegend=False, separators=", ",
                      paper_bgcolor="rgba(0,0,0,0)", uniformtext=dict(minsize=10, mode="hide"),
                      font=dict(family=style.POLICE, color=style.TEXTE, size=12),
                      hoverlabel=dict(bgcolor=style.PANNEAU_2, font=dict(color=style.TEXTE)))
    st.plotly_chart(fig, config=SANS_BARRE, key=cle)
    # Légende compacte : couleur, nom et part de chaque élément (lisible même en fenêtre étroite).
    total = sum(valeurs) or 1
    st.markdown('<div class="puces" style="margin-top:0">' + "".join(
        f'<span class="puce"><span class="point" style="background:{c}"></span>{html.escape(str(l))} '
        f'<b>{fmt_pct(v / total * 100, signe=False, dec=2)}</b></span>'
        for l, v, c in sorted(zip(labels, valeurs, couleurs), key=lambda x: -x[1])) + "</div>",
        unsafe_allow_html=True)


def camemberts_portefeuilles(p: dict | None, cle: str, hauteur: int = 240) -> None:
    """Un camembert général (la part de chaque portefeuille, sans le détail des titres),
    puis un camembert par portefeuille (ses titres et ses espèces)."""
    base = donnees.devise_base()
    pos = p["positions"] if p else pd.DataFrame(columns=["enveloppe", "ticker", "quantite", "valeur_base"])
    actives = pos[(pos["quantite"] > 0) & (pos["valeur_base"] > 0)].copy()
    especes = {e: s for e, (s, _) in db.especes_actuelles().items() if s > 0}
    enveloppes = [e for e in db.lister_enveloppes() if e in set(actives["enveloppe"]) | set(especes)]
    if not enveloppes:
        style.note("Aucune position en cours.")
        return
    noms = donnees.cotations(tuple(actives["ticker"].unique())) if not actives.empty else pd.DataFrame()
    noms = dict(zip(noms["ticker"], noms["nom"])) if not noms.empty else {}
    totaux = {e: float(actives.loc[actives["enveloppe"] == e, "valeur_base"].sum()) + especes.get(e, 0.0)
              for e in enveloppes}
    total = sum(totaux.values())

    cartes = ["__general__"] + enveloppes
    par_ligne = 3
    for debut in range(0, len(cartes), par_ligne):
        colonnes = st.columns(par_ligne)
        for colonne, carte in zip(colonnes, cartes[debut:debut + par_ligne]):
            with colonne:
                if carte == "__general__":
                    st.markdown("**Tous mes portefeuilles**")
                    _donut(enveloppes, [totaux[e] for e in enveloppes],
                           [style.couleur_enveloppe(e) for e in enveloppes],
                           [f"{e}<br>{fmt(totaux[e], base, 0)} · {fmt_pct(totaux[e] / total * 100, signe=False, dec=2)}"
                            for e in enveloppes],
                           fmt(total, base, 0), f"{len(enveloppes)} portefeuille{'s' if len(enveloppes) > 1 else ''}",
                           f"{cle}_general", hauteur)
                    continue
                env = carte
                groupe = actives[actives["enveloppe"] == env].sort_values("valeur_base", ascending=False)
                cash = especes.get(env, 0.0)
                labels, valeurs, couleurs, survols = [], [], [], []
                for i, l in enumerate(groupe.itertuples(index=False)):
                    nom = str(noms.get(l.ticker, l.ticker)).replace("Amundi Index Solutions - ", "")
                    labels.append(l.ticker)
                    valeurs.append(float(l.valeur_base))
                    couleurs.append(style.PALETTE[i % len(style.PALETTE)])
                    survols.append(f"{nom}<br>{fmt(l.valeur_base, base, 0)} · plus-value "
                                   f"{fmt_signe(l.pv_latente_base, base, 0)} ({fmt_pct(l.pv_latente_pct)})")
                if cash:
                    labels.append("Espèces")
                    valeurs.append(cash)
                    couleurs.append(style.REPERE)
                    survols.append(f"Espèces non investies<br>{fmt(cash, base, 2)}")
                st.markdown(f"**{env}** · {fmt_pct(totaux[env] / total * 100, signe=False, dec=2)} du total")
                _donut(labels, valeurs, couleurs, survols, fmt(totaux[env], base, 0),
                       f"{len(groupe)} ligne{'s' if len(groupe) > 1 else ''}" + (" + espèces" if cash else ""),
                       f"{cle}_{''.join(c for c in env if c.isalnum())}", hauteur)
    style.note("Survolez une part pour le détail (valeur, plus-value). Les portefeuilles se gèrent dans "
               "Portefeuille › Mes enveloppes.")


PERIODES_APERCU = {"1 j": ("intraday", "5d", "5m", pd.Timedelta(days=1)),
                   "1 sem.": ("intraday", "1mo", "30m", pd.Timedelta(weeks=1)),
                   "1 mois": ("jour", pd.DateOffset(months=1)), "6 mois": ("jour", pd.DateOffset(months=6)),
                   "1 an": ("jour", pd.DateOffset(years=1)), "5 ans": ("jour", pd.DateOffset(years=5)),
                   "Depuis l'achat": ("achat", None)}


def _fermer_apercu() -> None:
    st.session_state.pop("apercu_position", None)


def _analyser_titre(ticker: str) -> None:
    st.session_state["saisie_analyse"] = ticker
    st.session_state["vue_marche"] = "Analyse"
    st.session_state["_aller_marches_pf"] = True
    st.session_state["_rerun_app"] = True


def apercu_cours(p: dict, env: str, ticker: str, nom: str, ligne, direct) -> None:
    """Aperçu du cours d'une position : courbe, PRU, points d'achat et de vente."""
    if st.session_state.pop("_rerun_app", False):
        st.rerun(scope="app")
    devise = ligne["devise"]
    with style.verre("apercu_cours"):
        c1, c2 = st.columns([3, 2], vertical_alignment="center")
        c1.markdown(f"**{html.escape(str(nom))}** · {ticker} · {env}")
        periode = c2.segmented_control("Période", list(PERIODES_APERCU), default="Depuis l'achat",
                                       key="periode_apercu", label_visibility="collapsed") or "Depuis l'achat"
        ops = p["tx"][(p["tx"]["ticker"] == ticker) & (p["tx"]["enveloppe"] == env)]
        conf = PERIODES_APERCU[periode]
        maintenant = pd.Timestamp.now()
        if conf[0] == "intraday":
            serie = donnees.histo_intraday((ticker,), conf[1], conf[2])
            serie = serie[ticker].dropna() if ticker in serie.columns else pd.Series(dtype=float)
            serie = serie[serie.index >= maintenant - conf[3]]
        else:
            debut = (ops["date"].min() - pd.Timedelta(days=7)) if conf[0] == "achat" else maintenant.normalize() - conf[1]
            serie = donnees.histo((ticker,), debut.strftime("%Y-%m-%d"), False)
            serie = serie[ticker].dropna() if ticker in serie.columns else pd.Series(dtype=float)
            serie = serie[serie.index >= debut]
            if direct is not None and len(serie):  # dernier point = cours en direct
                serie.index = pd.DatetimeIndex(serie.index).astype("datetime64[ns]")
                serie = pd.concat([serie, pd.Series([float(direct["cours"])],
                                                    index=pd.DatetimeIndex([maintenant]).astype("datetime64[ns]"))])
        if serie.empty:
            st.info("Cours indisponible pour cette période (marché fermé ou données manquantes).")
        else:
            ecart = float(serie.iloc[-1] / serie.iloc[0] - 1) * 100
            pv_pct = float(ligne["pv_latente_pct"])
            infos = [style.pilule(f"{fmt_pct(ecart)} sur {periode.lower()}", ecart),
                     style.pilule(f"{fmt_pct(pv_pct)} vs votre PRU", pv_pct)]
            if direct is not None:
                infos.insert(0, style.pilule(f"{fmt_pct(direct['variation_pct'])} aujourd'hui", direct["variation_pct"]))
            st.markdown(f'<span class="hero-valeur" style="font-size:2rem">{fmt(serie.iloc[-1], devise)}</span> '
                        + " ".join(infos), unsafe_allow_html=True)
            fig = style.courbe_cours(serie.index, serie.values, ticker, ecart >= 0, 320)
            fig.add_hline(y=float(ligne["pru"]), line=dict(color=style.ORANGE, width=1.4, dash="dot"),
                          annotation_text=f"PRU {fmt(ligne['pru'], devise)}", annotation_position="top left",
                          annotation_font=dict(color=style.ORANGE, size=11))
            visibles = ops[ops["date"] >= serie.index[0].normalize()]
            for type_, symbole, couleur in [("ACHAT", "triangle-up", style.VERT), ("VENTE", "triangle-down", style.ROUGE)]:
                o = visibles[visibles["type"] == type_]
                if not o.empty:
                    fig.add_scatter(x=o["date"], y=o["prix"], mode="markers", name="Achats" if type_ == "ACHAT" else "Ventes",
                                    marker=dict(symbol=symbole, size=11, color=couleur, line=dict(width=1, color=style.PANNEAU)),
                                    hovertemplate="%{x|%d/%m/%Y} : %{y:.2f}<extra></extra>")
            bas = min(float(serie.min()), float(ligne["pru"]))
            haut = max(float(serie.max()), float(ligne["pru"]))
            marge = (haut - bas) * 0.08 or haut * 0.02
            fig.update_yaxes(range=[bas - marge, haut + marge])
            fig.update_layout(showlegend=False)
            if conf[0] == "intraday":
                fig.update_xaxes(tickformat="%H:%M" if periode == "1 j" else "%d/%m %Hh")
            st.plotly_chart(fig, config=SANS_BARRE, key="graphe_apercu")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Quantité", fmt(ligne["quantite"], dec=4).rstrip("0").rstrip(","))
        m2.metric("PRU", fmt(ligne["pru"], devise))
        m3.metric("Valeur", fmt(ligne["valeur_base"], p["base"]))
        m4.metric("Plus-value", fmt_signe(ligne["pv_latente_base"], p["base"], 2), fmt_pct(ligne["pv_latente_pct"]))
        b1, b2, _ = st.columns([1, 1, 2])
        b1.button("Analyse complète", key="apercu_analyse", on_click=_analyser_titre, args=(ticker,), width="stretch")
        b2.button("Fermer l'aperçu", key="apercu_fermer", on_click=_fermer_apercu, width="stretch")


@st.fragment(run_every=donnees.ACTUALISATION_S)
def _synthese_en_direct() -> None:
    """Valeur, plus-values et positions recalculées chaque minute à partir des cours en direct."""
    p = donnees.charger_portefeuille()
    if p is None:
        return
    donnees.avertir_introuvables(p)
    base, pos = p["base"], p["positions"].copy()
    cout = pos["cout_revient_base"].sum()
    latente = pos["pv_latente_base"].sum()

    # Variation du jour, à partir de la clôture de la veille.
    actives = pos[pos["quantite"] > 0].copy()
    q = donnees.cotations(tuple(actives["ticker"])).set_index("ticker")
    actives["var_jour_pct"] = actives["ticker"].map(q["variation_pct"]) if not q.empty else float("nan")
    actives["var_jour_base"] = (actives["ticker"].map(q["variation"]) * actives["quantite"]
                                * actives["taux_change"]) if not q.empty else float("nan")
    var_jour = float(actives["var_jour_base"].sum(min_count=1)) if actives["var_jour_base"].notna().any() else None
    valeur_veille = p["valeur"] - (var_jour or 0)

    especes = {e: s for e, (s, _) in db.especes_actuelles().items()}
    total_especes = sum(especes.values())
    puces = [(style.GRIS, "Espèces non investies", fmt(total_especes, base, 0))] if total_especes else []
    puces += [(style.VERT, "Plus-values réalisées", fmt(pos["pv_realisee_base"].sum(), base, 0)),
             (style.ORANGE, "Dividendes reçus", fmt(pos["dividendes_base"].sum(), base, 0)),
             (style.BLEU, "Rendement annualisé (XIRR)", fmt_pct(p["xirr"] * 100 if p["xirr"] is not None else None))]
    variation = style.pilule(f"{fmt_signe(latente, base, 0)} ({fmt_pct(latente / cout * 100 if cout else None)})",
                             latente)
    if var_jour is not None:
        variation += " " + style.pilule(
            f"{fmt_signe(var_jour, base, 0)} ({fmt_pct(var_jour / valeur_veille * 100 if valeur_veille else None)}) "
            "aujourd'hui", var_jour)
    style.hero("Valeur du portefeuille" + (" (titres + espèces)" if total_especes else ""),
               fmt(p["valeur"] + total_especes, base), variation,
               f"de plus-value latente · investi {fmt(cout, base, 0)} · mis à jour à {pd.Timestamp.now():%H:%M:%S}",
               puces)
    if p["anciennete_jours"] < 90:
        style.note("Moins de 3 mois d'historique : le rendement annualisé est encore peu significatif.")

    actives["xirr_pct"] = _xirr_lignes(actives, p)
    actives["nom"] = actives["ticker"].map(q["nom"]) if not q.empty else actives["ticker"]
    actives["nom"] = (actives["nom"].fillna(actives["ticker"]).astype(str)
                      .str.replace("Amundi Index Solutions - ", "", regex=False))
    actives["type"] = (actives["ticker"].map(q["type"]).map(lambda t: bourses.TYPES_ACTIFS.get(t, "–"))
                       if not q.empty else "–")
    enveloppes = sorted(actives["enveloppe"].unique())
    with style.verre("positions"):
        c1, c2 = st.columns([2, 3], vertical_alignment="center")
        c1.markdown("**Positions en cours**")
        filtre = "Toutes"
        if len(enveloppes) > 1:
            filtre = c2.segmented_control("Enveloppe", ["Toutes"] + enveloppes, default="Toutes",
                                          key="filtre_enveloppe", label_visibility="collapsed") or "Toutes"
        if filtre != "Toutes":
            actives = actives[actives["enveloppe"] == filtre]
            sous_total = actives["valeur_base"].sum()
            pv = actives["pv_latente_base"].sum()
            investi = actives["cout_revient_base"].sum()
            cash = especes.get(filtre, 0.0)
            style.note(f"{filtre} : {fmt(sous_total + cash, base, 2)}"
                       + (f" dont {fmt(cash, base, 2)} d'espèces" if cash else "")
                       + f" · titres investis {fmt(investi, base, 0)} · plus-value "
                       f"{fmt_signe(pv, base, 0)} ({fmt_pct(pv / investi * 100 if investi else None)})")
        actives = actives.sort_values(["enveloppe", "valeur_base"], ascending=[True, False])
        style.note("Calculé automatiquement depuis vos opérations (page Transactions) et les cours en direct, "
                   "actualisé chaque minute. Cliquez sur une ligne pour afficher l'aperçu du cours.")
        actives = actives.reset_index(drop=True)
        colonnes = ["enveloppe", "nom", "type", "ticker", "quantite", "pru", "cours", "devise", "var_jour_pct",
                    "cout_revient_base", "valeur_base", "pv_latente_base", "pv_latente_pct", "dividendes_base",
                    "gain_total_base", "poids_pct", "xirr_pct"]
        # Vert = favorable (hausse, plus-value, cours au-dessus du PRU), rouge = défavorable.
        tableau = style.tableau_gains(
            actives[colonnes],
            ["var_jour_pct", "pv_latente_base", "pv_latente_pct", "gain_total_base", "xirr_pct"],
            FORMATS_POSITIONS, cours_et_pru=("cours", "pru"))
        selection = st.dataframe(
            tableau,
            hide_index=True, key="table_positions", on_select="rerun", selection_mode=style.SELECTION_CLIC,
            column_config={
                "enveloppe": "Enveloppe", "nom": "Titre", "type": "Type", "ticker": "Ticker",
                # Pas de format ici : l'affichage (▲ / ▼, couleurs, virgule française) vient du Styler.
                "quantite": st.column_config.Column("Quantité"),
                "pru": st.column_config.Column("PRU", help="Prix de revient unitaire, frais inclus"),
                "cours": st.column_config.Column("Cours", help="▲ vert : au-dessus de votre PRU · ▼ rouge : en dessous"),
                "devise": "Devise",
                "var_jour_pct": st.column_config.Column("Jour", help="Variation depuis la clôture de la veille"),
                "cout_revient_base": st.column_config.Column(f"Investi ({base})", help="Prix de revient total, frais inclus"),
                "valeur_base": st.column_config.Column(f"Valeur ({base})"),
                "pv_latente_base": st.column_config.Column(f"Plus-value ({base})"),
                "pv_latente_pct": st.column_config.Column("Plus-value %"),
                "dividendes_base": st.column_config.Column(f"Dividendes ({base})"),
                "gain_total_base": st.column_config.Column(
                    f"Gain total ({base})", help="Plus-value latente + plus-values réalisées + dividendes nets"),
                "poids_pct": st.column_config.ProgressColumn("Poids", format="%.2f %%", min_value=0, max_value=100),
                "xirr_pct": st.column_config.Column("Rendement annualisé", help="XIRR de la ligne, dans la devise du titre"),
            })
    # La ligne choisie reste en mémoire : l'aperçu survit à l'actualisation automatique du tableau.
    ligne = style.ligne_selectionnee(selection)
    if ligne is not None and ligne < len(actives):
        choisie = actives.iloc[ligne]
        st.session_state["apercu_position"] = (choisie["enveloppe"], choisie["ticker"])
    if st.session_state.get("apercu_position"):
        env, ticker = st.session_state["apercu_position"]
        ligne = pos[(pos["enveloppe"] == env) & (pos["ticker"] == ticker) & (pos["quantite"] > 0)]
        if ligne.empty:
            st.session_state.pop("apercu_position", None)
        else:
            nom = q["nom"].get(ticker, ticker) if not q.empty and "nom" in q.columns else ticker
            apercu_cours(p, env, ticker, nom, ligne.iloc[0], q.loc[ticker] if ticker in q.index else None)


# ------------------------------------------------------------ enveloppes
TYPES_ENVELOPPES = ["PEA", "CTO", "PEA-PME", "Assurance vie", "PER"]


def _choisir_type_enveloppe() -> None:
    if st.session_state.get("type_nouvelle_enveloppe"):
        st.session_state["nom_nouvelle_enveloppe"] = st.session_state["type_nouvelle_enveloppe"]


def _creer_enveloppe() -> None:
    nom = (st.session_state.get("nom_nouvelle_enveloppe") or "").strip()
    if not nom:
        st.session_state["_msg_enveloppe"] = "Donnez un nom à l'enveloppe."
        return
    if nom in db.lister_enveloppes():
        st.session_state["_msg_enveloppe"] = f"L'enveloppe « {nom} » existe déjà."
        return
    db.creer_enveloppe(nom)
    especes = float(st.session_state.get("especes_nouvelle_enveloppe") or 0.0)
    if especes > 0:
        db.enregistrer_especes(nom, date.today(), especes)
    st.session_state["_msg_enveloppe"] = f"Enveloppe « {nom} » créée."
    st.session_state["nom_nouvelle_enveloppe"] = ""
    st.session_state["especes_nouvelle_enveloppe"] = 0.0
    st.session_state.pop("type_nouvelle_enveloppe", None)


def _renommer_enveloppe(ancien: str) -> None:
    nouveau = (st.session_state.get(f"renommer_env_{ancien}") or "").strip()
    if not nouveau or nouveau == ancien:
        return
    if nouveau in db.lister_enveloppes():
        st.session_state["_msg_enveloppe"] = f"L'enveloppe « {nouveau} » existe déjà."
        return
    db.renommer_enveloppe(ancien, nouveau)
    st.session_state["_msg_enveloppe"] = f"« {ancien} » renommée en « {nouveau} »."


def _supprimer_enveloppe(nom: str) -> None:
    try:
        db.supprimer_enveloppe(nom)
        st.session_state["_msg_enveloppe"] = f"Enveloppe « {nom} » supprimée."
    except ValueError as e:
        st.session_state["_msg_enveloppe"] = str(e)


def _maj_especes(nom: str) -> None:
    valeur = st.session_state.get(f"especes_env_{nom}")
    if valeur is not None:
        db.enregistrer_especes(nom, date.today(), float(valeur))
        st.session_state["_msg_enveloppe"] = f"Espèces de « {nom} » : {fmt(float(valeur), donnees.devise_base())}."


def _saisir_dans(nom: str) -> None:
    st.session_state["enveloppe_tx"] = nom
    st.session_state["_aller_transactions_pf"] = True


def mes_enveloppes(p: dict | None) -> None:
    """Création et suivi des enveloppes (PEA, CTO…) : titres + espèces de chacune."""
    base = donnees.devise_base()
    enveloppes = db.lister_enveloppes()
    especes = db.especes_actuelles()
    pos = p["positions"] if p else pd.DataFrame(columns=["enveloppe", "quantite", "valeur_base",
                                                         "cout_revient_base", "pv_latente_base"])
    if msg := st.session_state.pop("_msg_enveloppe", None):
        st.toast(msg)

    with style.verre("mes_enveloppes"):
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.markdown("**Mes enveloppes**")
        with c2.popover("＋ Nouvelle enveloppe", width="stretch", type="primary"):
            libres = [t for t in TYPES_ENVELOPPES if t not in enveloppes]
            if libres:
                st.pills("Type", libres, key="type_nouvelle_enveloppe", on_change=_choisir_type_enveloppe)
            st.text_input("Nom", key="nom_nouvelle_enveloppe", placeholder="ex. PEA, CTO Boursorama")
            st.number_input(f"Espèces disponibles ({base})", min_value=0.0, step=50.0,
                            key="especes_nouvelle_enveloppe",
                            help="L'argent non investi sur l'enveloppe (facultatif).")
            st.button("Créer l'enveloppe", on_click=_creer_enveloppe, type="primary", width="stretch")

        if not enveloppes:
            st.info("Créez votre première enveloppe (PEA, CTO…) avec le bouton **＋ Nouvelle enveloppe**, puis "
                    "saisissez vos achats dedans.")
            return

        colonnes = st.columns(min(len(enveloppes), 3))
        for i, nom in enumerate(enveloppes):
            lignes = pos[(pos["enveloppe"] == nom) & (pos["quantite"] > 0)]
            titres = float(lignes["valeur_base"].sum())
            investi = float(lignes["cout_revient_base"].sum())
            pv = float(lignes["pv_latente_base"].sum())
            cash, releve = especes.get(nom, (0.0, None))
            couleur = style.couleur_enveloppe(nom)
            classe = "pos" if pv > 0 else ("neg" if pv < 0 else "neutre")
            detail = (f'{len(lignes)} ligne{"s" if len(lignes) > 1 else ""} · titres {fmt(titres, base, 0)}'
                      f' · espèces {fmt(cash, base, 0)}')
            with colonnes[i % len(colonnes)]:
                st.markdown(
                    f'<div class="enveloppe" style="border-top: 3px solid {couleur}">'
                    f'<div class="enveloppe-nom">{html.escape(nom)}</div>'
                    f'<div class="enveloppe-valeur">{html.escape(fmt(titres + cash, base))}</div>'
                    f'<div class="note">{html.escape(detail)}</div>'
                    + (f'<span class="pilule {classe}">{html.escape(fmt_signe(pv, base, 0))} '
                       f'({html.escape(fmt_pct(pv / investi * 100 if investi else None))})</span>' if investi else "")
                    + '</div>', unsafe_allow_html=True)
                b1, b2 = st.columns(2)
                b1.button("Saisir une opération", key=f"saisir_env_{nom}", on_click=_saisir_dans, args=(nom,),
                          width="stretch")
                with b2.popover("Gérer", width="stretch"):
                    st.number_input(f"Espèces non investies ({base})", min_value=0.0, value=float(cash), step=10.0,
                                    key=f"especes_env_{nom}",
                                    help=f"Dernier relevé : {releve:%d/%m/%Y}" if releve is not None else None)
                    st.button("Mettre à jour les espèces", key=f"btn_especes_{nom}", on_click=_maj_especes,
                              args=(nom,), width="stretch")
                    st.divider()
                    st.text_input("Renommer", value=nom, key=f"renommer_env_{nom}")
                    st.button("Renommer", key=f"btn_renommer_{nom}", on_click=_renommer_enveloppe, args=(nom,),
                              width="stretch")
                    nb = db.nb_operations_enveloppe(nom)
                    st.button("Supprimer l'enveloppe", key=f"btn_suppr_env_{nom}", on_click=_supprimer_enveloppe,
                              args=(nom,), disabled=nb > 0, width="stretch",
                              help=(f"Contient {nb} opération(s) : déplacez-les d'abord (page Transactions)."
                                    if nb else None))


def page_portefeuille() -> None:
    st.session_state.pop("_rerun_app", None)
    if st.session_state.pop("_aller_transactions_pf", False) and "transactions" in vue_marche.PAGES:
        st.switch_page(vue_marche.PAGES["transactions"])
    if st.session_state.pop("_aller_marches_pf", False) and "marches" in vue_marche.PAGES:
        st.switch_page(vue_marche.PAGES["marches"])
    st.title("Portefeuille")
    p = donnees.charger_portefeuille()
    mes_enveloppes(p)
    if p is None:
        if db.lister_enveloppes():
            st.info("Cliquez sur **Saisir une opération** dans une enveloppe pour ajouter vos achats.")
        return
    _synthese_en_direct()
    base, pos, hist = p["base"], p["positions"].copy(), p["hist"]
    latente = pos["pv_latente_base"].sum()
    pos["xirr_pct"] = _xirr_lignes(pos, p)

    soldees = pos[pos["quantite"] == 0]
    if not soldees.empty:
        with st.expander(f"Positions soldées ({len(soldees)})"):
            st.dataframe(style.tableau_gains(
                soldees[["enveloppe", "ticker", "devise", "pv_realisee", "dividendes", "frais", "xirr_pct"]],
                ["pv_realisee", "xirr_pct"], FORMATS_POSITIONS),
                         hide_index=True, column_config={
                             "enveloppe": "Enveloppe", "ticker": "Titre", "devise": "Devise",
                             "pv_realisee": st.column_config.Column("Plus-value réalisée"),
                             "dividendes": st.column_config.Column("Dividendes"),
                             "frais": st.column_config.Column("Frais payés"),
                             "xirr_pct": st.column_config.Column("Rendement annualisé")})

    with style.verre("repartition_titres"):
        st.markdown("**Répartition de mes portefeuilles**")
        camemberts_portefeuilles(p, "graphe_repartition")

    if hist.empty:
        st.warning("Historique des cours indisponible : impossible de tracer la performance.")
        return

    with style.verre("valeur_investi"):
        st.markdown("**Valeur et montant investi**")
        fig = go.Figure()
        fig.add_scatter(x=hist.index, y=hist["investi_net"], name="Montant investi net", mode="lines",
                        line=dict(color=style.GRIS, width=1.5, dash="dot"))
        fig.add_scatter(x=hist.index, y=hist["valeur"], name="Valeur", mode="lines", fill="tonexty",
                        fillcolor=style.rgba(style.VERT if latente >= 0 else style.ROUGE, 0.12),
                        line=dict(color=style.VERT if latente >= 0 else style.ROUGE, width=2.6, shape="spline"))
        st.plotly_chart(style.graphique(fig, 330), config=SANS_BARRE, key="graphe_valeur_investi")

    with style.verre("perf_comparee"):
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        c1.markdown("**Performance comparée à un indice**")
        indice = c2.text_input("Indice de référence", db.lire_parametre("indice_reference"),
                               help="Ticker Yahoo : ^FCHI (CAC 40), ^GSPC (S&P 500), URTH (MSCI World)…")
        perf_indice = None
        ref = donnees.histo((indice,), hist.index[0].strftime("%Y-%m-%d"), True) if indice else pd.DataFrame()
        fig = go.Figure()
        fig.add_scatter(x=hist.index, y=hist["twr_cumule"] * 100, name="Mon portefeuille (TWR)", mode="lines",
                        line=dict(color=style.BLEU, width=2.8, shape="spline"))
        if not ref.empty and indice in ref.columns:
            serie = ref[indice].reindex(hist.index).ffill().dropna()
            if not serie.empty:
                courbe = (serie / serie.iloc[0] - 1) * 100
                perf_indice = float(courbe.iloc[-1])
                fig.add_scatter(x=courbe.index, y=courbe, name=indice, mode="lines",
                                line=dict(color=style.ORANGE, width=1.8))
        fig.update_yaxes(ticksuffix=" %")
        st.plotly_chart(style.graphique(fig, 380), config=SANS_BARRE, key="graphe_twr")

        twr = hist["twr_cumule"].iloc[-1] * 100
        twr_an = calculs.twr_annualise(hist)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("TWR depuis le début", fmt_pct(twr))
        c2.metric("TWR annualisé", fmt_pct(twr_an * 100 if twr_an is not None else None))
        c3.metric("XIRR (rendement personnel)", fmt_pct(p["xirr"] * 100 if p["xirr"] is not None else None))
        c4.metric(f"{indice} sur la même période", fmt_pct(perf_indice),
                  fmt_pct(twr - perf_indice) + " d'écart" if perf_indice is not None else None)

    with st.expander("Quelle différence entre TWR et XIRR ?"):
        st.markdown(
            "Le **TWR** mesure la performance de vos placements indépendamment du moment où vous avez "
            "ajouté ou retiré de l'argent. C'est la bonne mesure pour vous comparer à un indice.\n\n"
            "Le **XIRR** mesure le rendement réellement obtenu sur *votre* argent : si vous avez "
            "beaucoup investi juste avant une hausse, il sera meilleur que le TWR, et inversement.")


# ============================================================ TRANSACTIONS
def _utiliser_titre_recherche() -> None:
    if st.session_state.get("recherche_tx"):
        st.session_state["ticker_tx"] = st.session_state["recherche_tx"]


def page_transactions() -> None:
    st.title("Transactions")
    tx = db.lister_transactions()
    base = donnees.devise_base()

    with style.verre("nouvelle_operation"):
        st.markdown("**Nouvelle opération**")
        enveloppes = db.lister_enveloppes()
        if not enveloppes:
            st.info("Créez d'abord une enveloppe (PEA, CTO…) dans **Portefeuille › Mes enveloppes**.")
            st.page_link(vue_marche.PAGES["portefeuille"], label="Aller au Portefeuille",
                         icon=":material/donut_large:") if "portefeuille" in vue_marche.PAGES else None
            return
        if st.session_state.get("enveloppe_tx") not in enveloppes:
            st.session_state["enveloppe_tx"] = enveloppes[0]
        enveloppe = st.segmented_control(
            "Enveloppe", enveloppes, key="enveloppe_tx",
            help="Les enveloppes se créent et se gèrent dans Portefeuille › Mes enveloppes. "
                 "Chacune a ses propres positions, prix de revient et espèces.") or enveloppes[0]
        c1, c2, c3 = st.columns(3)
        type_ = c1.segmented_control("Type", calculs.TYPES_TRANSACTION, default="ACHAT", key="type_operation",
                                     format_func={"ACHAT": "Achat", "VENTE": "Vente", "DIVIDENDE": "Dividende"}.get) \
            or "ACHAT"
        st.session_state.setdefault("ticker_tx", "")
        ticker = c2.text_input("Ticker (Yahoo Finance)", key="ticker_tx",
                               placeholder="ex. MC.PA, AAPL, CW8.PA").strip().upper()
        with c2.popover("Rechercher par nom", width="stretch"):
            vue_marche.choisir_titre("recherche_tx")
            st.button("Utiliser ce titre", on_click=_utiliser_titre_recherche, type="primary",
                      disabled=not st.session_state.get("recherche_tx"))
        d1, d2 = c3.columns([3, 2])
        jour = d1.date_input("Date", date.today(), format="DD/MM/YYYY", max_value=date.today())
        heure = d2.time_input("Heure", value=None, step=60, key="heure_tx",
                              help="Heure de passage de l'ordre (facultatif).")

        devise_detectee, cours_detecte, cours_jour = None, None, None
        if ticker:
            cours_detecte, devise_detectee = donnees.cours_actuels((ticker,))[ticker]
            if cours_detecte is None:
                c2.caption("Ticker introuvable sur Yahoo Finance.")
            else:
                c2.caption(f"{donnees.infos(ticker).get('nom', ticker)} : {fmt(cours_detecte, devise_detectee)}")
                cours_jour = cours_detecte
                if jour < date.today():
                    cours_jour = donnees.cours_a_date(ticker, jour.isoformat()) or cours_detecte
                    c3.caption(f"Clôture du {jour:%d/%m/%Y} : {fmt(cours_jour, devise_detectee)}")

        c1, c2, c3, c4 = st.columns(4)
        dividende = type_ == "DIVIDENDE"
        quantite = c1.number_input("Nombre de titres" if dividende else "Quantité",
                                   min_value=0.0, value=1.0, step=1.0, format="%.6g")
        prix = c2.number_input("Dividende par titre" if dividende else "Prix unitaire",
                               min_value=0.0, value=0.0 if dividende else float(cours_jour or 0.0),
                               step=0.01, format="%.8g", key=f"prix_{ticker}_{type_}_{jour}",
                               help="Pré-rempli avec le cours de clôture à la date choisie : "
                                    "remplacez-le par votre prix d'exécution réel.")
        # On saisit le montant réellement payé ou reçu ; les frais s'en déduisent.
        brut = quantite * prix
        libelle_total, aide_total = {
            "ACHAT": ("Montant total payé", "Le montant débité, frais de courtage inclus (voir votre avis d'opéré)."),
            "VENTE": ("Montant total reçu", "Le montant crédité, après frais de courtage."),
            "DIVIDENDE": ("Montant net reçu", "Le dividende réellement versé, après prélèvements et retenues."),
        }[type_]
        total = c3.number_input(libelle_total, min_value=0.0, value=None, step=0.01, format="%.2f",
                                key=f"total_{ticker}_{type_}", placeholder=f"{brut:.2f}".replace(".", ","),
                                help=aide_total + " Laissez vide s'il n'y a pas de frais.")
        if total is None:
            total = brut
        frais = round(total - brut if type_ == "ACHAT" else brut - total, 2)
        frais_incoherents = frais < -0.005
        nom_frais = "Retenue / impôts" if dividende else "Frais"
        if frais_incoherents:
            c3.caption(f"⚠ Le montant {'payé est inférieur' if type_ == 'ACHAT' else 'reçu est supérieur'} "
                       f"au prix des titres ({fmt(brut)}).")
        else:
            c3.caption(f"{nom_frais} calculés : {fmt(max(frais, 0.0))}"
                       + (f" ({fmt_pct(frais / brut * 100, signe=False)})" if brut and frais > 0 else ""))
        frais = max(frais, 0.0)
        devise_defaut = devise_detectee if devise_detectee in donnees.DEVISES else donnees.devise_base()
        devise = c4.selectbox("Devise", donnees.DEVISES, key=f"devise_{ticker}",
                              index=donnees.DEVISES.index(devise_defaut) if devise_defaut in donnees.DEVISES else 0)
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        note = c1.text_input("Note (facultatif)")
        montant = quantite * prix + (frais if type_ == "ACHAT" else -frais)
        apercu = f"Montant de l'opération : {fmt(montant, devise)}"
        if type_ == "ACHAT" and quantite > 0 and prix > 0:
            apercu += f" · prix de revient {fmt(montant / quantite, devise)} par titre, frais inclus"
            if cours_detecte and devise == devise_detectee:
                gain = quantite * cours_detecte - montant
                apercu += (f" · au cours actuel ({fmt(cours_detecte, devise)}), cet achat vaut "
                           f"{fmt(quantite * cours_detecte, devise)}, soit {fmt_signe(gain, devise, 2)} "
                           f"({fmt_pct(gain / montant * 100)})")
        style.note(apercu)
        especes = db.especes_actuelles()
        solde_especes = especes.get(enveloppe, (None, None))[0] if enveloppe else None
        sens = -1 if type_ == "ACHAT" else 1
        maj_especes = st.checkbox(
            f"{'Débiter' if sens < 0 else 'Créditer'} les espèces de « {enveloppe or '…'} »"
            + (f" (solde actuel {fmt(solde_especes, base)})" if solde_especes is not None else ""),
            value=solde_especes is not None, key="maj_especes_tx",
            help="Met à jour automatiquement les espèces non investies de l'enveloppe "
                 "(achat : montant débité ; vente ou dividende : montant crédité).")

        if c2.button("Enregistrer l'opération", type="primary"):
            meme = tx[(tx["ticker"] == ticker) & (tx["enveloppe"] == enveloppe)] if not tx.empty else tx
            detenu = calculs.calculer_positions(meme) if not meme.empty else pd.DataFrame()
            q_detenue = float(detenu["quantite"].iloc[0]) if not detenu.empty else 0.0
            if not ticker:
                st.error("Indiquez un ticker.")
            elif not enveloppe:
                st.error("Donnez un nom à l'enveloppe.")
            elif quantite <= 0 or prix <= 0:
                st.error("La quantité et le prix doivent être supérieurs à zéro.")
            elif frais_incoherents:
                st.error(f"Le {libelle_total.lower()} ne peut pas être "
                         f"{'inférieur' if type_ == 'ACHAT' else 'supérieur'} au prix des titres "
                         f"({fmt(brut, devise)}). Vérifiez la quantité, le prix ou le montant.")
            elif type_ == "VENTE" and quantite > q_detenue + 1e-9:
                st.error(f"Vous ne détenez que {fmt(q_detenue, dec=4)} titres {ticker} dans « {enveloppe} ».")
            else:
                db.ajouter_transaction(jour, type_, ticker, quantite, prix, frais, devise, note, enveloppe, heure)
                if maj_especes:
                    taux = donnees.taux_change((devise,), base).get(devise, 1.0) if devise != base else 1.0
                    ancien, date_releve = especes.get(enveloppe, (0.0, None))
                    nouveau = ancien + sens * montant * taux
                    quand = max(pd.Timestamp(jour), date_releve) if date_releve is not None else pd.Timestamp(jour)
                    db.enregistrer_especes(enveloppe, quand, nouveau)
                    st.toast(f"Espèces de « {enveloppe} » : {fmt(nouveau, base)}.")
                st.toast(f"Opération enregistrée dans « {enveloppe} ».")
                st.rerun()

    if tx.empty:
        st.caption("Aucune transaction pour l'instant.")
    else:
        with style.verre("historique_tx"):
            st.markdown("**Historique**")
            affichage = tx.sort_values(["date", "heure", "id"], ascending=False)
            colonnes = ["date", "heure"] + [c for c in affichage.columns if c not in ("date", "heure")]
            st.dataframe(affichage[colonnes], hide_index=True, column_config={
                "id": None, "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                "heure": "Heure",
                "type": "Type", "ticker": "Titre",
                "quantite": st.column_config.NumberColumn("Quantité", format="%.6g"),
                "prix": st.column_config.NumberColumn("Prix", format="%.4f"),
                "frais": st.column_config.NumberColumn("Frais", format="%.2f"),
                "devise": "Devise", "note": "Note", "enveloppe": "Enveloppe"})
            with st.expander("Changer l'enveloppe d'opérations (ex. les ranger dans votre PEA)"):
                a_deplacer = st.multiselect(
                    "Opérations", affichage["id"].tolist(), key="tx_a_deplacer",
                    format_func=lambda i: "{:%d/%m/%Y} : {} {:g} {} ({})".format(
                        *tx.loc[tx["id"] == i, ["date", "type", "quantite", "ticker", "enveloppe"]].iloc[0]))
                g, d = st.columns([2, 1], vertical_alignment="bottom")
                cible = g.selectbox("Nouvelle enveloppe", db.lister_enveloppes(), key="enveloppe_cible")
                if d.button("Déplacer", disabled=not a_deplacer, key="btn_deplacer"):
                    db.changer_enveloppe(a_deplacer, cible)
                    st.toast(f"{len(a_deplacer)} opération(s) rangée(s) dans « {cible} ».")
                    st.rerun()
            with st.expander("Supprimer des opérations"):
                ids = st.multiselect("Opérations à supprimer", affichage["id"].tolist(),
                                     format_func=lambda i: "{:%d/%m/%Y} : {} {:g} {}".format(
                                         *tx.loc[tx["id"] == i, ["date", "type", "quantite", "ticker"]].iloc[0]))
                if st.button("Supprimer la sélection", disabled=not ids, key="suppr_tx"):
                    db.supprimer_transactions(ids)
                    st.rerun()

    with style.verre("import_tx"):
        st.markdown("**Import et export**")
        c1, c2 = st.columns(2)
        if not tx.empty:
            c1.download_button("Exporter en CSV", tx.drop(columns=["id"]).to_csv(index=False).encode("utf-8"),
                               "transactions.csv", "text/csv")
        fichier = c2.file_uploader("Importer un CSV", type="csv", key="import_tx",
                                   help="Colonnes : date, type (ACHAT/VENTE/DIVIDENDE), ticker, quantite, "
                                        "prix, frais, devise, note, enveloppe (ex. PEA ; facultatif)")
        if fichier is not None and c2.button("Importer ce fichier", key="btn_import_tx"):
            try:
                n = db.importer_transactions_csv(pd.read_csv(fichier, sep=None, engine="python"))
                st.success(f"{n} opérations importées.")
                st.rerun()
            except Exception as e:
                st.error(f"Import impossible : {e}")

