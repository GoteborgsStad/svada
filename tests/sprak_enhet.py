#!/usr/bin/env python3
"""K33 (utan stack, körs i dashboard-imagen): språket för kontrollrummets API-svar följer SIDANS språk (huvudet X-Svada-Lang), inte kakan,
och en okänd adress ger en 404-sida för webbläsare men JSON för API-anrop. Externa webbläsartestet 2026-10-23, F7 och F2."""
import os
import sys

for sok in ("/app", "/srv", "/srv/dashboard"):        # sist insatt vinner: den monterade utcheckningen går före imagens inbyggda kod
    if os.path.isdir(sok):
        sys.path.insert(0, sok)
os.environ.setdefault("DEMO_VARIANT", "extern")
import main  # noqa: E402
import asyncio  # noqa: E402

fel = 0


def kolla(villkor, text):
    global fel
    print("  [%s] %s" % ("OK" if villkor else "FEL", text))
    fel += 0 if villkor else 1


class R:
    def __init__(self, q=None, h=None, c=None):
        self.query_params, self.headers, self.cookies = q or {}, h or {}, c or {}


kolla(main._valt_sprak(R(h={"x-svada-lang": "en"}, c={"svada-sprak": "sv"}))[0] == "en", "sidans språk (huvudet) går före kakan: en sida på engelska får engelska svar även om kakan säger svenska")
kolla(main._valt_sprak(R(h={"x-svada-lang": "sv"}, c={"svada-sprak": "en"}))[0] == "sv", "en svensk sida får svenska svar även om en annan flik satt kakan till engelska (F7)")
kolla(main._valt_sprak(R(q={"lang": "sv"}, h={"x-svada-lang": "en"}))[0] == "sv", "?lang= i adressen går före huvudet")
kolla(main._valt_sprak(R(c={"svada-sprak": "en"}))[0] == "en" and main._valt_sprak(R())[0] == "sv", "utan huvud följer språket kakan, och utan kaka är det svenska")
kolla(main._valt_sprak(R(h={"x-svada-lang": "xx"}, c={"svada-sprak": "en"}))[0] == "en", "ett okänt språk i huvudet ignoreras")

def hamta(sokvag, rubriker=None):
    """GET mot appen utan nätverk (ASGI direkt; testklienten kräver ett extra paket som imagen saknar). Returnerar (status, rubriker, text)."""
    vag, _, fraga = sokvag.partition("?")
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET", "scheme": "http", "path": vag,
             "raw_path": vag.encode(), "query_string": fraga.encode(), "server": ("test", 80), "client": ("203.0.113.9", 1234),
             "headers": [(k.lower().encode(), v.encode()) for k, v in (rubriker or {}).items()]}
    ut = {"status": 0, "headers": {}, "body": b""}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(m):
        if m["type"] == "http.response.start":
            ut["status"] = m["status"]
            ut["headers"] = {k.decode().lower(): v.decode() for k, v in m["headers"]}
        elif m["type"] == "http.response.body":
            ut["body"] += m.get("body", b"")
    asyncio.run(main.app(scope, receive, send))
    return ut["status"], ut["headers"], ut["body"].decode("utf-8", "replace")


for lang, rubrik in (("sv", "Sidan finns inte"), ("en", "Page not found")):
    st, h, t = hamta("/finns-inte-alls?lang=" + lang, {"accept": "text/html"})
    kolla(st == 404 and rubrik in t and "detail" not in t, "okänd adress (%s): 404-sida med väg tillbaka, inte rå JSON" % lang)
st, h, t = hamta("/api/finns-inte", {"accept": "text/html"})
kolla(st == 404 and h.get("content-type", "").startswith("application/json"), "okänd API-adress ger JSON, inte en sida")
for v in ("/avtal/", "/avtal/%3Cscript%3E%27%22%C3%A5", "/avtal/" + "x" * 200, "/avtal/a%2Fb"):
    st, h, t = hamta(v)
    kolla(st == 404, "ogiltigt avtals-id %s ger 404 (fick %s), aldrig 500" % (v[:24], st))
print("FEL: %d" % fel if fel else "OK: alla prov gröna")
sys.exit(min(fel, 99))
