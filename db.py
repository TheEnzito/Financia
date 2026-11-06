"""Stockage local dans un fichier SQLite (finances.db).

Emplacement :
- version .exe : Documents/MesFinances/finances.db (survit aux mises à jour du programme) ;
- lancement par `streamlit run app.py` : à côté de app.py ;
- dans tous les cas, la variable d'environnement MES_FINANCES_DB peut imposer un autre chemin.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd


def _chemin_db() -> Path:
    if os.environ.get("MES_FINANCES_DB"):
        return Path(os.environ["MES_FINANCES_DB"]).expanduser()
    if getattr(sys, "frozen", False):  # exécutable construit avec PyInstaller
        dossier = Path.home() / "Documents" / "MesFinances"
        dossier.mkdir(parents=True, exist_ok=True)
        return dossier / "finances.db"
    return Path(__file__).with_name("finances.db")


CHEMIN_DB = _chemin_db()

PARAMETRES_DEFAUT = {
    "devise_base": "EUR",
    "indice_reference": "^FCHI",
    "categories": "Logement,Alimentation,Transport,Santé,Loisirs,Abonnements,"
                  "Shopping,Voyages,Impôts,Épargne,Autre",
    "categories_revenus": "Salaire,Prime,Revenus locatifs,Remboursement,Autre",
    "revenu_prevu": "0",
    "groupes_budget": "Besoins,Envies,Épargne",
    "theme": "Sombre",
}
ENVELOPPE_DEFAUT = "Compte-titres"

CATEGORIES_PATRIMOINE = ["Comptes courants", "Épargne", "Placements hors application",
                         "Immobilier", "Crypto", "Autres actifs", "Dettes"]
GROUPES_BUDGET = ["Besoins", "Envies", "Épargne"]  # groupes de départ ; l'utilisateur peut en créer d'autres
GROUPE_EPARGNE = "Épargne"  # groupe réservé : l'argent mis de côté (exclu des dépenses dans les comparaisons)
GROUPE_PAR_DEFAUT = {
    "Logement": "Besoins", "Alimentation": "Besoins", "Transport": "Besoins", "Santé": "Besoins",
    "Impôts": "Besoins", "Abonnements": "Besoins", "Loisirs": "Envies", "Shopping": "Envies",
    "Voyages": "Envies", "Autre": "Envies", "Épargne": "Épargne",
}


def _connexion() -> sqlite3.Connection:
    return sqlite3.connect(CHEMIN_DB)


def initialiser() -> None:
    with _connexion() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('ACHAT','VENTE','DIVIDENDE')),
                ticker TEXT NOT NULL,
                quantite REAL NOT NULL,
                prix REAL NOT NULL,
                frais REAL NOT NULL DEFAULT 0,
                devise TEXT NOT NULL DEFAULT 'EUR',
                note TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS budget (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('DEPENSE','REVENU','VIREMENT')),
                categorie TEXT NOT NULL,
                montant REAL NOT NULL,
                description TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS comptes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                categorie TEXT NOT NULL,
                taux_annuel REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS soldes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                compte_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                montant REAL NOT NULL,
                UNIQUE (compte_id, date)
            );
            CREATE TABLE IF NOT EXISTS budget_plan (
                categorie TEXT PRIMARY KEY,
                groupe TEXT NOT NULL DEFAULT 'Besoins',
                montant REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS parametres (
                cle TEXT PRIMARY KEY,
                valeur TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS regles_budget (
                type TEXT NOT NULL,
                cle TEXT NOT NULL,
                categorie TEXT NOT NULL,
                PRIMARY KEY (type, cle)
            );
            CREATE TABLE IF NOT EXISTS enveloppes (
                nom TEXT PRIMARY KEY,
                cree_le TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS especes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                enveloppe TEXT NOT NULL,
                date TEXT NOT NULL,
                montant REAL NOT NULL,
                UNIQUE (enveloppe, date)
            );
            CREATE TABLE IF NOT EXISTS listes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS liste_titres (
                liste_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                ajoute_le TEXT NOT NULL,
                PRIMARY KEY (liste_id, ticker)
            );
        """)
        # Enveloppe fiscale de chaque opération (PEA, compte-titres…), ajoutée après coup.
        if "enveloppe" not in [r[1] for r in c.execute("PRAGMA table_info(transactions)")]:
            c.execute(f"ALTER TABLE transactions ADD COLUMN enveloppe TEXT NOT NULL DEFAULT '{ENVELOPPE_DEFAUT}'")
        # Type « VIREMENT » (entre vos propres comptes) : la contrainte de l'ancienne table l'interdisait,
        # on reconstruit la table en conservant toutes les lignes.
        sql_budget = c.execute("SELECT sql FROM sqlite_master WHERE name = 'budget'").fetchone()[0]
        if "VIREMENT" not in sql_budget:
            c.executescript("""
                CREATE TABLE budget_v2 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    type TEXT NOT NULL CHECK (type IN ('DEPENSE','REVENU','VIREMENT')),
                    categorie TEXT NOT NULL,
                    montant REAL NOT NULL,
                    description TEXT DEFAULT ''
                );
                INSERT INTO budget_v2 (id, date, type, categorie, montant, description)
                    SELECT id, date, type, categorie, montant, description FROM budget;
                DROP TABLE budget;
                ALTER TABLE budget_v2 RENAME TO budget;
            """)
        # Heure de passage de l'ordre (HH:MM), facultative.
        if "heure" not in [r[1] for r in c.execute("PRAGMA table_info(transactions)")]:
            c.execute("ALTER TABLE transactions ADD COLUMN heure TEXT DEFAULT ''")
        # Toute enveloppe déjà utilisée (opérations, espèces) figure dans la liste des enveloppes.
        c.execute("INSERT OR IGNORE INTO enveloppes (nom) "
                  "SELECT enveloppe FROM transactions UNION SELECT enveloppe FROM especes")
        if c.execute("SELECT COUNT(*) FROM listes").fetchone()[0] == 0:
            import bourses
            for nom, tickers in bourses.LISTES_DE_DEPART.items():
                liste_id = c.execute("INSERT INTO listes (nom) VALUES (?)", (nom,)).lastrowid
                c.executemany("INSERT OR IGNORE INTO liste_titres VALUES (?, ?, datetime('now'))",
                              [(liste_id, t) for t in tickers])
        for cle, valeur in PARAMETRES_DEFAUT.items():
            c.execute("INSERT OR IGNORE INTO parametres (cle, valeur) VALUES (?, ?)", (cle, valeur))
        if c.execute("SELECT COUNT(*) FROM budget_plan").fetchone()[0] == 0:
            categories = c.execute("SELECT valeur FROM parametres WHERE cle = 'categories'").fetchone()[0]
            for cat in [x.strip() for x in categories.split(",") if x.strip()]:
                c.execute("INSERT INTO budget_plan (categorie, groupe, montant) VALUES (?, ?, 0)",
                          (cat, GROUPE_PAR_DEFAUT.get(cat, "Envies")))


# ---------------------------------------------------------------- paramètres
def lire_parametre(cle: str) -> str:
    with _connexion() as c:
        ligne = c.execute("SELECT valeur FROM parametres WHERE cle = ?", (cle,)).fetchone()
    return ligne[0] if ligne else PARAMETRES_DEFAUT.get(cle, "")


def ecrire_parametre(cle: str, valeur: str) -> None:
    with _connexion() as c:
        c.execute("INSERT OR REPLACE INTO parametres (cle, valeur) VALUES (?, ?)", (cle, valeur))


# -------------------------------------------------------------- transactions
def lister_transactions() -> pd.DataFrame:
    with _connexion() as c:
        df = pd.read_sql_query("SELECT * FROM transactions ORDER BY date, COALESCE(heure, ''), id", c)
    df["date"] = pd.to_datetime(df["date"])
    if "heure" in df.columns:
        df["heure"] = df["heure"].fillna("")
    return df


def ajouter_transaction(date, type_, ticker, quantite, prix, frais=0.0, devise="EUR", note="",
                        enveloppe: str = ENVELOPPE_DEFAUT, heure=None) -> None:
    """heure : datetime.time, « HH:MM » ou None (inconnue)."""
    if heure is not None and hasattr(heure, "strftime"):
        heure = heure.strftime("%H:%M")
    heure = str(heure or "").strip()[:5]
    with _connexion() as c:
        c.execute(
            "INSERT INTO transactions (date, type, ticker, quantite, prix, frais, devise, note, enveloppe, heure) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (pd.Timestamp(date).strftime("%Y-%m-%d"), type_, ticker.strip().upper(),
             float(quantite), float(prix), float(frais), devise.upper(), note,
             (enveloppe or ENVELOPPE_DEFAUT).strip(), heure))
        c.execute("INSERT OR IGNORE INTO enveloppes (nom) VALUES (?)", ((enveloppe or ENVELOPPE_DEFAUT).strip(),))


def changer_enveloppe(ids: list[int], enveloppe: str) -> None:
    with _connexion() as c:
        c.execute("INSERT OR IGNORE INTO enveloppes (nom) VALUES (?)", (enveloppe.strip(),))
        c.executemany("UPDATE transactions SET enveloppe = ? WHERE id = ?",
                      [(enveloppe.strip(), int(i)) for i in ids])


def enregistrer_especes(enveloppe: str, date, montant: float) -> None:
    """Solde d'espèces non investies d'une enveloppe (un relevé par jour : le dernier remplace)."""
    with _connexion() as c:
        c.execute("INSERT OR REPLACE INTO especes (enveloppe, date, montant) VALUES (?, ?, ?)",
                  (enveloppe.strip(), pd.Timestamp(date).strftime("%Y-%m-%d"), float(montant)))
        c.execute("INSERT OR IGNORE INTO enveloppes (nom) VALUES (?)", (enveloppe.strip(),))


def lister_especes() -> pd.DataFrame:
    with _connexion() as c:
        df = pd.read_sql_query("SELECT * FROM especes ORDER BY date, id", c)
    df["date"] = pd.to_datetime(df["date"])
    return df


def supprimer_especes(ids: list[int]) -> None:
    with _connexion() as c:
        c.executemany("DELETE FROM especes WHERE id = ?", [(int(i),) for i in ids])


def especes_actuelles() -> dict[str, tuple[float, pd.Timestamp]]:
    """{enveloppe: (dernier solde d'espèces, date du relevé)}."""
    df = lister_especes()
    if df.empty:
        return {}
    dernier = df.sort_values(["date", "id"]).groupby("enveloppe").last()
    return {e: (float(r.montant), r.date) for e, r in dernier.iterrows()}


def lister_enveloppes() -> list[str]:
    """Enveloppes créées par l'utilisateur (PEA, CTO…), dans l'ordre de création."""
    with _connexion() as c:
        return [r[0] for r in c.execute("SELECT nom FROM enveloppes ORDER BY cree_le, rowid")]


def creer_enveloppe(nom: str) -> None:
    with _connexion() as c:
        c.execute("INSERT OR IGNORE INTO enveloppes (nom) VALUES (?)", (nom.strip(),))


def renommer_enveloppe(ancien: str, nouveau: str) -> None:
    """Renomme l'enveloppe partout : opérations, espèces et liste."""
    nouveau = nouveau.strip()
    with _connexion() as c:
        c.execute("UPDATE transactions SET enveloppe = ? WHERE enveloppe = ?", (nouveau, ancien))
        c.execute("UPDATE especes SET enveloppe = ? WHERE enveloppe = ?", (nouveau, ancien))
        c.execute("UPDATE enveloppes SET nom = ? WHERE nom = ?", (nouveau, ancien))


def nb_operations_enveloppe(nom: str) -> int:
    with _connexion() as c:
        return int(c.execute("SELECT COUNT(*) FROM transactions WHERE enveloppe = ?", (nom,)).fetchone()[0])


def supprimer_enveloppe(nom: str) -> None:
    """Supprime une enveloppe sans opération (ses relevés d'espèces avec)."""
    if nb_operations_enveloppe(nom):
        raise ValueError("Cette enveloppe contient des opérations : déplacez-les ou supprimez-les d'abord.")
    with _connexion() as c:
        c.execute("DELETE FROM especes WHERE enveloppe = ?", (nom,))
        c.execute("DELETE FROM enveloppes WHERE nom = ?", (nom,))


def supprimer_transactions(ids: list[int]) -> None:
    with _connexion() as c:
        c.executemany("DELETE FROM transactions WHERE id = ?", [(int(i),) for i in ids])


def importer_transactions_csv(df: pd.DataFrame) -> int:
    """Colonnes attendues : date, type, ticker, quantite, prix, frais, devise, (note)."""
    requises = {"date", "type", "ticker", "quantite", "prix"}
    manquantes = requises - set(df.columns)
    if manquantes:
        raise ValueError(f"Colonnes manquantes : {', '.join(sorted(manquantes))}")
    n = 0
    for r in df.to_dict("records"):
        ajouter_transaction(r["date"], str(r["type"]).upper(), str(r["ticker"]), r["quantite"],
                            r["prix"], r.get("frais", 0) or 0, str(r.get("devise", "EUR") or "EUR"),
                            str(r.get("note", "") or "") if r.get("note") == r.get("note") else "",
                            str(r.get("enveloppe") or ENVELOPPE_DEFAUT)
                            if r.get("enveloppe") == r.get("enveloppe") else ENVELOPPE_DEFAUT,
                            str(r.get("heure") or "") if r.get("heure") == r.get("heure") else None)
        n += 1
    return n


# ------------------------------------------------- listes de titres suivis
FAVORIS = "Favoris"


def lister_listes() -> pd.DataFrame:
    """id, nom, nb (nombre de titres). Les favoris en premier."""
    with _connexion() as c:
        return pd.read_sql_query(
            "SELECT l.id, l.nom, COUNT(t.ticker) AS nb FROM listes l "
            "LEFT JOIN liste_titres t ON t.liste_id = l.id GROUP BY l.id "
            "ORDER BY l.nom <> ?, l.id", c, params=(FAVORIS,))


def creer_liste(nom: str) -> int:
    with _connexion() as c:
        return int(c.execute("INSERT INTO listes (nom) VALUES (?)", (nom.strip(),)).lastrowid)


def renommer_liste(liste_id: int, nom: str) -> None:
    with _connexion() as c:
        c.execute("UPDATE listes SET nom = ? WHERE id = ?", (nom.strip(), int(liste_id)))


def supprimer_liste(liste_id: int) -> None:
    with _connexion() as c:
        c.execute("DELETE FROM liste_titres WHERE liste_id = ?", (int(liste_id),))
        c.execute("DELETE FROM listes WHERE id = ?", (int(liste_id),))


def id_favoris() -> int:
    with _connexion() as c:
        c.execute("INSERT OR IGNORE INTO listes (nom) VALUES (?)", (FAVORIS,))
        return int(c.execute("SELECT id FROM listes WHERE nom = ?", (FAVORIS,)).fetchone()[0])


def titres_liste(liste_id: int) -> list[str]:
    with _connexion() as c:
        return [r[0] for r in c.execute(
            "SELECT ticker FROM liste_titres WHERE liste_id = ? ORDER BY ajoute_le, rowid", (int(liste_id),))]


def ajouter_a_liste(liste_id: int, ticker: str) -> None:
    with _connexion() as c:
        c.execute("INSERT OR IGNORE INTO liste_titres VALUES (?, ?, datetime('now'))",
                  (int(liste_id), ticker.strip().upper()))


def retirer_de_liste(liste_id: int, tickers: list[str]) -> None:
    with _connexion() as c:
        c.executemany("DELETE FROM liste_titres WHERE liste_id = ? AND ticker = ?",
                      [(int(liste_id), t) for t in tickers])


def listes_du_titre(ticker: str) -> set[int]:
    with _connexion() as c:
        return {r[0] for r in c.execute("SELECT liste_id FROM liste_titres WHERE ticker = ?", (ticker,))}


# -------------------------------------------------------------------- budget
def lister_budget() -> pd.DataFrame:
    with _connexion() as c:
        df = pd.read_sql_query("SELECT * FROM budget ORDER BY date DESC, id DESC", c)
    df["date"] = pd.to_datetime(df["date"])
    return df


def ajouter_mouvement(date, type_, categorie, montant, description="") -> None:
    with _connexion() as c:
        c.execute(
            "INSERT INTO budget (date, type, categorie, montant, description) VALUES (?, ?, ?, ?, ?)",
            (pd.Timestamp(date).strftime("%Y-%m-%d"), type_, categorie, abs(float(montant)), description))


def supprimer_mouvements(ids: list[int]) -> None:
    with _connexion() as c:
        c.executemany("DELETE FROM budget WHERE id = ?", [(int(i),) for i in ids])


def lire_regles_budget() -> dict[tuple[str, str], str]:
    """Catégories apprises lors des imports de relevés : {(type, clé du libellé): catégorie}."""
    with _connexion() as c:
        return {(t, k): cat for t, k, cat in c.execute("SELECT type, cle, categorie FROM regles_budget")}


def apprendre_regle_budget(type_: str, cle: str, categorie: str) -> None:
    if cle:
        with _connexion() as c:
            c.execute("INSERT OR REPLACE INTO regles_budget (type, cle, categorie) VALUES (?, ?, ?)",
                      (type_, cle, categorie))


def ajouter_mouvements(lignes: list[tuple]) -> int:
    """Ajout groupé : [(date, type, categorie, montant, description)]."""
    with _connexion() as c:
        c.executemany(
            "INSERT INTO budget (date, type, categorie, montant, description) VALUES (?, ?, ?, ?, ?)",
            [(pd.Timestamp(d).strftime("%Y-%m-%d"), t, cat, abs(float(m)), desc) for d, t, cat, m, desc in lignes])
    return len(lignes)


def importer_budget_csv(df: pd.DataFrame) -> int:
    """Colonnes attendues : date, type (DEPENSE/REVENU/VIREMENT), categorie, montant, (description)."""
    requises = {"date", "type", "categorie", "montant"}
    manquantes = requises - set(df.columns)
    if manquantes:
        raise ValueError(f"Colonnes manquantes : {', '.join(sorted(manquantes))}")
    n = 0
    for r in df.to_dict("records"):
        ajouter_mouvement(r["date"], str(r["type"]).upper(), str(r["categorie"]), r["montant"],
                          str(r.get("description", "") or ""))
        n += 1
    return n


# ------------------------------------------------------- comptes et soldes
def lister_comptes() -> pd.DataFrame:
    with _connexion() as c:
        return pd.read_sql_query("SELECT * FROM comptes ORDER BY categorie, nom", c)


def ajouter_compte(nom: str, categorie: str, taux_annuel: float = 0.0) -> int:
    with _connexion() as c:
        cur = c.execute("INSERT INTO comptes (nom, categorie, taux_annuel) VALUES (?, ?, ?)",
                        (nom.strip(), categorie, float(taux_annuel)))
        return int(cur.lastrowid)


def modifier_compte(compte_id: int, nom: str, categorie: str, taux_annuel: float) -> None:
    with _connexion() as c:
        c.execute("UPDATE comptes SET nom = ?, categorie = ?, taux_annuel = ? WHERE id = ?",
                  (nom.strip(), categorie, float(taux_annuel), int(compte_id)))


def supprimer_compte(compte_id: int) -> None:
    with _connexion() as c:
        c.execute("DELETE FROM soldes WHERE compte_id = ?", (int(compte_id),))
        c.execute("DELETE FROM comptes WHERE id = ?", (int(compte_id),))


def enregistrer_solde(compte_id: int, date, montant: float) -> None:
    """Un solde par compte et par jour : une nouvelle saisie le même jour remplace l'ancienne."""
    with _connexion() as c:
        c.execute("INSERT OR REPLACE INTO soldes (compte_id, date, montant) VALUES (?, ?, ?)",
                  (int(compte_id), pd.Timestamp(date).strftime("%Y-%m-%d"), float(montant)))


def lister_soldes() -> pd.DataFrame:
    with _connexion() as c:
        df = pd.read_sql_query(
            "SELECT s.id, s.compte_id, s.date, s.montant, c.nom, c.categorie "
            "FROM soldes s JOIN comptes c ON c.id = s.compte_id ORDER BY s.date, s.id", c)
    df["date"] = pd.to_datetime(df["date"])
    return df


def supprimer_soldes(ids: list[int]) -> None:
    with _connexion() as c:
        c.executemany("DELETE FROM soldes WHERE id = ?", [(int(i),) for i in ids])


# ------------------------------------------------------ groupes de dépenses
def lister_groupes() -> list[str]:
    """Groupes de dépenses (Besoins, Envies, Épargne et ceux créés par l'utilisateur), dans l'ordre choisi."""
    groupes = [g.strip() for g in lire_parametre("groupes_budget").split(",") if g.strip()]
    with _connexion() as c:  # un groupe utilisé dans le plan figure toujours dans la liste
        utilises = [r[0] for r in c.execute("SELECT DISTINCT groupe FROM budget_plan")]
    groupes = list(dict.fromkeys(groupes + [g for g in utilises if g]))
    return groupes if GROUPE_EPARGNE in groupes else groupes + [GROUPE_EPARGNE]


def groupe_par_defaut() -> str:
    groupes = lister_groupes()
    if "Envies" in groupes:
        return "Envies"
    return next((g for g in groupes if g != GROUPE_EPARGNE), GROUPE_EPARGNE)


def _ecrire_groupes(groupes: list[str]) -> None:
    ecrire_parametre("groupes_budget", ",".join(dict.fromkeys(g.strip() for g in groupes if g.strip())))


def ajouter_groupe(nom: str) -> None:
    nom = nom.strip().replace(",", " ")
    if nom:
        _ecrire_groupes(lister_groupes() + [nom])


def renommer_groupe(ancien: str, nouveau: str) -> None:
    """Renomme le groupe dans la liste et dans le plan (le groupe Épargne est réservé)."""
    nouveau = nouveau.strip().replace(",", " ")
    if not nouveau or ancien == GROUPE_EPARGNE:
        return
    _ecrire_groupes([nouveau if g == ancien else g for g in lister_groupes()])
    with _connexion() as c:
        c.execute("UPDATE budget_plan SET groupe = ? WHERE groupe = ?", (nouveau, ancien))


def supprimer_groupe(nom: str, remplacement: str) -> None:
    """Supprime le groupe ; ses catégories passent dans le groupe `remplacement`."""
    if nom == GROUPE_EPARGNE:
        return
    with _connexion() as c:
        c.execute("UPDATE budget_plan SET groupe = ? WHERE groupe = ?", (remplacement, nom))
    _ecrire_groupes([g for g in lister_groupes() if g != nom])


def deplacer_groupe(nom: str, decalage: int) -> None:
    """Change l'ordre d'affichage des groupes (-1 : plus haut, +1 : plus bas)."""
    groupes = lister_groupes()
    i = groupes.index(nom)
    j = max(0, min(len(groupes) - 1, i + decalage))
    groupes[i], groupes[j] = groupes[j], groupes[i]
    _ecrire_groupes(groupes)


# ----------------------------------------------------------- plan budgétaire
def lire_plan() -> pd.DataFrame:
    with _connexion() as c:
        return pd.read_sql_query("SELECT categorie, groupe, montant FROM budget_plan ORDER BY rowid", c)


def enregistrer_plan(plan: pd.DataFrame) -> None:
    """Remplace le plan et synchronise la liste des catégories de dépenses."""
    plan = plan.dropna(subset=["categorie"]).copy()
    plan["categorie"] = plan["categorie"].astype(str).str.strip()
    plan = plan[plan["categorie"] != ""].drop_duplicates("categorie")
    groupes = lister_groupes()
    with _connexion() as c:
        c.execute("DELETE FROM budget_plan")
        c.executemany("INSERT INTO budget_plan (categorie, groupe, montant) VALUES (?, ?, ?)",
                      [(r.categorie, r.groupe if r.groupe in groupes else groupe_par_defaut(),
                        float(r.montant) if r.montant == r.montant else 0.0)
                       for r in plan.itertuples(index=False)])
        c.execute("INSERT OR REPLACE INTO parametres (cle, valeur) VALUES ('categories', ?)",
                  (",".join(plan["categorie"]),))
