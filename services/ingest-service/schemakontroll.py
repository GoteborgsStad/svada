"""Schemakontroll vid inläsning (MIM2 R3.4): varje entitet staden är på väg att lagra kontrolleras mot datamodellens publicerade JSON Schema.

Schemat är UTKASTET (datamodell/utkast, serveras på /modell): en tillfällig modell framtagen för PoC:en, inte ett slutgiltigt val.
Kontrollen sker i nyckel-värde-form (det förenklade NGSI-LD-formatet som schemat beskriver). Ingen extern pakettjänst: en liten
kontroll av just de nyckelord våra genererade scheman använder (type, const, enum, pattern, required, properties, additionalProperties,
items, minItems, maxItems). Provet tests/schemakontroll_enhet.py jämför mot biblioteket jsonschema när det finns.
Saknas schemat rapporteras det öppet som EJ_KONTROLLERAD; leveransen avvisas inte av det skälet.
"""
import json
import os
import re

KATALOG = os.environ.get("MODELL_KATALOG", "/modell")
MODELL_ID = "SewerOverflowModelResult"
SCHEMAFIL = {"a": "schema.json", "b": "schema-profil-B.json"}
_cache = {}


def _schema(dist):
    namn = SCHEMAFIL[dist.lower()]
    if namn not in _cache:
        try:
            with open(os.path.join(KATALOG, namn), encoding="utf-8") as f:
                _cache[namn] = json.load(f)
        except (OSError, ValueError):
            return namn, None    # läsfelet cachas inte: nästa leverans försöker igen
    return namn, _cache[namn]


def _typ_ok(v, t):
    if t == "string":
        return isinstance(v, str)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "object":
        return isinstance(v, dict)
    if t == "array":
        return isinstance(v, list)
    if t == "null":
        return v is None
    return True


def validera(v, s, rot, sokvag="", fel=None):
    """Lista med (sökväg, orsak) för de ställen där v inte uppfyller s."""
    fel = [] if fel is None else fel
    if s is True:
        return fel
    if s is False:    # ett schema som förbjuder egenskapen (profil B: location och sourceSrs)
        fel.append((sokvag or "/", "finns inte i modellens profil / not in the model's profile"))
        return fel
    if "$ref" in s:
        mal = rot
        for del_ in s["$ref"].lstrip("#/").split("/"):
            mal = mal[del_]
        return validera(v, mal, rot, sokvag, fel)
    t = s.get("type")
    if t is not None and not any(_typ_ok(v, x) for x in (t if isinstance(t, list) else [t])):
        fel.append((sokvag or "/", "fel typ / wrong type (väntade %s)" % t))
        return fel
    if "const" in s and v != s["const"]:
        fel.append((sokvag or "/", "väntade %r / expected %r" % (s["const"], s["const"])))
    if "enum" in s and v not in s["enum"]:
        fel.append((sokvag or "/", "värdet är inte tillåtet / value not allowed"))
    if "pattern" in s and isinstance(v, str) and not re.search(s["pattern"], v):
        fel.append((sokvag or "/", "följer inte mönstret / does not match the pattern"))
    if isinstance(v, dict):
        for k in s.get("required", []):
            if k not in v:
                fel.append((sokvag + "/" + k, "saknas / missing"))
        egenskaper = s.get("properties", {})
        for k, x in v.items():
            if k in egenskaper:
                validera(x, egenskaper[k], rot, sokvag + "/" + k, fel)
            elif s.get("additionalProperties") is False:
                fel.append((sokvag + "/" + k, "finns inte i modellen"))
    if isinstance(v, list):
        if "minItems" in s and len(v) < s["minItems"]:
            fel.append((sokvag or "/", "för få poster / too few items"))
        if "maxItems" in s and len(v) > s["maxItems"]:
            fel.append((sokvag or "/", "för många poster / too many items"))
        if "items" in s:
            for i, x in enumerate(v):
                validera(x, s["items"], rot, "%s/%d" % (sokvag, i), fel)
    return fel


def nyckel_varde(entitet):
    """NGSI-LD i normaliserad form -> det förenklade nyckel-värde-formatet som schemat beskriver. Typen byts mot modellens namn
    (A och B är två profiler av samma modell)."""
    kv = {}
    for k, v in entitet.items():
        if k in ("id", "type"):
            kv[k] = v
        elif isinstance(v, dict) and v.get("type") == "Relationship":
            kv[k] = v.get("object")
        elif isinstance(v, dict) and "value" in v:
            kv[k] = v["value"]
        else:
            kv[k] = v
    kv["type"] = MODELL_ID
    return kv


def kontrollera(entiteter, dist, max_exempel=3):
    """Kontrollerar alla entiteter. Returnerar ett resultat som visas öppet i kvittot:
    {"resultat": OK|AVVIKELSE|EJ_KONTROLLERAD, "schema": filnamn, "poster": n, "godkanda": n, "exempel": [...]}"""
    namn, schema = _schema(dist)
    ut = {"resultat": "EJ_KONTROLLERAD", "schema": namn, "poster": len(entiteter), "godkanda": 0, "exempel": []}
    if schema is None:
        return ut
    for e in entiteter:
        kv = nyckel_varde(e)
        fel = validera(kv, schema, schema)
        if fel:
            if len(ut["exempel"]) < max_exempel:
                ut["exempel"].append("%s: %s %s" % (kv.get("id", "?"), fel[0][0], fel[0][1]))
        else:
            ut["godkanda"] += 1
    ut["resultat"] = "OK" if ut["godkanda"] == ut["poster"] else "AVVIKELSE"
    return ut
