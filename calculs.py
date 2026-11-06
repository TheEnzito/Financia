"""Calculs financiers : positions, PRU, plus-values, XIRR, TWR, statistiques de cours, budget.

Ce module ne dépend ni de Streamlit ni d'Internet : il ne fait que des calculs
sur des DataFrames, ce qui permet de le tester facilement.

Format attendu des transactions (DataFrame) :
    date (datetime), type ("ACHAT" | "VENTE" | "DIVIDENDE"), ticker (str),
    quantite (float), prix (float, dans la devise du titre), frais (float),
    devise (str, ex. "EUR", "USD")
Pour un dividende : quantite = nombre de titres (ou 1), prix = montant par titre
(ou montant total si quantite = 1), frais = retenue à la source / taxes.
"""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd

TYPES_TRANSACTION = ("ACHAT", "VENTE", "DIVIDENDE")
ENVELOPPE_DEFAUT = "Compte-titres"
JOURS_BOURSE_AN = 252


# --------------------------------------------------------------------------
# Positions et prix de revient
# --------------------------------------------------------------------------
def calculer_positions(tx: pd.DataFrame) -> pd.DataFrame:
    """Calcule, pour chaque titre, la quantité détenue, le PRU (prix de revient
    unitaire, frais d'achat inclus, méthode du coût moyen pondéré), la plus-value
    réalisée et les dividendes nets. Montants dans la devise du titre."""
    colonnes = ["enveloppe", "ticker", "devise", "quantite", "pru", "cout_revient",
                "pv_realisee", "dividendes", "frais", "investi_brut"]
    if tx is None or tx.empty:
        return pd.DataFrame(columns=colonnes)

    # Une position par (enveloppe, titre) : le même titre en PEA et en compte-titres
    # a deux prix de revient distincts.
    positions: dict[tuple[str, str], dict] = {}
    for t in tx.sort_values("date", kind="stable").itertuples(index=False):
        enveloppe = getattr(t, "enveloppe", None) or ENVELOPPE_DEFAUT
        p = positions.setdefault((enveloppe, t.ticker), dict(
            enveloppe=enveloppe, ticker=t.ticker, devise=t.devise, quantite=0.0, pru=0.0,
            pv_realisee=0.0, dividendes=0.0, frais=0.0, investi_brut=0.0))
        q, prix, frais = float(t.quantite), float(t.prix), float(t.frais or 0)

        if t.type == "ACHAT":
            cout = q * prix + frais
            nouvelle_q = p["quantite"] + q
            p["pru"] = (p["quantite"] * p["pru"] + cout) / nouvelle_q if nouvelle_q else 0.0
            p["quantite"] = nouvelle_q
            p["investi_brut"] += cout
        elif t.type == "VENTE":
            q_vendue = min(q, p["quantite"])
            p["pv_realisee"] += q_vendue * (prix - p["pru"]) - frais
            p["quantite"] -= q_vendue
            if p["quantite"] < 1e-9:
                p["quantite"], p["pru"] = 0.0, 0.0
        elif t.type == "DIVIDENDE":
            p["dividendes"] += q * prix - frais
        p["frais"] += frais

    df = pd.DataFrame(list(positions.values()))
    df["cout_revient"] = df["quantite"] * df["pru"]
    return df[colonnes]


def valoriser_positions(positions: pd.DataFrame, cours: dict[str, float | None],
                        fx: dict[str, float]) -> pd.DataFrame:
    """Ajoute le cours actuel, la valeur, la plus-value latente et les montants
    convertis dans la devise de référence.
    cours : {ticker: dernier cours (devise du titre) ou None si indisponible}
    fx    : {devise: taux de conversion vers la devise de référence}"""
    df = positions.copy()
    if df.empty:
        for c in ["cours", "cours_disponible", "valeur", "pv_latente", "pv_latente_pct",
                  "taux_change", "valeur_base", "cout_revient_base", "pv_latente_base",
                  "pv_realisee_base", "dividendes_base", "gain_total_base", "poids_pct"]:
            df[c] = []
        return df

    df["cours_disponible"] = df["ticker"].map(lambda t: cours.get(t) is not None)
    # Si le cours est indisponible, on retombe sur le PRU pour ne pas fausser les totaux.
    df["cours"] = [cours.get(t) if cours.get(t) is not None else pru
                   for t, pru in zip(df["ticker"], df["pru"])]
    df["valeur"] = df["quantite"] * df["cours"]
    df["pv_latente"] = df["valeur"] - df["cout_revient"]
    df["pv_latente_pct"] = np.where(df["cout_revient"] > 0,
                                    df["pv_latente"] / df["cout_revient"] * 100, 0.0)
    df["taux_change"] = df["devise"].map(lambda d: fx.get(d, 1.0))
    for col in ["valeur", "cout_revient", "pv_latente", "pv_realisee", "dividendes"]:
        df[f"{col}_base"] = df[col] * df["taux_change"]
    df["gain_total_base"] = df["pv_latente_base"] + df["pv_realisee_base"] + df["dividendes_base"]
    total = df["valeur_base"].sum()
    df["poids_pct"] = df["valeur_base"] / total * 100 if total > 0 else 0.0
    return df


# --------------------------------------------------------------------------
# Rendement annualisé (XIRR / TRI)
# --------------------------------------------------------------------------
def xirr(flux: list[tuple[date | datetime | pd.Timestamp, float]]) -> float | None:
    """Taux de rendement interne annualisé de flux datés (équivalent de
    TRI.PAIEMENTS / XIRR dans un tableur). Convention : sorties d'argent de
    votre poche négatives (achats), entrées positives (ventes, dividendes,
    valeur actuelle). Renvoie un taux (0.08 = 8 %/an) ou None."""
    flux = [(pd.Timestamp(d), float(m)) for d, m in flux if m and not np.isnan(m)]
    if len(flux) < 2:
        return None
    montants = np.array([m for _, m in flux])
    if not (montants.min() < 0 < montants.max()):
        return None
    t0 = min(d for d, _ in flux)
    annees = np.array([(d - t0).days / 365.0 for d, _ in flux])

    def van(r: float) -> float:
        return float(np.sum(montants / (1.0 + r) ** annees))

    # Recherche d'un changement de signe sur une grille, puis dichotomie.
    grille = np.concatenate([np.linspace(-0.99, 1, 200), np.linspace(1.05, 100, 200)])
    valeurs = [van(r) for r in grille]
    for i in range(len(grille) - 1):
        if np.sign(valeurs[i]) != np.sign(valeurs[i + 1]):
            bas, haut = grille[i], grille[i + 1]
            for _ in range(200):
                milieu = (bas + haut) / 2
                if np.sign(van(milieu)) == np.sign(van(bas)):
                    bas = milieu
                else:
                    haut = milieu
                if haut - bas < 1e-10:
                    break
            return (bas + haut) / 2
    return None


def flux_investisseur(tx: pd.DataFrame, colonne_fx: str | None = None) -> list[tuple]:
    """Transforme les transactions en flux du point de vue de l'investisseur."""
    flux = []
    for t in tx.itertuples(index=False):
        taux = getattr(t, colonne_fx) if colonne_fx else 1.0
        montant = float(t.quantite) * float(t.prix)
        frais = float(t.frais or 0)
        if t.type == "ACHAT":
            flux.append((t.date, -(montant + frais) * taux))
        else:  # VENTE ou DIVIDENDE
            flux.append((t.date, (montant - frais) * taux))
    return flux


def xirr_portefeuille(tx: pd.DataFrame, valeur_actuelle_base: float,
                      colonne_fx: str = "fx") -> float | None:
    """XIRR global en devise de référence. tx doit contenir une colonne avec le
    taux de change à la date de chaque transaction."""
    if tx.empty:
        return None
    flux = flux_investisseur(tx, colonne_fx)
    flux.append((pd.Timestamp.today().normalize(), valeur_actuelle_base))
    return xirr(flux)


def xirr_par_titre(tx: pd.DataFrame, positions_valorisees: pd.DataFrame) -> dict[tuple[str, str], float | None]:
    """XIRR de chaque ligne (clé : (enveloppe, ticker)), dans la devise du titre."""
    resultat = {}
    aujourd_hui = pd.Timestamp.today().normalize()
    env_tx = tx["enveloppe"] if "enveloppe" in tx.columns else pd.Series(ENVELOPPE_DEFAUT, index=tx.index)
    for ligne in positions_valorisees.itertuples(index=False):
        enveloppe = getattr(ligne, "enveloppe", ENVELOPPE_DEFAUT)
        flux = flux_investisseur(tx[(tx["ticker"] == ligne.ticker) & (env_tx == enveloppe)])
        if ligne.valeur > 0:
            flux.append((aujourd_hui, ligne.valeur))
        resultat[(enveloppe, ligne.ticker)] = xirr(flux)
    return resultat


# --------------------------------------------------------------------------
# Historique du portefeuille et TWR
# --------------------------------------------------------------------------
def _date_de_bourse(index: pd.DatetimeIndex, d: pd.Timestamp) -> pd.Timestamp:
    """Premier jour de cotation >= d (ou le dernier disponible)."""
    pos = index.searchsorted(pd.Timestamp(d).normalize())
    return index[min(pos, len(index) - 1)]


def historique_portefeuille(tx: pd.DataFrame, prix_hist: pd.DataFrame,
                            fx_hist: pd.DataFrame) -> pd.DataFrame:
    """Valeur quotidienne du portefeuille en devise de référence.

    prix_hist : index = dates, colonnes = tickers (cours de clôture, devise du titre)
    fx_hist   : index = dates, colonnes = devises (taux vers la devise de référence)

    Renvoie un DataFrame avec : valeur, apports (achats), retraits (ventes et
    dividendes), investi_net (cumul apports - retraits), rendement_jour, twr_cumule.
    Le TWR (rendement pondéré dans le temps) neutralise l'effet des montants
    ajoutés ou retirés : il mesure la qualité des placements eux-mêmes."""
    if tx.empty or prix_hist.empty:
        return pd.DataFrame()

    index = prix_hist.index
    prix = prix_hist.sort_index().ffill()
    fx = fx_hist.reindex(index).ffill().bfill() if not fx_hist.empty else pd.DataFrame(index=index)
    devise_titre = tx.groupby("ticker")["devise"].last().to_dict()

    signes = {"ACHAT": 1.0, "VENTE": -1.0, "DIVIDENDE": 0.0}
    tx = tx.copy()
    tx["jour"] = [_date_de_bourse(index, d) for d in tx["date"]]
    tx["q_signee"] = tx["quantite"].astype(float) * tx["type"].map(signes)
    tx["taux"] = [fx.at[j, devise_titre[t]] if devise_titre[t] in fx.columns else 1.0
                  for j, t in zip(tx["jour"], tx["ticker"])]
    brut = tx["quantite"].astype(float) * tx["prix"].astype(float)
    frais = tx["frais"].astype(float).fillna(0)
    tx["apport"] = np.where(tx["type"] == "ACHAT", (brut + frais) * tx["taux"], 0.0)
    tx["retrait"] = np.where(tx["type"] != "ACHAT", (brut - frais) * tx["taux"], 0.0)

    quantites = (tx.pivot_table(index="jour", columns="ticker", values="q_signee", aggfunc="sum")
                 .reindex(index).fillna(0).cumsum())
    valeur = pd.Series(0.0, index=index)
    for ticker in quantites.columns:
        if ticker not in prix.columns:
            continue
        devise = devise_titre[ticker]
        taux = fx[devise] if devise in fx.columns else 1.0
        valeur += (quantites[ticker] * prix[ticker] * taux).fillna(0)

    apports = tx.groupby("jour")["apport"].sum().reindex(index).fillna(0)
    retraits = tx.groupby("jour")["retrait"].sum().reindex(index).fillna(0)

    # Apports supposés en début de journée, retraits en fin de journée.
    valeur_veille = valeur.shift(1).fillna(0)
    denominateur = valeur_veille + apports
    rendement = pd.Series(
        np.where(denominateur > 0, (valeur + retraits) / denominateur.where(denominateur > 0, 1) - 1, 0.0),
        index=index)

    hist = pd.DataFrame({
        "valeur": valeur,
        "apports": apports,
        "retraits": retraits,
        "investi_net": (apports - retraits).cumsum(),
        "rendement_jour": rendement,
    })
    hist["twr_cumule"] = (1 + hist["rendement_jour"]).cumprod() - 1
    return hist


def twr_annualise(hist: pd.DataFrame) -> float | None:
    if hist.empty:
        return None
    jours = (hist.index[-1] - hist.index[0]).days
    total = hist["twr_cumule"].iloc[-1]
    if jours < 1:
        return None
    return (1 + total) ** (365.0 / jours) - 1


# --------------------------------------------------------------------------
# Statistiques sur un cours de bourse
# --------------------------------------------------------------------------
def moyennes_mobiles(cours: pd.Series, fenetres=(50, 200)) -> pd.DataFrame:
    df = pd.DataFrame({"cours": cours})
    for f in fenetres:
        df[f"MM{f}"] = cours.rolling(f).mean()
    return df


def drawdown(cours: pd.Series) -> pd.Series:
    """Baisse en % par rapport au plus haut précédent."""
    return (cours / cours.cummax() - 1) * 100


def _cours_a_date(cours: pd.Series, d: pd.Timestamp) -> float | None:
    avant = cours[cours.index <= d]
    return float(avant.iloc[-1]) if not avant.empty else None


def statistiques_titre(cours: pd.Series) -> dict[str, float | None]:
    """Performances par période, volatilité, perte maximale, etc. (en %)."""
    cours = cours.dropna()
    if len(cours) < 2:
        return {}
    dernier = float(cours.iloc[-1])
    fin = cours.index[-1]

    def perf(debut: pd.Timestamp, annualiser: float | None = None):
        if debut < cours.index[0]:
            return None
        ref = _cours_a_date(cours, debut)
        if not ref:
            return None
        p = dernier / ref - 1
        if annualiser:
            p = (1 + p) ** (1 / annualiser) - 1
        return p * 100

    rend = np.log(cours / cours.shift(1)).dropna()
    rend_1an = rend[rend.index > fin - pd.DateOffset(years=1)]
    vol = float(rend_1an.std() * np.sqrt(JOURS_BOURSE_AN) * 100) if len(rend_1an) > 20 else None
    perf_1an = perf(fin - pd.DateOffset(years=1))

    return {
        "Dernier cours": dernier,
        "Perf. 1 mois (%)": perf(fin - pd.DateOffset(months=1)),
        "Perf. 3 mois (%)": perf(fin - pd.DateOffset(months=3)),
        "Perf. 6 mois (%)": perf(fin - pd.DateOffset(months=6)),
        "Perf. depuis le 1er janvier (%)": perf(pd.Timestamp(year=fin.year, month=1, day=1) - pd.Timedelta(days=1)),
        "Perf. 1 an (%)": perf_1an,
        "Perf. 3 ans annualisée (%)": perf(fin - pd.DateOffset(years=3), annualiser=3),
        "Perf. 5 ans annualisée (%)": perf(fin - pd.DateOffset(years=5), annualiser=5),
        "Volatilité 1 an (%)": vol,
        "Ratio perf./volatilité 1 an": (perf_1an / vol) if (perf_1an is not None and vol and vol > 0.5) else None,
        "Perte max. sur la période (%)": float(drawdown(cours).min()),
        "Plus haut sur la période": float(cours.max()),
        "Plus bas sur la période": float(cours.min()),
    }


def base_100(prix: pd.DataFrame) -> pd.DataFrame:
    """Normalise plusieurs séries à 100 au premier jour commun, pour comparer."""
    prix = prix.dropna(how="all").ffill().dropna()
    if prix.empty:
        return prix
    return prix / prix.iloc[0] * 100


# --------------------------------------------------------------------------
# Budget
# --------------------------------------------------------------------------
def synthese_mensuelle(mouvements: pd.DataFrame) -> pd.DataFrame:
    """Revenus, dépenses, épargne et taux d'épargne par mois."""
    if mouvements.empty:
        return pd.DataFrame(columns=["mois", "revenus", "depenses", "epargne", "taux_epargne_pct"])
    df = mouvements.copy()
    df["mois"] = df["date"].dt.to_period("M").astype(str)
    piv = df.pivot_table(index="mois", columns="type", values="montant", aggfunc="sum").fillna(0)
    revenus = piv["REVENU"] if "REVENU" in piv else 0.0
    depenses = piv["DEPENSE"] if "DEPENSE" in piv else 0.0
    out = pd.DataFrame({"revenus": revenus, "depenses": depenses}, index=piv.index)
    out["epargne"] = out["revenus"] - out["depenses"]
    out["taux_epargne_pct"] = np.where(out["revenus"] > 0, out["epargne"] / out["revenus"] * 100, np.nan)
    return out.reset_index()


def depenses_par_categorie(mouvements: pd.DataFrame) -> pd.DataFrame:
    dep = mouvements[mouvements["type"] == "DEPENSE"]
    if dep.empty:
        return pd.DataFrame(columns=["categorie", "montant"])
    return (dep.groupby("categorie", as_index=False)["montant"].sum()
            .sort_values("montant", ascending=False))


# --------------------------------------------------------------------------
# Revenus des placements (dividendes et plus-values réalisées, datés)
# --------------------------------------------------------------------------
def journal_revenus(tx: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par dividende ou vente, avec le gain en devise de référence
    (colonne fx utilisée si présente)."""
    lignes, pru, qte = [], {}, {}
    if tx is None or tx.empty:
        return pd.DataFrame(columns=["date", "ticker", "nature", "montant_base"])
    for t in tx.sort_values("date", kind="stable").itertuples(index=False):
        taux = getattr(t, "fx", 1.0)
        q, prix, frais = float(t.quantite), float(t.prix), float(t.frais or 0)
        p, n = pru.get(t.ticker, 0.0), qte.get(t.ticker, 0.0)
        if t.type == "ACHAT":
            pru[t.ticker] = (n * p + q * prix + frais) / (n + q) if n + q else 0.0
            qte[t.ticker] = n + q
        elif t.type == "VENTE":
            qv = min(q, n)
            lignes.append((t.date, t.ticker, "Plus-values réalisées", (qv * (prix - p) - frais) * taux))
            qte[t.ticker] = n - qv
        else:
            lignes.append((t.date, t.ticker, "Dividendes", (q * prix - frais) * taux))
    return pd.DataFrame(lignes, columns=["date", "ticker", "nature", "montant_base"])


def revenus_mensuels(journal: pd.DataFrame, nb_mois: int = 24) -> pd.DataFrame:
    """Tableau mois × nature (Dividendes, Plus-values réalisées)."""
    mois = pd.period_range(end=pd.Timestamp.today().to_period("M"), periods=nb_mois, freq="M")
    if journal.empty:
        return pd.DataFrame(0.0, index=mois.astype(str), columns=["Dividendes", "Plus-values réalisées"])
    j = journal.copy()
    j["mois"] = j["date"].dt.to_period("M")
    piv = j.pivot_table(index="mois", columns="nature", values="montant_base", aggfunc="sum")
    piv = piv.reindex(mois).fillna(0.0)
    for c in ["Dividendes", "Plus-values réalisées"]:
        if c not in piv.columns:
            piv[c] = 0.0
    piv.index = piv.index.astype(str)
    return piv[["Dividendes", "Plus-values réalisées"]]


def versement_mensuel_moyen(tx: pd.DataFrame, nb_mois: int = 12) -> float:
    """Argent net placé en bourse par mois (achats − ventes) sur la période récente."""
    if tx is None or tx.empty:
        return 0.0
    limite = pd.Timestamp.today() - pd.DateOffset(months=nb_mois)
    r = tx[tx["date"] >= limite]
    taux = r["fx"] if "fx" in r.columns else 1.0
    montant = (r["quantite"] * r["prix"]) * taux
    frais = r["frais"].fillna(0) * taux
    achats = (montant + frais)[r["type"] == "ACHAT"].sum()
    ventes = (montant - frais)[r["type"] == "VENTE"].sum()
    return max(0.0, float(achats - ventes) / nb_mois)


# --------------------------------------------------------------------------
# Patrimoine total
# --------------------------------------------------------------------------
CATEGORIE_BOURSE = "Bourse (portefeuille)"


def soldes_actuels(comptes: pd.DataFrame, soldes: pd.DataFrame) -> pd.DataFrame:
    """Dernier solde connu de chaque compte (les dettes sont comptées en négatif)."""
    if comptes.empty:
        return pd.DataFrame(columns=["id", "nom", "categorie", "taux_annuel", "solde", "date", "valeur"])
    derniers = (soldes.sort_values("date").groupby("compte_id").last()[["montant", "date"]]
                if not soldes.empty else pd.DataFrame(columns=["montant", "date"]))
    df = comptes.merge(derniers, left_on="id", right_index=True, how="left")
    df = df.rename(columns={"montant": "solde"})
    df["solde"] = df["solde"].fillna(0.0)
    df["valeur"] = np.where(df["categorie"] == "Dettes", -df["solde"].abs(), df["solde"])
    return df


def categorie_enveloppe(enveloppe: str) -> str:
    """Catégorie de patrimoine d'une enveloppe boursière, ex. « Bourse · PEA »."""
    return f"Bourse · {enveloppe}"


def historique_patrimoine(comptes: pd.DataFrame, soldes: pd.DataFrame,
                          bourse: dict[str, tuple[pd.Series | None, float]] | None = None) -> pd.DataFrame:
    """Valeur quotidienne de chaque catégorie d'actifs et du patrimoine net.
    Entre deux relevés, un compte garde son dernier solde connu.
    bourse : {catégorie (ex. « Bourse · PEA ») : (historique de valeur, valeur actuelle en direct)}."""
    aujourd_hui = pd.Timestamp.today().normalize()
    bourse = {k: v for k, v in (bourse or {}).items() if (v[0] is not None and not v[0].empty) or v[1]}
    debuts = []
    if soldes is not None and not soldes.empty:
        debuts.append(soldes["date"].min())
    debuts += [serie.index.min() for serie, _ in bourse.values() if serie is not None and not serie.empty]
    if not debuts:
        if bourse:
            df = pd.DataFrame({k: [v[1]] for k, v in bourse.items()}, index=pd.DatetimeIndex([aujourd_hui]))
            df["total"] = df.sum(axis=1)
            return df
        return pd.DataFrame()
    index = pd.date_range(min(debuts).normalize(), aujourd_hui, freq="D")
    df = pd.DataFrame(index=index)

    if soldes is not None and not soldes.empty:
        categorie = comptes.set_index("id")["categorie"].to_dict()
        for compte_id, s in soldes.groupby("compte_id"):
            serie = s.groupby(s["date"].dt.normalize())["montant"].last().reindex(index).ffill().fillna(0.0)
            cat = categorie.get(compte_id, "Autres actifs")
            if cat == "Dettes":
                serie = -serie.abs()
            df[cat] = df[cat] + serie if cat in df.columns else serie

    for cat, (serie, actuelle) in bourse.items():
        if serie is not None and not serie.empty:
            b = serie.copy()
            b.index = pd.to_datetime(b.index).normalize()
            df[cat] = b.groupby(level=0).last().reindex(index).ffill().fillna(0.0)
        else:
            df[cat] = 0.0
        df.loc[aujourd_hui, cat] = actuelle  # cours en direct
    df["total"] = df.sum(axis=1)
    return df


# --------------------------------------------------------------------------
# Projection « revenus sûrs » : dividendes annoncés + intérêts des livrets
# --------------------------------------------------------------------------
def projeter_revenus(bourse: float, rendement_dividende: float, comptes_remuneres: list[tuple[str, float, float]],
                     autres: float, annees: int, reinvestir: bool = True, hausse_cours: float = 0.0,
                     versement_mensuel: float = 0.0, versement_epargne: float = 0.0) -> pd.DataFrame:
    """Simulation mois par mois, sans hypothèse de marché par défaut (hausse_cours = 0) :
    seuls les dividendes (au rendement actuel) et les intérêts des comptes rémunérés font grossir
    le patrimoine. Les intérêts des livrets sont capitalisés chaque année, comme en France.
    comptes_remuneres : [(nom, solde, taux annuel en %)]
    reinvestir        : dividendes réinvestis en bourse (sinon conservés en liquidités)
    versement_mensuel : ajouté chaque mois à la bourse
    versement_epargne : ajouté chaque mois aux comptes rémunérés, au prorata de leur solde
                        (en liquidités s'il n'y en a pas)."""
    rc = (1 + hausse_cours) ** (1 / 12) - 1
    debut = pd.Timestamp.today().normalize()
    P = float(bourse)
    soldes = [float(s) for _, s, _ in comptes_remuneres]
    taux = [float(t) / 100 for _, _, t in comptes_remuneres]
    courus = [0.0] * len(soldes)          # intérêts acquis, versés au 31 décembre
    total_soldes = sum(soldes)
    parts = [s / total_soldes for s in soldes] if total_soldes > 0 else []
    liquidites, div_cumul, int_cumul, verse = 0.0, 0.0, 0.0, 0.0
    def rythme() -> float:  # revenu annuel au rythme du moment (dividendes + intérêts)
        return P * rendement_dividende + sum(s * t for s, t in zip(soldes, taux))

    lignes = [(debut, P, sum(soldes), liquidites, autres, 0.0, 0.0, 0.0, 0.0, 0.0, rythme())]
    for m in range(1, int(annees * 12) + 1):
        date_m = debut + pd.DateOffset(months=m)
        div = P * rendement_dividende / 12
        P = P * (1 + rc) + versement_mensuel
        if reinvestir:
            P += div
        else:
            liquidites += div
        interets = 0.0
        for i in range(len(soldes)):
            gain = soldes[i] * taux[i] / 12
            courus[i] += gain
            interets += gain
        if date_m.month == 1:  # capitalisation annuelle des intérêts
            for i in range(len(soldes)):
                soldes[i] += courus[i]
                courus[i] = 0.0
        if versement_epargne:
            if parts:
                for i in range(len(soldes)):
                    soldes[i] += versement_epargne * parts[i]
            else:
                liquidites += versement_epargne
        div_cumul += div
        int_cumul += interets
        verse += versement_mensuel + versement_epargne
        lignes.append((date_m, P, sum(soldes) + sum(courus), liquidites, autres, div, interets,
                       div_cumul, int_cumul, verse, rythme()))
    df = pd.DataFrame(lignes, columns=["date", "bourse", "epargne", "liquidites", "autres", "dividendes_mois",
                                       "interets_mois", "dividendes_cumules", "interets_cumules",
                                       "verse_cumule", "revenu_annuel"]).set_index("date")
    df["total"] = df["bourse"] + df["epargne"] + df["liquidites"] + df["autres"]
    return df


# --------------------------------------------------------------------------
# Projections
# --------------------------------------------------------------------------
def projeter(placements: float, epargne: float, autres: float,
             versement_placements: float, versement_epargne: float,
             hausse_annuelle: float, rendement_dividende: float, taux_epargne: float,
             annees: int, dividendes: str = "reinvestis", inflation: float = 0.0) -> pd.DataFrame:
    """Simulation mois par mois.
    hausse_annuelle      : progression annuelle des cours, hors dividendes (0.05 = 5 %)
    rendement_dividende  : dividendes annuels / valeur des placements
    taux_epargne         : rémunération annuelle de l'épargne
    dividendes           : "reinvestis" | "epargne" (versés sur l'épargne) | "depenses" (consommés)
    inflation            : si > 0, les montants sont exprimés en euros d'aujourd'hui."""
    rp = (1 + hausse_annuelle) ** (1 / 12) - 1
    re = (1 + taux_epargne) ** (1 / 12) - 1
    debut = pd.Timestamp.today().normalize()
    P, E = float(placements), float(epargne)
    verse, recus = 0.0, 0.0
    lignes = [(debut, P, E, autres, P * rendement_dividende, 0.0, 0.0, 0.0)]
    for m in range(1, int(annees * 12) + 1):
        div = P * rendement_dividende / 12
        P = P * (1 + rp) + versement_placements
        E = E * (1 + re) + versement_epargne
        if dividendes == "reinvestis":
            P += div
        elif dividendes == "epargne":
            E += div
        verse += versement_placements + versement_epargne
        recus += div
        d = (1 + inflation) ** (m / 12)
        lignes.append((debut + pd.DateOffset(months=m), P / d, E / d, autres / d,
                       P * rendement_dividende / d, div / d, verse / d, recus / d))
    df = pd.DataFrame(lignes, columns=["date", "placements", "epargne", "autres", "dividendes_annuels",
                                       "dividendes_mois", "verse_cumule", "dividendes_cumules"]).set_index("date")
    df["total"] = df["placements"] + df["epargne"] + df["autres"]
    return df


def premiere_date(projection: pd.DataFrame, condition: pd.Series) -> pd.Timestamp | None:
    ok = projection.index[condition.values]
    return ok[0] if len(ok) else None


# --------------------------------------------------------------------------
# Dépenses : tendances et plan
# --------------------------------------------------------------------------
def depenses_mois_categorie(mouvements: pd.DataFrame, nb_mois: int = 12) -> pd.DataFrame:
    """Tableau mois × catégorie des dépenses, mois sans dépense inclus (dernier mois = mois en cours)."""
    mois = pd.period_range(end=pd.Timestamp.today().to_period("M"), periods=nb_mois, freq="M")
    dep = mouvements[mouvements["type"] == "DEPENSE"] if not mouvements.empty else mouvements
    if dep is None or dep.empty:
        return pd.DataFrame(index=mois.astype(str))
    dep = dep.assign(mois=dep["date"].dt.to_period("M"))
    piv = dep.pivot_table(index="mois", columns="categorie", values="montant", aggfunc="sum")
    piv = piv.reindex(mois).fillna(0.0)
    piv.index = piv.index.astype(str)
    piv = piv[piv.sum().sort_values(ascending=False).index]
    return piv


def _libelle_tendance(pente_pct: float | None) -> str:
    if pente_pct is None or pente_pct != pente_pct:
        return "–"
    if pente_pct > 3:
        return "↗ En hausse"
    if pente_pct < -3:
        return "↘ En baisse"
    return "→ Stable"


def tendances_categories(piv: pd.DataFrame) -> pd.DataFrame:
    """Pour chaque catégorie : moyenne des mois complets, dernier mois complet,
    mois en cours, écart du dernier mois à la moyenne, tendance (pente de la droite
    de régression, en % de la moyenne par mois) et historique pour mini-graphique."""
    if piv.empty or piv.shape[1] == 0:
        return pd.DataFrame()
    complets = piv.iloc[:-1] if len(piv) > 1 else piv
    lignes = []
    for cat in piv.columns:
        s = complets[cat]
        moyenne = float(s.mean())
        pente = float(np.polyfit(np.arange(len(s)), s.values, 1)[0]) if len(s) >= 3 else np.nan
        pente_pct = pente / moyenne * 100 if moyenne > 0 else np.nan
        dernier = float(s.iloc[-1])
        lignes.append({
            "categorie": cat,
            "historique": [float(v) for v in piv[cat].values],
            "moyenne": moyenne,
            "dernier_mois": dernier,
            "mois_en_cours": float(piv[cat].iloc[-1]),
            "ecart_pct": (dernier / moyenne - 1) * 100 if moyenne > 0 else np.nan,
            "pente_pct": pente_pct,
            "tendance": _libelle_tendance(pente_pct),
        })
    return pd.DataFrame(lignes)


def tendance_globale(piv: pd.DataFrame, fenetre: int = 3) -> float | None:
    """Variation en % entre la moyenne des `fenetre` derniers mois complets et celle
    des `fenetre` mois complets précédents."""
    if piv.empty:
        return None
    total = piv.sum(axis=1).iloc[:-1]
    if len(total) < 2 * fenetre:
        return None
    recent, avant = total.iloc[-fenetre:].mean(), total.iloc[-2 * fenetre:-fenetre].mean()
    return (recent / avant - 1) * 100 if avant > 0 else None


def moyenne_mois_complets(mouvements: pd.DataFrame, colonne: str, nb_mois: int = 6) -> float:
    """Moyenne mensuelle (revenus, depenses ou epargne) sur les derniers mois complets."""
    s = synthese_mensuelle(mouvements)
    if s.empty:
        return 0.0
    en_cours = pd.Timestamp.today().strftime("%Y-%m")
    s = s[s["mois"] < en_cours].tail(nb_mois)
    return float(s[colonne].mean()) if not s.empty else 0.0


REGLE_50_30_20 = {"Besoins": 0.50, "Envies": 0.30, "Épargne": 0.20}


def proposer_50_30_20(plan: pd.DataFrame, revenu: float, moyennes: dict[str, float]) -> pd.DataFrame:
    """Répartit le revenu : 50 % besoins, 30 % envies, 20 % épargne. Dans chaque
    groupe, au prorata des dépenses habituelles (ou à parts égales sans historique)."""
    plan = plan.copy()
    for groupe, part in REGLE_50_30_20.items():
        masque = plan["groupe"] == groupe
        if not masque.any():
            continue
        poids = plan.loc[masque, "categorie"].map(lambda c: moyennes.get(c, 0.0)).astype(float)
        if poids.sum() <= 0:
            poids = pd.Series(1.0, index=poids.index)
        plan.loc[masque, "montant"] = (revenu * part * poids / poids.sum()).round(0)
    return plan


def suivi_plan(plan: pd.DataFrame, mouvements: pd.DataFrame, mois: str) -> pd.DataFrame:
    """Prévu / dépensé / reste par catégorie pour un mois (format AAAA-MM)."""
    dep = mouvements[(mouvements["type"] == "DEPENSE") &
                     (mouvements["date"].dt.strftime("%Y-%m") == mois)] if not mouvements.empty else mouvements
    depense = dep.groupby("categorie")["montant"].sum() if dep is not None and not dep.empty else pd.Series(dtype=float)
    df = plan[["categorie", "groupe", "montant"]].rename(columns={"montant": "prevu"}).copy()
    hors_plan = [c for c in depense.index if c not in set(df["categorie"])]
    if hors_plan:
        df = pd.concat([df, pd.DataFrame({"categorie": hors_plan, "groupe": "Envies", "prevu": 0.0})],
                       ignore_index=True)
    df["depense"] = df["categorie"].map(depense).fillna(0.0)
    df["reste"] = df["prevu"] - df["depense"]
    return df
