# Leggi italiane

[![Aggiorna leggi](https://github.com/Andrea-Bruno/leggi-italiane/actions/workflows/aggiorna.yml/badge.svg)](https://github.com/Andrea-Bruno/leggi-italiane/actions/workflows/aggiorna.yml)
[![Licenza MIT](https://img.shields.io/badge/licenza-MIT-blue.svg)](LICENSE)
[![Schema](https://img.shields.io/badge/schema-articolo%401-informational.svg)](schema/articolo.schema.json)

Codice civile e codice penale italiani in formato leggibile da una macchina, riallineati
ogni giorno alla fonte ufficiale. Ogni articolo è un file JSON con testo, rubrica, stato di
vigenza accertato e note di aggiornamento, più un gemello Markdown per la lettura umana.

Lo scopo è dare a un modello linguistico una base verificabile: la validità di un articolo
si legge da un campo esplicito, non si deduce dal testo. Il repository non contiene opinioni
né commenti: solo ciò che risulta dagli atti pubblicati.

> **Avvertenza.** Questo repository non è una consulenza legale e non sostituisce la
> Gazzetta Ufficiale. Il testo ufficiale è quello pubblicato in Gazzetta; qui se ne conserva
> una trascrizione con lo stato di vigenza ricostruito dagli atti.

## Cosa contiene

```
data/
  indice.json              elenco dei codici, con conteggi e data di aggiornamento
  civile/
    index.json             indice degli articoli del codice civile
    indice.md              lo stesso indice in tabella
    aggiornamenti.json     storico completo degli atti che hanno modificato il codice
    codice/1.json           un file per articolo
    codice/1.md
    preleggi/1.json        disposizioni sulla legge in generale
  penale/
    ...
schema/articolo.schema.json   schema JSON di un articolo
sync/                         il programma che scarica e normalizza i dati
docs/                         formato dei dati e note sulla fonte
```

Oltre quattromila articoli, ognuno con rubrica, testo consolidato e storia delle modifiche.
Le cartelle `civile` e `penale` sono indipendenti: si possono leggere, scaricare o citare
separatamente.

## Un articolo, in breve

```json
{
  "schema": "leggi-italiane/articolo@1",
  "articolo": { "numero": "2043", "rubrica": "Risarcimento per fatto illecito", "sezione": "CODICE CIVILE" },
  "stato": {
    "codice": "vigente",
    "inapplicabile": false,
    "certezza": "alta",
    "motivazione": "Nessuna abrogazione o dichiarazione di illegittimita' rilevata nelle note dell'articolo.",
    "parti_non_applicabili": [],
    "elementi": []
  },
  "testo": { "vigente": "Qualunque fatto doloso o colposo...", "con_marcatori": "Art. 2043. ..." },
  "note": []
}
```

Il campo `note` conserva le note ufficiali di aggiornamento, con l'atto citato, la sentenza
quando esiste e l'ambito dell'effetto. `impronta` cambia solo quando cambia il contenuto
normativo: è il modo più rapido per sapere se un articolo è stato toccato.

## Stati di vigenza

| `stato.codice` | Significato | `inapplicabile` |
| --- | --- | --- |
| `vigente` | Nessun effetto abrogativo o di illegittimità rilevato | `false` |
| `abrogato` | Abrogazione dell'intero articolo | `true` |
| `dichiarato_incostituzionale` | Illegittimità costituzionale dell'intero articolo | `true` |
| `parzialmente_inapplicabile` | Effetto limitato a commi o parti indicate | `null` |
| `da_verificare` | Effetto segnalato ma non determinabile con certezza | `null` |
| `assente_dalla_fonte` | L'articolo non compare più nell'export ufficiale | `null` |

`certezza` dice quanto è solida la ricostruzione: `alta` per abrogazioni espresse e
pronunce sull'intero articolo, `media` per gli effetti parziali, `bassa` quando serve un
controllo umano. Il campo `elementi` elenca le note che hanno prodotto lo stato.

## Come usarlo da un agente

1. leggi `data/<codice>/index.json` per trovare l'articolo e il suo stato;
2. apri `data/<codice>/<sezione>/<numero>.json` per testo, note e motivazione;
3. non dedurre la validità dal solo testo: usa `stato`, e quando è `da_verificare` o
   `parzialmente_inapplicabile` riporta la motivazione e le note, senza concludere.

L'indice contiene `numero`, `rubrica`, `sezione`, `stato` e `percorso` per ogni articolo;
il percorso è senza estensione, quindi `codice/2043` indica sia `2043.json` sia `2043.md`.

## Come si aggiorna

Una GitHub Action gira ogni giorno alle 03:17 UTC. Per ogni codice fa tre richieste a
Normattiva: la pagina consolidata (data di vigenza e parametri dell'atto), l'export Akoma
Ntoso (testo, rubriche, note) e l'elenco degli aggiornamenti (date di Gazzetta). Poi
riscrive solo i file cambiati e aggiorna gli indici.

Due guardie impediscono di pubblicare dati peggiori dei precedenti: se la fonte dichiara
una data di vigenza anteriore a quella già archiviata, o se il numero di articoli estratti
cala di oltre il 5%, la sincronizzazione si ferma senza scrivere nulla.

Dettagli su formato, regole di lettura e limiti: [`docs/formato.md`](docs/formato.md) e
[`docs/fonti.md`](docs/fonti.md). Il README è solo la presentazione: la documentazione nel
repository spiega come i dati sono prodotti e come vanno interpretati.

## Aggiungere un codice

Basta una voce in [`sync/sources.json`](sync/sources.json): identificatore, denominazione,
URN Normattiva e mappa delle sezioni. Nessuna modifica al codice Python.

```bash
python -m sync --codice civile     # un solo codice
python -m sync --prova             # legge e confronta, non scrive
python -m unittest discover -s tests
```

## Limiti noti

- I commi non sono segmentati: il testo è conservato come pubblicato, e le note indicano i
  commi colpiti senza dire quanti commi abbia l'articolo. Per questo gli effetti parziali
  hanno `inapplicabile: null`.
- Le note sono prosa ufficiale: gli effetti sono classificati con regole esplicite, non con
  interpretazione. Quando la regola non basta lo stato diventa `da_verificare`.
- La fonte è un sito pubblico senza contratto di servizio: un cambio di struttura viene
  trattato come errore bloccante, non come aggiornamento.
- Alcuni articoli non hanno rubrica tra parentesi nel testo ufficiale: in quel caso
  `rubrica` è `null` e il testo resta integrale.

## Licenza

Il codice di questo repository è distribuito con licenza MIT (vedi [LICENSE](LICENSE)).
I testi degli atti normativi non sono coperti da diritto d'autore (art. 5 della legge
633/1941); i dati sono trascritti da Normattiva, il portale della legge vigente curato
dall'Istituto Poligrafico e Zecca dello Stato.
