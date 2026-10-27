#!/usr/bin/env python3
"""Råmätvärdeslagret: läser sensorbrunnen SSO1_01-4526 ur orion-dhi.

GOTCHA: allt som läser orion-dhi
MÅSTE skicka headern "NGSILD-Tenant: dhi". Utan den svarar Orion-LD med en
TOM LISTA – inte 404 – vilket är extra förvillande.

Klassen MatvardesFonster pollar entiteten och håller ett glidande fönster
av unika mätpunkter (observedAt, totalFlow, spillFlow). Fönstret är den
"glidande beräkningens" indata: bräddmodellen i modell.py aggregerar över
det, och de 90 sensorlösa brunnarna får sina syntetiska serier genom att
skala om samma fönster (brunnspecifikt).
"""

import json
import os
import threading
import time
import urllib.error
import urllib.request
from collections import deque


class MatvardesFonster:
    def __init__(self, orion_url, entitets_id, tenant, fonster=576,
                 intervall_s=5.0):
        self.orion_url = orion_url.rstrip("/")
        self.entitets_id = entitets_id
        self.tenant = tenant
        self.intervall_s = intervall_s
        # 576 punkter à 5 min = två dygn av rådataserien.
        self._punkter = deque(maxlen=fonster)
        self._sedda = deque(maxlen=fonster)
        self._las = threading.Lock()
        self._stopp = threading.Event()
        self.senaste_fel = None
        self.antal_pollningar = 0

    # ---- läsning mot Orion-LD -------------------------------------------
    def hamta_entitet(self):
        url = "%s/ngsi-ld/v1/entities/%s" % (self.orion_url, self.entitets_id)
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        req.add_header("NGSILD-Tenant", self.tenant)   # obligatorisk, se ovan
        with urllib.request.urlopen(req, timeout=10) as svar:
            return json.loads(svar.read().decode("utf-8", "replace"))

    def _poll_en_gang(self):
        try:
            ent = self.hamta_entitet()
            tf = ent.get("totalFlow", {})
            sf = ent.get("spillFlow", {})
            observed = tf.get("observedAt") or sf.get("observedAt")
            if observed is None or "value" not in tf:
                return
            punkt = {
                "observedAt": observed,
                "totalFlow": float(tf.get("value", 0.0)),
                "spillFlow": float(sf.get("value", 0.0)),
                "weirId": (ent.get("weirId") or {}).get("value"),
            }
            with self._las:
                if observed in self._sedda:
                    return
                self._sedda.append(observed)
                self._punkter.append(punkt)
            self.senaste_fel = None
        except urllib.error.HTTPError as fel:
            self.senaste_fel = "HTTP %d från orion-dhi" % fel.code
        except Exception as fel:                      # noqa: BLE001 – loggas
            self.senaste_fel = "%s: %s" % (type(fel).__name__, fel)
        finally:
            self.antal_pollningar += 1

    # ---- trådstyrning ----------------------------------------------------
    def starta(self):
        t = threading.Thread(target=self._loop, name="matvarden", daemon=True)
        t.start()
        return t

    def _loop(self):
        while not self._stopp.is_set():
            self._poll_en_gang()
            self._stopp.wait(self.intervall_s)

    def stoppa(self):
        self._stopp.set()

    # ---- avläsning -------------------------------------------------------
    def punkter(self):
        """Fönstret sorterat på mätvärdets EGEN tid (observedAt), inte på
        uppspelningsordningen – simulatorn loopar om serien."""
        with self._las:
            kopia = list(self._punkter)
        return sorted(kopia, key=lambda p: p["observedAt"])

    def senaste(self):
        with self._las:
            return self._punkter[-1] if self._punkter else None

    def lage(self):
        senaste = self.senaste()
        return {
            "orionUrl": self.orion_url,
            "entityId": self.entitets_id,
            "tenant": self.tenant,
            "punkterIFonstret": len(self._punkter),
            "pollningar": self.antal_pollningar,
            "senasteMatvarde": senaste,
            "senasteFel": self.senaste_fel,
        }

    def vanta_pa_data(self, sekunder, minst=1):
        """Blockerar tills fönstret har `minst` mätpunkter (eller tiden går ut).

        Returnerar True om kravet nåddes. Anropas vid uppstart så att första
        batchen bygger på riktiga mätvärden i stället för reservmönstret.
        """
        slut = time.time() + sekunder
        while time.time() < slut:
            with self._las:
                if len(self._punkter) >= minst:
                    return True
            time.sleep(0.5)
        with self._las:
            return len(self._punkter) >= minst


class CsvFonster:
    """Svada-mini: mätvärdena läses direkt ur brunn 4526:s CSV-filer.

    Data är oförändrat (samma brunns riktiga värden, 5 minuters upplösning); det som
    försvunnit är sensorledet (MQTT, IoT-agent, orion-dhi) som tidigare spelade upp
    samma filer. Gränssnittet är detsamma som MatvardesFonster, så resten av FCF
    (bräddmodellen, batchproduktionen, API:t) är orört. Hela serien finns från start,
    så täckningsgraden är full från första batchen och resultatet är reproducerbart.
    """

    def __init__(self, csv_total, csv_spill, entitets_id, fonster=576):
        self.csv_total = csv_total
        self.csv_spill = csv_spill
        self.entitets_id = entitets_id
        self.fonster = fonster
        self._punkter = []
        self.senaste_fel = None
        self.antal_pollningar = 0

    @staticmethod
    def _las(sokvag):
        ut = {}
        with open(sokvag, encoding="utf-8") as f:
            next(f)                                   # rubrikraden
            for rad in f:
                rad = rad.strip()
                if not rad:
                    continue
                tid, _, varde = rad.rpartition(",")
                # "2026-06-13 00:05:00" -> "2026-06-13T00:05:00.000Z" (samma format som observedAt)
                ut[tid.replace(" ", "T") + ".000Z"] = float(varde)
        return ut

    def _ladda(self):
        try:
            totalt = self._las(self.csv_total)
            spill = self._las(self.csv_spill)
            tider = sorted(totalt)[-self.fonster:]
            self._punkter = [{"observedAt": t, "totalFlow": totalt[t],
                              "spillFlow": spill.get(t, 0.0),
                              "weirId": self.entitets_id} for t in tider]
            self.senaste_fel = None
        except (OSError, ValueError) as fel:
            self.senaste_fel = "%s: %s" % (type(fel).__name__, fel)
        finally:
            self.antal_pollningar += 1

    def starta(self):
        self._ladda()
        return None

    def stoppa(self):
        pass

    def punkter(self):
        return list(self._punkter)

    def senaste(self):
        return self._punkter[-1] if self._punkter else None

    def lage(self):
        return {
            "kalla": "csv",
            "csvTotal": os.path.basename(self.csv_total),
            "csvSpill": os.path.basename(self.csv_spill),
            "entityId": self.entitets_id,
            "punkterIFonstret": len(self._punkter),
            "pollningar": self.antal_pollningar,
            "senasteMatvarde": self.senaste(),
            "senasteFel": self.senaste_fel,
        }

    def vanta_pa_data(self, sekunder, minst=1):
        return len(self._punkter) >= minst
