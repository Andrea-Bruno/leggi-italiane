# Formato dei dati

Un file per articolo, in JSON e in Markdown, più due indici per codice. I file sono
generati: una modifica manuale viene sovrascritta alla sincronizzazione successiva.

## Percorsi

```
data/indice.json                       elenco dei codici
data/<codice>/index.json               indice degli articoli, con stato e percorso
data/<codice>/indice.md                lo stesso indice in tabella
data/<codice>/aggiornamenti.json       storico degli atti che hanno modificato il codice
data/<codice>/<sezione>/<numero>.json  articolo
data/<codice>/<sezione>/<numero>.md    articolo in Markdown
```

`<numero>` è il numero pubblicato con `/`, `.` e spazi sostituiti da `-`:
l'articolo `270-quinquies.1` diventa `270-quinquies-1.json`, l'articolo `314/28` diventa
`314-28.json`. Il campo `articolo.numero` conserva la forma originale.

`<sezione>` distingue le partizioni che hanno numerazione propria. Nel codice civile
`codice/` contiene gli articoli del codice e `preleggi/` le disposizioni sulla legge in
generale, che ripartono da 1.

## Campi di un articolo

| Campo | Contenuto |
| --- | --- |
| `schema` | Versione del formato, oggi `leggi-italiane/articolo@1` |
| `codice.id`, `codice.denominazione` | Codice di appartenenza |
| `codice.atto` | Titolo, URN, URN dell'atto, ELI, codice redazionale, Gazzetta, URL |
| `articolo.numero` | Numero come pubblicato |
| `articolo.rubrica` | Rubrica ufficiale, `null` se assente nel testo |
| `articolo.sezione` | Sezione dell'export (es. `CODICE CIVILE`) |
| `articolo.url` | Link al testo ufficiale, con ancora all'articolo quando possibile |
| `stato` | Esito deterministico, vedi sotto |
| `testo.vigente` | Testo consolidato, senza richiami alle note né doppie parentesi |
| `testo.con_marcatori` | Testo come pubblicato, con `((n))` e `((testo modificato))` |
| `testo.caratteri` | Lunghezza del testo vigente |
| `note` | Note ufficiali di aggiornamento, strutturate |
| `impronta` | `sha256:` del contenuto normativo (testo, note, stato) |

### Fonti citabili

Ogni articolo porta due link, entrambi a siti istituzionali, così che chi riceve un parere
possa verificarlo senza fidarsi di chi lo ha prodotto:

- `articolo.url` — il testo consolidato su Normattiva, con l'ancora all'articolo
  (`…;262~art2043`): è il formato che Normattiva usa nei propri collegamenti interni;
- `codice.atto.gazzetta.url` — il PDF della pubblicazione originale dell'atto in Gazzetta
  Ufficiale. È l'atto come pubblicato, non il testo aggiornato: serve a verificare l'atto
  di partenza, non le modifiche successive.

Il campo `impronta` dice se il contenuto normativo è cambiato dall'ultima lettura.

### `stato`

| Campo | Valori | Uso |
| --- | --- | --- |
| `codice` | `vigente`, `abrogato`, `dichiarato_incostituzionale`, `parzialmente_inapplicabile`, `da_verificare`, `assente_dalla_fonte` | Decisione principale |
| `inapplicabile` | `true`, `false`, `null` | `true` solo se l'intero articolo è caduto |
| `certezza` | `alta`, `media`, `bassa` | Affidabilità della ricostruzione |
| `motivazione` | testo | Perché lo stato è quello |
| `parti_non_applicabili` | lista | Commi indicati dalle pronunce, es. `comma 3` |
| `elementi` | lista | Note che hanno prodotto lo stato, con numero e ambito |

### `note`

| Campo | Contenuto |
| --- | --- |
| `numero` | Numero della nota nel testo ufficiale |
| `effetto` | `abrogazione`, `illegittimita_costituzionale`, `revoca_illegittimita`, `modifica`, `altro` |
| `ambito` | `intero`, `commi`, `parte`, `non_determinato` |
| `parti` | Commi citati, quando `ambito` è `commi` |
| `atti` | Atti citati dalla nota, con URN e data di Gazzetta quando nota |
| `sentenza` | Organo, data e numero della pronuncia, quando la nota la riporta |
| `testo` | Testo integrale della nota |

## Come si determina lo stato

Le regole sono applicate in quest'ordine e sono le stesse per tutti i codici.

1. Se il testo consolidato riporta `ARTICOLO ABROGATO DA ...`, lo stato è `abrogato`,
   certezza alta, con l'atto nel campo `elementi[].fonte`.
2. Se una nota dichiara l'abrogazione dell'intero articolo, lo stato è `abrogato`.
3. Se una nota dichiara l'illegittimità costituzionale dell'intero articolo, lo stato è
   `dichiarato_incostituzionale`.
4. Se l'effetto riguarda commi o parti (`nella parte in cui`, `limitatamente a`, commi
   indicati) lo stato è `parzialmente_inapplicabile`, con `parti_non_applicabili` valorizzato
   e `inapplicabile: null`.
5. Se una nota di errata corrige esclude una dichiarazione di illegittimità, lo stato è
   `da_verificare`: la fonte contraddice sé stessa e la decisione spetta a chi legge.
6. Se una nota segnala un effetto senza che se ne possa determinare l'oggetto, lo stato è
   `da_verificare`, certezza bassa.
7. Altrimenti lo stato è `vigente`, certezza alta.

Le modifiche non cambiano lo stato: un articolo modificato resta vigente. Le citazioni tra
virgolette non contano come effetto sull'articolo: una nota che riferisce l'abrogazione di
altri articoli non rende abrogato quello che la riporta.

## Cosa il formato non dice

- **Non** dice quanti commi abbia un articolo: il testo consolidato non li numera.
- **Non** dice la data di entrata in vigore di una modifica: la data di Gazzetta è quella
  di pubblicazione, non quella di decorrenza.
- **Non** interpreta: non distingue una norma incostituzionale nel merito da una
  interpretativa. Riporta quello che l'atto dice e lo classifica con regole fisse.

## Garanzie sulle scritture

- I file cambiano solo se cambia il contenuto: due sincronizzazioni consecutive sugli stessi
  dati producono zero modifiche.
- La data di aggiornamento è unica per codice (`index.json`), non ripetuta in ogni articolo.
- Un articolo che scompare dall'export non viene cancellato: viene marcato
  `assente_dalla_fonte` e conserva l'ultimo testo noto.
