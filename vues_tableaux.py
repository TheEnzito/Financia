"""Vues de tableaux enregistrées : colonnes affichées (et leur ordre) et tri, mémorisés d'une session à l'autre.

Chaque tableau a une vue « Par défaut » (non modifiable) et autant de vues nommées que voulu. La dernière vue
choisie est retenue. Tout est stocké dans la base (paramètre « vues_tableaux », au format JSON).

Utilisation :
    vue = vues_tableaux.barre("positions", {"nom": "Titre", ...}, colonnes_par_defaut)
    df = vues_tableaux.trier(df, vue)
    st.dataframe(..., column_order=vue["colonnes"])
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

import db

DEFAUT = "Par défaut"
PARAMETRE = "vues_tableaux"


def _tout() -> dict:
    try:
        d = json.loads(db.lire_parametre(PARAMETRE) or "{}")
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def _sauver(d: dict) -> None:
    db.ecrire_parametre(PARAMETRE, json.dumps(d, ensure_ascii=False))


def _nettoyer(vue: dict, colonnes: dict, defaut: dict) -> dict:
    """Vue valide pour le tableau actuel (une colonne disparue depuis l'enregistrement est ignorée)."""
    cols = [c for c in vue.get("colonnes", []) if c in colonnes] or list(defaut["colonnes"])
    tri = vue.get("tri") if vue.get("tri") in colonnes else None
    return {"colonnes": cols, "tri": tri, "desc": bool(vue.get("desc", True))}


def _memoriser(cle_tableau: str, **changements) -> None:
    tout = _tout()
    t = tout.setdefault(cle_tableau, {})
    t.setdefault("vues", {})
    t.update(changements)
    _sauver(tout)


def barre(cle_tableau: str, colonnes: dict[str, str], defaut: list[str], tri_defaut: str | None = None,
          desc_defaut: bool = True, non_triables: tuple[str, ...] = ()) -> dict:
    """Affiche le choix de la vue et le bouton « Personnaliser » ; renvoie la vue à appliquer :
    {"colonnes": [...], "tri": colonne ou None, "desc": bool}.
    non_triables : colonnes qu'on ne peut pas trier (mini-graphiques…)."""
    k = f"vue_{cle_tableau}"
    t = _tout().get(cle_tableau, {})
    vues = t.get("vues", {}) if isinstance(t.get("vues"), dict) else {}
    noms = [DEFAUT] + sorted(vues, key=str.lower)
    vue_defaut = {"colonnes": [c for c in defaut if c in colonnes], "tri": tri_defaut, "desc": desc_defaut}

    # Vue à sélectionner (après un enregistrement ou une suppression), puis dernière vue utilisée.
    if (suivante := st.session_state.pop(f"{k}_suivante", None)) is not None:
        st.session_state[k] = suivante
    st.session_state.setdefault(k, t.get("active", DEFAUT))
    if st.session_state[k] not in noms:
        st.session_state[k] = DEFAUT

    def _changer() -> None:
        _memoriser(cle_tableau, active=st.session_state[k])

    g, d = st.columns([3, 2], vertical_alignment="center")
    choix = g.selectbox("Vue du tableau", noms, key=k, on_change=_changer, label_visibility="collapsed",
                        format_func=lambda n: f"Vue : {n}",
                        help="Vues enregistrées de ce tableau (colonnes et tri). La dernière choisie est retenue.")
    base = vue_defaut if choix == DEFAUT else _nettoyer(vues[choix], colonnes, vue_defaut)
    p = f"{k}_{choix}"  # les réglages repartent de la vue choisie quand on en change

    with d.popover("Personnaliser", icon=":material/tune:", width="stretch"):
        cols = st.multiselect("Colonnes affichées (dans l'ordre choisi)", list(colonnes), default=base["colonnes"],
                              format_func=lambda c: colonnes[c], key=f"{p}_colonnes",
                              help="Retirez une colonne pour la masquer ; ajoutez-la à nouveau pour la placer en fin.")
        options_tri = [None] + [c for c in colonnes if c not in non_triables]
        tri = st.selectbox("Trier par", options_tri,
                           index=options_tri.index(base["tri"]) if base["tri"] in options_tri else 0,
                           format_func=lambda c: "Ordre habituel" if c is None else colonnes[c], key=f"{p}_tri")
        desc = st.toggle("Du plus grand au plus petit", value=base["desc"], key=f"{p}_desc", disabled=tri is None)
        actuelle = {"colonnes": cols or base["colonnes"], "tri": tri, "desc": desc}
        modifiee = actuelle != base

        if choix != DEFAUT:
            if st.button(f"Enregistrer dans « {choix} »", key=f"{p}_maj", type="primary", disabled=not modifiee,
                         width="stretch"):
                tout = _tout()
                tout.setdefault(cle_tableau, {}).setdefault("vues", {})[choix] = actuelle
                _sauver(tout)
                st.toast(f"Vue « {choix} » mise à jour.")
                st.rerun()
        nom = st.text_input("Nouvelle vue", key=f"{k}_nom", placeholder="ex. Performance, Dividendes…",
                            max_chars=40).strip()
        if st.button("Enregistrer comme nouvelle vue", key=f"{p}_creer", disabled=not nom or nom == DEFAUT,
                     width="stretch", type="secondary" if choix != DEFAUT else "primary"):
            tout = _tout()
            tout.setdefault(cle_tableau, {}).setdefault("vues", {})[nom] = actuelle
            tout[cle_tableau]["active"] = nom
            _sauver(tout)
            st.session_state[f"{k}_suivante"] = nom
            st.session_state.pop(f"{k}_nom", None)
            st.toast(f"Vue « {nom} » enregistrée.")
            st.rerun()
        if choix != DEFAUT and st.button("Supprimer cette vue", key=f"{p}_suppr", icon=":material/delete:",
                                         width="stretch"):
            tout = _tout()
            tout.get(cle_tableau, {}).get("vues", {}).pop(choix, None)
            tout.setdefault(cle_tableau, {})["active"] = DEFAUT
            _sauver(tout)
            st.session_state[f"{k}_suivante"] = DEFAUT
            st.rerun()
        if modifiee:
            st.caption("Modifications appliquées au tableau, pas encore enregistrées.")
    return actuelle


def trier(df: pd.DataFrame, vue: dict) -> pd.DataFrame:
    """Applique le tri de la vue (les valeurs manquantes en dernier)."""
    if vue.get("tri") and vue["tri"] in df.columns:
        return df.sort_values(vue["tri"], ascending=not vue.get("desc", True), na_position="last", kind="stable")
    return df
