"""Composizione e resa dei dati: un JSON ricco e un Markdown leggibile."""

from __future__ import annotations

import hashlib
import json

SCHEMA = "leggi-italiane/articolo@1"

ETICHETTE = {
    "vigente": "In vigore",
    "abrogato": "Abrogato",
    "dichiarato_incostituzionale": "Dichiarato incostituzionale",
    "parzialmente_inapplicabile": "Parzialmente inapplicabile",
    "da_verificare": "Da verificare",
    "assente_dalla_fonte": "Non piu' presente nella fonte",
}


def componi(codice: dict, articolo: dict, stato: dict, url: str) -> dict:
    record = {
        "schema": SCHEMA,
        "codice": codice,
        "articolo": {
            "numero": articolo["numero"],
            "rubrica": articolo["rubrica"],
            "sezione": articolo["sezione"],
            "url": url,
        },
        "stato": stato,
        "testo": {
            "vigente": articolo["testo"],
            "con_marcatori": articolo["testo_con_marcatori"],
            "caratteri": len(articolo["testo"]),
        },
        "note": articolo["note"],
    }
    record["impronta"] = impronta(record)
    return record


def impronta(record: dict) -> str:
    materiale = json.dumps(
        [
            record["testo"]["con_marcatori"],
            [
                [n["numero"], n["effetto"], n["ambito"], n["parti"], n["atti"]]
                for n in record["note"]
            ],
            [record["stato"]["codice"], record["stato"]["parti_non_applicabili"]],
        ],
        ensure_ascii=False,
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(materiale.encode("utf-8")).hexdigest()


def json_articolo(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, indent=2) + "\n"


def _nota_md(nota: dict) -> str:
    righe = [f"### Nota {nota['numero']} · {nota['effetto'].replace('_', ' ')}"]
    if nota["parti"]:
        righe[0] += f" ({', '.join(nota['parti'])})"
    righe.append("")
    righe.append(nota["testo"])
    for atto in nota["atti"]:
        dettaglio = atto["denominazione"]
        if atto.get("urn"):
            dettaglio += f" — `{atto['urn']}`"
        if atto.get("data_gazzetta"):
            dettaglio += f" — G.U. {atto['data_gazzetta']}"
        righe.append(f"- {dettaglio}")
    sentenza = nota.get("sentenza")
    if sentenza:
        righe.append(
            f"- {sentenza['organo']}, sentenza n. {sentenza['numero']} "
            f"del {sentenza['data']}"
        )
    return "\n".join(righe)


def markdown_articolo(record: dict) -> str:
    articolo = record["articolo"]
    stato = record["stato"]
    codice = record["codice"]
    rubrica = articolo["rubrica"] or "senza rubrica"
    contesto = f"**{codice['denominazione']}**"
    if articolo["sezione"].casefold() != codice["denominazione"].casefold():
        contesto += f" · {articolo['sezione']}"
    intestazione_testo = {
        "vigente": "## Testo vigente",
        "assente_dalla_fonte": "## Ultimo testo noto",
    }.get(stato["codice"], "## Testo")
    righe = [
        f"# Art. {articolo['numero']} — {rubrica}",
        "",
        f"{contesto} · [atto su Normattiva]({articolo['url']})",
        "",
        f"> **{ETICHETTE[stato['codice']]}** — certezza {stato['certezza']}",
        f"> {stato['motivazione']}",
    ]
    if stato["parti_non_applicabili"]:
        righe.append(f"> Parti non applicabili: {', '.join(stato['parti_non_applicabili'])}")
    righe += ["", intestazione_testo, "", record["testo"]["vigente"] or "_(nessun testo)_"]
    if record["note"]:
        righe += ["", "## Note di aggiornamento", ""]
        righe.append("\n\n".join(_nota_md(nota) for nota in record["note"]))
    gazzetta = codice["atto"]["gazzetta"]
    fonti = [
        f"[{codice['denominazione']} su Normattiva]({articolo['url']})"
        " — l'articolo si individua con il numero indicato sopra"
    ]
    if gazzetta:
        fonti.append(
            f"[Gazzetta Ufficiale n. {gazzetta['numero']} del {gazzetta['data']}]"
            f"({gazzetta['url']})"
        )
    righe += [
        "",
        "---",
        "",
        "Fonti ufficiali: " + " · ".join(fonti) + ".",
        "",
        "Dati generati automaticamente da Normattiva (Istituto Poligrafico e Zecca dello "
        "Stato). Il testo ufficiale e' quello pubblicato in Gazzetta Ufficiale; il link "
        "alla Gazzetta porta alla pubblicazione originale dell'atto, non al testo "
        "consolidato. Normattiva non espone un permalink per il singolo articolo.",
        "",
    ]
    return "\n".join(righe)


def json_indice(codice: dict, aggiornato_al: str, voci: list[dict]) -> str:
    conteggi = {chiave: 0 for chiave in ETICHETTE}
    sezioni: dict[str, int] = {}
    for voce in voci:
        conteggi[voce["stato"]] = conteggi.get(voce["stato"], 0) + 1
        sezioni[voce["sezione"]] = sezioni.get(voce["sezione"], 0) + 1
    indice = {
        "schema": "leggi-italiane/indice@1",
        "codice": codice,
        "aggiornato_al": aggiornato_al,
        "conteggi": {"totale": len(voci), **{k: v for k, v in conteggi.items() if v}},
        "sezioni": sezioni,
        "articoli": voci,
    }
    return json.dumps(indice, ensure_ascii=False, indent=2) + "\n"


def markdown_indice(codice: dict, aggiornato_al: str, voci: list[dict]) -> str:
    righe = [
        f"# {codice['denominazione']} — indice degli articoli",
        "",
        f"Aggiornato al {aggiornato_al}. {len(voci)} articoli. "
        f"[Testo ufficiale]({codice['atto']['url']})",
        "",
        "| Articolo | Rubrica | Stato |",
        "| --- | --- | --- |",
    ]
    for voce in voci:
        rubrica = (voce["rubrica"] or "").replace("|", "\\|")
        righe.append(
            f"| [{voce['numero']}]({voce['percorso']}.md) | {rubrica} | "
            f"{ETICHETTE[voce['stato']]} |"
        )
    righe.append("")
    return "\n".join(righe)
