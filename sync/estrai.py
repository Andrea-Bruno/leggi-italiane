"""Estrazione dei dati da Normattiva.

Tre sorgenti, tutte ufficiali:
  * pagina consolidata  -> data di vigenza, riferimenti dell'atto, parametri AKN;
  * export Akoma Ntoso  -> testo, rubrica, note di aggiornamento per articolo;
  * elenco aggiornamenti -> data di Gazzetta degli atti che hanno modificato l'atto.

Le regole di lettura sono volutamente conservative: quando un effetto non e'
determinabile con certezza lo stato diventa "da_verificare" invece di essere
indovinato.
"""

from __future__ import annotations

import html as html_mod
import re
import unicodedata
import urllib.parse

from lxml import etree, html as lxml_html

NS = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"

MESI = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}

ORDINALI = {
    "primo": 1,
    "secondo": 2,
    "terzo": 3,
    "quarto": 4,
    "quinto": 5,
    "sesto": 6,
    "settimo": 7,
    "ottavo": 8,
    "nono": 9,
    "decimo": 10,
    "undicesimo": 11,
    "dodicesimo": 12,
    "tredicesimo": 13,
    "quattordicesimo": 14,
    "quindicesimo": 15,
    "sedicesimo": 16,
    "diciassettesimo": 17,
    "diciottesimo": 18,
    "diciannovesimo": 19,
    "ventesimo": 20,
}

SUFFISSI = {
    "bis": 1,
    "ter": 2,
    "quater": 3,
    "quinquies": 4,
    "sexies": 5,
    "septies": 6,
    "octies": 7,
    "novies": 8,
    "decies": 9,
}

_RAMO = (
    r"(?:[\s\-]*(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)"
    r"(?![a-z]))"
)
_IDENTIFICATIVO = re.compile(
    r"(\d+)((?:" + _RAMO + r")*)((?:\.\d{1,2})*)", re.I
)
_ID_ORDINE = re.compile(r"(\d+)((?:[\s\-/.][0-9A-Za-z]+)*)")


def normalizza(testo: str) -> str:
    return " ".join(testo.split())


def slug(testo: str) -> str:
    senza_accenti = unicodedata.normalize("NFKD", testo)
    senza_accenti = "".join(c for c in senza_accenti if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", senza_accenti.lower()).strip("-")


def ordine(numero: str) -> tuple[int, tuple, str]:
    """Chiave di ordinamento: 2043 < 2043-bis < 270-quinquies.1 < 314/28."""
    m = _ID_ORDINE.match(numero.strip())
    if not m:
        return 10**6, (), numero
    pesi = []
    for parte in re.findall(r"[0-9A-Za-z]+", m.group(2)):
        pesi.append(SUFFISSI.get(parte.lower(), int(parte) if parte.isdigit() else 50))
    return int(m.group(1)), tuple(pesi), numero


# --------------------------------------------------------------------------- #
# pagina consolidata
# --------------------------------------------------------------------------- #

def leggi_pagina(contenuto: str) -> dict:
    dati: dict = {}

    m = re.search(r'eli:version_date"\s+content="(\d{4}-\d{2}-\d{2})"', contenuto)
    if not m:
        raise ValueError("data di vigenza non trovata nella pagina consolidata")
    dati["data_vigenza"] = m.group(1)

    m = re.search(r'href="(/do/atto/caricaAKN\?[^"]+)"', contenuto)
    if not m:
        raise ValueError("link Akoma Ntoso non trovato nella pagina consolidata")
    query = urllib.parse.parse_qs(
        urllib.parse.urlsplit(html_mod.unescape(m.group(1))).query
    )
    dati["akn"] = {
        "data_gu": query["dataGU"][0],
        "codice_redazionale": query["codiceRedaz"][0],
        "data_vigenza": query["dataVigenza"][0],
    }

    m = re.search(r"atto\.dataPubblicazioneGazzetta=(\d{4}-\d{2}-\d{2})", contenuto)
    if not m:
        raise ValueError("data di pubblicazione in Gazzetta non trovata")
    dati["data_pubblicazione"] = m.group(1)

    m = re.search(
        r'eli:realizes"\s+resource="na:id/(\d{4})/(\d{2})/(\d{2})/([0-9A-Z]+)/CONSOLIDATED',
        contenuto,
    )
    if m:
        dati["eli"] = (
            f"eli/id/{m.group(1)}/{m.group(2)}/{m.group(3)}/{m.group(4)}"
            f"/CONSOLIDATED/{dati['data_vigenza'].replace('-', '')}"
        )
    else:
        m = re.search(
            r"eli/id/(\d{4}/\d{2}/\d{2}/[0-9A-Z]+)/CONSOLIDATED/(\d{8})", contenuto
        )
        if m:
            dati["eli"] = f"eli/id/{m.group(1)}/CONSOLIDATED/{m.group(2)}"

    m = re.search(
        r"gazzettaufficiale\.it/eli/gu/(\d{4})/(\d{2})/(\d{2})/(\d+)/", contenuto
    )
    if m:
        dati["gazzetta"] = {
            "numero": int(m.group(4)),
            "data": f"{m.group(1)}-{m.group(2)}-{m.group(3)}",
        }

    m = re.search(r'<meta name="description" content="([^"]+)"', contenuto)
    if m:
        dati["titolo"] = re.sub(r"\s*\([0-9A-Z]{7,}\)\s*$", "", m.group(1)).strip()

    m = re.search(r"<title>(.*?)\s*-\s*Normattiva</title>", contenuto)
    if m:
        dati["denominazione_atto"] = normalizza(m.group(1))

    return dati


# --------------------------------------------------------------------------- #
# export Akoma Ntoso
# --------------------------------------------------------------------------- #

def leggi_akn(contenuto: bytes) -> tuple[str | None, list[dict]]:
    radice = etree.fromstring(contenuto)
    urn_atto = None
    articoli = []
    for documento in radice.iter(f"{NS}doc"):
        alias = documento.find(
            f"{NS}meta/{NS}identification/{NS}FRBRWork/{NS}FRBRalias[@name='urn:nir']"
        )
        if urn_atto is None and alias is not None:
            urn_atto = alias.get("value")
        articoli.append(_articolo(documento))
    return urn_atto, articoli


def _articolo(documento) -> dict:
    nome = documento.get("name", "")
    sezione, separatore, numero_dal_nome = nome.rpartition("-art.")
    if not separatore:
        raise ValueError(f"nome di documento inatteso: {nome!r}")

    paragrafi = [
        "".join(p.itertext())
        for p in documento.findall(f"{NS}mainBody/{NS}paragraph")
    ]
    intero = "\n".join(paragrafi)
    pezzi = re.split(r"-{3,}\s*AGGIORNAMENTO\s*\((\d+)\)", intero)
    grezzo = _senza_prefisso(normalizza(pezzi[0]), nome, sezione)

    # Il campo name e' un'etichetta di gruppo: gli articoli inseriti dopo il
    # 1942 compaiono sotto il numero originario (es. 240-ter dentro "240 bis").
    # Il nome resta piu' preciso quando il testo omette la parte finale
    # (es. 270-quinquies.1 nel nome, 270-quinquies nel testo).
    dal_nome = normalizza(numero_dal_nome).replace(" ", "-")
    dal_testo = _numero_dal_testo(grezzo)
    numero = dal_nome if dal_testo and dal_nome.startswith(dal_testo) else dal_testo
    numero = numero or dal_nome

    riferimenti = _riferimenti(documento)
    corpo, rubrica = _intestazione(grezzo)
    note = [
        _nota(int(pezzi[i]), pezzi[i + 1], riferimenti, numero)
        for i in range(1, len(pezzi) - 1, 2)
    ]

    return {
        "sezione": normalizza(sezione),
        "numero": numero,
        "rubrica": rubrica,
        "testo_con_marcatori": grezzo,
        "testo": pulisci(corpo),
        "note": note,
    }


def _senza_prefisso(grezzo: str, nome: str, sezione: str) -> str:
    for prefisso in (nome, normalizza(sezione)):
        if prefisso and grezzo.startswith(prefisso):
            return grezzo[len(prefisso) :].lstrip(" -")
    return grezzo


def _numero_dal_testo(grezzo: str) -> str | None:
    m = re.match(r"\s*Art\.\s*", grezzo)
    if not m:
        return None
    identificativo = _IDENTIFICATIVO.match(grezzo[m.end() :])
    if not identificativo:
        return None
    base, catena, punti = identificativo.groups()
    catena = catena.strip()
    if catena and not catena.startswith(("-", "/", ".")):
        catena = "-" + catena
    return f"{base}{re.sub(r'\s+', '-', catena)}{punti}"


def _riferimenti(documento) -> list[dict]:
    visti = []
    for riferimento in documento.iter(f"{NS}ref"):
        href = riferimento.get("href") or ""
        if not href.startswith("/akn/it/act/"):
            continue
        denominazione = normalizza("".join(riferimento.itertext()))
        if not denominazione:
            continue
        urn, data, numero = _da_akn(href)
        voce = {
            "denominazione": denominazione,
            "urn": urn,
            "data": data,
            "numero": numero,
        }
        if voce not in visti:
            visti.append(voce)
    return visti


def _da_akn(href: str) -> tuple[str | None, str | None, str | None]:
    m = re.match(
        r"^/akn/it/act/([^/]+)/([^/]+)/(\d{4}-\d{2}-\d{2})/([^/#]+)", href
    )
    if not m:
        return None, None, None
    tipo, autorita, data, numero = m.groups()
    return f"urn:nir:{autorita}:{tipo}:{data};{numero}", data, numero


def _intestazione(grezzo: str) -> tuple[str, str | None]:
    m = re.match(r"Art\.\s*[0-9][0-9A-Za-z\-/.]*\.?\s*", grezzo)
    if not m:
        return grezzo, None
    resto = grezzo[m.end() :]

    for schema in (
        r"\(\(\s*\((.*?)\)\.?\s*\)\)",
        r"\(\(\s*(.*?)\s*\)\)",
        r"\(([^()]*)\)\.?",
    ):
        trovato = re.match(schema, resto)
        if not trovato:
            continue
        candidata = normalizza(trovato.group(1)).strip().rstrip(".")
        if schema == r"\(\(\s*(.*?)\s*\)\)" and (
            len(candidata) > 160
            or (candidata.isupper() and len(candidata) > 40)
            or re.search(r"ARTICOLO\s+(?:ABROGATO|SOPPRESSO|NON\s+PIU)", candidata, re.I)
        ):
            continue
        corpo = resto[trovato.end() :].strip()
        if not corpo:
            continue
        return corpo, candidata or None

    return resto.strip(), None


def pulisci(testo: str) -> str:
    """Rimuove i richiami alle note e le doppie parentesi di modifica."""
    testo = re.sub(r"\(\(\s*\d+\s*\)\)", "", testo)
    testo = re.sub(r"\((\d+)\)", "", testo)
    precedente = None
    while precedente != testo:
        precedente = testo
        testo = re.sub(r"\(\((.*?)\)\)", r"\1", testo, flags=re.S)
    return normalizza(testo)


def _nota(
    numero: int, testo: str, riferimenti: list[dict], numero_articolo: str
) -> dict:
    testo = normalizza(testo)
    effetto = _effetto(testo)
    ambito, parti = _ambito(testo, numero_articolo)
    return {
        "numero": numero,
        "effetto": effetto,
        "ambito": ambito,
        "parti": parti,
        "atti": [r for r in riferimenti if r["denominazione"] in testo],
        "sentenza": _sentenza(testo),
        "testo": testo,
    }


def _sentenza(testo: str) -> dict | None:
    m = re.search(
        r"con sentenza\s+(\d{1,2})(?:\s+\w+)?\s*-\s*(\d{1,2})\s+(\w+)\s+(\d{4}),?\s*n\.\s*(\d+)",
        testo,
        re.I,
    )
    if m:
        giorno, mese, anno, numero = m.group(2), m.group(3), m.group(4), m.group(5)
    else:
        m = re.search(
            r"con sentenza\s+(\d{1,2})\s+(\w+)\s+(\d{4}),?\s*n\.\s*(\d+)", testo, re.I
        )
        if not m:
            return None
        giorno, mese, anno, numero = m.groups()
    if mese.lower() not in MESI:
        return None
    return {
        "organo": "Corte costituzionale",
        "data": f"{anno}-{MESI[mese.lower()]:02d}-{int(giorno):02d}",
        "numero": numero,
    }


def _effetto(testo: str) -> str:
    if re.search(r"illegittimit|incostituzional", testo, re.I) and re.search(
        r"non\s+prevede\s+pi[uù]|non\s+contiene\s+pi[uù]|non\s+ha\s+pi[uù]", testo, re.I
    ):
        return "revoca_illegittimita"
    if re.search(r"illegittimit|incostituzional", testo, re.I):
        return "illegittimita_costituzionale"
    fuori_dalle_citazioni = re.sub(r'"[^"]*"|«[^»]*»', " ", testo)
    if re.search(r"abrogazion|abrogat|soppress", fuori_dalle_citazioni, re.I):
        return "abrogazione"
    if re.search(
        r"ha disposto|modific|sostituz|integraz|inserim|introduz|prorog",
        testo,
        re.I,
    ):
        return "modifica"
    return "altro"


def _ambito(testo: str, numero_articolo: str) -> tuple[str, list[str]]:
    m = re.search(
        r"(?:illegittimit\w*'?\s+costituzionale|l'abrogazione|abrogazione|abrogato)"
        r"\s+(.{0,240})",
        testo,
        re.I,
    )
    if not m:
        return "non_determinato", []
    coda = m.group(1)

    if re.search(r"\bcomm[ai]\b", coda, re.I):
        numeri = set()
        for parola in re.findall(r"[a-zà-ù0-9]+", coda.lower()):
            if parola in ORDINALI:
                numeri.add(ORDINALI[parola])
        numeri.update(int(n) for n in re.findall(r"comm[ai]\s+(\d+)", coda, re.I))
        return "commi", [f"comma {n}" for n in sorted(numeri)]

    if re.search(
        r"nella parte in cui|limitatamente|nei limiti|nella misura in cui|\bnumero\s+\d",
        coda,
        re.I,
    ):
        return "parte", []

    if re.search(r"presente articolo", coda, re.I):
        return "intero", []

    citato = re.search(
        r"dell'articolo\s+(\d+(?:[-/][0-9A-Za-z]+)*)|"
        r"dell'art\.\s*(\d+(?:[-/][0-9A-Za-z]+)*)",
        coda,
        re.I,
    )
    if citato:
        numero = citato.group(1) or citato.group(2)
        if numero.strip() == numero_articolo.strip():
            return "intero", []

    return "non_determinato", []


_ABROGAZIONE_TESTUALE = re.compile(
    r"ARTICOLO\s+(?:ABROGATO|SOPPRESSO|NON\s+PIU'?\s+PREVISTO)"
    r"|HA\s+CONFERMATO\s+(?:L'ABROGAZIONE|LA\s+SOPPRESSIONE)",
    re.I,
)
_ABROGAZIONE_DI_PARTE = re.compile(
    r"HA\s+CONFERMATO\s+L'ABROGAZIONE\s+DEL\s+PRESENTE\s+(?:COMMA|COMMI|PERIODO|CAPOVERSO)",
    re.I,
)


def _abrogazione_testuale(testo: str) -> dict | None:
    """Riconosce le formule con cui la fonte dichiara l'abrogazione dell'articolo."""
    if not _ABROGAZIONE_TESTUALE.search(testo):
        return None
    portata = "ambiguo" if _ABROGAZIONE_DI_PARTE.search(testo) else "articolo"
    fonte = None
    for schema in (
        r"ARTICOLO\s+(?:ABROGATO|SOPPRESSO|NON\s+PIU'?\s+PREVISTO)\s+"
        r"(?:DALL[A-Z']*|DAI|DAGLI)\s*([^)\n]+)",
        r"^(.*?)\s+HA\s+CONFERMATO",
        r"DISPOSTA\s+DAL\s+(.+?)(?:\s+HA\s+CONFERMATO|$)",
    ):
        trovato = re.search(schema, testo, re.I)
        if trovato:
            fonte = normalizza(trovato.group(1)).rstrip(".")
            break
    return {"portata": portata, "fonte": fonte, "testo": testo[:300]}


def valuta_stato(testo: str, note: list[dict]) -> dict:
    """Stato deterministico dell'articolo, con gli elementi che lo giustificano."""
    abrogazione = _abrogazione_testuale(testo)
    if abrogazione and abrogazione["portata"] == "articolo":
        return {
            "codice": "abrogato",
            "inapplicabile": True,
            "certezza": "alta",
            "motivazione": "Il testo consolidato riporta l'abrogazione dell'articolo.",
            "parti_non_applicabili": [],
            "elementi": [
                {
                    "tipo": "abrogazione_espressa",
                    "fonte": abrogazione["fonte"],
                    "testo": abrogazione["testo"],
                }
            ],
        }
    if not re.search(r"[0-9A-Za-z]", testo):
        return _stato(
            "da_verificare",
            None,
            "bassa",
            "Il testo consolidato non contiene il testo dell'articolo: verificare sulla fonte.",
            [],
            [],
        )
    if abrogazione:
        return {
            "codice": "da_verificare",
            "inapplicabile": None,
            "certezza": "bassa",
            "motivazione": (
                "Il testo riporta un'abrogazione riferita a una parte non identificata "
                "dell'articolo: verificare sulla fonte."
            ),
            "parti_non_applicabili": [],
            "elementi": [
                {
                    "tipo": "abrogazione",
                    "ambito": "parte",
                    "fonte": abrogazione["fonte"],
                    "testo": abrogazione["testo"],
                }
            ],
        }

    interi = [
        n
        for n in note
        if n["effetto"] in ("abrogazione", "illegittimita_costituzionale")
        and n["ambito"] == "intero"
    ]
    parziali = [
        n
        for n in note
        if n["effetto"] in ("abrogazione", "illegittimita_costituzionale")
        and n["ambito"] in ("commi", "parte")
    ]
    dubbi = [
        n
        for n in note
        if n["effetto"] in ("abrogazione", "illegittimita_costituzionale")
        and n["ambito"] == "non_determinato"
    ]
    revoche = [n for n in note if n["effetto"] == "revoca_illegittimita"]

    if revoche and (interi or parziali):
        return _stato(
            "da_verificare",
            None,
            "bassa",
            "Una nota di errata corrige esclude la dichiarazione di illegittimita' "
            "riportata in un'altra nota: lo stato va verificato sul testo ufficiale.",
            [],
            revoche + interi + parziali,
        )

    if any(n["effetto"] == "abrogazione" for n in interi):
        return _stato(
            "abrogato",
            True,
            "alta",
            "Una nota di aggiornamento dichiara l'abrogazione dell'intero articolo.",
            [],
            interi,
        )
    if interi:
        return _stato(
            "dichiarato_incostituzionale",
            True,
            "alta",
            "Una pronuncia della Corte costituzionale ha dichiarato illegittimo l'intero articolo.",
            [],
            interi,
        )
    if parziali:
        parti = sorted({p for n in parziali for p in n["parti"]}, key=_ordine_comma)
        dettaglio = (
            f"parti indicate: {', '.join(parti)}"
            if parti
            else "l'estensione non e' determinabile dalle note"
        )
        effetti = " e ".join(
            sorted({n["effetto"].replace("_", " ") for n in parziali})
        )
        return _stato(
            "parzialmente_inapplicabile",
            None,
            "media",
            f"{effetti.capitalize()} limitata a parti determinate ({dettaglio}). "
            "Il numero complessivo dei commi non e' calcolato, verificare sul testo.",
            parti,
            parziali,
        )
    if dubbi:
        return _stato(
            "da_verificare",
            None,
            "bassa",
            "Una nota segnala un effetto abrogativo o di illegittimita' "
            "di cui non e' stato possibile determinare l'oggetto: leggere il testo della nota.",
            [],
            dubbi,
        )
    return _stato(
        "vigente",
        False,
        "alta",
        "Nessuna abrogazione o dichiarazione di illegittimita' rilevata nelle note dell'articolo.",
        [],
        [],
    )


def _stato(codice, inapplicabile, certezza, motivazione, parti, note) -> dict:
    return {
        "codice": codice,
        "inapplicabile": inapplicabile,
        "certezza": certezza,
        "motivazione": motivazione,
        "parti_non_applicabili": parti,
        "elementi": [
            {"tipo": n["effetto"], "nota": n["numero"], "ambito": n["ambito"]}
            for n in note
        ],
    }


def _ordine_comma(etichetta: str) -> int:
    m = re.search(r"(\d+)", etichetta)
    return int(m.group(1)) if m else 99


# --------------------------------------------------------------------------- #
# elenco aggiornamenti all'atto
# --------------------------------------------------------------------------- #

def leggi_aggiornamenti(contenuto: str) -> list[dict]:
    albero = lxml_html.fromstring(contenuto)
    if albero is None:
        raise ValueError("elenco aggiornamenti illeggibile")

    eventi = []
    for riga in albero.iter("tr"):
        celle = riga.findall("td")
        if len(celle) < 3:
            continue
        data = _data_iso(normalizza(celle[1].text_content()))
        voci = [normalizza(li.text_content()) for li in celle[2].iter("li")]
        voci = [v for v in voci if v]
        if not voci:
            continue
        eventi.append(
            {
                "data_gazzetta": data,
                "atti": [voci[0]],
                "effetti": [_effetto_storico(v) for v in voci[1:]],
            }
        )
    return eventi


def _data_iso(testo: str) -> str | None:
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", testo)
    if not m:
        return None
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"


def _effetto_storico(descrizione: str) -> dict:
    articoli = sorted(
        {
            n
            for n in re.findall(
                r"(?:dell'art\.|dell'articolo|all'art\.|all'articolo|agli articoli|degli articoli)\s*"
                r"(\d+(?:[-/][0-9A-Za-z]+)*)",
                descrizione,
            )
        },
        key=ordine,
    )
    if re.search(r"illegittimit|incostituzional", descrizione, re.I):
        azione = "illegittimita_costituzionale"
    elif re.search(r"abrogazion|abrogat|soppress", descrizione, re.I):
        azione = "abrogazione"
    elif re.search(r"sostituz", descrizione, re.I):
        azione = "sostituzione"
    elif re.search(r"inserim|introduz|aggiunt", descrizione, re.I):
        azione = "inserimento"
    elif re.search(r"modific|integraz", descrizione, re.I):
        azione = "modifica"
    else:
        azione = "altro"
    return {"azione": azione, "articoli": articoli, "descrizione": descrizione}


def indice_date(eventi: list[dict]) -> dict[tuple[str, str], str | None]:
    """Mappa (data dell'atto, numero) -> data di pubblicazione in Gazzetta."""
    mappa: dict[tuple[str, str], str | None] = {}
    for evento in eventi:
        for atto in evento["atti"]:
            chiave = _chiave_atto(atto)
            if chiave:
                mappa.setdefault(chiave, evento["data_gazzetta"])
    return mappa


def _chiave_atto(denominazione: str) -> tuple[str, str] | None:
    m = re.search(
        r"(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|"
        r"settembre|ottobre|novembre|dicembre)\s+(\d{4})",
        denominazione,
        re.I,
    )
    n = re.search(r"\bn\.\s*(\d+)", denominazione)
    if not m or not n:
        return None
    data = f"{m.group(3)}-{MESI[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return data, n.group(1)
