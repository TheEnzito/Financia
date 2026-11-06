"""Page « Devises » : cours des monnaies en direct, graphique par paire et calculateur de change."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

import db
import donnees
import style
from style import fmt, fmt_pct

SANS_BARRE = {"displayModeBar": False}

MONNAIES = {
    "EUR": "Euro", "USD": "Dollar américain", "GBP": "Livre sterling", "CHF": "Franc suisse",
    "JPY": "Yen japonais", "CAD": "Dollar canadien", "AUD": "Dollar australien", "NZD": "Dollar néo-zélandais",
    "CNY": "Yuan chinois", "HKD": "Dollar de Hong Kong", "SGD": "Dollar de Singapour", "KRW": "Won sud-coréen",
    "INR": "Roupie indienne", "THB": "Baht thaïlandais", "SEK": "Couronne suédoise", "NOK": "Couronne norvégienne",
    "DKK": "Couronne danoise", "PLN": "Zloty polonais", "CZK": "Couronne tchèque", "HUF": "Forint hongrois",
    "RON": "Leu roumain", "TRY": "Livre turque", "MAD": "Dirham marocain", "TND": "Dinar tunisien",
    "ZAR": "Rand sud-africain", "AED": "Dirham des Émirats", "SAR": "Riyal saoudien", "ILS": "Shekel israélien",
    "BRL": "Real brésilien", "MXN": "Peso mexicain",
}
SUIVIES_DEFAUT = ["USD", "GBP", "CHF", "JPY", "CAD", "AUD", "CNY", "MAD"]
PERIODES = {"1 j": ("intraday", "5d", "5m", pd.Timedelta(days=1)),
            "1 sem.": ("intraday", "1mo", "30m", pd.Timedelta(weeks=1)),
            "1 mois": ("jour", pd.DateOffset(months=1)), "6 mois": ("jour", pd.DateOffset(months=6)),
            "1 an": ("jour", pd.DateOffset(years=1)), "5 ans": ("jour", pd.DateOffset(years=5))}
MONTANTS_RAPIDES = [1, 10, 50, 100, 500, 1000, 5000]


def nom(code: str) -> str:
    return f"{code} · {MONNAIES.get(code, code)}"


def dec_taux(v) -> int:
    """Décimales d'un taux : 4 pour les taux proches de 1, 2 pour les grands nombres (yen, won…)."""
    try:
        return 4 if abs(float(v)) < 20 else 2
    except (TypeError, ValueError):
        return 4


def devises_suivies(base: str) -> list[str]:
    brut = db.lire_parametre("devises_suivies")
    liste = [c for c in (brut.split(",") if brut else SUIVIES_DEFAUT) if c in MONNAIES]
    return [c for c in liste if c != base] or [c for c in SUIVIES_DEFAUT if c != base]


def taux(de: str, vers: str) -> tuple[float | None, float | None]:
    """(taux de → vers, variation du jour en %). Passe par le dollar si la paire directe n'est pas cotée."""
    if de == vers:
        return 1.0, 0.0
    direct = donnees.cotations((f"{de}{vers}=X",))
    if not direct.empty:
        return float(direct["cours"].iloc[0]), float(direct["variation_pct"].iloc[0])
    paires = donnees.cotations(tuple(p for p in (f"{de}USD=X", f"USD{vers}=X") if p[:3] != p[3:6]))
    valeurs = {r.ticker: (r.cours, r.variation_pct) for r in paires.itertuples(index=False)}
    a = valeurs.get(f"{de}USD=X", (1.0, 0.0)) if de != "USD" else (1.0, 0.0)
    b = valeurs.get(f"USD{vers}=X", (1.0, 0.0)) if vers != "USD" else (1.0, 0.0)
    if (de != "USD" and f"{de}USD=X" not in valeurs) or (vers != "USD" and f"USD{vers}=X" not in valeurs):
        return None, None
    return a[0] * b[0], ((1 + a[1] / 100) * (1 + b[1] / 100) - 1) * 100


# ----------------------------------------------------------------- calculateur
def _inverser() -> None:
    st.session_state["calc_de"], st.session_state["calc_vers"] = (st.session_state.get("calc_vers"),
                                                                  st.session_state.get("calc_de"))


def calculateur(base: str) -> None:
    codes = list(MONNAIES)
    st.session_state.setdefault("calc_de", base if base in codes else "EUR")
    st.session_state.setdefault("calc_vers", "USD" if base != "USD" else "EUR")
    with style.verre("calculateur_devises"):
        st.markdown("**Calculateur de change**")
        montant = st.number_input("Montant", min_value=0.0, value=100.0, step=10.0, format="%.2f",
                                  key="calc_montant")
        g, m, d = st.columns([4, 1.4, 4], vertical_alignment="bottom")
        de = g.selectbox("De", codes, key="calc_de", format_func=nom)
        m.button("⇄", key="calc_inverser", on_click=_inverser, help="Inverser les devises", width="stretch")
        vers = d.selectbox("Vers", codes, key="calc_vers", format_func=nom)
        frais = st.number_input("Frais de change (%)", min_value=0.0, max_value=20.0, value=0.0, step=0.1,
                                format="%.2f", key="calc_frais",
                                help="Commission ou marge de votre banque / bureau de change (souvent 1 à 3 %). "
                                     "Laissez 0 pour le cours officiel.")
        t, _ = taux(de, vers)
        if t is None:
            st.warning(f"Cours {de}/{vers} indisponible pour le moment.")
            return
        brut = montant * t
        net = brut * (1 - frais / 100)
        st.markdown(
            f'<div class="hero" style="margin:6px 0 8px">'
            f'<div class="hero-libelle">{html.escape(fmt(montant, de))} =</div>'
            f'<div class="hero-valeur">{html.escape(fmt(net, vers))}</div>'
            f'<div class="hero-pied">1 {de} = {fmt(t, dec=dec_taux(t))} {vers} · '
            f'1 {vers} = {fmt(1 / t, dec=dec_taux(1 / t))} {de}'
            + (f" · frais : {html.escape(fmt(brut - net, vers))} (sans frais : {html.escape(fmt(brut, vers))})"
               if frais else "") + "</div></div>", unsafe_allow_html=True)
        lignes = "".join(
            f"<tr><td>{fmt(a, de, 0)}</td><td>{fmt(a * t * (1 - frais / 100), vers)}</td>"
            f"<td>{fmt(a, vers, 0)}</td><td>{fmt(a / t * (1 - frais / 100), de)}</td></tr>"
            for a in MONTANTS_RAPIDES)
        st.markdown(f'<table class="conversions"><thead><tr><th>{de}</th><th>{vers}</th><th>{vers}</th>'
                    f'<th>{de}</th></tr></thead><tbody>{lignes}</tbody></table>', unsafe_allow_html=True)
        style.note("Cours Yahoo Finance (différé de quelques minutes). Le cours réellement obtenu dépend de votre "
                   "banque ou de votre bureau de change.")


# ------------------------------------------------------------------- graphique
def graphique_paire(base: str, devise: str, direct: float | None, var_jour: float | None) -> None:
    ticker = f"{base}{devise}=X"
    with style.verre("graphique_devises"):
        c1, c2 = st.columns([2, 3], vertical_alignment="center")
        c1.markdown(f"**{base} / {devise}** · {html.escape(MONNAIES.get(devise, devise))}")
        periode = c2.segmented_control("Période", list(PERIODES), default="1 mois", key="periode_devises",
                                       label_visibility="collapsed") or "1 mois"
        conf = PERIODES[periode]
        maintenant = pd.Timestamp.now()
        if conf[0] == "intraday":
            serie = donnees.histo_intraday((ticker,), conf[1], conf[2])
            serie = serie[ticker].dropna() if ticker in serie.columns else pd.Series(dtype=float)
            serie = serie[serie.index >= maintenant - conf[3]]
        else:
            debut = maintenant.normalize() - conf[1]
            serie = donnees.histo((ticker,), debut.strftime("%Y-%m-%d"), False)
            serie = serie[ticker].dropna() if ticker in serie.columns else pd.Series(dtype=float)
            serie = serie[serie.index >= debut]
            if direct is not None and len(serie):  # dernier point = cours en direct
                serie.index = pd.DatetimeIndex(serie.index).astype("datetime64[ns]")
                serie = pd.concat([serie, pd.Series([float(direct)],
                                                    index=pd.DatetimeIndex([maintenant]).astype("datetime64[ns]"))])
        if serie.empty:
            st.info("Historique indisponible pour cette période.")
            return
        dernier = float(direct if direct is not None else serie.iloc[-1])
        ecart = (dernier / float(serie.iloc[0]) - 1) * 100
        infos = [style.pilule(f"{fmt_pct(ecart)} sur {periode.lower()}", ecart)]
        if var_jour is not None:
            infos.insert(0, style.pilule(f"{fmt_pct(var_jour)} aujourd'hui", var_jour))
        st.markdown(f'<span class="hero-valeur" style="font-size:2rem">1 {base} = {fmt(dernier, dec=dec_taux(dernier))}'
                    f' {devise}</span><br>' + " ".join(infos), unsafe_allow_html=True)
        fig = style.courbe_cours(serie.index, serie.values, f"{base}/{devise}", ecart >= 0, 300)
        fig.update_traces(hovertemplate="%{x|%d/%m/%Y %H:%M} : %{y:.4f}<extra></extra>", selector=dict(name=f"{base}/{devise}"))
        fig.update_xaxes(tickformat={"1 j": "%H:%M", "5 ans": "%m/%Y"}.get(periode, "%d/%m"))
        st.plotly_chart(fig, config=SANS_BARRE, key="courbe_devise")
        style.note(f"Une hausse signifie que l'{'euro' if base == 'EUR' else base} se renforce face à "
                   f"{MONNAIES.get(devise, devise).lower()} : vos {base} valent plus de {devise}.")


# ----------------------------------------------------------------------- tableau
def _choisir_ligne() -> None:
    ev = st.session_state.get("tableau_devises")
    ordre = st.session_state.get("_ordre_devises", [])
    try:
        cellules = ev["selection"]["cells"] or []
        lignes = [c[0] for c in cellules] or list(ev["selection"]["rows"] or [])
    except (TypeError, KeyError):
        return
    if lignes and lignes[0] < len(ordre):
        st.session_state["paire_devises"] = ordre[lignes[0]]


def tableau_taux(base: str, suivies: list[str], cot: pd.DataFrame) -> None:
    with style.verre("taux_devises"):
        g, d = st.columns([3, 1], vertical_alignment="center")
        g.markdown(f"**Taux du jour** · pour 1 {base}")
        with d.popover("Mes devises", width="stretch"):
            choix = st.multiselect("Devises suivies", [c for c in MONNAIES if c != base], default=suivies,
                                   format_func=nom, key="choix_devises_suivies")
            if st.button("Enregistrer", type="primary", key="enregistrer_devises", width="stretch"):
                db.ecrire_parametre("devises_suivies", ",".join(choix))
                st.rerun()
        tickers = [f"{base}{c}=X" for c in suivies]
        tend = donnees.tendances(tuple(tickers))
        lignes = []
        for c, t in zip(suivies, tickers):
            r = cot[cot["ticker"] == t]
            cours = float(r["cours"].iloc[0]) if not r.empty else None
            lignes.append({"devise": nom(c), "taux": cours,
                           "inverse": (1 / cours) if cours else None,
                           "variation_pct": float(r["variation_pct"].iloc[0]) if not r.empty else None,
                           "tendance": tend.get(t) or None})
        aff = pd.DataFrame(lignes)
        st.session_state["_ordre_devises"] = suivies
        formats = {"taux": lambda v: fmt(v, dec=dec_taux(v)),
                   "inverse": lambda v: fmt(v, dec=dec_taux(v)) + f" {base}"}
        styler = style.tableau_gains(aff, ["variation_pct"], {**formats, "variation_pct": fmt_pct})
        st.dataframe(styler, hide_index=True, on_select=_choisir_ligne, selection_mode=style.SELECTION_CLIC,
                     key="tableau_devises", height=min(38 + 35 * len(aff), 740),
                     column_config={"devise": st.column_config.TextColumn("Devise", width="medium"),
                                    "taux": f"1 {base} =", "inverse": f"Inverse (1 unité en {base})",
                                    "variation_pct": "Variation du jour",
                                    "tendance": st.column_config.LineChartColumn("30 jours", width="small")})
        style.note("Cliquez sur une ligne pour afficher son graphique. Actualisé automatiquement chaque minute.")


# -------------------------------------------------------------------------- page
@st.fragment(run_every=donnees.ACTUALISATION_S)
def _en_direct(base: str, suivies: list[str]) -> None:
    cot = donnees.cotations(tuple(f"{base}{c}=X" for c in suivies))
    paire = st.session_state.get("paire_devises")
    if paire not in suivies:
        paire = suivies[0]
    r = cot[cot["ticker"] == f"{base}{paire}=X"]
    direct = float(r["cours"].iloc[0]) if not r.empty else None
    var_jour = float(r["variation_pct"].iloc[0]) if not r.empty else None
    g, d = st.columns([5, 7])
    with g:
        calculateur(base)
    with d:
        graphique_paire(base, paire, direct, var_jour)
    tableau_taux(base, suivies, cot)


def page() -> None:
    st.title("Devises")
    base = donnees.devise_base() or "EUR"
    _en_direct(base, devises_suivies(base))
