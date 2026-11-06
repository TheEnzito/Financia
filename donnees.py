"""Chargement des données partagées par les pages (avec cache des cours)."""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

import calculs
import db
import marche

DEVISES = ["EUR", "USD", "GBP", "CHF", "CAD", "JPY", "PLN", "SEK", "NOK", "DKK", "AUD"]


ACTUALISATION_S = 60  # rafraîchissement automatique des pages « en direct »


@st.cache_data(ttl=30, show_spinner=False)
def cotations(tickers: tuple[str, ...]) -> pd.DataFrame:
    return marche.cotations(list(tickers))


@st.cache_data(ttl=30, show_spinner=False)
def cours_actuels(tickers: tuple[str, ...]) -> dict[str, tuple]:
    """{ticker: (cours, devise)} : cotation groupée, puis requête individuelle pour les absents."""
    df = marche.cotations(list(tickers))
    res = {r.ticker: (r.cours, r.devise) for r in df.itertuples(index=False)}
    for t in tickers:
        if t not in res:
            res[t] = marche.dernier_cours(t)
    return res


@st.cache_data(ttl=30, show_spinner=False)
def top_mondial(nb: int = 50) -> pd.DataFrame:
    """Plus grosses capitalisations mondiales, classées en dollars, cours en direct."""
    import bourses
    df = marche.cotations(bourses.CANDIDATS_TOP)
    if df.empty:
        return df
    taux = marche.taux_vers(df["devise"].dropna().unique().tolist(), "USD")
    df["capi_usd"] = df["capitalisation"] * df["devise"].map(taux)
    df = df.dropna(subset=["capi_usd"]).sort_values("capi_usd", ascending=False).head(nb)
    df.insert(0, "rang", range(1, len(df) + 1))
    return df.reset_index(drop=True)


_TENDANCES: dict[str, tuple[float, list[float]]] = {}


def tendances(tickers: tuple[str, ...], jours: int = 30) -> dict[str, list[float]]:
    """Cours de clôture des 30 derniers jours (mini-graphiques). Mémorisés une heure par
    titre : ajouter un titre à une liste ne retélécharge que celui-ci."""
    maintenant = time.time()
    manquants = [t for t in tickers if t not in _TENDANCES or maintenant - _TENDANCES[t][0] > 3600]
    if manquants:
        debut = (pd.Timestamp.today() - pd.Timedelta(days=jours)).strftime("%Y-%m-%d")
        df = marche.historique(manquants, debut, False)
        for t in manquants:
            serie = df[t].dropna().round(4).tolist() if t in df.columns else []
            _TENDANCES[t] = (maintenant, serie)
    return {t: _TENDANCES[t][1] for t in tickers}


@st.cache_data(ttl=3600, show_spinner=False)
def recherche(texte: str) -> list[dict]:
    return marche.recherche(texte)


@st.cache_data(ttl=3600, show_spinner=False)
def cours_a_date(ticker: str, jour: str) -> float | None:
    """Cours de clôture du `jour` (ou du dernier jour de bourse précédent)."""
    d = pd.Timestamp(jour)
    df = marche.historique([ticker], (d - pd.Timedelta(days=10)).strftime("%Y-%m-%d"), False)
    if df.empty or ticker not in df.columns:
        return None
    serie = df[ticker].dropna()
    serie = serie[serie.index <= d]
    return float(serie.iloc[-1]) if not serie.empty else None


@st.cache_data(ttl=300, show_spinner=False)
def taux_change(devises: tuple[str, ...], base: str) -> dict[str, float]:
    return marche.taux_actuels(list(devises), base)


@st.cache_data(ttl=3600, show_spinner=False)
def histo(tickers: tuple[str, ...], debut: str, ajuste: bool) -> pd.DataFrame:
    return marche.historique(list(tickers), debut, ajuste)


@st.cache_data(ttl=3600, show_spinner=False)
def histo_change(devises: tuple[str, ...], base: str, debut: str) -> pd.DataFrame:
    return marche.historique_change(list(devises), base, debut)


@st.cache_data(ttl=86400, show_spinner=False)
def infos(ticker: str) -> dict:
    return marche.infos_titre(ticker)


@st.cache_data(ttl=60, show_spinner=False)
def histo_intraday(tickers: tuple[str, ...], periode: str, intervalle: str) -> pd.DataFrame:
    return marche.historique_intraday(list(tickers), periode, intervalle)


def patrimoine_intraday(p: dict | None, pat: dict, duree: pd.Timedelta, periode: str,
                        intervalle: str, pas: str) -> pd.Series:
    """Patrimoine net minute par minute (ou heure par heure) sur `duree` :
    comptes au dernier solde connu du jour + portefeuille valorisé aux cours intra-journée."""
    maintenant = pd.Timestamp.now().floor(pas)
    grille = pd.date_range(maintenant - duree, maintenant, freq=pas)
    jours = pd.DatetimeIndex(grille.normalize())
    hist = pat["hist"]
    if hist.empty:
        return pd.Series(dtype=float)

    autres = [c for c in hist.columns if c != "total" and c not in pat.get("categories_bourse", [])]
    autres_jour = hist[autres].sum(axis=1) if autres else pd.Series(0.0, index=hist.index)
    autres_jour = autres_jour + pat.get("especes_jour", pd.Series(0.0, index=hist.index)).reindex(hist.index).fillna(0.0)
    total = pd.Series(autres_jour.reindex(jours).ffill().fillna(0.0).values, index=grille)

    if p:
        tx = p["tx"]
        pos = p["positions"].groupby("ticker")[["cours", "taux_change"]].first()
        signe = tx["type"].map({"ACHAT": 1.0, "VENTE": -1.0}).fillna(0.0)
        q_jour = (tx.assign(q=tx["quantite"].astype(float) * signe, jour=tx["date"].dt.normalize())
                  .pivot_table(index="jour", columns="ticker", values="q", aggfunc="sum").cumsum())
        q = (q_jour.reindex(q_jour.index.union(jours.unique())).sort_index().ffill().fillna(0.0)
             .reindex(jours))
        tickers = [t for t in q.columns if (q[t] > 0).any()]
        if tickers:
            prix = histo_intraday(tuple(tickers), periode, intervalle)
            prix = prix[~prix.index.duplicated(keep="last")] if not prix.empty else prix
            prix = prix.reindex(prix.index.union(grille)).sort_index().ffill().reindex(grille) \
                if not prix.empty else pd.DataFrame(index=grille)
            for t in tickers:
                cours = prix[t] if t in prix.columns else pd.Series(float("nan"), index=grille)
                cours = cours.fillna(float(pos.at[t, "cours"]) if t in pos.index else 0.0)
                taux = float(pos.at[t, "taux_change"]) if t in pos.index else 1.0
                total += q[t].values * cours.values * taux
    # Le dernier point reprend la valeur en direct utilisée partout ailleurs.
    total.iloc[-1] = float(hist["total"].iloc[-1])
    return total


def titres_par_enveloppe() -> dict[str, list[str]]:
    """{enveloppe: tickers détenus (quantité > 0)}, calculé depuis les opérations (sans Internet)."""
    tx = db.lister_transactions()
    if tx.empty:
        return {}
    pos = calculs.calculer_positions(tx)
    pos = pos[pos["quantite"] > 1e-9]
    return {env: g["ticker"].tolist() for env, g in pos.groupby("enveloppe")}


def devise_base() -> str:
    return db.lire_parametre("devise_base")


def _taux_a_la_date(tx: pd.DataFrame, fx_hist: pd.DataFrame, fx_actuel: dict, base: str) -> list[float]:
    taux = []
    for r in tx.itertuples(index=False):
        valeur = 1.0 if r.devise == base else fx_actuel.get(r.devise, 1.0)
        if r.devise != base and not fx_hist.empty and r.devise in fx_hist.columns:
            serie = fx_hist[r.devise].dropna()
            serie = serie[serie.index <= r.date]
            if not serie.empty:
                valeur = float(serie.iloc[-1])
        taux.append(valeur)
    return taux


def charger_portefeuille() -> dict | None:
    """Positions valorisées en direct, historique, rendements, revenus. None si vide."""
    tx = db.lister_transactions()
    if tx.empty:
        return None
    base = devise_base()
    tickers = tuple(sorted(tx["ticker"].unique()))
    devises = tuple(sorted(tx["devise"].unique()))
    debut = (tx["date"].min() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")

    with st.spinner("Récupération des cours…"):
        cours = cours_actuels(tickers)
        fx_actuel = taux_change(devises, base)
        fx_hist = histo_change(devises, base, debut)
        prix_hist = histo(tickers, debut, False)

    tx["fx"] = _taux_a_la_date(tx, fx_hist, fx_actuel, base)
    positions = calculs.valoriser_positions(
        calculs.calculer_positions(tx), {t: c[0] for t, c in cours.items()}, fx_actuel)
    hist = calculs.historique_portefeuille(tx, prix_hist, fx_hist)
    hist_enveloppes = {env: calculs.historique_portefeuille(t, prix_hist, fx_hist)
                       for env, t in tx.groupby("enveloppe")}

    # Dividendes attendus sur 12 mois : dividende annuel annoncé × quantité détenue.
    positions["dividendes_attendus_base"] = [
        (infos(l.ticker).get("dividende_annuel") or 0.0) * l.quantite * l.taux_change if l.quantite > 0 else 0.0
        for l in positions.itertuples(index=False)]
    attendus = float(positions["dividendes_attendus_base"].sum())

    return {
        "tx": tx, "base": base, "positions": positions, "hist": hist, "hist_enveloppes": hist_enveloppes,
        "valeur": float(positions["valeur_base"].sum()),
        "xirr": calculs.xirr_portefeuille(tx, positions["valeur_base"].sum()),
        "xirr_titres": calculs.xirr_par_titre(tx, positions),
        "journal": calculs.journal_revenus(tx),
        "dividendes_attendus": attendus,
        "introuvables": [t for t, c in cours.items() if c[0] is None],
        "anciennete_jours": (pd.Timestamp.today() - tx["date"].min()).days,
    }


def charger_patrimoine(p: dict | None) -> dict:
    comptes = db.lister_comptes()
    soldes = db.lister_soldes()
    actuels = calculs.soldes_actuels(comptes, soldes)
    valeur_bourse = p["valeur"] if p else 0.0
    especes = series_especes()
    actuelles = {e: s for e, (s, _) in db.especes_actuelles().items()}
    valeurs = p["positions"].groupby("enveloppe")["valeur_base"].sum() if p else pd.Series(dtype=float)
    hist_env = p["hist_enveloppes"] if p else {}
    bourse = {}
    for env in sorted(set(hist_env) | set(especes)):
        # Valeur d'une enveloppe = titres + espèces non investies.
        titres = hist_env[env]["valeur"] if env in hist_env and not hist_env[env].empty else None
        cash = especes.get(env)
        serie = titres
        if cash is not None:
            morceaux = [s for s in (titres, cash) if s is not None]
            index = morceaux[0].index
            for s in morceaux[1:]:
                index = index.union(s.index)
            serie = sum(s.reindex(index).ffill().fillna(0.0) for s in morceaux)
        bourse[calculs.categorie_enveloppe(env)] = (serie, float(valeurs.get(env, 0.0)) + actuelles.get(env, 0.0))
    hist = calculs.historique_patrimoine(comptes, soldes, bourse)
    total_especes = pd.Series(0.0, index=hist.index)
    for s in especes.values():
        total_especes += s.reindex(hist.index).ffill().fillna(0.0)
    return {"comptes": comptes, "soldes": soldes, "actuels": actuels, "hist": hist,
            "valeur_bourse": valeur_bourse, "categories_bourse": list(bourse),
            "especes": actuelles, "especes_jour": total_especes}


def series_especes() -> dict[str, pd.Series]:
    """Espèces non investies de chaque enveloppe, au jour le jour (dernier relevé connu)."""
    df = db.lister_especes()
    aujourd_hui = pd.Timestamp.today().normalize()
    res = {}
    for env, g in df.groupby("enveloppe"):
        s = g.sort_values(["date", "id"]).groupby(g["date"].dt.normalize())["montant"].last()
        index = pd.date_range(s.index.min(), max(aujourd_hui, s.index.max()), freq="D")
        res[env] = s.reindex(index).ffill()
    return res


def avertir_introuvables(p: dict | None) -> None:
    if p and p["introuvables"]:
        st.warning("Cours indisponible pour : " + ", ".join(p["introuvables"]) +
                   ". Vérifiez le ticker (format Yahoo Finance, ex. MC.PA) ou votre connexion. "
                   "Ces lignes sont valorisées à leur prix de revient.")
