# La fonte: Normattiva

I dati provengono da [Normattiva](https://www.normattiva.it), il portale della legge vigente
curato dall'Istituto Poligrafico e Zecca dello Stato per la Presidenza del Consiglio. Ogni
atto ha un URN permanente, per il codice civile `urn:nir:stato:codice.civile:1942-03-16;262`
e per il codice penale `urn:nir:stato:codice.penale:1930-10-19;1398`.

## Le tre richieste

Per ogni codice la sincronizzazione fa tre richieste, tutte nella stessa sessione HTTP:

1. **Pagina consolidata** — `GET /uri-res/N2Ls?<urn>`. Restituisce il testo consolidato
   dell'atto e i metadati: `eli:version_date` (data di vigenza), il link all'export Akoma
   Ntoso con i parametri `dataGU` e `codiceRedaz`, la Gazzetta di pubblicazione.
2. **Export Akoma Ntoso** — `GET /do/atto/caricaAKN?dataGU=...&codiceRedaz=...&dataVigenza=...`.
   Restituisce un XML di alcuni megabyte con un documento per articolo: numero, rubrica,
   testo, note di aggiornamento e riferimenti agli atti modificatori.
3. **Elenco aggiornamenti** — `GET /do/atto/vediAggiornamentiAllAtto?...`. Restituisce la
   tabella di tutti gli atti che hanno modificato l'atto, con data di Gazzetta; serve a
   datare gli atti citati nelle note.

La sessione serve davvero: gli endpoint 2 e 3 rispondono «Sessione Scaduta» se chiamati
senza i cookie ottenuti dalla richiesta 1.

## Perché l'Akoma Ntoso

L'export è una *collezione*: l'elemento radice contiene un `<doc>` per articolo, con
`name` tipo `CODICE CIVILE-art. 2043`, il testo in `<mainBody><paragraph><p>` e le note in
paragrafi successivi, ciascuno aperto da `AGGIORNAMENTO (n)`.

Due trappole note, entrambe gestite:

- **`name` non è il numero dell'articolo.** Gli articoli inseriti dopo il 1942 restano
  raggruppati sotto il numero originario: `Art. 240-ter` compare in un documento chiamato
  `240 bis`, e `Art. 635.1` sotto `635`. Il numero si legge dall'inizio del testo.
- **Le note non sono separate in modo uniforme.** A volte sono paragrafi distinti, a volte
  seguono il testo nello stesso paragrafo: la separazione avviene sul marcatore
  `AGGIORNAMENTO (n)`.

Il testo pubblicato usa le doppie parentesi con un significato preciso: `((n))` è il
richiamo a una nota, `((testo))` è testo inserito o sostituito dall'ultima modifica,
`((...))` è testo soppresso. Il campo `testo.con_marcatori` li conserva, `testo.vigente` li
normalizza.

## Perché non il portale open data

`dati.normattiva.it` espone gli stessi contenuti in blocco, ma risponde `409` con un
messaggio dei sistemi di protezione del Poligrafico a qualunque client che non sia un
browser con JavaScript. Non è utilizzabile da una GitHub Action senza automazione di
browser, quindi la strada scelta è il sito pubblico con sessioni normali.

## Comportamento verso la fonte

- Pausa di 1,5 secondi tra le richieste, utente dichiarato, nessun parallelismo.
- Tre richieste per codice al giorno: l'impatto è trascurabile.
- Errori 5xx e timeout: quattro tentativi con attesa crescente. Errori 403 e 404: nessun
  tentativo, fallimento immediato.
- Un export che sembra incompleto (meno del 95% degli articoli attesi, o data di vigenza
  anteriore alla precedente) blocca la scrittura invece di produrre un aggiornamento
  parziale.

## Natura giuridica dei dati

I testi normativi non sono protetti dal diritto d'autore (art. 5 della legge 633/1941). Il
repository riproduce i testi ufficiali e li arricchisce con metadati ricostruiti; la licenza
MIT riguarda il codice e la documentazione, non i testi di legge. In caso di divergenza
prevale il testo pubblicato in Gazzetta Ufficiale.
