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


def _changer_theme() -> None:
    nom = st.session_state.get("choix_theme")
    if nom:
        db.ecrire_parametre("theme", nom)
        style.activer_theme(nom)


def _apercu_theme(nom: str) -> str:
    t = style.THEMES[nom]
    pastilles = "".join(f'<span style="display:inline-block;width:18px;height:18px;border-radius:50%;'
                        f'background:{c};margin-right:4px;border:1px solid {t["BORD"]}"></span>'
                        for c in [t["FOND"], t["PANNEAU_2"], t["ACCENT"], t["PALETTE"][1], style.VERT, style.ROUGE])
    return (f'<div style="background:{t["PANNEAU"]};border:1px solid {t["BORD"]};border-radius:10px;padding:10px 12px;'
            f'margin-bottom:6px"><b style="color:{t["TEXTE"]} !important">{nom}</b>'
            f'<div style="margin-top:6px">{pastilles}</div>'
            f'<span class="pilule pos">▲ +2,45 %</span> <span class="pilule neg">▼ −1,10 %</span></div>')


def page() -> None:
    st.title("Paramètres")
    with style.verre("theme"):
        st.markdown("**Thème de l'application**")
        noms = list(style.THEMES)
        actuel = db.lire_parametre("theme") or style.THEME_DEFAUT
        colonnes = st.columns(len(noms))
        for col, nom in zip(colonnes, noms):
            col.markdown(_apercu_theme(nom), unsafe_allow_html=True)
        st.segmented_control("Thème", noms, default=actuel if actuel in noms else noms[0], key="choix_theme",
                             on_change=_changer_theme, label_visibility="collapsed")
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
