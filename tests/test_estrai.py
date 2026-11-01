"""Test delle regole di lettura, con un export AKN minimo ma realistico."""

from __future__ import annotations

import unittest

from sync import estrai

AKN = """<?xml version="1.0" encoding="UTF-8"?>
<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0">
  <act>
    <doc name="Codice Penale-art. 1">
      <meta><identification><FRBRWork>
        <FRBRalias name="urn:nir" value="urn:nir:stato:regio.decreto:1930-10-19;1398"/>
        <FRBRthis value="/akn/it/act/regio_decreto/stato/1930-10-19/1398/!main/annesso_1"/>
      </FRBRWork></identification></meta>
      <mainBody><paragraph><content><p> Art. 1. (Reati e pene). Nessuno puo' essere punito. </p></content></paragraph></mainBody>
    </doc>
    <doc name="Codice Penale-art. 17">
      <meta><identification><FRBRWork>
        <FRBRthis value="/akn/it/act/regio_decreto/stato/1930-10-19/1398/!main/annesso_2"/>
      </FRBRWork></identification></meta>
      <mainBody><paragraph><content><p> Art. 17. ((ARTICOLO ABROGATO DALLA L. 31 MAGGIO 1995, N. 218)) </p></content></paragraph></mainBody>
    </doc>
    <doc name="Codice Penale-art. 240 bis">
      <meta><identification><FRBRWork>
        <FRBRthis value="/akn/it/act/regio_decreto/stato/1930-10-19/1398/!main/annesso_3"/>
      </FRBRWork></identification></meta>
      <mainBody><paragraph><content><p> Art. 240-ter. (( (Confisca per equivalente).)) ((Nei casi di condanna si applica la confisca.)) </p></content></paragraph></mainBody>
    </doc>
    <doc name="Codice Penale-art. 559">
      <meta><identification><FRBRWork>
        <FRBRthis value="/akn/it/act/regio_decreto/stato/1930-10-19/1398/!main/annesso_4"/>
      </FRBRWork></identification></meta>
      <mainBody>
        <paragraph><content><p> Art. 559. (Adulterio) La moglie adultera e' punita. ((42)) Il delitto e' punibile a querela. ((46)) </p></content></paragraph>
        <paragraph><content>
          <p> ------------- AGGIORNAMENTO (42) La Corte Costituzionale, con sentenza 16 - 19 dicembre 1968, n. 126 (in G.U. 1a s.s. 28/12/1968, n. 329), ha dichiarato l'illegittimita' costituzionale del primo e del secondo comma del presente articolo. </p>
          <p> ------------- AGGIORNAMENTO (46) La Corte Costituzionale, con sentenza 27 novembre - 3 dicembre 1969, n. 147 (in G.U. 1a s.s. 10/12/1969, n. 311), ha dichiarato la illegittimita' costituzionale dell'art. 559, comma terzo del Codice penale. </p>
        </content></paragraph>
      </mainBody>
    </doc>
    <doc name="Codice Penale-art. 603">
      <meta><identification><FRBRWork>
        <FRBRthis value="/akn/it/act/regio_decreto/stato/1930-10-19/1398/!main/annesso_5"/>
      </FRBRWork></identification></meta>
      <mainBody>
        <paragraph><content><p> Art. 603. (Plagio) Chiunque sottopone una persona al proprio potere. </p></content></paragraph>
        <paragraph><content>
          <p> ------------- AGGIORNAMENTO (88) La Corte Costituzionale, con sentenza 9 aprile - 8 giugno 1981, n. 96 (in G.U. 1a s.s. 10/6/1981, n. 158), ha dichiarato l'illegittimita' costituzionale del presente articolo. </p>
        </content></paragraph>
      </mainBody>
    </doc>
    <doc name="Codice Penale-art. 100">
      <meta><identification><FRBRWork>
        <FRBRthis value="/akn/it/act/regio_decreto/stato/1930-10-19/1398/!main/annesso_6"/>
      </FRBRWork></identification></meta>
      <mainBody>
        <paragraph><content><p> Art. 100. (Modifiche). Il testo e' modificato. </p></content></paragraph>
        <paragraph><content>
          <p> ------------- AGGIORNAMENTO (7) Il <ref href="/akn/it/act/legge/stato/2020-01-01/10/!main">D.Lgs. 1 gennaio 2020, n. 10</ref> ha disposto (con l'art. 2, comma 1) la modifica del comma 1 dell'art. 100. </p>
        </content></paragraph>
      </mainBody>
    </doc>
  </act>
</akomaNtoso>
"""

AGGIORNAMENTI = """
<table><tr><th>Progr.</th><th>data</th><th>aggiornamenti</th></tr>
<tr>
  <td>1</td>
  <td>09/02/2020</td>
  <td><ul>
    <li>DECRETO LEGISLATIVO 1 gennaio 2020, n. 10 (in G.U. 09/02/2020, n.5)</li>
    <li><a href="#">ha disposto (con l'art. 2, comma 1) la modifica dell'art. 100.</a></li>
    <li><a href="#">ha disposto (con l'art. 3) l'abrogazione del comma terzo dell'art. 101.</a></li>
  </ul></td>
</tr></table>
"""


class LetturaArticoli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.urn, cls.articoli = estrai.leggi_akn(AKN.encode("utf-8"))
        cls.per_numero = {a["numero"]: a for a in cls.articoli}

    def test_urn_atto(self):
        self.assertEqual(self.urn, "urn:nir:stato:regio.decreto:1930-10-19;1398")

    def test_numero_dal_testo_prevale_sull_etichetta(self):
        self.assertIn("240-ter", self.per_numero)
        self.assertNotIn("240-bis", self.per_numero)
        self.assertEqual(self.per_numero["240-ter"]["rubrica"], "Confisca per equivalente")

    def test_rubrica_tra_parentesi(self):
        self.assertEqual(
            self.per_numero["1"]["rubrica"], "Reati e pene"
        )
        self.assertEqual(
            self.per_numero["1"]["testo"], "Nessuno puo' essere punito."
        )

    def test_abrogazione_espressa(self):
        stato = estrai.valuta_stato(
            self.per_numero["17"]["testo"], self.per_numero["17"]["note"]
        )
        self.assertEqual(stato["codice"], "abrogato")
        self.assertTrue(stato["inapplicabile"])
        self.assertIn("31 MAGGIO 1995", stato["elementi"][0]["fonte"])

    def test_incostituzionalita_totale(self):
        articolo = self.per_numero["603"]
        stato = estrai.valuta_stato(articolo["testo"], articolo["note"])
        self.assertEqual(stato["codice"], "dichiarato_incostituzionale")
        self.assertTrue(stato["inapplicabile"])
        self.assertEqual(
            articolo["note"][0]["sentenza"],
            {"organo": "Corte costituzionale", "data": "1981-06-08", "numero": "96"},
        )

    def test_incostituzionalita_per_commi(self):
        articolo = self.per_numero["559"]
        stato = estrai.valuta_stato(articolo["testo"], articolo["note"])
        self.assertEqual(stato["codice"], "parzialmente_inapplicabile")
        self.assertEqual(
            stato["parti_non_applicabili"], ["comma 1", "comma 2", "comma 3"]
        )

    def test_modifica_non_incide_sullo_stato(self):
        articolo = self.per_numero["100"]
        self.assertEqual(articolo["note"][0]["effetto"], "modifica")
        self.assertEqual(
            articolo["note"][0]["atti"][0]["urn"],
            "urn:nir:stato:legge:2020-01-01;10",
        )
        stato = estrai.valuta_stato(articolo["testo"], articolo["note"])
        self.assertEqual(stato["codice"], "vigente")

    def test_note_separate_dal_testo(self):
        articolo = self.per_numero["559"]
        self.assertEqual(len(articolo["note"]), 2)
        self.assertNotIn("AGGIORNAMENTO", articolo["testo"])
        self.assertIn("((42))", articolo["testo_con_marcatori"])


class Numerazione(unittest.TestCase):
    def test_varianti(self):
        casi = {
            "Art. 2043. (Risarcimento) x": "2043",
            "Art. 230 ter. (Diritti) x": "230-ter",
            "Art. 270-quinquies.1 (( (Finanziamento).)) x": "270-quinquies.1",
            "Art. 635.1 (( (Gruppo).)) x": "635.1",
        }
        for testo, atteso in casi.items():
            with self.subTest(testo=testo):
                self.assertEqual(estrai._numero_dal_testo(testo), atteso)

    def test_elenco_numerato_non_diventa_suffisso(self):
        self.assertEqual(estrai._numero_dal_testo("Art. 5. 1) primo caso"), "5")

    def test_ordine(self):
        ordinati = sorted(["2043", "2043-bis", "10", "270-quinquies.1"], key=estrai.ordine)
        self.assertEqual(ordinati, ["10", "270-quinquies.1", "2043", "2043-bis"])


class Testo(unittest.TestCase):
    def test_pulisci(self):
        self.assertEqual(
            estrai.pulisci("Il debitore ((deve)) comportarsi (12) cosi'."),
            "Il debitore deve comportarsi cosi'.",
        )

    def test_rubrica_in_doppie_parentesi(self):
        corpo, rubrica = estrai._intestazione(
            "Art. 157. ((Cessazione degli effetti della separazione.)) Il resto."
        )
        self.assertEqual(rubrica, "Cessazione degli effetti della separazione")
        self.assertEqual(corpo, "Il resto.")

    def test_rubrica_non_puo_essere_tutto_il_testo(self):
        corpo, rubrica = estrai._intestazione(
            "Art. 155. ((In caso di separazione si applicano le disposizioni del Capo II.))"
        )
        self.assertIsNone(rubrica)
        self.assertEqual(
            corpo, "((In caso di separazione si applicano le disposizioni del Capo II.))"
        )

    def test_abrogazione_confermata(self):
        stato = estrai.valuta_stato(
            "IL D.LGS. LUOGOTENENZIALE 14 SETTEMBRE 1944, N. 287 HA CONFERMATO "
            "L'ABROGAZIONE DEL PRESENTE ARTICOLO",
            [],
        )
        self.assertEqual(stato["codice"], "abrogato")
        self.assertIn("287", stato["elementi"][0]["fonte"])

    def test_articolo_non_piu_previsto(self):
        stato = estrai.valuta_stato(
            "ARTICOLO NON PIU' PREVISTO A SEGUITO DELLA SOSTITUZIONE DEL LIBRO V "
            "DISPOSTA DAL D.LGS. 17 GENNAIO 2003, N. 6",
            [],
        )
        self.assertEqual(stato["codice"], "abrogato")
        self.assertIn("2003", stato["elementi"][0]["fonte"])

    def test_abrogazione_di_un_comma_non_abroga_l_articolo(self):
        stato = estrai.valuta_stato(
            "La capacita' giuridica si acquista dal momento della nascita. "
            "IL D.LGS. LUOGOTENENZIALE 14 SETTEMBRE 1944, N. 287 HA CONFERMATO "
            "L'ABROGAZIONE DEL PRESENTE COMMA",
            [],
        )
        self.assertEqual(stato["codice"], "da_verificare")
        self.assertIsNone(stato["inapplicabile"])

    def test_testo_assente_non_e_vigente(self):
        self.assertEqual(estrai.valuta_stato(".", [])["codice"], "da_verificare")


class Storico(unittest.TestCase):
    def test_eventi_e_date(self):
        eventi = estrai.leggi_aggiornamenti(AGGIORNAMENTI)
        self.assertEqual(len(eventi), 1)
        evento = eventi[0]
        self.assertEqual(evento["data_gazzetta"], "2020-02-09")
        self.assertEqual([e["azione"] for e in evento["effetti"]], ["modifica", "abrogazione"])
        self.assertEqual(evento["effetti"][1]["articoli"], ["101"])
        mappa = estrai.indice_date(eventi)
        self.assertEqual(mappa[("2020-01-01", "10")], "2020-02-09")


class Pagina(unittest.TestCase):
    PAGINA = """
    <meta about="na:id/1942/04/04/042U0262/CONSOLIDATED" property="eli:version_date" content="2026-11-01" />
    <meta property="eli:realizes" resource="na:id/1942/04/04/042U0262/CONSOLIDATED" />
    <a href="/do/atto/caricaAKN?dataGU=19420404&amp;codiceRedaz=042U0262&amp;dataVigenza=20261101">akn</a>
    <a href="/esporta/attoCompleto?atto.dataPubblicazioneGazzetta=1942-04-04&amp;atto.codiceRedazionale=042U0262">atto</a>
    <a href="https://www.gazzettaufficiale.it/eli/gu/1942/04/04/79/sg/pdf">GU</a>
    <meta name="description" content="Approvazione del testo del Codice civile. (042U0262)" />
    <title>REGIO DECRETO 16 marzo 1942, n. 262 - Normattiva</title>
    """

    def test_metadati(self):
        dati = estrai.leggi_pagina(self.PAGINA)
        self.assertEqual(dati["data_vigenza"], "2026-11-01")
        self.assertEqual(dati["akn"]["codice_redazionale"], "042U0262")
        self.assertEqual(dati["akn"]["data_gu"], "19420404")
        self.assertEqual(dati["eli"], "eli/id/1942/04/04/042U0262/CONSOLIDATED/20261101")
        self.assertEqual(
            dati["gazzetta"],
            {
                "numero": 79,
                "data": "1942-04-04",
                "url": "https://www.gazzettaufficiale.it/eli/gu/1942/04/04/79/sg/pdf",
            },
        )
        self.assertEqual(dati["titolo"], "Approvazione del testo del Codice civile.")
        self.assertEqual(dati["denominazione_atto"], "REGIO DECRETO 16 marzo 1942, n. 262")


if __name__ == "__main__":
    unittest.main()
