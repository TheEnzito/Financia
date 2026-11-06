"""Données de référence des marchés : places boursières (horaires) et listes de titres.

Ce module ne dépend ni de Streamlit ni d'Internet.
Les compositions d'indices évoluent : elles servent de point de départ et restent
modifiables dans l'application (page Marchés → Mes listes).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


# ======================================================== places boursières
@dataclass(frozen=True)
class Place:
    nom: str
    indice: str                                 # ticker Yahoo d'un indice de la place
    fuseau: str
    seances: tuple[tuple[str, str], ...]        # heures locales (ouverture, fermeture)
    jours: tuple[int, ...] = (0, 1, 2, 3, 4)    # 0 = lundi


PLACES = [
    Place("New York (NYSE, Nasdaq)", "^GSPC", "America/New_York", (("09:30", "16:00"),)),
    Place("Toronto", "^GSPTSE", "America/Toronto", (("09:30", "16:00"),)),
    Place("São Paulo", "^BVSP", "America/Sao_Paulo", (("10:00", "17:00"),)),
    Place("Londres", "^FTSE", "Europe/London", (("08:00", "16:30"),)),
    Place("Paris", "^FCHI", "Europe/Paris", (("09:00", "17:30"),)),
    Place("Francfort", "^GDAXI", "Europe/Berlin", (("09:00", "17:30"),)),
    Place("Zurich", "^SSMI", "Europe/Zurich", (("09:00", "17:30"),)),
    Place("Riyad", "^TASI.SR", "Asia/Riyadh", (("10:00", "15:00"),), (6, 0, 1, 2, 3)),
    Place("Bombay", "^NSEI", "Asia/Kolkata", (("09:15", "15:30"),)),
    Place("Shanghai", "000001.SS", "Asia/Shanghai", (("09:30", "11:30"), ("13:00", "15:00"))),
    Place("Hong Kong", "^HSI", "Asia/Hong_Kong", (("09:30", "12:00"), ("13:00", "16:00"))),
    Place("Taïwan", "^TWII", "Asia/Taipei", (("09:00", "13:30"),)),
    Place("Séoul", "^KS11", "Asia/Seoul", (("09:00", "15:30"),)),
    Place("Tokyo", "^N225", "Asia/Tokyo", (("09:00", "11:30"), ("12:30", "15:30"))),
    Place("Sydney", "^AXJO", "Australia/Sydney", (("10:00", "16:00"),)),
]


NOMS_INDICES = {
    "^GSPC": "S&P 500", "^GSPTSE": "S&P/TSX", "^BVSP": "Ibovespa", "^FTSE": "FTSE 100", "^FCHI": "CAC 40",
    "^GDAXI": "DAX", "^SSMI": "SMI", "^TASI.SR": "TASI", "^NSEI": "Nifty 50", "000001.SS": "SSE Composite",
    "^HSI": "Hang Seng", "^TWII": "TAIEX", "^KS11": "KOSPI", "^N225": "Nikkei 225", "^AXJO": "ASX 200",
}


def _heure(texte: str) -> time:
    h, m = texte.split(":")
    return time(int(h), int(m))


def _intervalles(place: Place, autour: datetime) -> list[tuple[datetime, datetime]]:
    """Séances de la veille à J+9, en heure locale de la place."""
    tz = ZoneInfo(place.fuseau)
    local = autour.astimezone(tz)
    res = []
    for k in range(-1, 10):
        jour = (local + timedelta(days=k)).date()
        if jour.weekday() not in place.jours:
            continue
        for o, f in place.seances:
            res.append((datetime.combine(jour, _heure(o), tz), datetime.combine(jour, _heure(f), tz)))
    return res


def _duree(delta: timedelta) -> str:
    minutes = max(int(delta.total_seconds() // 60), 0)
    j, reste = divmod(minutes, 1440)
    h, m = divmod(reste, 60)
    if j:
        return f"{j} j {h} h"
    return f"{h} h {m:02d}" if h else f"{m} min"


def statut_place(place: Place, maintenant: datetime, etat_yahoo: str | None = None,
                 fuseau_utilisateur=None) -> dict:
    """État d'une place à l'instant `maintenant` (datetime avec fuseau).

    Les horaires viennent du calendrier ci-dessus ; l'état renvoyé par Yahoo pour
    l'indice de la place (REGULAR = séance en cours) permet de repérer les jours fériés."""
    tz = ZoneInfo(place.fuseau)
    chez_vous = fuseau_utilisateur or maintenant.astimezone().tzinfo
    local = maintenant.astimezone(tz)
    intervalles = _intervalles(place, maintenant)
    courant = next((iv for iv in intervalles if iv[0] <= local < iv[1]), None)
    suivants = [iv for iv in intervalles if iv[0] > local]

    if courant and etat_yahoo and etat_yahoo != "REGULAR" and local - courant[0] > timedelta(minutes=30):
        # En principe ouvert, mais Yahoo indique une place fermée : jour férié.
        suivants = [iv for iv in suivants if iv[0].date() > local.date()]
        courant, etat = None, "Férié"
    elif courant:
        etat = "Ouvert"
    elif suivants and suivants[0][0].date() == local.date() and any(
            iv[1] <= local and iv[1].date() == local.date() for iv in intervalles):
        etat = "Pause"
    else:
        etat = "Fermé"

    if courant:
        evenement = f"ferme dans {_duree(courant[1] - local)}"
    elif suivants:
        prochaine = suivants[0][0]
        quand = prochaine.astimezone(chez_vous)
        jours_fr = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
        jour = "" if quand.date() == maintenant.astimezone(chez_vous).date() else f"{jours_fr[quand.weekday()]} "
        evenement = f"ouvre dans {_duree(prochaine - local)} ({jour}{quand:%H:%M})"
    else:
        evenement = ""

    # Horaires de la séance du jour (ou de la prochaine), affichés aussi à l'heure de l'utilisateur.
    reference = local.date() if local.weekday() in place.jours else (suivants[0][0].date() if suivants else local.date())
    seances_jour = [iv for iv in intervalles if iv[0].date() == reference] or intervalles[:len(place.seances)]
    debut, fin = seances_jour[0][0], seances_jour[-1][1]
    pause = ""
    if len(seances_jour) > 1:
        pause = f"pause {seances_jour[0][1]:%H:%M}–{seances_jour[1][0]:%H:%M}"
    return {
        "nom": place.nom, "indice": place.indice, "etat": etat, "ouvert": etat == "Ouvert",
        "evenement": evenement,
        "horaires_locaux": f"{debut:%H:%M}–{fin:%H:%M}",
        "horaires_chez_vous": f"{debut.astimezone(chez_vous):%H:%M}–{fin.astimezone(chez_vous):%H:%M}",
        "pause": pause,
        "heure_locale": f"{local:%H:%M}",
    }


# ===================================================== titres de référence
# Grandes capitalisations mondiales (cotation principale). Le classement « Top 50 »
# est recalculé en direct à partir de leur capitalisation convertie en dollars.
CANDIDATS_TOP = [
    # États-Unis
    "AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "AVGO", "TSLA", "BRK-B", "LLY", "JPM", "V",
    "WMT", "ORCL", "MA", "XOM", "NFLX", "COST", "JNJ", "PLTR", "HD", "PG", "ABBV", "BAC", "AMD",
    "UNH", "KO", "GE", "CVX", "CSCO", "IBM", "MU", "CRM", "WFC", "MS", "GS", "PM", "AMAT", "TMUS",
    "MRK", "ABT", "LIN", "LRCX", "INTC", "CAT", "AXP", "RTX", "MCD", "PEP", "TMO", "ISRG", "UBER",
    "NOW", "INTU", "C", "BX", "SCHW", "KLAC", "APP", "ANET", "TXN", "QCOM", "BKNG", "DIS", "ADBE",
    # Europe
    "ASML.AS", "SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE", "MC.PA", "RMS.PA", "OR.PA", "TTE.PA", "SU.PA",
    "AIR.PA", "SAN.PA", "ROP.SW", "NESN.SW", "NOVN.SW", "AZN.L", "SHEL.L", "HSBA.L", "ULVR.L",
    "NOVO-B.CO", "ITX.MC", "SAN.MC", "UCG.MI", "RACE.MI",
    # Asie-Pacifique, Moyen-Orient, Amériques
    "2330.TW", "2454.TW", "2317.TW", "005930.KS", "000660.KS", "0700.HK", "9988.HK", "1398.HK",
    "0939.HK", "1288.HK", "3690.HK", "1810.HK", "0941.HK", "600519.SS", "300750.SZ", "601318.SS",
    "7203.T", "8306.T", "6758.T", "6501.T", "9984.T", "8035.T", "RELIANCE.NS", "HDFCBANK.NS",
    "TCS.NS", "BHARTIARTL.NS", "ICICIBANK.NS", "2222.SR", "1120.SR", "CBA.AX", "BHP.AX",
    "RY.TO", "SHOP.TO", "MELI", "NU",
]

CAC40 = [
    "AC.PA", "AI.PA", "AIR.PA", "MT.AS", "CS.PA", "BNP.PA", "EN.PA", "BVI.PA", "CAP.PA", "CA.PA",
    "ACA.PA", "BN.PA", "DSY.PA", "EDEN.PA", "ENGI.PA", "EL.PA", "ERF.PA", "RMS.PA", "KER.PA",
    "LR.PA", "OR.PA", "MC.PA", "ML.PA", "ORA.PA", "RI.PA", "PUB.PA", "RNO.PA", "SAF.PA", "SGO.PA",
    "SAN.PA", "SU.PA", "GLE.PA", "STLAP.PA", "STMPA.PA", "TEP.PA", "HO.PA", "TTE.PA", "URW.PA",
    "VIE.PA", "DG.PA",
]

NASDAQ100 = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "COST", "NFLX", "PLTR", "ASML",
    "AMD", "CSCO", "TMUS", "AZN", "LIN", "INTU", "PEP", "ISRG", "BKNG", "AMGN", "TXN", "QCOM",
    "ADBE", "AMAT", "HON", "GILD", "ARM", "LRCX", "MU", "PANW", "KLAC", "ADP", "CMCSA", "SHOP",
    "APP", "CRWD", "MELI", "ADI", "SBUX", "INTC", "VRTX", "CEG", "DASH", "CDNS", "SNPS", "ORLY",
    "MAR", "MSTR", "CTAS", "PDD", "ABNB", "MDLZ", "FTNT", "WDAY", "REGN", "CSX", "ROP", "ADSK",
    "AEP", "NXPI", "PYPL", "CHTR", "MNST", "PCAR", "AXON", "TRI", "IDXX", "FAST", "PAYX", "ROST",
    "ZS", "KDP", "BKR", "TTWO", "CPRT", "EXC", "XEL", "DDOG", "CCEP", "VRSK", "FANG", "TEAM",
    "CTSH", "GEHC", "LULU", "KHC", "ODFL", "MCHP", "CSGP", "DXCM", "BIIB", "ON", "TTD",
    "CDW", "GFS", "MRVL",
]

# Principales cryptomonnaies, cotées en euros (classées en direct par capitalisation).
CRYPTOS = [
    "BTC-EUR", "ETH-EUR", "USDT-EUR", "XRP-EUR", "BNB-EUR", "SOL-EUR", "USDC-EUR", "TRX-EUR", "DOGE-EUR",
    "XMR-EUR", "LINK-EUR", "ADA-EUR", "BCH-EUR", "XLM-EUR", "UNI7083-EUR", "LTC-EUR", "AVAX-EUR", "HBAR-EUR",
    "SHIB-EUR", "AAVE-EUR", "DOT-EUR", "ICP-EUR", "ETC-EUR", "POL28321-EUR", "ALGO-EUR", "ATOM-EUR", "FIL-EUR",
]

# ETF par émetteur (tickers Yahoo vérifiés ; tous les autres ETF restent accessibles par la recherche).
ETF = {
    "Amundi": [
        "CW8.PA", "EWLD.PA", "DCAM.PA", "MWRD.PA", "WLD.PA", "PAEEM.PA", "AEEM.PA", "PAASI.PA", "500.PA",
        "PSP5.PA", "PE500.PA", "CU2.PA", "ANX.PA", "PUST.PA", "PANX.PA", "RS2K.PA", "C40.PA", "CAC.PA",
        "C50.PA", "MSE.PA", "MEUD.PA", "CEU.PA", "PCEU.PA", "MMS.PA", "CI2.PA", "OBLI.PA", "GOLD.PA",
        "LQQ.PA", "CL2.PA",
    ],
    "Éligibles PEA": [
        "CW8.PA", "EWLD.PA", "DCAM.PA", "PSP5.PA", "PE500.PA", "ESE.PA", "PUST.PA", "PANX.PA", "CU2.PA",
        "PAEEM.PA", "PAASI.PA", "PCEU.PA", "ETZ.PA", "C40.PA", "CAC.PA", "OBLI.PA", "LQQ.PA", "CL2.PA",
    ],
    "iShares": ["IWDA.AS", "EUNL.DE", "IUSQ.DE", "SXR8.DE", "CSPX.L", "SXRV.DE", "QDVE.DE", "IS3N.DE",
                "EIMI.L", "IVV"],
    "Vanguard": ["VWCE.DE", "VWRL.AS", "VUAA.DE", "VUSA.AS", "VEUR.AS", "VFEM.AS", "VT", "VOO", "VTI"],
    "Autres": ["XDWD.DE", "XMME.DE", "SPPW.DE", "ESE.PA", "ETZ.PA", "SPY", "QQQ", "SCHD", "GLD", "ARKK"],
}

TYPES_ACTIFS = {"EQUITY": "Action", "ETF": "ETF", "CRYPTOCURRENCY": "Crypto", "MUTUALFUND": "Fonds",
                "INDEX": "Indice", "CURRENCY": "Devise", "FUTURE": "Contrat à terme"}

LISTES_DE_DEPART = {"Favoris": [], "CAC 40": CAC40, "NASDAQ 100": NASDAQ100}
