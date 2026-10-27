#!/usr/bin/env bash
# Enhetstest av nattens återställningsomslag och upptidskontrollen (utan Docker).
set -u
cd "$(dirname "$0")/.."
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fel=0
ok() { echo "  OK   $1"; }
bad() { echo "  FEL  $1"; fel=1; }

# Stubb: misslyckas första gången, lyckas andra.
cat > "$T/stubb1.sh" <<S
n=\$(cat "$T/n" 2>/dev/null || echo 0); echo \$((n+1)) > "$T/n"; [ \$n -ge 1 ]
S
rm -f "$T/n"
ATERSTALL_SKRIPT="$T/stubb1.sh" PAUS_S=1 bash tools/server/aterstall-med-forsok.sh >/dev/null && [ "$(cat "$T/n")" = 2 ] \
  && ok "misslyckas först, lyckas vid nytt försök (2 körningar, exit 0)" || bad "andra försöket"

# Räknande stubb även här (del e, E10): exakt två körningar, inte ett tredje försök.
cat > "$T/stubb2.sh" <<S
n=\$(cat "$T/n" 2>/dev/null || echo 0); echo \$((n+1)) > "$T/n"; false
S
rm -f "$T/n"
ATERSTALL_SKRIPT="$T/stubb2.sh" PAUS_S=1 bash tools/server/aterstall-med-forsok.sh >/dev/null; r=$?
[ $r = 1 ] && [ "$(cat "$T/n")" = 2 ] && ok "två misslyckanden ger exit 1 efter exakt två körningar (inget tredje försök)" || bad "dubbelfel: exit $r, körningar $(cat "$T/n" 2>/dev/null)"

echo 'true' > "$T/stubb3.sh"; s=$(date +%s)
ATERSTALL_SKRIPT="$T/stubb3.sh" PAUS_S=30 bash tools/server/aterstall-med-forsok.sh >/dev/null; r=$?
[ $r = 0 ] && [ $(( $(date +%s) - s )) -lt 5 ] && ok "lyckat första försök väntar inte" || bad "lyckat första försök"

# Upptidskontrollen mot en liten server som svarar 200/503.
python3 - "$T" <<'PY' &
import http.server, sys, os
t = sys.argv[1]
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        läge = open(t + "/lage").read().strip()
        start_ok = läge in ("ok", "api500", "apihtml", "apijsonfel")
        if self.path.startswith("/api/") and läge == "ok":
            b = b'{"nastaUtc":null}'; self.send_response(200)
        elif self.path.startswith("/api/") and läge == "api500":
            b = b'{"fel":"nastaUtc saknas"}'; self.send_response(500)
        elif self.path.startswith("/api/") and läge == "apihtml":
            b = b"<html>nastaUtc</html>"; self.send_response(200)
        elif self.path.startswith("/api/") and läge == "apijsonfel":
            b = b'{"annat":"nastaUtc"}'; self.send_response(200)
        elif start_ok and self.path == "/":
            b = b"x"; self.send_response(200)
        elif läge == "uppehall":
            b = "<h1>Demon nollställs</h1>".encode(); self.send_response(503)
        elif läge == "annat503":
            b = b"Service Unavailable"; self.send_response(503)
        else:
            b = b"e"; self.send_response(500)
        self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
s = http.server.HTTPServer(("127.0.0.1", 0), H)
open(t + "/port", "w").write(str(s.server_port)); s.serve_forever()
PY
SRV=$!
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -s "$T/port" ] && break; sleep 0.3; done
U="http://127.0.0.1:$(cat "$T/port")"
echo ok > "$T/lage";       bash tools/server/kontrollera-demo.sh "$U" >/dev/null; [ $? = 0 ] && ok "kontroll: friskt svar → 0" || bad "kontroll ok"
echo uppehall > "$T/lage"; bash tools/server/kontrollera-demo.sh "$U" >/dev/null; [ $? = 2 ] && ok "kontroll: 503 → 2 (nollställs)" || bad "kontroll 503"
echo fel > "$T/lage";      bash tools/server/kontrollera-demo.sh "$U" >/dev/null; [ $? = 1 ] && ok "kontroll: 500 → 1" || bad "kontroll 500"
# Blandade fall (del e, E10): startsidan 200 men API:t fel ska ge 1, och ett 503 utan demons underhållssida är ett fel.
echo api500 > "$T/lage";     bash tools/server/kontrollera-demo.sh "$U" >/dev/null; [ $? = 1 ] && ok "kontroll: startsida 200 + API 500 (med ordet nastaUtc) → 1" || bad "API 500"
echo apihtml > "$T/lage";    bash tools/server/kontrollera-demo.sh "$U" >/dev/null; [ $? = 1 ] && ok "kontroll: API 200 men HTML → 1" || bad "API HTML"
echo apijsonfel > "$T/lage"; bash tools/server/kontrollera-demo.sh "$U" >/dev/null; [ $? = 1 ] && ok "kontroll: API 200, JSON utan fältet → 1" || bad "API JSON utan fält"
echo annat503 > "$T/lage";   bash tools/server/kontrollera-demo.sh "$U" >/dev/null; [ $? = 1 ] && ok "kontroll: 503 utan underhållssidan → 1" || bad "annat 503"
kill $SRV 2>/dev/null
[ $fel = 0 ] && echo "ALLT OK" || { echo "FEL"; exit 1; }
