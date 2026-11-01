"""Accesso a normattiva.it.

Una sessione HTTP e tre richieste per codice: pagina consolidata, export
Akoma Ntoso, elenco degli aggiornamenti all'atto. La sessione e' necessaria:
gli endpoint secondari rispondono "Sessione Scaduta" senza cookie.
"""

from __future__ import annotations

import time

import requests

BASE = "https://www.normattiva.it"
UA = "leggi-italiane/1.0 (+https://github.com/Andrea-Bruno/leggi-italiane)"


class ErroreFonte(RuntimeError):
    pass


class Normattiva:
    def __init__(self, pausa: float = 1.5, tentativi: int = 4, timeout: int = 240):
        self.http = requests.Session()
        self.http.headers.update(
            {"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"}
        )
        self.pausa = pausa
        self.tentativi = tentativi
        self.timeout = timeout
        self.referer: str | None = None

    def _get(self, percorso: str, tipo_atteso: str) -> requests.Response:
        url = BASE + percorso
        ultimo = ""
        for tentativo in range(1, self.tentativi + 1):
            try:
                risposta = self.http.get(
                    url,
                    timeout=self.timeout,
                    headers={"Referer": self.referer} if self.referer else None,
                )
                tipo = risposta.headers.get("Content-Type", "")
                if risposta.status_code == 200 and tipo.startswith(tipo_atteso):
                    time.sleep(self.pausa)
                    return risposta
                ultimo = f"HTTP {risposta.status_code}, Content-Type {tipo!r}"
                if risposta.status_code in (403, 404):
                    break
            except requests.RequestException as errore:
                ultimo = str(errore)
            time.sleep(min(2**tentativo, 30))
        raise ErroreFonte(f"richiesta fallita: {url} ({ultimo})")

    def pagina(self, urn: str) -> str:
        """Testo consolidato dell'atto e avvio della sessione."""
        self.referer = f"{BASE}/uri-res/N2Ls?{urn}"
        return self._get(f"/uri-res/N2Ls?{urn}", "text/html").text

    def akn(self, data_gu: str, codice_redazionale: str, data_vigenza: str) -> bytes:
        """Export Akoma Ntoso dell'intero atto alla data di vigenza indicata."""
        percorso = (
            f"/do/atto/caricaAKN?dataGU={data_gu}"
            f"&codiceRedaz={codice_redazionale}&dataVigenza={data_vigenza}"
        )
        return self._get(percorso, "text/xml").content

    def aggiornamenti(self, data_pubblicazione: str, codice_redazionale: str) -> str:
        """Elenco completo degli aggiornamenti all'atto, con date di Gazzetta."""
        percorso = (
            "/do/atto/vediAggiornamentiAllAtto"
            f"?atto.dataPubblicazioneGazzetta={data_pubblicazione}"
            f"&atto.codiceRedazionale={codice_redazionale}"
        )
        return self._get(percorso, "text/html").text
