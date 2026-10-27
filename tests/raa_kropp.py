#!/usr/bin/env python3
"""Rå HTTP-anrop genom Caddy för 9.9d (verify_ap9.sh): avbruten kropp och långsam kropp, som curl inte kan göra.

Anropen bär SAMMA tillträdeskaka som testets curl (ur kakburken från demo_inloggning) och går till den publika adressens
schema/värd/port (https med SNI på servern). En positiv kontroll med samma transport visar att anropen verkligen når
dashboarden och inte fastnar i lösenordsgrinden (fynd E1 i del e). Kakans värde skrivs aldrig ut.

  python3 tests/raa_kropp.py <PUBLIK_URL_KONTROLLRUM> <kakburk> {positiv|avbryt|langsam}
"""
import json
import os
import socket
import ssl
import sys
import time
from urllib.parse import urlsplit

bas, kakburk, lage = sys.argv[1], sys.argv[2], sys.argv[3]
u = urlsplit(bas)
vard, schema = u.hostname, u.scheme
port = u.port or (443 if schema == "https" else 80)
origin = "%s://%s" % (schema, u.netloc)

kaka = ""
try:
    for rad in open(kakburk, encoding="utf-8"):
        delar = rad.rstrip("\n").split("\t")
        if len(delar) >= 7 and delar[5] == "svada_tilltrade":
            kaka = delar[6]
except OSError:
    pass
if not kaka and os.environ.get("DEMO_GATE", "on") != "off":
    print("UTAN_KAKA")          # anroparen räknar detta som fel: provet skulle annars testa grinden, inte backend
    sys.exit(0)


def oppna():
    s = socket.create_connection(("127.0.0.1" if vard.endswith(".localhost") else vard, port), timeout=25)
    if schema == "https":
        s = ssl.create_default_context().wrap_socket(s, server_hostname=vard)
    return s


def rubrik(sokvag, langd):
    return ("POST %s HTTP/1.1\r\nHost: %s\r\nOrigin: %s\r\nCookie: svada_tilltrade=%s\r\nContent-Type: application/json\r\n"
            "Content-Length: %d\r\nConnection: close\r\n\r\n" % (sokvag, u.netloc, origin, kaka, langd)).encode()


def las_svar(s):
    data = b""
    try:
        while True:
            bit = s.recv(65536)
            if not bit:
                break
            data += bit
    except (socket.timeout, OSError):
        pass
    return data


if lage == "positiv":
    kropp = b"{}"
    s = oppna(); s.sendall(rubrik("/api/atgard/okand-prov", len(kropp)) + kropp)
    svar = las_svar(s); s.close()
    huvud, _, text = svar.partition(b"\r\n\r\n")
    status = huvud.split(b" ")[1].decode() if huvud.startswith(b"HTTP/") else "000"
    try:
        kod = json.loads(text.decode("utf-8", "replace") or "{}").get("kod", "")
    except ValueError:
        kod = ""
    print("POSITIV %s %s" % (status, kod or "-"))
elif lage == "avbryt":
    for sokvag, del_ in (("/api/atgard/kor-batch", b'{"a": '), ("/api/felinjektion", b'{"schemadrift": tru')):
        s = oppna(); s.sendall(rubrik(sokvag, 500) + del_)
        time.sleep(0.5); s.close()
    print("AVBRUTET 2")
elif lage == "langsam":
    s = oppna(); s.sendall(rubrik("/api/atgard/okand-prov", 100) + b"{")
    t0 = time.time()
    svar = las_svar(s); s.close()
    huvud = svar.split(b"\r\n", 1)[0].decode("latin-1", "replace")
    print("LANGSAM %.1f %s" % (time.time() - t0, huvud.replace(" ", "_") or "stängd"))
