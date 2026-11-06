"""Récupération des cours de bourse et des taux de change via Yahoo Finance (yfinance).

Exemples de tickers Yahoo :
    Paris : MC.PA (LVMH), AIR.PA (Airbus), CW8.PA (ETF MSCI World)
    Francfort : SAP.DE    Amsterdam : ASML.AS    Londres : SHEL.L
    États-Unis : AAPL, MSFT    Indices : ^FCHI (CAC 40), ^GSPC (S&P 500)
    Crypto : BTC-EUR
"""

from __future__ import annotations

import pandas as pd
import yfinance as yf


def _normaliser_devise(prix: float | None, devise: str | None) -> tuple[float | None, str | None]:
    # Londres cote souvent en pence (GBp) : on convertit en livres.
    if devise == "GBp" and prix is not None:
        return prix / 100, "GBP"
    return prix, devise.upper() if devise else devise


def dernier_cours(ticker: str) -> tuple[float | None, str | None]:
    """Renvoie (dernier cours, devise). (None, None) si introuvable."""
    try:
        t = yf.Ticker(ticker)
        try:
            prix = t.fast_info.last_price
            devise = t.fast_info.currency
        except Exception:
            prix, devise = None, None
        if prix is None or pd.isna(prix):
            hist = t.history(period="5d")
            prix = float(hist["Close"].dropna().iloc[-1]) if not hist.empty else None
        if devise is None:
            devise = (t.info or {}).get("currency")
        return _normaliser_devise(float(prix) if prix is not None else None, devise)
    except Exception:
        return None, None


def _extraire_close(df: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        close = df["Close"]
    else:
        close = df[["Close"]].rename(columns={"Close": tickers[0]})
    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])
    close.index = pd.to_datetime(close.index)
    if close.index.tz is not None:
        close.index = close.index.tz_localize(None)
    close.index = close.index.normalize()
    return close.sort_index()


def historique(tickers: list[str], debut, ajuste: bool = False) -> pd.DataFrame:
    """Cours de clôture quotidiens (colonnes = tickers).
    ajuste=False : cours bruts (pour valoriser un portefeuille dont les dividendes
                   sont saisis à part) ;
    ajuste=True  : cours dividendes réinvestis (pour analyser la performance d'un titre)."""
    tickers = sorted(set(tickers))
    if not tickers:
        return pd.DataFrame()
    try:
        df = yf.download(tickers, start=pd.Timestamp(debut).strftime("%Y-%m-%d"),
                         auto_adjust=ajuste, progress=False, threads=True)
    except Exception:
        return pd.DataFrame()
    close = _extraire_close(df, tickers)
    # Conversion des titres cotés en pence.
    for t in close.columns:
        if str(t).endswith(".L"):
            _, devise = dernier_cours(t)
            if devise == "GBP":
                close[t] = close[t] / 100
    return close


def historique_intraday(tickers: list[str], periode: str, intervalle: str) -> pd.DataFrame:
    """Cours intra-journée (colonnes = tickers), index en heure locale de l'ordinateur (sans fuseau).
    Limites Yahoo : 1m sur 7 jours, 5m/30m sur 60 jours, 1h sur 730 jours."""
    from datetime import datetime

    tickers = sorted(set(tickers))
    if not tickers:
        return pd.DataFrame()
    try:
        df = yf.download(tickers, period=periode, interval=intervalle, auto_adjust=False,
                         progress=False, threads=True, prepost=False)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    close = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df[["Close"]].rename(
        columns={"Close": tickers[0]})
    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])
    close.index = pd.to_datetime(close.index)
    if close.index.tz is not None:
        close.index = close.index.tz_convert(datetime.now().astimezone().tzinfo).tz_localize(None)
    for t in close.columns:
        if str(t).endswith(".L") and dernier_cours(t)[1] == "GBP":
            close[t] = close[t] / 100  # cotation en pence
    return close.sort_index()


def symbole_change(devise: str, devise_base: str) -> str:
    return f"{devise}{devise_base}=X"


def taux_actuels(devises: list[str], devise_base: str) -> dict[str, float]:
    """{devise: taux vers devise_base}, ex. {"USD": 0.92, "EUR": 1.0}."""
    taux = {devise_base: 1.0}
    for d in set(devises) - {devise_base}:
        prix, _ = dernier_cours(symbole_change(d, devise_base))
        taux[d] = prix if prix else 1.0
    return taux


def historique_change(devises: list[str], devise_base: str, debut) -> pd.DataFrame:
    """Taux de change quotidiens vers la devise de référence (colonnes = devises)."""
    autres = sorted(set(devises) - {devise_base})
    if not autres:
        return pd.DataFrame()
    symboles = [symbole_change(d, devise_base) for d in autres]
    brut = historique(symboles, debut, ajuste=False)
    return brut.rename(columns={symbole_change(d, devise_base): d for d in autres})


# ------------------------------------------------- cotations en direct (lot)
URL_COTATIONS = "https://query1.finance.yahoo.com/v7/finance/quote"
COLONNES_COTATIONS = ["ticker", "nom", "devise", "cours", "variation", "variation_pct", "cloture_veille",
                      "capitalisation", "etat", "place", "fuseau", "heure", "type", "delai_min"]
# Cotations en centièmes d'unité (pence, cents sud-africains, agorot).
CENTIEMES = {"GBp": "GBP", "GBX": "GBP", "ZAc": "ZAR", "ILA": "ILS"}


def cotations(symboles: list[str]) -> pd.DataFrame:
    """Cours en direct (différé de 0 à 20 min selon la place) pour une liste de tickers,
    en une requête par lot de 50. Les tickers inconnus sont simplement absents."""
    from yfinance.data import YfData

    symboles = list(dict.fromkeys(s.strip().upper() for s in symboles if s and s.strip()))
    lignes: list[dict] = []
    for i in range(0, len(symboles), 50):
        lot = symboles[i:i + 50]
        try:
            r = YfData().get_raw_json(URL_COTATIONS, params={
                "symbols": ",".join(lot), "formatted": "false", "lang": "fr-FR", "region": "FR"})
            lignes += (r.get("quoteResponse") or {}).get("result") or []
        except Exception:
            continue

    res = []
    for q in lignes:
        prix = q.get("regularMarketPrice")
        if prix is None:
            continue
        devise = q.get("currency")
        diviseur = 1.0
        if devise in CENTIEMES:
            devise, diviseur = CENTIEMES[devise], 100.0
        heure = q.get("regularMarketTime")
        res.append({
            "ticker": q.get("symbol"),
            "nom": q.get("longName") or q.get("shortName") or q.get("symbol"),
            "devise": (devise or "").upper() or None,
            "cours": float(prix) / diviseur,
            "variation": float(q.get("regularMarketChange") or 0) / diviseur,
            "variation_pct": float(q.get("regularMarketChangePercent") or 0),
            "cloture_veille": (float(q["regularMarketPreviousClose"]) / diviseur
                               if q.get("regularMarketPreviousClose") else None),
            "capitalisation": float(q["marketCap"]) if q.get("marketCap") else None,
            "etat": q.get("marketState"),
            "place": q.get("fullExchangeName") or q.get("exchange"),
            "fuseau": q.get("exchangeTimezoneName"),
            "heure": pd.to_datetime(heure, unit="s", utc=True) if heure else pd.NaT,
            "type": q.get("quoteType"),
            "delai_min": q.get("exchangeDataDelayedBy"),
        })
    return pd.DataFrame(res, columns=COLONNES_COTATIONS)


def taux_vers(devises: list[str], cible: str = "USD") -> dict[str, float]:
    """{devise: taux de conversion vers `cible`} en une requête."""
    autres = sorted({d for d in devises if d and d != cible})
    taux = {cible: 1.0}
    if autres:
        df = cotations([symbole_change(d, cible) for d in autres])
        for d in autres:
            ligne = df[df["ticker"] == symbole_change(d, cible)]
            if not ligne.empty:
                taux[d] = float(ligne["cours"].iloc[0])
    return taux


def recherche(texte: str, nb: int = 15) -> list[dict]:
    """Recherche de titres par nom ou ticker (actions, ETF, indices, cryptos…), toutes places."""
    texte = (texte or "").strip()
    if len(texte) < 2:
        return []
    try:
        quotes = yf.Search(texte, max_results=nb, news_count=0, enable_fuzzy_query=True).quotes
    except Exception:
        return []
    return [{"ticker": q["symbol"], "nom": q.get("longname") or q.get("shortname") or q["symbol"],
             "place": q.get("exchDisp") or q.get("exchange") or "",
             "type": q.get("typeDisp") or q.get("quoteType") or ""}
            for q in quotes if q.get("symbol")]


def infos_titre(ticker: str) -> dict:
    """Nom et quelques informations descriptives (peut être lent)."""
    try:
        info = yf.Ticker(ticker).info or {}
        dividende = info.get("dividendRate") or info.get("trailingAnnualDividendRate")
        if dividende and info.get("currency") == "GBp":
            dividende = dividende / 100  # cotation en pence
        return {
            "dividende_annuel": float(dividende) if dividende else 0.0,
            "nom": info.get("longName") or info.get("shortName") or ticker,
            "devise": info.get("currency"),
            "place": info.get("exchange"),
            "secteur": info.get("sector"),
            "pays": info.get("country"),
            "per": info.get("trailingPE"),
            "rendement_dividende": info.get("dividendYield"),
            "capitalisation": info.get("marketCap"),
        }
    except Exception:
        return {"nom": ticker, "dividende_annuel": 0.0}
