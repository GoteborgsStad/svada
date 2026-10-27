#!/usr/bin/env python3
"""Hård regel 4 (taggar låses, inga :latest) prövad på varje image-referens, inte bara som strängsökning (del e, E14).

Samlar varje FROM i Dockerfile, varje image: i compose.*.yml och varje *_IMAGE i .env, löser ${VAR} och ${VAR:-standard}
mot .env och kräver en uttrycklig tagg som inte är latest. En okänd variabel är också ett fel (då vet vi inte vad som byggs).
Skriver en rad per fel och avslutar med antalet fel; vid noll skriver den "OK <antal referenser>".
Digest-låsning (@sha256:…) krävs INTE: regeln gäller versionstaggar."""
import glob
import re
import sys

env = {}
for rad in open(".env", encoding="utf-8"):
    m = re.match(r"^([A-Z0-9_]+)=([^#]*)", rad)
    if m:
        env[m.group(1)] = m.group(2).strip().strip('"\'')


# build.args i compose sätter Dockerfile-argument ur .env (t.ex. CADDY_RUNTIME_IMAGE: ${CADDY_IMAGE}).
for f in sorted(glob.glob("compose.*.yml")):
    for rad in open(f, encoding="utf-8"):
        m = re.match(r"^\s+([A-Z0-9_]+):\s*\$\{([A-Z0-9_]+)\}\s*$", rad)
        if m and m.group(1) not in env and env.get(m.group(2)):
            env[m.group(1)] = env[m.group(2)]


def los(v, lokala=None):
    lokala = lokala or {}
    def ers(m):
        namn, std = m.group(1), m.group(3)
        if namn in env and env[namn]:
            return env[namn]
        if namn in lokala and lokala[namn]:
            return lokala[namn]
        if std is not None:
            return std
        raise KeyError(namn)
    return re.sub(r"\$\{([A-Z0-9_]+)(:-([^}]*))?\}", ers, v)


fel, antal = [], 0


def prova(kalla, ref):
    global antal
    antal += 1
    namn = ref.split("@")[0]
    sista = namn.rsplit("/", 1)[-1]
    if "@sha256:" in ref:
        return
    if ":" not in sista:
        fel.append("%s: '%s' saknar tagg" % (kalla, ref))
    elif sista.rsplit(":", 1)[1] in ("latest", ""):
        fel.append("%s: '%s' har rörlig tagg" % (kalla, ref))


for f in sorted(glob.glob("compose.*.yml")):
    for nr, rad in enumerate(open(f, encoding="utf-8"), 1):
        m = re.match(r"^\s*image:\s*(\S+)", rad)
        if m:
            try:
                prova("%s:%d" % (f, nr), los(m.group(1)))
            except KeyError as e:
                fel.append("%s:%d: okänd variabel %s" % (f, nr, e))
for f in sorted(set(glob.glob("**/Dockerfile", recursive=True))):
    if "node_modules" in f or "/upstream/" in f:
        continue
    lokala, steg = {}, set()
    for nr, rad in enumerate(open(f, encoding="utf-8"), 1):
        a = re.match(r"^ARG\s+([A-Z0-9_]+)(=(\S+))?", rad)
        if a:
            lokala[a.group(1)] = a.group(3)
        m = re.match(r"^FROM\s+(\S+)(\s+AS\s+(\S+))?", rad, re.I)
        if m:
            ref = m.group(1)
            if m.group(3):
                steg.add(m.group(3))
            if ref in steg or ref == "scratch":
                continue
            try:
                prova("%s:%d" % (f, nr), los(ref, lokala))
            except KeyError as e:
                fel.append("%s:%d: okänd variabel %s" % (f, nr, e))
for namn, v in env.items():
    if namn.endswith("_IMAGE") and v:
        prova(".env:%s" % namn, v)
for r in fel:
    print(r)
if not fel:
    print("OK %d" % antal)
sys.exit(min(len(fel), 99))
