"""Page « Paramètres »."""

from __future__ import annotations

import streamlit as st

import db
import donnees
import mise_a_jour
import style


# ------------------------------------------------------------ mises à jour
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def verifier_mise_a_jour(_jeton: int = 0) -> dict:
    """Vérification en ligne, au plus une fois toutes les 6 heures (ou à la demande)."""
    return mise_a_jour.verifier()


def installer_mise_a_jour(res: dict) -> None:
    with st.spinner(f"Installation de la version {res['distante']}…"):
        try:
            fichiers = mise_a_jour.installer(res["manifeste"])
        except Exception as e:
            st.error(f"La mise à jour n'a pas pu être installée : {e} Votre version actuelle est conservée.")
            return
    st.cache_data.clear()
    mise_a_jour.recharger_modules()
    st.session_state["_maj_installee"] = (res["distante"], len(fichiers))
    st.rerun()


def bandeau_mise_a_jour() -> None:
    """Dans le menu latéral : signale une nouvelle version et l'installe en un clic."""
    if fait := st.session_state.pop("_maj_installee", None):
        st.toast(f"Version {fait[0]} installée ({fait[1]} fichier(s) mis à jour).")
    if not mise_a_jour.lire_source():
        return
    res = verifier_mise_a_jour(st.session_state.get("_jeton_maj", 0))
    if res.get("disponible"):
        st.markdown(f'<div class="enveloppe" style="margin-top:8px"><div class="enveloppe-nom">Mise à jour disponible'
                    f'</div><b>Version {res["distante"]}</b><div class="note">Vous avez la {res["locale"]}.</div></div>',
                    unsafe_allow_html=True)
        if res.get("notes"):
            with st.expander("Nouveautés"):
                st.markdown("\n".join(f"- {n}" for n in res["notes"]))
        if st.button("Mettre à jour", type="primary", key="btn_maj_lateral", width="stretch"):
            installer_mise_a_jour(res)


def encadre_version() -> None:
    """Dans le menu latéral : la version installée de l'application."""
    locale = mise_a_jour.version_locale()
    date = locale.get("date")
    st.markdown(f'<div class="version-appli"><img src="{style.logo_svg(icone_seule=True)}" alt="">'
                f'<div><div class="nom">{style.NOM_APPLI}</div>'
                f'<div class="note">Version {locale.get("version", "—")}' + (f" · {date}" if date else "")
                + "</div></div></div>", unsafe_allow_html=True)


def section_mises_a_jour() -> None:
    locale = mise_a_jour.version_locale()
    with style.verre("mises_a_jour"):
        st.markdown(f"**Mises à jour** · version installée : {locale.get('version', '—')}")
        source = mise_a_jour.lire_source()
        g, d = st.columns([3, 1], vertical_alignment="bottom")
        nouvelle = g.text_input("Source des mises à jour", value=source, key="source_maj",
                                placeholder="https://github.com/votre-nom/mesfinances",
                                help="Adresse du dépôt GitHub (public) où sont publiées les nouvelles versions.")
        if d.button("Enregistrer", key="btn_source_maj", width="stretch") and nouvelle.strip() != source:
            mise_a_jour.ecrire_source(nouvelle)
            verifier_mise_a_jour.clear()
            st.rerun()
        if not source:
            style.note("Aucune source configurée : l'application ne recherche pas de mises à jour.")
            return
        if st.button("Rechercher une mise à jour maintenant", key="btn_verifier_maj"):
            st.session_state["_jeton_maj"] = st.session_state.get("_jeton_maj", 0) + 1
        res = verifier_mise_a_jour(st.session_state.get("_jeton_maj", 0))
        if res.get("erreur"):
            st.warning(res["erreur"])
        elif res.get("disponible"):
            st.success(f"Version {res['distante']} disponible" + (f" (publiée le {res['date']})" if res.get("date") else ""))
            if res.get("notes"):
                st.markdown("\n".join(f"- {n}" for n in res["notes"]))
            if st.button(f"Installer la version {res['distante']}", type="primary", key="btn_installer_maj"):
                installer_mise_a_jour(res)
        else:
            st.success("Vous avez la dernière version.")
        style.note("Vos données ne sont jamais touchées par une mise à jour (elles sont dans Documents\\MesFinances). "
                   "Les fichiers remplacés sont sauvegardés dans le dossier _sauvegardes de l'application.")


def _styles_apercus() -> str:
    """Couleurs de texte des miniatures, par classes (Streamlit ignore les couleurs « !important » en ligne)."""
    regles = []
    for i, (nom, t) in enumerate(style.THEMES.items()):
        c = f".apercu-{i}"
        regles += [f"{c} .ap-texte {{ color: {t['TEXTE']} !important; }}",
                   f"{c} .ap-texte-2 {{ color: {t['TEXTE_2']} !important; font-size: 0.7rem; }}",
                   f"{c} .ap-pos {{ color: {t['VERT_TEXTE']} !important; font-size: 0.76rem; }}",
                   f"{c} .ap-neg {{ color: {t['ROUGE_TEXTE']} !important; font-size: 0.76rem; }}"]
    return "<style>" + "\n".join(regles) + "</style>"


def _apercu_theme(nom: str, actif: bool) -> str:
    """Miniature d'un thème : fond, carte, valeur, barre d'accent, variations vert/rouge, palette."""
    t = style.THEMES[nom]
    i = list(style.THEMES).index(nom)
    pastilles = "".join(f'<span style="background:{c}"></span>' for c in t["PALETTE"][:6])
    return (f'<div class="apercu-theme apercu-{i}{" actif" if actif else ""}" style="background:{t["FOND"]};'
            f'border:1px solid {t["BORD"]}">'
            f'<div style="background:{t["PANNEAU"]};border:1px solid {t["BORD"]};border-radius:10px;padding:9px 10px">'
            f'<div class="ligne-apercu"><span class="nom-apercu ap-texte">{nom}</span>'
            f'<span class="ap-texte-2">{"Clair" if t["CLAIR"] else "Sombre"}</span></div>'
            f'<div class="valeur-apercu ap-texte">24 580 €</div>'
            f'<span class="pilule ap-pos">▲ +2,45 %</span>'
            f'<span class="pilule ap-neg">▼ −1,10 %</span>'
            f'<div class="barre-apercu" style="background:linear-gradient(90deg,{t["ACCENT"]},{t["ACCENT_2"]})"></div>'
            f'<div class="pastilles">{pastilles}</div></div></div>')


def _choisir_theme(nom: str) -> None:
    db.ecrire_parametre("theme", nom)
    style.activer_theme(nom)


def page() -> None:
    st.title("Paramètres")
    with style.verre("theme"):
        st.markdown("**Thème de l'application**")
        noms = list(style.THEMES)
        actuel = db.lire_parametre("theme") or style.THEME_DEFAUT
        actuel = actuel if actuel in noms else style.THEME_DEFAUT
        par_ligne = 5
        st.markdown(_styles_apercus(), unsafe_allow_html=True)
        with st.container(key="grille_themes"):
            for debut in range(0, len(noms), par_ligne):
                colonnes = st.columns(par_ligne)
                for col, nom in zip(colonnes, noms[debut:debut + par_ligne]):
                    with col:
                        st.markdown(_apercu_theme(nom, nom == actuel), unsafe_allow_html=True)
                        st.button("✓ Thème actif" if nom == actuel else "Choisir", key=f"theme_{nom}",
                                  width="stretch", disabled=nom == actuel, on_click=_choisir_theme, args=(nom,))
        style.note("Les hausses et gains restent toujours en vert, les baisses et pertes en rouge, quel que soit "
                   "le thème.")
    with style.verre("parametres"):
        base = db.lire_parametre("devise_base")
        nouvelle_base = st.selectbox("Devise de référence", donnees.DEVISES,
                                     index=donnees.DEVISES.index(base) if base in donnees.DEVISES else 0,
                                     help="Tous les totaux sont convertis dans cette devise.")
        indice = st.text_input("Indice de référence par défaut", db.lire_parametre("indice_reference"),
                               help="Ticker Yahoo : ^FCHI (CAC 40), ^GSPC (S&P 500), URTH (MSCI World)…")
        cat_rev = st.text_area("Catégories de revenus (séparées par des virgules)",
                               db.lire_parametre("categories_revenus"))
        style.note("Les catégories de dépenses se gèrent dans Budget, onglet Mon plan.")
        if st.button("Enregistrer les paramètres", type="primary"):
            db.ecrire_parametre("devise_base", nouvelle_base)
            db.ecrire_parametre("indice_reference", indice.strip())
            db.ecrire_parametre("categories_revenus", cat_rev)
            st.cache_data.clear()
            st.toast("Paramètres enregistrés.")

    section_mises_a_jour()

    with style.verre("donnees"):
        st.markdown("**Données**")
        if st.button("Actualiser les cours maintenant"):
            st.cache_data.clear()
            st.toast("Les cours seront rechargés.")
        style.note(f"Vos données sont stockées localement dans {db.CHEMIN_DB}. "
                   "Copiez ce fichier pour faire une sauvegarde.")
