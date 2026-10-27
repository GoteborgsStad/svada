"""Enhetsprov av batch-upserten mot Orion-LD (services/ingest-service/ngsild.py, skriv()). Ingen stack: en lokal stubbserver svarar.

Bevisar att 200, 201 och 204 godtas, att 207 godtas bara när `errors` är tom eller saknas, och att en 207 med trasig eller oväntad
kropp, och alla andra felkoder, ger OrionFel (alltså ett loggat avslag i mottagningen) och aldrig ett okontrollerat undantag.

Körs i dashboard-imagen med arbetskopian monterad (tests/verify_kedjevy.sh, K30), eller lokalt:  python3 -I tests/ngsild_enhet.py
"""
import http.server
import os
import sys
import threading

rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sok in ("/srv/ingest-service", "/srv", os.path.join(rot, "services", "ingest-service"), os.path.join(rot, "services")):
    if os.path.isdir(sok):
        sys.path.insert(0, sok)
import ngsild  # noqa: E402

SVAR = {"status": 204, "kropp": b""}


class Stubbe(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(SVAR["status"])
        self.send_header("Content-Length", str(len(SVAR["kropp"])))
        self.end_headers()
        self.wfile.write(SVAR["kropp"])

    def log_message(self, *a):
        pass


server = http.server.HTTPServer(("127.0.0.1", 0), Stubbe)
threading.Thread(target=server.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:%d" % server.server_address[1]
ENT = [{"id": "urn:ngsi-ld:T:1", "type": "T"}]
fel = 0


def prova(namn, status, kropp, forvantat_ok):
    global fel
    SVAR.update(status=status, kropp=kropp)
    try:
        n = ngsild.skriv(URL, ENT)
        ok, text = forvantat_ok, "godtogs (%d skrivna)" % n
    except ngsild.OrionFel as e:
        ok, text = (not forvantat_ok), "OrionFel: %s" % str(e)[:60]
    except Exception as e:  # noqa: BLE001
        ok, text = False, "OKONTROLLERAT %s: %s" % (type(e).__name__, e)
    print("  [%s] %s -> %s" % ("OK" if ok else "FEL", namn, text))
    fel += 0 if ok else 1


prova("204 utan kropp", 204, b"", True)
prova("201 med lista över skapade id", 201, b'["urn:ngsi-ld:T:1"]', True)
prova("200", 200, b"", True)
prova("207 utan fel (success, tom errors)", 207, b'{"success":["urn:ngsi-ld:T:1"],"errors":[]}', True)
prova("207 med tom kropp", 207, b"", True)
prova("207 med fel i errors", 207, b'{"success":[],"errors":[{"entityId":"urn:ngsi-ld:T:1"}]}', False)
prova("207 med ogiltig JSON", 207, b"nej", False)
prova("207 med en lista som kropp", 207, b"[]", False)
prova("207 med en sträng som kropp", 207, b'"x"', False)
prova("400 avslås", 400, b'{"title":"Bad"}', False)
prova("500 avslås", 500, b"", False)
prova("202 (inte ett väntat svar) avslås", 202, b"", False)
server.shutdown()
print("FEL: %d" % fel if fel else "OK: alla prov gröna")
sys.exit(1 if fel else 0)
