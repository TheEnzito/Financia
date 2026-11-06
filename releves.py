"""Lecture des relevés bancaires (CSV, OFX/QFX, QIF, Excel .xlsx, PDF si pypdf est disponible)
et catégorisation automatique des opérations.

Ce module ne dépend ni de Streamlit ni d'Internet.
Résultat commun : DataFrame [date, libelle, montant] (montant signé : négatif = dépense).
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
import zipfile
from xml.etree import ElementTree

import pandas as pd

COLONNES = ["date", "libelle", "montant"]


# ================================================================ utilitaires
def sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(texte)) if not unicodedata.combining(c))


def _norm(texte: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", sans_accents(texte).lower()).strip()


def nombre(valeur) -> float | None:
    """« 1 234,56 », « -12,50 € », « 1.234,56 », « 12.50 », « (45,00) » → float."""
    if valeur is None:
        return None
    if isinstance(valeur, (int, float)):
        return None if valeur != valeur else float(valeur)
    s = str(valeur).strip().replace(" ", "").replace(" ", "").replace(" ", "")
    s = re.sub(r"(EUR|€|eur|USD|\$)", "", s)
    if not s or s in {"-", "+"}:
        return None
    negatif = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    if s.endswith("-"):  # « 12,50- »
        negatif, s = True, s[:-1]
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return -abs(v) if negatif else v


def date_fr(valeur) -> pd.Timestamp | None:
    if valeur is None or (isinstance(valeur, float) and valeur != valeur):
        return None
    if isinstance(valeur, (int, float)) and 20000 < float(valeur) < 80000:  # date Excel (n° de série)
        return pd.Timestamp("1899-12-30") + pd.Timedelta(days=float(valeur))
    s = str(valeur).strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        a, mo, j = map(int, m.groups())
    else:
        m = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", s)
        if not m:
            return None
        j, mo, a = map(int, m.groups())
        if a < 100:
            a += 2000
    try:
        return pd.Timestamp(year=a, month=mo, day=j)
    except ValueError:
        return None


def _resultat(lignes: list[tuple]) -> pd.DataFrame:
    df = pd.DataFrame(lignes, columns=COLONNES)
    df = df.dropna(subset=["date", "montant"])
    df = df[df["montant"] != 0]
    df["libelle"] = df["libelle"].fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    return df.sort_values("date", kind="stable").reset_index(drop=True)


# ============================================== tableaux (CSV et Excel)
_DATE = ["date operation", "date de l operation", "date d operation", "dateop", "date op", "date comptable",
         "date de comptabilisation", "started date", "date", "completed date", "date valeur", "dateval"]
_LIBELLE = ["libelle operation", "libelle simplifie", "libelle", "label", "description", "intitule", "details",
            "detail de l ecriture", "nature de l operation", "nature", "payee", "beneficiaire", "merchant", "reference"]
_MONTANT = ["montant de l operation", "montant", "amount", "montant eur", "montant euros", "valeur"]
_DEBIT = ["debit", "debit euros", "debit eur", "sortie", "depense", "paid out"]
_CREDIT = ["credit", "credit euros", "credit eur", "entree", "recette", "paid in"]


def _trouver(entetes: list[str], candidats: list[str], exclure: set[int] = frozenset()) -> int | None:
    for cand in candidats:  # ordre de préférence
        for i, e in enumerate(entetes):
            if i not in exclure and (e == cand or e.startswith(cand + " ") or e.replace(" ", "") == cand.replace(" ", "")):
                return i
    for cand in candidats:
        for i, e in enumerate(entetes):
            if i not in exclure and cand in e:
                return i
    return None


def _depuis_lignes(lignes: list[list]) -> tuple[pd.DataFrame, str]:
    """Repère la ligne d'en-tête (les banques ajoutent souvent des lignes d'introduction)."""
    lignes = [[("" if c is None else c) for c in l] for l in lignes if any(str(c).strip() for c in l if c is not None)]
    for i, ligne in enumerate(lignes[:40]):
        entetes = [_norm(c) for c in ligne]
        i_date = _trouver(entetes, _DATE)
        i_montant = _trouver(entetes, _MONTANT)
        i_debit, i_credit = _trouver(entetes, _DEBIT), _trouver(entetes, _CREDIT)
        if i_date is None or (i_montant is None and i_debit is None and i_credit is None):
            continue
        i_lib = _trouver(entetes, _LIBELLE, {i_date})
        res = []
        for l in lignes[i + 1:]:
            l = list(l) + [""] * (len(ligne) - len(l))
            d = date_fr(l[i_date])
            if i_montant is not None:
                m = nombre(l[i_montant])
            else:
                deb = nombre(l[i_debit]) if i_debit is not None else None
                cre = nombre(l[i_credit]) if i_credit is not None else None
                m = (abs(cre) if cre else 0.0) - (abs(deb) if deb else 0.0)
                m = m if (deb or cre) else None
            lib = str(l[i_lib]) if i_lib is not None else ""
            res.append((d, lib, m))
        return _resultat(res), "en-tête « " + " ; ".join(str(c) for c in ligne if str(c).strip())[:90] + " »"
    return _sans_entete(lignes)


def _sans_entete(lignes: list[list]) -> tuple[pd.DataFrame, str]:
    """Pas d'en-tête reconnu (ex. LCL) : on devine les colonnes date, montant et libellé par leur contenu."""
    if not lignes:
        return pd.DataFrame(columns=COLONNES), ""
    largeur = max(len(l) for l in lignes)
    lignes = [list(l) + [""] * (largeur - len(l)) for l in lignes]
    def part(f, j):
        return sum(f(l[j]) is not None for l in lignes) / len(lignes)
    scores_date = [part(date_fr, j) for j in range(largeur)]
    i_date = max(range(largeur), key=lambda j: scores_date[j])
    candidats = [j for j in range(largeur) if j != i_date and part(nombre, j) > 0.8]
    if scores_date[i_date] < 0.6 or not candidats:
        return pd.DataFrame(columns=COLONNES), ""
    i_montant = candidats[0]
    textes = [j for j in range(largeur) if j not in (i_date, i_montant)]
    i_lib = max(textes, key=lambda j: sum(len(str(l[j])) for l in lignes)) if textes else None
    res = [(date_fr(l[i_date]), str(l[i_lib]) if i_lib is not None else "", nombre(l[i_montant])) for l in lignes]
    return _resultat(res), "colonnes devinées (fichier sans en-tête)"


def _decoder(contenu: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return contenu.decode(enc)
        except UnicodeDecodeError:
            continue
    return contenu.decode("utf-8", errors="replace")


def lire_csv(contenu: bytes) -> tuple[pd.DataFrame, str]:
    texte = _decoder(contenu)
    echantillon = "\n".join(texte.splitlines()[:60])
    separateur = max([";", ",", "\t", "|"], key=lambda s: echantillon.count(s))
    lignes = list(csv.reader(io.StringIO(texte), delimiter=separateur))
    df, detail = _depuis_lignes(lignes)
    return df, f"CSV (séparateur « {separateur} », {detail})"


def lire_xlsx(contenu: bytes) -> tuple[pd.DataFrame, str]:
    """Lecture minimale d'un classeur Excel (première feuille), sans bibliothèque externe."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        partages = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ElementTree.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                partages.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        feuilles = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))
        racine = ElementTree.fromstring(z.read(feuilles[0]))
    lignes = []
    for row in racine.iter(f"{{{ns['m']}}}row"):
        valeurs = {}
        for c in row.findall("m:c", ns):
            ref = re.match(r"([A-Z]+)", c.get("r", "A")).group(1)
            col = 0
            for ch in ref:
                col = col * 26 + ord(ch) - 64
            v = c.find("m:v", ns)
            t = c.get("t")
            if t == "s" and v is not None:
                val = partages[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(f"{{{ns['m']}}}t"))
            else:
                val = v.text if v is not None else ""
                try:
                    val = float(val) if val not in ("", None) else ""
                except ValueError:
                    pass
            valeurs[col - 1] = val
        if valeurs:
            lignes.append([valeurs.get(j, "") for j in range(max(valeurs) + 1)])
    df, detail = _depuis_lignes(lignes)
    return df, f"Excel ({detail})"


# =============================================================== OFX / QIF
def lire_ofx(contenu: bytes) -> tuple[pd.DataFrame, str]:
    texte = _decoder(contenu)
    res = []
    for bloc in re.findall(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|</BANKTRANLIST>)", texte, re.S | re.I):
        def champ(nom):
            m = re.search(rf"<{nom}>([^<\r\n]*)", bloc, re.I)
            return m.group(1).strip() if m else ""
        d = champ("DTPOSTED")
        date = pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:8]}") if len(d) >= 8 and d[:8].isdigit() else None
        libelle = " ".join(x for x in (champ("NAME"), champ("MEMO")) if x)
        res.append((date, libelle, nombre(champ("TRNAMT"))))
    return _resultat(res), "OFX"


def lire_qif(contenu: bytes) -> tuple[pd.DataFrame, str]:
    texte = _decoder(contenu)
    res, courant = [], {}
    for ligne in texte.splitlines():
        if not ligne:
            continue
        code, valeur = ligne[0], ligne[1:].strip()
        if code == "^":
            res.append((date_fr(courant.get("D", "").replace("'", "/")),
                        " ".join(x for x in (courant.get("P", ""), courant.get("M", "")) if x),
                        nombre(courant.get("T") or courant.get("U"))))
            courant = {}
        elif code in "DTUPM":
            courant[code] = valeur
    return _resultat(res), "QIF"


# ===================================================================== PDF
def pdf_disponible() -> bool:
    try:
        import pypdf  # noqa: F401
        return True
    except ImportError:
        return False


def lire_pdf(contenu: bytes) -> tuple[pd.DataFrame, str]:
    """Relevé PDF, quelle que soit la banque.

    1. Le texte de chaque page est reconstitué ligne par ligne (avec sa hauteur sur la page).
    2. Une opération commence par une date (« 24.09 », « 24/09/2026 », éventuellement suivie de la date de
       valeur) ; son montant est en fin de ligne ou sur une ligne suivante (conversions de devises…).
    3. Le sens se déduit, dans l'ordre : du signe affiché, de la position du montant sous les colonnes
       « Débit » / « Crédit », puis du libellé (avoir, virement reçu, salaire…).
    4. Les totaux imprimés sur le relevé (« Total des opérations ») servent de contrôle."""
    import pypdf
    lecteur = pypdf.PdfReader(io.BytesIO(contenu))
    if lecteur.is_encrypted:
        try:
            lecteur.decrypt("")  # beaucoup de relevés sont « protégés » sans mot de passe
            lecteur.pages[0].extract_text()
        except Exception:
            raise ValueError("Ce PDF est protégé (chiffrement non pris en charge). Imprimez-le en PDF depuis "
                             "votre lecteur, ou exportez le relevé en CSV / OFX depuis votre banque.")
    pages = [_page_pdf(p) for p in lecteur.pages]
    fin_periode = _fin_de_periode("\n".join(l for lignes, _ in pages for _y, l in lignes))

    operations, totaux, devines, positionnes = [], None, 0, 0
    for lignes, blocs in pages:
        colonnes = _colonnes_pdf(lignes, blocs)
        courante = None  # opération en cours de lecture : [date, libellé, montant, y du montant]
        for y, ligne in lignes:
            n = _norm(ligne)
            if re.match(r"^(total|totaux|sous total)\b", n):
                montants = re.findall(_MONTANT_PDF, ligne)
                if len(montants) >= 2:
                    totaux = (abs(nombre(montants[-2])), abs(nombre(montants[-1])))
                courante = None
                continue
            if re.search(r"\b(ancien|nouveau) solde\b|\bsolde (crediteur|debiteur|au|precedent|final)\b|"
                         r"\breport\b", n):
                courante = None
                continue
            debut = _DEBUT_OPERATION.match(ligne)
            if debut:
                courante = [_date_operation(debut.group(1), fin_periode), ligne[debut.end():], None, None]
                operations.append(courante)
            elif courante is None or courante[2] is not None:
                continue  # ligne de détail sans opération en attente
            texte = courante[1] if debut else ligne
            montant = _MONTANT_FIN.search(texte)
            if montant:
                if debut:
                    courante[1] = texte[:montant.start()]
                courante[2], courante[3] = montant.group(1), y
                # Sens de l'opération
                valeur = nombre(montant.group(1))
                if montant.group(1).strip()[0] in "+-":
                    courante[2] = valeur
                    positionnes += 1
                    continue
                cote = _cote_montant(montant.group(1), y, blocs, colonnes)
                if cote is None:
                    devines += 1
                    cote = "credit" if _CREDIT_PROBABLE.search(_norm(courante[1])) else "debit"
                else:
                    positionnes += 1
                courante[2] = abs(valeur) if cote == "credit" else -abs(valeur)
    res = [(d, lib, m) for d, lib, m, _y in operations if d is not None and isinstance(m, float)]
    df = _resultat(res)
    df.attrs["titulaire"] = _titulaire("\n".join(l for lignes, _ in pages for _y, l in lignes))

    detail = "PDF"
    if devines:
        detail += f" · {devines} sens débit / crédit deviné(s) d'après le libellé : vérifiez l'aperçu"
    if totaux:
        debits, credits = float(-df.loc[df["montant"] < 0, "montant"].sum()), float(df.loc[df["montant"] > 0, "montant"].sum())
        if abs(debits - totaux[0]) < 0.02 and abs(credits - totaux[1]) < 0.02:
            detail += " · contrôle OK : totaux identiques à ceux du relevé"
        else:
            detail += (f" · ⚠ écart avec les totaux du relevé (débits lus {debits:,.2f} / relevé {totaux[0]:,.2f} ; "
                       f"crédits lus {credits:,.2f} / relevé {totaux[1]:,.2f}) : vérifiez l'aperçu").replace(",", " ")
    return df, detail


_DATE_PDF = r"\d{2}[/.\-]\d{2}(?:[/.\-]\d{2,4})?"
_DEBUT_OPERATION = re.compile(rf"^\s*({_DATE_PDF})(?:\s+{_DATE_PDF})?\s+(?=\S)")
_MONTANT_PDF = r"[+-]?\s?\d{1,3}(?:[ .  ]\d{3})*,\d{2}"
# Montant en fin de ligne, éventuellement suivi d'un second montant (solde) et de symboles décoratifs.
_MONTANT_FIN = re.compile(rf"(?:^|\s)({_MONTANT_PDF})(?:\s+{_MONTANT_PDF})?\s*(?:€|EUR)?[^\w€]*$")
_LIGNE_PDF = re.compile(rf"^\s*({_DATE_PDF})\s+(?:{_DATE_PDF}\s+)?(.+?)\s+({_MONTANT_PDF})(?:\s+({_MONTANT_PDF}))?"
                        r"[^\w€]*$")
_CREDIT_PROBABLE = re.compile(r"\b(vir(ement)? (recu|en votre faveur|de)|virement de|salaire|paie|remboursement|"
                              r"rembt|remise|avoir|prime|interets|allocation|caf|pension|depot|versement recu)\b")
_MOIS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
         "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}


def _titulaire(texte: str) -> str:
    """Nom du titulaire du compte (« M. Dupont Jean » → « dupont jean »), le plus souvent cité sur le relevé."""
    noms = re.findall(r"\b(?:M\.|MME|Mme|MLLE|Mlle|MONSIEUR|Monsieur|MADAME|Madame)\s+([A-ZÉÈ][\w\-]+(?:\s+[A-ZÉÈ][\w\-]+)?)",
                      texte)
    if not noms:
        return ""
    return _norm(max(set(noms), key=noms.count))


def _fin_de_periode(texte: str) -> pd.Timestamp:
    """Date la plus récente écrite en entier sur le relevé (date d'arrêté, nouveau solde au …)."""
    dates = [date_fr(d) for d in re.findall(r"\b\d{2}[/.\-]\d{2}[/.\-]\d{4}\b", texte)]
    for j, mois, a in re.findall(r"\b(\d{1,2})\s+([A-Za-zéûÉÛ]+)\s+(20\d{2})\b", texte):
        m = _MOIS.get(_norm(mois))
        if m:
            try:
                dates.append(pd.Timestamp(year=int(a), month=m, day=int(j)))
            except ValueError:
                pass
    dates = [d for d in dates if d is not None and d <= pd.Timestamp.today() + pd.Timedelta(days=60)]
    return max(dates) if dates else pd.Timestamp.today().normalize()


def _date_operation(texte: str, fin: pd.Timestamp) -> pd.Timestamp | None:
    """« 24.09 » → 24/09 de l'année du relevé (ou de l'année d'avant, pour un relevé à cheval sur janvier)."""
    if len(re.sub(r"\D", "", texte)) > 4:
        return date_fr(texte.replace("-", "/"))
    j, m = map(int, re.findall(r"\d{2}", texte)[:2])
    try:
        d = pd.Timestamp(year=fin.year, month=m, day=j)
    except ValueError:
        return None
    return d.replace(year=fin.year - 1) if d > fin + pd.Timedelta(days=7) else d


def _page_pdf(page) -> tuple[list[tuple[float, str]], list[tuple[float, float, int]]]:
    """Lignes de texte décodées [(y, texte)] de haut en bas, et blocs d'affichage [(x centre, y, nb caractères)].
    Les blocs donnent la position exacte de chaque morceau de texte même quand la police empêche de le lire."""
    morceaux, blocs = [], []
    polices = (page.get("/Resources") or {}).get("/Font") or {}
    etat = {"taille": 9.0, "octets": 1}

    def texte_visite(texte, cm, tm, police, taille):
        if texte and texte.strip():
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            for i, partie in enumerate(texte.split("\n")):
                if partie.strip():
                    morceaux.append((y - i * 0.01, x, partie))

    def operateur(op, args, cm, tm):
        if op == b"Tf" and len(args) >= 2:
            try:
                etat["taille"] = float(args[1])
                police = polices.get(args[0])
                police = police.get_object() if police is not None else None
                etat["octets"] = 2 if police is not None and police.get("/Subtype") == "/Type0" else 1
            except Exception:
                pass
        elif op in (b"Tj", b"'", b'"', b"TJ") and args:
            elements = args[0] if op == b"TJ" else [args[-1]]
            longueur = sum(len(bytes(e)) if isinstance(e, bytes) else len(str(e)) * etat["octets"]
                           for e in elements if isinstance(e, (str, bytes)))
            nb = longueur // etat["octets"]
            if nb:
                echelle = abs(tm[0] * cm[0]) or 1.0
                x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
                y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
                blocs.append((x + nb * etat["taille"] * echelle * 0.25, y, nb))

    page.extract_text(visitor_text=texte_visite, visitor_operand_before=operateur)
    if not morceaux:
        return [(0.0, l) for l in (page.extract_text() or "").splitlines()], blocs
    morceaux.sort(key=lambda m: (-m[0], m[1]))
    lignes, courante, y_ligne = [], [], None
    for y, x, t in morceaux:
        if y_ligne is not None and abs(y - y_ligne) > 2.0:
            lignes.append((y_ligne, " ".join(p for _x, p in sorted(courante))))
            courante = []
        if not courante:
            y_ligne = y
        courante.append((x, t.strip()))
    if courante:
        lignes.append((y_ligne, " ".join(p for _x, p in sorted(courante))))
    return lignes, blocs


def _colonnes_pdf(lignes, blocs) -> tuple[float, float] | None:
    """Centres horizontaux des colonnes « Débit » et « Crédit » : blocs de 5 et 6 caractères sur la ligne d'en-tête."""
    for y, ligne in lignes:
        n = _norm(ligne)
        if re.search(r"\bdebit", n) and re.search(r"\bcredit", n):
            # En-têtes souvent sur deux lignes (« Date / opé. ») : tolérance verticale plus large.
            sur_ligne = sorted((b for b in blocs if abs(b[1] - y) < 8.0), key=lambda b: b[0])
            credit = next((b for b in reversed(sur_ligne) if b[2] in (6, 7)), None)  # « Crédit » (« Crédit € »)
            debit = next((b for b in reversed(sur_ligne) if b[2] in (5, 6) and credit and b[0] < credit[0]), None)
            if debit and credit:
                return debit[0], credit[0]
            # Police lisible mais en-tête d'un seul bloc : position relative dans le texte.
            return None
    return None


def _cote_montant(montant: str, y: float, blocs, colonnes) -> str | None:
    """« debit » ou « credit » selon la colonne sous laquelle le montant est affiché."""
    if not colonnes:
        return None
    longueurs = {len(montant.strip()), len(montant.replace(" ", "").replace(" ", "").strip())}
    candidats = [b for b in blocs if abs(b[1] - y) < 2.0 and b[2] in longueurs]
    if not candidats:
        return None
    x = max(candidats, key=lambda b: b[0])[0]
    return "credit" if abs(x - colonnes[1]) < abs(x - colonnes[0]) else "debit"


# ================================================================ entrée
FORMATS = ["csv", "txt", "ofx", "qfx", "qif", "xlsx"] + (["pdf"] if pdf_disponible() else [])


def lire_releve(nom: str, contenu: bytes) -> tuple[pd.DataFrame, str]:
    """Lit un relevé bancaire quel que soit son format. Renvoie (opérations, description du format)."""
    ext = nom.lower().rsplit(".", 1)[-1] if "." in nom else ""
    debut = contenu[:400].lstrip().upper()
    if ext in ("ofx", "qfx") or b"<OFX>" in debut or b"OFXHEADER" in debut:
        return lire_ofx(contenu)
    if ext == "qif" or debut.startswith(b"!TYPE"):
        return lire_qif(contenu)
    if ext == "xlsx" or contenu[:2] == b"PK":
        return lire_xlsx(contenu)
    if ext == "pdf" or contenu[:4] == b"%PDF":
        if not pdf_disponible():
            raise ValueError("La lecture des PDF n'est pas encore installée. Exportez votre relevé en CSV, OFX ou "
                             "Excel depuis votre espace bancaire.")
        return lire_pdf(contenu)
    if ext == "xls":
        raise ValueError("Ancien format Excel (.xls) non pris en charge : enregistrez-le en .xlsx ou en CSV.")
    return lire_csv(contenu)


# ================================================== virements entre comptes
def virement_interne(libelle: str, titulaire: str = "") -> bool:
    """Virement entre vos propres comptes (ni dépense ni revenu) : libellé de virement qui cite le
    titulaire du compte, ou mention explicite d'un virement interne."""
    n = " " + _norm(libelle) + " "
    if re.search(r" (virement interne|vir interne|compte a compte|transfert interne) ", n):
        return True
    if not re.search(r" (vir|virement|transfert|transfer) ", n):
        return False
    mots = [m for m in titulaire.split() if len(m) > 2]
    return bool(mots) and any(f" {m} " in n for m in mots)


# ========================================================= catégorisation
# Mots-clés courants → catégorie (seules les catégories qui existent chez l'utilisateur sont utilisées).
MOTS_CLES_DEPENSES = {
    "Alimentation": ["carrefour", "leclerc", "auchan", "lidl", "intermarche", "monoprix", "franprix", "casino",
                     "picard", "super u", "hyper u", "aldi", "grand frais", "biocoop", "naturalia", "boulangerie",
                     "boucherie", "netto", "cora", "spar", "la vie claire", "g20", "carrefour city", "proxi",
                     "vival", "coccinelle", "epicerie", "primeur", "fromagerie", "marche", "la paniere",
                     # étranger : Belgique, Pays-Bas, Allemagne, Pologne, Suisse, Royaume-Uni, Espagne, Italie
                     "delhaize", "colruyt", "albert heijn", "jumbo", "rewe", "edeka", "penny", "kaufland",
                     "zabka", "biedronka", "lewiatan", "dino", "migros", "coop", "denner", "tesco",
                     "sainsbury", "mercadona", "esselunga", "conad"],
    "Restaurants": ["restaurant", "resto", "mcdonald", "mc do", "burger", "kfc", "quick", "deliveroo", "uber eats",
                    "ubereats", "eats", "just eat", "starbucks", "costa coffee", "brasserie", "bistro", "pizza",
                    "sushi", "o tacos", "subway", "cafe", "coffee", "bar ", "pub ", "kebab", "boulangerie paul",
                    "paul ", "pret a manger", "areas", "newrest", "le patio", "creperie", "traiteur", "food"],
    "Transport": ["sncf", "ratp", "navigo", "uber", "ubr", "bolt", "blablacar", "peage", "autoroute", "parking",
                  "total", "esso", "shell", "bp ", "carburant", "lime", "velib", "ouigo", "transilien", "tgv",
                  "gare ", "taxi", "freenow", "heetch", "tier", "dott", "voi ", "stib", "sncb", "nmbs", "mpk",
                  "ztm", "jakdojade", "ns reizen", "db bahn", "deutsche bahn", "trenitalia", "renfe", "tcl ",
                  "tisseo", "rtm", "star ", "tag ", "ilevia", "indigo", "effia", "q park", "onepark"],
    "Logement": ["loyer", "edf", "engie", "veolia", "eau de", "suez", "foncia", "nexity", "syndic", "habitation",
                 "totalenergies electricite", "ekwateur", "ohm energie", "mint energie"],
    "Abonnements": ["netflix", "spotify", "deezer", "disney", "canal", "prime video", "amazon prime", "free mobile",
                    "free telecom", "orange", "sfr", "bouygues", "sosh", "red by", "apple com", "icloud", "google",
                    "youtube", "basic fit", "fitness", "salle de sport", "chatgpt", "openai", "adobe", "ionos",
                    "ovh", "microsoft", "notion", "github", "dropbox", "canva", "magnific", "patreon", "twitch",
                    "cotis", "cotisation", "offre globe", "abonnement", "frais tenue", "assurance carte"],
    "Loisirs": ["ugc", "pathe", "gaumont", "cinema", "fnac", "cultura", "steam", "playstation", "nintendo",
                "concert", "ticketmaster", "fnac spectacles", "theatre", "musee", "bowling", "lego", "escape",
                "parc ", "ski", "remontees", "forfait"],
    "Shopping": ["amazon", "zara", "h m", "uniqlo", "primark", "decathlon", "ikea", "leroy merlin", "darty",
                 "boulanger", "cdiscount", "vinted", "sephora", "action", "kiabi", "galeries lafayette", "zalando",
                 "shein", "temu", "aliexpress", "etsy", "shopify", "barber", "coiffeur", "coiffure", "nocibe",
                 "jules", "celio", "bershka", "pull bear", "mango", "normal ", "hema", "flying tiger"],
    "Santé": ["pharmacie", "docteur", "medecin", "dr ", "mutuelle", "dentiste", "ophtalmo", "kine", "laboratoire",
              "hopital", "clinique", "doctolib", "opticien", "optique", "optic", "audition", "osteo"],
    "Voyages": ["airbnb", "booking", "hotel", "air france", "easyjet", "ryanair", "transavia", "vueling",
                "expedia", "trainline", "flixbus", "brussels airlines", "sn airl", "snbru", "lufthansa", "klm",
                "wizz", "lot polish", "volotea", "eurostar", "europodroze", "hostel", "ibis", "accor"],
    "Impôts": ["dgfip", "impot", "tresor public", "taxe", "amende", "urssaf", "antai"],
    "Épargne": ["livret", "vers epargne", "epargne", "assurance vie", "pea", "versement programme", "boursobank"],
}
MOTS_CLES_REVENUS = {
    "Salaire": ["salaire", "paie", "payfit", "remuneration", "traitement"],
    "Prime": ["prime", "interessement", "participation", "bonus"],
    "Remboursement": ["remboursement", "rembt", "cpam", "ameli", "mutuelle", "avoir", "refund", "annulation"],
    "Revenus locatifs": ["loyer percu", "location"],
}
# Mentions bancaires sans intérêt pour reconnaître un commerçant.
_BRUIT = re.compile(r"\b(cb|carte|x?\d{4}x*|prlv|prelevement|sepa|vir|virement|inst|instantane|recu|emis|"
                    r"paiement|achat|retrait|dab|facture|fact|du|le|de|des|la|les|ref|ech|mandat|ttc|sas|sa|sarl|"
                    r"eur|frais|par|en|votre|vos|faveur|pour|au|aux|sur|chez|et|recu|emis|ordre|com|fr|www)\b")


def cle_libelle(libelle: str) -> str:
    """Clé stable d'un commerçant : « CB CARREFOUR CITY 12/09 PARIS 15 » → « carrefour city paris »."""
    n = _norm(libelle)
    n = re.sub(r"\b\d+\b", " ", n)
    n = _BRUIT.sub(" ", n)
    mots = [m for m in n.split() if len(m) > 1]
    return " ".join(mots[:3])


def categoriser(libelle: str, montant: float, regles: dict[tuple[str, str], str],
                categories_depenses: list[str], categories_revenus: list[str]) -> str:
    """Catégorie proposée : d'abord vos corrections passées (règles apprises), puis des mots-clés courants."""
    type_ = "REVENU" if montant > 0 else "DEPENSE"
    cle = cle_libelle(libelle)
    if cle and (type_, cle) in regles:
        return regles[(type_, cle)]
    n = " " + _norm(libelle) + " "
    for (t, regle_cle), cat in regles.items():  # règle apprise contenue dans le libellé
        if t == type_ and regle_cle and f" {regle_cle} " in n:
            return cat
    disponibles = categories_revenus if type_ == "REVENU" else categories_depenses
    par_nom = {_norm(c): c for c in disponibles}
    for cat, mots in (MOTS_CLES_REVENUS if type_ == "REVENU" else MOTS_CLES_DEPENSES).items():
        cible = par_nom.get(_norm(cat)) or (par_nom.get("loisirs") if cat == "Restaurants" else None)
        # Un mot-clé correspond au début d'un mot du libellé (« mcdonald » trouve « MCDONALDS »).
        if cible and any(f" {_norm(m)}" in n for m in mots):
            return cible
    for defaut in ("autre", "autres", "divers"):
        if defaut in par_nom:
            return par_nom[defaut]
    return disponibles[-1] if disponibles else "Autre"
