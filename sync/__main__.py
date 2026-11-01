"""Sincronizzazione giornaliera di Normattiva verso data/.

Uso:
    python -m sync                # tutti i codici del registro
    python -m sync --codice civile
    python -m sync --prova        # legge e confronta, non scrive
    python -m sync --forza        # ignora le guardie sulla fonte
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from . import estrai, rendi
from .normattiva import BASE, ErroreFonte, Normattiva

RADICE = Path(__file__).resolve().parent.parent
DATI = RADICE / "data"
REGISTRO = Path(__file__).resolve().parent / "sources.json"

RIDUZIONE_AMMESSA = 0.95


def main() -> int:
    argomenti = _argomenti()
    codici = json.loads(REGISTRO.read_text(encoding="utf-8"))["codici"]
    if argomenti.codice:
        codici = [c for c in codici if c["id"] in argomenti.codice]
        if not codici:
            print(f"nessun codice corrisponde a {argomenti.codice}", file=sys.stderr)
            return 2

    client = Normattiva(pausa=argomenti.attesa)
    errori = []
    riepiloghi = []

    for codice in codici:
        try:
            riepiloghi.append(
                sincronizza(codice, client, argomenti.forza, argomenti.prova)
            )
        except (ErroreFonte, ValueError) as errore:
            errori.append(f"{codice['id']}: {errore}")
            print(f"ERRORE {codice['id']}: {errore}", file=sys.stderr)

    if not argomenti.prova:
        _scrivi_indice_globale(riepiloghi)

    for riga in riepiloghi:
        print(
            f"{riga['codice']}: {riga['articoli']} articoli, "
            f"{riga['aggiornati']} aggiornati, {riga['creati']} nuovi, "
            f"{riga['assenti']} assenti (vigenza {riga['aggiornato_al']})"
        )
    if errori:
        print("\n".join(errori), file=sys.stderr)
        return 1
    return 0


def sincronizza(codice: dict, client: Normattiva, forza: bool, prova: bool) -> dict:
    cartella = DATI / codice["id"]
    precedente = _indice_esistente(cartella)

    pagina = client.pagina(codice["urn"])
    meta = estrai.leggi_pagina(pagina)
    urn_atto, articoli = estrai.leggi_akn(
        client.akn(
            meta["akn"]["data_gu"],
            meta["akn"]["codice_redazionale"],
            meta["akn"]["data_vigenza"],
        )
    )
    storico = estrai.leggi_aggiornamenti(
        client.aggiornamenti(meta["data_pubblicazione"], meta["akn"]["codice_redazionale"])
    )

    if not forza:
        _guardie(precedente, meta, articoli)
    _verifica_unicita(articoli)

    _arricchisci(articoli, storico)
    contesto = _contesto(codice, meta, urn_atto)

    voci, aggiornati, creati = [], 0, 0
    presenti = set()
    for articolo in articoli:
        sezione = codice["sezioni"].get(articolo["sezione"]) or estrai.slug(
            articolo["sezione"]
        )
        percorso = Path(sezione) / _nome_file(articolo["numero"])
        presenti.add(percorso)
        stato = estrai.valuta_stato(articolo["testo"], articolo["note"])
        record = rendi.componi(
            contesto, articolo, stato, contesto["atto"]["url"]
        )
        esito = _scrivi_coppia(cartella, percorso, record, prova)
        creati += esito == "creato"
        aggiornati += esito == "aggiornato"
        voci.append(_voce(articolo, stato, percorso))

    assenti = _segnala_assenti(cartella, presenti, contesto, voci, prova)
    voci.sort(key=lambda v: (v["sezione"], estrai.ordine(v["numero"])))

    if not prova:
        _scrivi_indice_codice(cartella, contesto, meta["data_vigenza"], voci)
        _scrivi_storico(cartella, codice, meta, storico)

    return {
        "codice": codice["id"],
        "denominazione": codice["denominazione"],
        "url": f"{BASE}/uri-res/N2Ls?{codice['urn']}",
        "aggiornato_al": meta["data_vigenza"],
        "articoli": len(articoli),
        "aggiornati": aggiornati,
        "creati": creati,
        "assenti": assenti,
        "conteggi": _conteggi(voci),
        "indice": f"{codice['id']}/index.json",
    }


def _argomenti() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="sync", description=__doc__)
    parser.add_argument("--codice", action="append", help="limita a un codice (ripetibile)")
    parser.add_argument("--prova", action="store_true", help="non scrivere file")
    parser.add_argument("--forza", action="store_true", help="ignora le guardie")
    parser.add_argument("--attesa", type=float, default=1.5, help="pausa fra richieste")
    return parser.parse_args()


def _contesto(codice: dict, meta: dict, urn_atto: str | None) -> dict:
    return {
        "id": codice["id"],
        "denominazione": codice["denominazione"],
        "atto": {
            "titolo": meta.get("titolo"),
            "denominazione": meta.get("denominazione_atto"),
            "urn": codice["urn"],
            "urn_atto": urn_atto,
            "eli": meta.get("eli"),
            "codice_redazionale": meta["akn"]["codice_redazionale"],
            "gazzetta": meta.get("gazzetta"),
            "url": f"{BASE}/uri-res/N2Ls?{codice['urn']}",
        },
    }


def _nome_file(numero: str) -> str:
    return numero.replace("/", "-").replace(".", "-").replace(" ", "")


def _voce(articolo: dict, stato: dict, percorso: Path) -> dict:
    return {
        "numero": articolo["numero"],
        "rubrica": articolo["rubrica"],
        "sezione": percorso.parts[0],
        "stato": stato["codice"],
        "percorso": percorso.with_suffix("").as_posix(),
    }


def _arricchisci(articoli: list[dict], storico: list[dict]) -> None:
    date_atti = estrai.indice_date(storico)
    for articolo in articoli:
        for nota in articolo["note"]:
            for atto in nota["atti"]:
                atto["data_gazzetta"] = (
                    date_atti.get((atto["data"], atto["numero"]))
                    if atto["data"]
                    else None
                )


def _scrivi_coppia(cartella: Path, percorso: Path, record: dict, prova: bool) -> str:
    esisteva = (cartella / percorso.with_suffix(".json")).exists()
    cambiato = _scrivi(
        cartella / percorso.with_suffix(".json"),
        rendi.json_articolo(record),
        prova,
    )
    _scrivi(cartella / percorso.with_suffix(".md"), rendi.markdown_articolo(record), prova)
    if not cambiato:
        return "invariato"
    return "aggiornato" if esisteva else "creato"


def _segnala_assenti(
    cartella: Path, presenti: set[Path], contesto: dict, voci: list[dict], prova: bool
) -> int:
    assenti = 0
    for esistente in sorted(cartella.glob("*/*.json")):
        relativo = esistente.relative_to(cartella).with_suffix("")
        if relativo in presenti:
            continue
        record = json.loads(esistente.read_text(encoding="utf-8"))
        if record["stato"]["codice"] != "assente_dalla_fonte":
            record["stato"] = {
                "codice": "assente_dalla_fonte",
                "inapplicabile": None,
                "certezza": "bassa",
                "motivazione": (
                    "L'articolo non compare piu' nell'export ufficiale: il file e' "
                    "conservato con l'ultimo testo noto. Verificare su Normattiva."
                ),
                "parti_non_applicabili": [],
                "elementi": [],
            }
            record["impronta"] = rendi.impronta(record)
            _scrivi(esistente, rendi.json_articolo(record), prova)
            _scrivi(
                esistente.with_suffix(".md"), rendi.markdown_articolo(record), prova
            )
        assenti += 1
        voci.append(
            {
                "numero": record["articolo"]["numero"],
                "rubrica": record["articolo"]["rubrica"],
                "sezione": relativo.parts[0],
                "stato": "assente_dalla_fonte",
                "percorso": relativo.as_posix(),
            }
        )
    return assenti


def _scrivi_indice_codice(
    cartella: Path, contesto: dict, aggiornato_al: str, voci: list[dict]
) -> None:
    _scrivi(
        cartella / "index.json",
        rendi.json_indice(contesto, aggiornato_al, voci),
    )
    _scrivi(cartella / "indice.md", rendi.markdown_indice(contesto, aggiornato_al, voci))


def _scrivi_storico(cartella: Path, codice: dict, meta: dict, storico: list[dict]) -> None:
    contenuto = {
        "schema": "leggi-italiane/aggiornamenti@1",
        "codice": codice["id"],
        "aggiornato_al": meta["data_vigenza"],
        "eventi": storico,
    }
    _scrivi(
        cartella / "aggiornamenti.json",
        json.dumps(contenuto, ensure_ascii=False, indent=2) + "\n",
    )


def _scrivi_indice_globale(riepiloghi: list[dict]) -> None:
    if not riepiloghi:
        return
    indice = {
        "schema": "leggi-italiane/indici@1",
        "aggiornato_al": max(r["aggiornato_al"] for r in riepiloghi),
        "codici": [{k: r[k] for k in ("codice", "denominazione", "url", "aggiornato_al", "articoli", "conteggi", "indice")} for r in riepiloghi],
    }
    _scrivi(
        DATI / "indice.json",
        json.dumps(indice, ensure_ascii=False, indent=2) + "\n",
    )


def _guardie(precedente: dict | None, meta: dict, articoli: list[dict]) -> None:
    if not precedente:
        return
    vecchia = precedente.get("aggiornato_al")
    if vecchia and meta["data_vigenza"] < vecchia:
        raise ValueError(
            f"la fonte dichiara vigenza {meta['data_vigenza']}, precedente {vecchia}: "
            "possibile risposta in cache, nessuna scrittura"
        )
    atteso = precedente.get("conteggi", {}).get("totale", 0)
    if atteso and len(articoli) < atteso * RIDUZIONE_AMMESSA:
        raise ValueError(
            f"estratti {len(articoli)} articoli contro {atteso} attesi: "
            "export incompleto, nessuna scrittura (usare --forza per ignorare)"
        )


def _verifica_unicita(articoli: list[dict]) -> None:
    chiavi = Counter((a["sezione"], a["numero"]) for a in articoli)
    doppie = sorted(c for c, n in chiavi.items() if n > 1)
    if doppie:
        raise ValueError(f"numeri di articolo duplicati nell'export: {doppie[:5]}")


def _indice_esistente(cartella: Path) -> dict | None:
    percorso = cartella / "index.json"
    if not percorso.exists():
        return None
    return json.loads(percorso.read_text(encoding="utf-8"))


def _conteggi(voci: list[dict]) -> dict:
    conteggi = {"totale": len(voci)}
    for voce in voci:
        conteggi[voce["stato"]] = conteggi.get(voce["stato"], 0) + 1
    return conteggi


def _scrivi(percorso: Path, contenuto: str, prova: bool = False) -> bool:
    if percorso.exists() and percorso.read_text(encoding="utf-8") == contenuto:
        return False
    if not prova:
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(contenuto, encoding="utf-8", newline="\n")
    return True


if __name__ == "__main__":
    sys.exit(main())
