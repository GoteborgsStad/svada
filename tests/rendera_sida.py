#!/usr/bin/env python3
"""Skriver kontrollrummets sida (extern variant) till stdout utan stack, för isolerade webbläsarfixturer
(tests/vy_handelser_webblasare.mjs). Samma anrop som tests/kedjevy_rendering.py. Ett andra argument anger språk (sv/en), ett
tredje, `utestangning`, renderar samordnarrutan med knappar (i den externa varianten har den annars bara ett inspelat exempel)."""
import os
import sys

RAD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "services")
sys.path.insert(0, os.path.join(RAD, "dashboard"))
sys.path.insert(0, RAD)
import kallor  # noqa: E402
import steg    # noqa: E402
import vy      # noqa: E402

KOMP = [{"id": k["id"], "namn": k["namn"], "org": k["org"], "steg": k["steg"],
         "status": "upp", "adress": "", "detalj": "svarar"}
        for k in steg.KOMPONENTER]
sys.stdout.write(vy.sida(steg.STEG, KOMP, kallor.PORTAR, "localhost", 0.5, [], sprak=sys.argv[1] if len(sys.argv) > 1 else "sv",
                         variant="extern", utestangning=(True if "utestangning" in sys.argv[2:] else None)))
