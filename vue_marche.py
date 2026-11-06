"""Page « Marchés » : places boursières, top 50 mondial, listes suivies (favoris, indices…),
recherche de titres et analyse détaillée. Les cours se rafraîchissent automatiquement."""

from __future__ import annotations

import html
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import bourses
import calculs
import db
import donnees
import style
import vues_tableaux
from style import fmt, fmt_pct

SANS_BARRE = {"displayModeBar": False}
VUES = ["Top 50 mondial", "Crypto", "ETF", "Mes listes", "Rechercher", "Analyse"]
PAGES: dict = {}  # pages de navigation, renseignées par app.py (pour « Saisir un achat »)

ETATS = {"REGULAR": "🟢 Ouvert", "PRE": "🟠 Pré-ouverture", "PREPRE": "⚪ Fermé",
         "POST": "🟠 Après-clôture", "POSTPOST": "⚪ Fermé", "CLOSED": "⚪ Fermé"}


# ================================================================== page
def page() -> None:
    st.session_state.pop("_rerun_app", None)  # déjà en train de tout recharger
    if st.session_state.pop("_aller_transactions", False) and "transactions" in PAGES:
        st.switch_page(PAGES["transactions"])
    st.title("Marchés")
    _places()
    if st.session_state.get("vue_marche") not in VUES:
        st.session_state["vue_marche"] = VUES[0]
    vue = st.segmented_control("Vue", VUES, key="vue_marche", label_visibility="collapsed") or VUES[0]
    {"Top 50 mondial": _vue_top, "Crypto": _vue_crypto, "ETF": _vue_etf, "Mes listes": _vue_listes,
     "Rechercher": _vue_recherche, "Analyse": _vue_analyse}[vue]()


def _relancer_si_demande() -> None:
    """Les boutons d'action vivent dans des fragments : ils demandent ici un rechargement complet."""
    if st.session_state.pop("_rerun_app", False):
        st.rerun(scope="app")


def _maj() -> str:
    return f"Mis à jour à {datetime.now():%H:%M:%S} · actualisation automatique chaque minute"


# ===================================================== places boursières
@st.fragment(run_every=donnees.ACTUALISATION_S)
def _places() -> None:
    indices = donnees.cotations(tuple(p.indice for p in bourses.PLACES))
    maintenant = datetime.now(timezone.utc)
    cartes, puces, nb_ouvertes = [], [], 0
    for p in bourses.PLACES:
        ligne = indices[indices["ticker"] == p.indice]
        etat_yahoo = ligne["etat"].iloc[0] if not ligne.empty else None
        s = bourses.statut_place(p, maintenant, etat_yahoo)
        nb_ouvertes += s["ouvert"]
        nom_court = s["nom"].split(" (")[0]
        puces.append((not s["ouvert"],
                      f'<span class="puce place-puce {s["etat"].lower()}"><span class="place-point"></span>'
                      f'{html.escape(nom_court)} <span class="note">{html.escape(s["evenement"])}</span></span>'))
        heures = f"{s['horaires_locaux']} heure locale"
        if s["horaires_chez_vous"] != s["horaires_locaux"]:
            heures += f" · {s['horaires_chez_vous']} chez vous"
        if s["pause"]:
            heures += f" · {s['pause']}"
        indice = ""
        if not ligne.empty:
            v = float(ligne["variation_pct"].iloc[0])
            classe = "pos" if v > 0 else ("neg" if v < 0 else "neutre")
            nom_indice = bourses.NOMS_INDICES.get(p.indice, str(ligne["nom"].iloc[0]))
            indice = (f'<span class="place-indice">{html.escape(nom_indice)} '
                      f'<span class="{classe}">{fmt_pct(v)}</span></span>')
        cartes.append(
            f'<div class="place {s["etat"].lower()}">'
            f'<div class="place-tete"><span class="place-point"></span><b>{html.escape(s["nom"])}</b>'
            f'<span class="place-etat">{s["etat"]}</span></div>'
            f'<div class="place-heures">{html.escape(heures)}</div>'
            f'<div class="place-evt">{html.escape(s["evenement"])}</div>{indice}</div>')
    with style.verre("places"):
        st.markdown(f"**Places boursières** · {nb_ouvertes} ouverte{'s' if nb_ouvertes > 1 else ''} "
                    f"sur {len(bourses.PLACES)} · il est {datetime.now():%H:%M} chez vous")
        puces.sort(key=lambda x: x[0])  # places ouvertes en premier
        st.markdown(f'<div class="puces places-puces">{"".join(h for _, h in puces)}</div>',
                    unsafe_allow_html=True)
        with st.expander("Horaires d'ouverture et indices de chaque place"):
            st.markdown(f'<div class="places">{"".join(cartes)}</div>', unsafe_allow_html=True)
            style.note("Horaires de séance normaux. Les jours fériés sont repérés grâce à l'état "
                       "de l'indice de chaque place publié par Yahoo Finance.")


# ================================================== tableau de cotations
def _tableau(df: pd.DataFrame, cle: str, hauteur: int | None = None) -> str | None:
    """Tableau de cours en direct ; renvoie le ticker de la ligne sélectionnée."""
    if df.empty:
        return None
    tend = donnees.tendances(tuple(df["ticker"]))
    types = df["type"] if "type" in df.columns else pd.Series([None] * len(df), index=df.index)
    aff = pd.DataFrame({
        "nom": df["nom"].astype(str).str.replace("Amundi Index Solutions - ", "", regex=False)
                        .str.replace(r"\s+(EUR|USD)$", "", regex=True),
        "ticker": df["ticker"], "type": types.map(lambda t: bourses.TYPES_ACTIFS.get(t, "–")),
        "place": df["place"], "cours": df["cours"], "devise": df["devise"], "variation_pct": df["variation_pct"],
        "tendance": df["ticker"].map(lambda t: tend.get(t) or None),
        "etat": [("🟢 24h/24" if t == "CRYPTOCURRENCY" else ETATS.get(e, "–")) if isinstance(e, str) else "–"
                 for e, t in zip(df["etat"], types)],
    })
    if "rang" in df.columns:
        aff.insert(0, "rang", df["rang"].values)
    libelle_capi = None
    for col, unite in (("capi_usd", "Md $"), ("capi_eur", "Md €")):
        if col in df.columns:
            aff.insert(aff.columns.get_loc("variation_pct") + 1, "capi", df[col].values / 1e9)
            libelle_capi = f"Capitalisation ({unite})"
    if types.nunique(dropna=True) <= 1:
        aff = aff.drop(columns="type")  # inutile si tout le tableau est du même type
    # Vue enregistrée (colonnes, tri) : une par type de tableau (Top 50, crypto, ETF, listes, recherche)
    groupe = next((g for g in ("top", "crypto", "etf", "liste", "recherche") if cle.startswith(f"table_{g}")), cle)
    libelles = {"rang": "#", "nom": "Entreprise", "ticker": "Ticker", "type": "Type", "place": "Place",
                "cours": "Cours", "devise": "Devise", "variation_pct": "Variation du jour",
                "capi": libelle_capi or "Capitalisation", "tendance": "30 jours", "etat": "Marché"}
    libelles = {c: l for c, l in libelles.items() if c in aff.columns}
    vue = vues_tableaux.barre(f"marches_{groupe}", libelles, list(libelles), non_triables=("tendance",))
    aff = vues_tableaux.trier(aff, vue).reset_index(drop=True)

    def couleur(v):
        if v is None or v != v or v == 0:
            return ""
        return f"color: {style.VERT_TEXTE}" if v > 0 else f"color: {style.ROUGE_TEXTE}"

    formats = {"cours": lambda v: fmt(v, dec=2 if v is None or v != v or abs(v) >= 1 else 6),
               "variation_pct": lambda v: style.fleche(v) + fmt_pct(v)}
    if "capi" in aff.columns:
        formats["capi"] = lambda v: fmt(v, dec=0)
    styler = aff.style.map(couleur, subset=["variation_pct"]).format(formats, na_rep="–")
    ev = st.dataframe(
        styler, hide_index=True, on_select="rerun", selection_mode=style.SELECTION_CLIC, key=cle,
        column_order=vue["colonnes"],
        height=hauteur or min(38 + 35 * len(aff), 740),
        column_config={
            "rang": st.column_config.NumberColumn("#", width=40),
            "nom": st.column_config.TextColumn("Entreprise", width="medium"),
            "ticker": "Ticker", "place": "Place",
            "cours": "Cours", "devise": "Devise",
            "variation_pct": "Variation du jour",
            "capi": st.column_config.Column(libelle_capi or "Capitalisation"),
            "type": "Type",
            "tendance": st.column_config.LineChartColumn("30 jours", width="small"),
            "etat": "Marché",
        })
    ligne = style.ligne_selectionnee(ev)
    return aff.iloc[ligne]["ticker"] if ligne is not None and ligne < len(aff) else None


# ============================================================== actions
def _basculer_favori(ticker: str) -> None:
    fav = db.id_favoris()
    if fav in db.listes_du_titre(ticker):
        db.retirer_de_liste(fav, [ticker])
    else:
        db.ajouter_a_liste(fav, ticker)


def _basculer_liste(liste_id: int, ticker: str, cle: str) -> None:
    if st.session_state.get(cle):
        db.ajouter_a_liste(liste_id, ticker)
    else:
        db.retirer_de_liste(liste_id, [ticker])


def _analyser(ticker: str) -> None:
    st.session_state["saisie_analyse"] = ticker
    st.session_state["vue_marche"] = "Analyse"
    st.session_state["_rerun_app"] = True


def _acheter(ticker: str) -> None:
    st.session_state["ticker_tx"] = ticker
    st.session_state["_aller_transactions"] = True
    st.session_state["_rerun_app"] = True


def _actions(ticker: str, df: pd.DataFrame, cle: str, liste_id: int | None = None,
             nom_liste: str = "") -> None:
    ligne = df[df["ticker"] == ticker]
    nom = ligne["nom"].iloc[0] if not ligne.empty else ticker
    fav = db.id_favoris()
    dans = db.listes_du_titre(ticker)
    with style.verre(f"actions_{cle}"):
        st.markdown(f"**{nom}** · {ticker}")
        colonnes = st.columns(5 if liste_id else 4)
        colonnes[0].button("★ Retirer des favoris" if fav in dans else "☆ Ajouter aux favoris",
                           key=f"fav_{cle}_{ticker}", on_click=_basculer_favori, args=(ticker,),
                           width="stretch")
        with colonnes[1].popover("Ajouter à une liste", width="stretch"):
            for r in db.lister_listes().itertuples(index=False):
                k = f"liste_{cle}_{ticker}_{r.id}"
                st.checkbox(r.nom, value=r.id in dans, key=k, on_change=_basculer_liste,
                            args=(r.id, ticker, k))
        colonnes[2].button("Analyser", key=f"analyser_{cle}_{ticker}", on_click=_analyser,
                           args=(ticker,), width="stretch")
        colonnes[3].button("Saisir un achat", key=f"acheter_{cle}_{ticker}", on_click=_acheter,
                           args=(ticker,), width="stretch", type="primary")
        if liste_id:
            colonnes[4].button(f"Retirer de « {nom_liste} »", key=f"retirer_{cle}_{ticker}",
                               on_click=db.retirer_de_liste, args=(liste_id, [ticker]),
                               width="stretch")


# ========================================================= top 50 mondial
@st.fragment(run_every=donnees.ACTUALISATION_S)
def _vue_top() -> None:
    _relancer_si_demande()
    with st.spinner("Chargement des cours…"):
        df = donnees.top_mondial()
    if df.empty:
        st.warning("Cours indisponibles pour le moment (connexion à Yahoo Finance impossible).")
        return
    with style.verre("top50"):
        st.markdown("**Les 50 plus grosses entreprises du monde**")
        style.note("Classement par capitalisation boursière convertie en dollars. " + _maj() +
                   ". Sélectionnez une ligne pour l'ajouter à une liste ou l'analyser.")
        choix = _tableau(df, "table_top")
    if choix:
        _actions(choix, df, "top")


# ================================================================ crypto
@st.fragment(run_every=donnees.ACTUALISATION_S)
def _vue_crypto() -> None:
    _relancer_si_demande()
    with st.spinner("Chargement des cours…"):
        df = donnees.cotations(tuple(bourses.CRYPTOS))
    if df.empty:
        st.warning("Cours indisponibles pour le moment (connexion à Yahoo Finance impossible).")
        return
    df = df.sort_values("capitalisation", ascending=False, na_position="last").reset_index(drop=True)
    df.insert(0, "rang", range(1, len(df) + 1))
    df["capi_eur"] = df["capitalisation"]
    with style.verre("crypto"):
        hausse = int((df["variation_pct"] > 0).sum())
        st.markdown(f"**Cryptomonnaies** · {len(df)} actifs · {hausse} en hausse sur 24 h")
        style.note("Cours en euros, marché ouvert 24h/24 et 7j/7, classés par capitalisation. " + _maj() +
                   ". Tapez un nom dans Rechercher pour trouver toute autre cryptomonnaie.")
        choix = _tableau(df, "table_crypto")
    if choix:
        _actions(choix, df, "crypto")


# =================================================================== ETF
def _vue_etf() -> None:
    groupes = list(bourses.ETF)
    if st.session_state.get("groupe_etf") not in groupes:
        st.session_state["groupe_etf"] = groupes[0]
    groupe = st.segmented_control("Émetteur", groupes, key="groupe_etf", label_visibility="collapsed") or groupes[0]
    _table_etf(groupe)


@st.fragment(run_every=donnees.ACTUALISATION_S)
def _table_etf(groupe: str) -> None:
    _relancer_si_demande()
    tickers = bourses.ETF[groupe]
    with st.spinner("Chargement des cours…"):
        q = donnees.cotations(tuple(tickers))
    q = q.set_index("ticker").reindex([t for t in tickers if t in set(q["ticker"])]).reset_index()
    with style.verre("etf"):
        st.markdown(f"**ETF {groupe}** · {len(q)} fonds")
        aide = ("Fonds éligibles au PEA (actions européennes, ou réplication synthétique d'indices mondiaux). "
                if groupe == "Éligibles PEA" else "")
        style.note(aide + _maj() + ". Pour tout autre ETF, utilisez Rechercher (filtre « ETF »).")
        choix = _tableau(q, f"table_etf_{groupe}")
    if choix:
        _actions(choix, q, f"etf_{''.join(c for c in groupe if c.isalnum())}")


# ============================================================ mes listes
def _creer_liste() -> None:
    nom = (st.session_state.get("nouvelle_liste") or "").strip()
    if not nom:
        st.session_state["_msg_liste"] = "Donnez un nom à la liste."
    elif nom in db.lister_listes()["nom"].tolist():
        st.session_state["_msg_liste"] = f"La liste « {nom} » existe déjà."
    else:
        db.creer_liste(nom)
        st.session_state["liste_active"] = nom
        st.session_state["nouvelle_liste"] = ""


def _renommer_liste(liste_id: int, ancien: str) -> None:
    nom = (st.session_state.get(f"renommer_{liste_id}") or "").strip()
    if nom and nom != ancien and nom not in db.lister_listes()["nom"].tolist():
        db.renommer_liste(liste_id, nom)
        st.session_state["liste_active"] = nom


def _supprimer_liste(liste_id: int) -> None:
    db.supprimer_liste(liste_id)
    st.session_state.pop("liste_active", None)


def _ajouter_depuis_recherche(liste_id: int, cle: str) -> None:
    ticker = st.session_state.get(cle)
    if ticker:
        db.ajouter_a_liste(liste_id, ticker)
        st.session_state["_msg_liste"] = f"{ticker} ajouté."


AUTO = "auto:"  # préfixe des listes automatiques (une par enveloppe du portefeuille)


def _vue_listes() -> None:
    db.id_favoris()  # la liste des favoris existe toujours
    listes = db.lister_listes()
    detenus = donnees.titres_par_enveloppe()
    auto = [AUTO + env for env in db.lister_enveloppes() if detenus.get(env)]
    noms = auto + listes["nom"].tolist()
    nb = dict(zip(listes["nom"], listes["nb"])) | {AUTO + e: len(t) for e, t in detenus.items()}
    if st.session_state.get("liste_active") not in noms:
        st.session_state["liste_active"] = noms[0]

    def libelle(n: str) -> str:
        return f"💼 {n[len(AUTO):]} ({nb.get(n, 0)})" if n.startswith(AUTO) else f"{n} ({nb.get(n, 0)})"

    c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
    nom = c1.segmented_control("Liste", noms, key="liste_active", label_visibility="collapsed",
                               format_func=libelle)
    if nom and nom.startswith(AUTO):
        env = nom[len(AUTO):]
        if msg := st.session_state.pop("_msg_liste", None):
            st.toast(msg)
        style.note(f"Liste automatique : les titres détenus dans votre enveloppe « {env} ». Elle se met à jour "
                   "toute seule à chaque achat ou vente (page Transactions).")
        _table_liste(None, f"💼 {env}", tuple(detenus.get(env, [])))
        return
    liste_id = int(listes.loc[listes["nom"] == nom, "id"].iloc[0]) if nom else None
    with c2.popover("Gérer les listes", width="stretch"):
        st.text_input("Nouvelle liste", key="nouvelle_liste", placeholder="ex. Dividendes, Tech, À surveiller")
        st.button("Créer la liste", on_click=_creer_liste, type="primary")
        if liste_id and nom != db.FAVORIS:
            st.divider()
            st.text_input(f"Renommer « {nom} »", value=nom, key=f"renommer_{liste_id}")
            st.button("Renommer", on_click=_renommer_liste, args=(liste_id, nom))
            st.button(f"Supprimer « {nom} »", on_click=_supprimer_liste, args=(liste_id,))
    if msg := st.session_state.pop("_msg_liste", None):
        st.toast(msg)
    if not liste_id:
        return

    with style.verre("ajout_liste"):
        st.markdown(f"**Ajouter un titre à « {nom} »**")
        g, d = st.columns([4, 1], vertical_alignment="bottom")
        with g:
            choisi = choisir_titre(f"ajout_{liste_id}")
        d.button("Ajouter", key=f"btn_ajout_{liste_id}", type="primary", disabled=choisi is None,
                 on_click=_ajouter_depuis_recherche, args=(liste_id, f"ajout_{liste_id}"), width="stretch")
    _table_liste(liste_id, nom)


@st.fragment(run_every=donnees.ACTUALISATION_S)
def _table_liste(liste_id: int | None, nom: str, tickers_auto: tuple[str, ...] = ()) -> None:
    """liste_id = None : liste automatique (titres fournis, non modifiable)."""
    _relancer_si_demande()
    tickers = list(tickers_auto) if liste_id is None else db.titres_liste(liste_id)
    cle = liste_id if liste_id is not None else "auto_" + "".join(c for c in nom if c.isalnum())
    if not tickers:
        st.info(f"La liste « {nom} » est vide. Recherchez un titre ci-dessus, ou sélectionnez une "
                "ligne du Top 50 pour l'ajouter.")
        return
    with st.spinner("Chargement des cours…"):
        q = donnees.cotations(tuple(tickers))
    manquants = [t for t in tickers if t not in set(q["ticker"])]
    q = q.set_index("ticker").reindex([t for t in tickers if t not in manquants]).reset_index()
    with style.verre(f"liste_{cle}"):
        hausse = int((q["variation_pct"] > 0).sum())
        st.markdown(f"**{nom}** · {len(q)} titres · {hausse} en hausse, {len(q) - hausse} stables ou en baisse")
        style.note(_maj() + ".")
        choix = _tableau(q, f"table_liste_{cle}")
        if manquants:
            style.note("Sans cotation (ticker à vérifier) : " + ", ".join(manquants))
            if liste_id is not None:
                st.button("Retirer ces tickers de la liste", key=f"purger_{liste_id}",
                          on_click=db.retirer_de_liste, args=(liste_id, manquants))
    if choix:
        _actions(choix, q, f"liste{cle}", liste_id, nom)


# ============================================================ recherche
def choisir_titre(cle: str, libelle: str = "Rechercher une entreprise, un ETF, un indice…") -> str | None:
    """Champ de recherche + liste de résultats ; renvoie le ticker choisi (clé de session `cle`)."""
    texte = st.text_input(libelle, key=f"{cle}_texte", placeholder="ex. LVMH, Apple, Toyota, MSCI World")
    texte = texte.strip()
    if len(texte) < 2:
        st.session_state.pop(cle, None)
        return None
    resultats = donnees.recherche(texte)
    if not resultats:
        st.caption("Aucun résultat.")
        st.session_state.pop(cle, None)
        return None
    libelles = {r["ticker"]: f'{r["nom"]} · {r["ticker"]} · {r["place"]} ({r["type"]})' for r in resultats}
    if st.session_state.get(cle) not in libelles:
        st.session_state[cle] = resultats[0]["ticker"]
    return st.selectbox("Résultat", list(libelles), format_func=libelles.get, key=cle)


def _vue_recherche() -> None:
    g, d = st.columns([3, 2], vertical_alignment="bottom")
    texte = g.text_input("Rechercher parmi toutes les actions, ETF et cryptomonnaies (nom ou ticker)",
                         key="recherche_texte", placeholder="ex. Hermès, Amundi MSCI World, Bitcoin, Nasdaq…")
    filtres = {"Tout": None, "Actions": ("equity",), "ETF": ("etf",), "Crypto": ("cryptocurrency",),
               "Indices": ("index",), "Fonds": ("mutualfund", "fund")}
    filtre = d.segmented_control("Type", list(filtres), default="Tout", key="filtre_recherche",
                                 label_visibility="collapsed") or "Tout"
    if len(texte.strip()) < 2:
        style.note("Actions, ETF (Amundi, iShares, Vanguard…), indices et cryptomonnaies de toutes les places, "
                   "via Yahoo Finance.")
        return
    requete = texte.strip()
    if filtre == "ETF" and "etf" not in requete.lower():
        requete += " ETF"  # oriente la recherche Yahoo vers les fonds indiciels
    resultats = donnees.recherche(requete)
    # Cryptos : proposer d'abord la cotation en euros (BTC-EUR plutôt que BTC-USD).
    enrichis = []
    for r in resultats:
        if str(r["type"]).lower() == "cryptocurrency" and r["ticker"].endswith("-USD"):
            enrichis.append({**r, "ticker": r["ticker"][:-4] + "-EUR"})
        enrichis.append(r)
    # Résultats des listes vérifiées de l'appli (ETF, cryptos) dont le nom contient tous les mots tapés.
    mots = [m for m in texte.lower().split() if m != "etf"]
    locaux = []
    if filtre in ("Tout", "ETF", "Crypto") and mots:
        reference = list(dict.fromkeys(sum(bourses.ETF.values(), [])
                                       + (bourses.CRYPTOS if filtre != "ETF" else [])))
        q_ref = donnees.cotations(tuple(reference))
        for r in q_ref.itertuples(index=False):
            cible = f"{r.nom} {r.ticker}".lower()
            if all(m in cible for m in mots) and (filtre == "Tout" or bourses.TYPES_ACTIFS.get(r.type) == filtre):
                locaux.append({"ticker": r.ticker, "nom": r.nom, "place": r.place or "",
                               "type": "Cryptocurrency" if r.type == "CRYPTOCURRENCY" else r.type})
    resultats = list({r["ticker"]: r for r in locaux + enrichis}.values())
    if filtres[filtre]:
        resultats = [r for r in resultats if str(r["type"]).lower().replace(" ", "") in filtres[filtre]]
    if not resultats:
        st.info("Aucun résultat pour cette recherche" + (f" parmi les {filtre.lower()}." if filtres[filtre] else "."))
        return
    _resultats_recherche(tuple(r["ticker"] for r in resultats))


@st.fragment(run_every=donnees.ACTUALISATION_S)
def _resultats_recherche(tickers: tuple[str, ...]) -> None:
    _relancer_si_demande()
    q = donnees.cotations(tickers)
    q = q.set_index("ticker").reindex([t for t in tickers if t in set(q["ticker"])]).reset_index()
    with style.verre("resultats"):
        st.markdown(f"**{len(q)} résultats** · sélectionnez une ligne pour l'ajouter aux favoris ou à une liste")
        choix = _tableau(q, "table_recherche")
    if choix:
        _actions(choix, q, "recherche")


# ============================================================== analyse
def _vue_analyse() -> None:
    if "saisie_analyse" not in st.session_state:
        tx = db.lister_transactions()
        st.session_state["saisie_analyse"] = (", ".join(sorted(tx["ticker"].unique())[:3])
                                              if not tx.empty else "MC.PA, CW8.PA")
    c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
    saisie = c1.text_input("Tickers à analyser (séparés par des virgules)", key="saisie_analyse")
    periodes = {"6 mois": 0.5, "1 an": 1, "3 ans": 3, "5 ans": 5, "10 ans": 10}
    periode = c2.segmented_control("Période", list(periodes), default="3 ans", key="periode_marche") or "3 ans"
    tickers = tuple(dict.fromkeys(t.strip().upper() for t in saisie.split(",") if t.strip()))
    if not tickers:
        return

    debut_affiche = pd.Timestamp.today().normalize() - pd.DateOffset(months=int(periodes[periode] * 12))
    debut_calcul = (debut_affiche - pd.Timedelta(days=320)).strftime("%Y-%m-%d")  # marge pour la MM200
    with st.spinner("Téléchargement des cours…"):
        prix = donnees.histo(tickers, debut_calcul, True)
    manquants = [t for t in tickers if t not in prix.columns or prix[t].dropna().empty]
    if manquants:
        st.warning("Aucune donnée pour : " + ", ".join(manquants))
    tickers = [t for t in tickers if t not in manquants]
    if not tickers:
        return

    choix = st.selectbox("Titre détaillé", tickers) if len(tickers) > 1 else tickers[0]
    info = donnees.infos(choix)
    direct = donnees.cotations((choix,))
    serie_periode = prix[choix].dropna()
    serie_periode = serie_periode[serie_periode.index >= debut_affiche]
    ecart = float(serie_periode.iloc[-1] / serie_periode.iloc[0] - 1) * 100 if len(serie_periode) > 1 else 0.0
    details = [x for x in [info.get("secteur"), info.get("pays")] if x]
    if not direct.empty:
        d = direct.iloc[0]
        valeur = fmt(d["cours"], d["devise"])
        variation = (style.pilule(f"{fmt_pct(d['variation_pct'])} aujourd'hui", d["variation_pct"]) + " " +
                     style.pilule(f"{fmt_pct(ecart)} sur {periode}", ecart))
        details.insert(0, ETATS.get(d["etat"], "").split(" ", 1)[-1])
    else:
        valeur = fmt(serie_periode.iloc[-1], info.get("devise"))
        variation = style.pilule(f"{fmt_pct(ecart)} sur {periode}", ecart)
    style.hero(info.get("nom", choix), valeur, variation, " · ".join(x for x in details if x))
    _actions(choix, pd.DataFrame({"ticker": [choix], "nom": [info.get("nom", choix)]}), "analyse")

    with style.verre("graphe_titre"):
        mm = calculs.moyennes_mobiles(prix[choix].dropna())
        mm = mm[mm.index >= debut_affiche]
        fig = style.courbe_cours(mm.index, mm["cours"].values, "Cours", ecart >= 0, 400)
        fig.add_scatter(x=mm.index, y=mm["MM50"], name="Moyenne 50 jours", mode="lines",
                        line=dict(color=style.ORANGE, width=1.3))
        fig.add_scatter(x=mm.index, y=mm["MM200"], name="Moyenne 200 jours", mode="lines",
                        line=dict(color=style.VIOLET, width=1.3))
        fig.update_layout(showlegend=True, margin=dict(t=40))  # place réservée à la légende (au-dessus)
        st.plotly_chart(fig, config=SANS_BARRE, key="graphe_cours_titre")
        style.note("Cours ajustés des dividendes et divisions d'actions (performance totale).")

    g, d = st.columns([3, 2])
    with g, style.verre("drawdown"):
        st.markdown("**Baisse depuis le plus haut**")
        dd = calculs.drawdown(serie_periode)
        fig = go.Figure(go.Scatter(x=dd.index, y=dd, fill="tozeroy", fillcolor=style.rgba(style.ROUGE, 0.15),
                                   line=dict(color=style.ROUGE, width=1.4), name="Baisse"))
        fig.update_yaxes(ticksuffix=" %")
        st.plotly_chart(style.graphique(fig, 240, legende=False), config=SANS_BARRE, key="graphe_drawdown")
    with d, style.verre("fondamentaux"):
        st.markdown("**Indicateurs**")
        c1, c2 = st.columns(2)
        c1.metric("PER", fmt(info.get("per"), dec=1))
        c2.metric("Dividende annuel", fmt(info.get("dividende_annuel") or None, info.get("devise")))
        c1.metric("Rendement du dividende", fmt_pct(info.get("rendement_dividende"), signe=False),
                  help="Valeur fournie par Yahoo Finance")
        c2.metric("Capitalisation", (fmt(info["capitalisation"] / 1e9, dec=1) + " Md")
                  if info.get("capitalisation") else "–")

    if len(tickers) > 1:
        with style.verre("comparaison"):
            st.markdown("**Comparaison (base 100)**")
            b100 = calculs.base_100(prix[tickers][prix.index >= debut_affiche])
            fig = go.Figure()
            for i, t in enumerate(b100.columns):
                fig.add_scatter(x=b100.index, y=b100[t], name=t, mode="lines",
                                line=dict(color=style.PALETTE[i % len(style.PALETTE)], width=2.2, shape="spline"))
            st.plotly_chart(style.graphique(fig, 360), config=SANS_BARRE, key="graphe_base100")

    with style.verre("stats_marche"):
        st.markdown("**Statistiques sur la période**")
        stats = pd.DataFrame({t: calculs.statistiques_titre(prix[t][prix.index >= debut_affiche]) for t in tickers})
        st.dataframe(stats.map(lambda v: "–" if v is None or pd.isna(v) else fmt(v)))
        style.note("Volatilité : amplitude habituelle des variations sur un an. "
                   "Perte maximale : pire baisse entre un plus haut et un plus bas sur la période.")
