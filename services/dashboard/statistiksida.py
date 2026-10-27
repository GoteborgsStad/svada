"""Sidan /statistik: enkel, öppen visning av hur demon används.

Servergenererad HTML med inbyggda SVG-staplar: inget JavaScript, inget externt anrop och ingen cookie. Allt som visas är
dagssummor (siffror); se services/gemensam/statistik.py för vad som räknas.
Diagrammen följer diagramguiden: en serie utan förklaringsruta (rubriken säger vad den visar), tunna staplar med rundad topp,
dämpade stödlinjer, siffran som text i tabellen och i verktygstips, ljus yta.
"""
import html

import steg as stegmodul

MIN = ";min-width:2px"      # en liten stapel ska synas, men ett nollvärde får ingen
BAR = "#255845"          # kontrollrummets kedjegröna: 8,4:1 mot vit yta, en serie

T = {
    "sv": {
        "titel": "Statistik", "tillbaka": "Kontrollrummet", "andra": ("English", "en"),
        "intro": ("Hur många som använder demon och vad de öppnar. Vi räknar besök och vilka delar som öppnas, utan spårningskakor "
                  "och utan att följa enskilda personer. Siffrorna är dagssummor."),
        "besok_rub": "Besökare per dag (senaste {n} dagarna)",
        "besok_not": "En besökare är en kapad adress och en webbläsare under ett dygn. Siffran är ett minimum: många datorer (inte bara många människor) med samma webbläsare på samma adress, till exempel i ett mötesrum, räknas som en besökare.",
        "ingen": "Ingen statistik ännu.", "tabell": "Visa som tabell",
        "dag": "Dag", "unika": "Besökare", "sidv": "Sidvisningar", "brunnar": "Brunnsvyn (sidvisningar)", "avvisade": "Avvisade vid lösenordet (besökare, bara när lösenord krävs)", "fel_dag": "Serverfel (5xx)", "gr_dag": "Begränsade (429)",
        "summa_rub": "Totalt sedan {dag}",
        "t_sidv": "sidvisningar i kontrollrummet", "t_bsidv": "sidvisningar i brunnsvyn", "t_dagar": "besökardagar (summa av dagens besökare)",
        "t_ts": "anrop mot tidsserie-API:t (B)", "t_cip": "anrop mot stadens plattform (CIP)",
        "oppnas_rub": "Vad besökare öppnar", "steg": "Steg", "steg_n": "Steg", "flikar": "Flikar", "atgarder": "Knappar som trycks", "ovrigt": "Övrigt",
        "sprak_en": "Bytte till engelska", "sprak_sv": "Bytte till svenska", "karta_osm": "Visade kartbakgrund (OpenStreetMap)",
        "analys_a": "Analys: distribution A", "analys_b": "Analys: distribution B", "antal": "gånger",
        "strul_rub": "Strul och spärrar",
        "strul_fel": "Serverfel (5xx) — {v}", "strul_gransad": "För många anrop (429), en spärr som gör sitt jobb — {v}", "strul_js": "Fel i webbläsaren (JavaScript)",
        "strul_nekad": "Nekade av en spärr (ett väntat nej, inget fel)",
        "kamp_rub": "Länkar med kampanjmärke (?k=…)",
        "def_rub": "Så räknar vi",
        "def": ("Sidvisning: en HTML-sida som visats (kontrollrummets statuspollning räknas inte).",
                "Besökare: kapad IP-adress och webbläsare under ett dygn; robotar räknas inte.",
                "Avvisade: besökare (kapad adress och webbläsare, inga robotar) som fick 401 men aldrig en sida under dygnet, alltså öppnade länken men kom inte förbi lösenordet. Den första 401 som den som loggar in får räknas inte.",
                "Dygnet följer svensk tid. Rådata sparas bara några dygn; dagssummorna ligger kvar.",
                "Händelser (steg, flikar, knappar) rapporteras av sidan själv utan identifierare: bara ett tal per dag och händelse, och bara efter att besökaren rört något."),
        "uppd": "Uppdaterad {t}",
        "forsta": "Första dagen med data: {d}.",
    },
    "en": {
        "titel": "Statistics", "tillbaka": "Control room", "andra": ("Svenska", "sv"),
        "intro": ("How many people use the demo and what they open. We count visits and which parts are opened, without tracking cookies "
                  "and without following individuals. The figures are daily totals."),
        "besok_rub": "Visitors per day (last {n} days)",
        "besok_not": "A visitor is a truncated address and a browser during one day. The figure is a minimum: many computers (not just many people) with the same browser on one address, for example in a meeting room, count as one visitor.",
        "ingen": "No statistics yet.", "tabell": "Show as a table",
        "dag": "Day", "unika": "Visitors", "sidv": "Page views", "brunnar": "Chambers view (page views)", "avvisade": "Turned away at the password (visitors, only when a password is required)", "fel_dag": "Server errors (5xx)", "gr_dag": "Rate limited (429)",
        "summa_rub": "Total since {dag}",
        "t_sidv": "page views in the control room", "t_bsidv": "page views in the chambers view", "t_dagar": "visitor days (sum of each day's visitors)",
        "t_ts": "calls to the time-series API (B)", "t_cip": "calls to the city's platform (CIP)",
        "oppnas_rub": "What visitors open", "steg": "Steps", "steg_n": "Step", "flikar": "Tabs", "atgarder": "Buttons pressed", "ovrigt": "Other",
        "sprak_en": "Switched to English", "sprak_sv": "Switched to Swedish", "karta_osm": "Showed the map background (OpenStreetMap)",
        "analys_a": "Analysis: distribution A", "analys_b": "Analysis: distribution B", "antal": "times",
        "strul_rub": "Problems and barriers",
        "strul_fel": "Server errors (5xx) — {v}", "strul_gransad": "Too many requests (429), a barrier doing its job — {v}", "strul_js": "Errors in the browser (JavaScript)",
        "strul_nekad": "Refused by a barrier (an expected no, not an error)",
        "kamp_rub": "Links with a campaign tag (?k=…)",
        "def_rub": "How we count",
        "def": ("Page view: an HTML page that was shown (the control room's status polling is not counted).",
                "Visitor: truncated IP address and browser during one day; robots are not counted.",
                "Turned away: visitors (truncated address and browser, no robots) who got a 401 but never a page during the day, that is, opened the link but did not get past the password. The first 401 that someone who logs in gets is not counted.",
                "The day follows Swedish time. Raw data is kept only a few days; the daily totals stay.",
                "Events (steps, tabs, buttons) are reported by the page itself without any identifier: just one number per day and event, and only after the visitor has touched something."),
        "uppd": "Updated {t}",
        "forsta": "First day with data: {d}.",
    },
}

VARDNAMN = {"sv": {"kontrollrum": "kontrollrummet", "brunnar": "brunnsvyn", "tidsserie": "tidsserie-API:t", "cip": "stadens plattform (CIP)"},
            "en": {"kontrollrum": "the control room", "brunnar": "the chambers view", "tidsserie": "the time-series API", "cip": "the city's platform (CIP)"}}


def _atgardsnamn(sprak):
    """Knapptexten för varje åtgärd (samma text som på knappen), annars åtgärdens id. KoV-knapparna har sin text i pedagogiken,
    övriga i stegets åtgärdslista."""
    ut = {}
    for st in stegmodul.STEG:
        for a in st.get("atgarder") or []:
            ut[a["id"]] = stegmodul.text(a.get("etikett"), sprak) or a["id"]
        for aid, k in ((st.get("pedagogik") or {}).get("knappar") or {}).items():
            if k.get("etikett"):
                ut[aid] = stegmodul.text(k["etikett"], sprak) or aid
    return ut


FLIKNAMN = {"sv": {"kedjan": "Kedjan", "folj": "Följ ett värde", "audit": "Auditlogg", "suveranitet": "Suveränitet",
                   "felinjektion": "Felinjektion", "jobb": "Jobb", "om": "Om", "ordlista": "Ordlista"},
            "en": {"kedjan": "The chain", "folj": "Follow a value", "audit": "Audit log", "suveranitet": "Sovereignty",
                   "felinjektion": "Fault injection", "jobb": "Jobs", "om": "About", "ordlista": "Glossary"}}


def _e(x):
    return html.escape(str(x))


def _stegtitel(nr, sprak):
    try:
        return stegmodul.text(stegmodul._P[nr]["titel"], sprak)     # samma rubrik som kontrollrummets steg, på rätt språk
    except Exception:                                    # noqa: BLE001 – titeln är en pryd, aldrig ett skäl att tappa sidan
        return ""


def _skala(maxv):
    """(tak, antal intervall) med hela tal som stödlinjer: ett jämnt steg (1, 2, 5, 10, 20 ...) så att högst fyra intervall behövs."""
    for steg in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000):
        n = -(-max(maxv, 1) // steg)
        if n <= 4:
            return steg * max(n, 1), max(n, 1)
    return 10000 * (-(-maxv // 10000)), 4


def stapeldiagram(dagar, t):
    """Besökare per dag: tunna staplar med rundad topp, 0-baslinje, tre dämpade stödlinjer, verktygstips per stapel."""
    if not any(d["unika"] or d["sidvisningar"] for d in dagar):
        return f'<p class="meta">{_e(t["ingen"])}</p>'
    B, H, ml, mb, mt, mr = 720, 230, 36, 28, 10, 8
    topp, intervall = _skala(max(d["unika"] for d in dagar))
    pw, ph = B - ml - mr, H - mt - mb
    steg = pw / len(dagar)
    bredd = max(4, min(18, steg * 0.6))
    delar = [f'<svg viewBox="0 0 {B} {H}" role="img" aria-label="{_e(t["besok_rub"].format(n=len(dagar)))}" class="diagram">']
    for i in range(0, intervall + 1):
        v = topp * i / intervall
        y = mt + ph - ph * (v / topp)
        delar.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{B - mr}" y2="{y:.1f}" stroke="#d3d9d5" stroke-width="1"/>')
        delar.append(f'<text x="{ml - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#47504c">{v:.0f}</text>')
    for i, d in enumerate(dagar):
        x = ml + steg * i + (steg - bredd) / 2
        h = ph * (d["unika"] / topp)
        tips = f'{d["dag"]}: {d["unika"]} {t["unika"].lower()}, {d["sidvisningar"]} {t["sidv"].lower()}'
        if h > 0:
            delar.append(f'<path d="M{x:.1f},{mt + ph:.1f} v{-max(h - 3, 0):.1f} q0,-3 3,-3 h{bredd - 6:.1f} q3,0 3,3 v{max(h - 3, 0):.1f} z" fill="{BAR}"><title>{_e(tips)}</title></path>')
        # ett osynligt, större träffområde per dag så att verktygstipset går att nå även för smala staplar
        delar.append(f'<rect x="{ml + steg * i:.1f}" y="{mt}" width="{steg:.1f}" height="{ph}" fill="transparent"><title>{_e(tips)}</title></rect>')
        if i % max(1, len(dagar) // 6) == 0 or i == len(dagar) - 1:
            delar.append(f'<text x="{x + bredd / 2:.1f}" y="{H - 8}" text-anchor="middle" font-size="11" fill="#47504c">{_e(d["dag"][5:])}</text>')
    delar.append(f'<line x1="{ml}" y1="{mt + ph}" x2="{B - mr}" y2="{mt + ph}" stroke="#47504c" stroke-width="1"/>')
    delar.append("</svg>")
    return "".join(delar)


def stapelrader(poster, t):
    """Vågräta staplar som HTML: etikett, stapel, antal som text. [(etikett, antal)], störst antal bestämmer skalan."""
    if not poster or not any(n for _, n in poster):
        return f'<p class="meta">{_e(t["ingen"])}</p>'
    storst = max(n for _, n in poster) or 1
    rader = "".join(
        f'<div class="rad"><span class="etikett">{_e(e)}</span><span class="spar"><span class="stapel" style="width:{100 * n / storst:.1f}%{MIN if n else ""}"></span></span>'
        f'<span class="antal">{n}</span></div>' for e, n in poster)
    return f'<div class="staplar">{rader}</div>'


def sida(data, sprak="sv"):
    t = T.get(sprak, T["sv"])
    sprak = sprak if sprak in T else "sv"
    h, s = data["handelser"], data["summa"]
    kr, br, ts, cip = (s.get(v, {}) for v in ("kontrollrum", "brunnar", "tidsserie", "cip"))
    dagar = data["dagar"]
    rubrik = t["summa_rub"].format(dag=data["forsta_dag"]) if data["forsta_dag"] else t["summa_rub"].format(dag="–")

    def tile(tal, text):
        return f'<div class="tile"><b>{tal}</b><span>{_e(text)}</span></div>'
    tiles = "".join([
        tile(kr.get("sidvisningar", 0), t["t_sidv"]), tile(br.get("sidvisningar", 0), t["t_bsidv"]),
        tile(kr.get("unika", 0), t["t_dagar"]), tile(ts.get("api_traffar", 0), t["t_ts"]), tile(cip.get("api_traffar", 0), t["t_cip"])])
    steg = [(f"{t['steg_n']} {n}" + (f" – {_stegtitel(n, sprak)}" if _stegtitel(n, sprak) else ""), h.get(f"steg_{n}", 0)) for n in range(1, 7)]
    flikar = sorted(((FLIKNAMN[sprak].get(k[5:], k[5:]), n) for k, n in h.items() if k.startswith("flik_")), key=lambda x: -x[1])
    namn_a = _atgardsnamn(sprak)
    atgarder = sorted(((namn_a.get(k[7:], k[7:]), n) for k, n in h.items() if k.startswith("atgard_") and k != "atgard_nekad"), key=lambda x: -x[1])
    ovrigt = [(t[k], h.get(k, 0)) for k in ("sprak_en", "sprak_sv", "karta_osm", "analys_a", "analys_b")]
    vn = VARDNAMN[sprak]
    strul_fel = [(t["strul_fel"].format(v=vn[v]), s.get(v, {}).get("fel", 0)) for v in ("kontrollrum", "brunnar", "tidsserie", "cip")]
    strul_gr = [(t["strul_gransad"].format(v=vn[v]), s.get(v, {}).get("begransade", 0)) for v in ("kontrollrum", "brunnar", "tidsserie", "cip")]
    strul = strul_fel + strul_gr + [(t["strul_js"], h.get("js_fel", 0)), (t["strul_nekad"], h.get("atgard_nekad", 0))]
    # Är lösenordsgrinden av (en öppen demo) finns inga avvisade: kolumnen och förklaringen om lösenordet visas bara när det finns sådana
    # (provrunda 2026-10-26: statistiken talade om lösenord fast demon saknar inloggning).
    grind = any(d["avvisade"] for d in dagar)
    avv_rubrik = ("<th>" + _e(t["avvisade"]) + "</th>") if grind else ""
    defrader = [x for x in t["def"] if grind or not x.startswith(("Avvisade:", "Turned away:"))]
    kamp = "".join(f"<tr><td><code>{_e(k)}</code></td><td>{n}</td></tr>" for k, n in data["kampanjer"].items())
    avv_cell = lambda d: ("<td>%d</td>" % d["avvisade"]) if grind else ""
    tabell = "".join(f'<tr><td>{_e(d["dag"])}</td><td>{d["unika"]}</td><td>{d["sidvisningar"]}</td><td>{d["brunnar_sidvisningar"]}</td>{avv_cell(d)}<td>{d.get("fel", 0)}</td><td>{d.get("begransade", 0)}</td></tr>'
                     for d in reversed(dagar))
    andra_namn, andra_kod = t["andra"]
    return f"""<!doctype html><html lang="{sprak}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(t["titel"])}</title><style>
:root{{color-scheme:light;--fg:#1d2421;--dov:#47504c;--ram:#d3d9d5;--bar:{BAR}}}
body{{background:#fff;color:var(--fg);font:16px/1.5 system-ui,sans-serif;max-width:52rem;margin:0 auto;padding:1rem 16px 3rem}}
h1{{margin:.6rem 0 .2rem}} h2{{margin:1.6rem 0 .4rem;font-size:1.15rem}}
.meta{{color:var(--dov);font-size:.88rem;margin:.2rem 0 .6rem}}
a{{color:#0848a6}}
.topp{{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap}}
.diagramrum{{overflow-x:auto}} .diagram{{width:100%;min-width:34rem;height:auto;display:block;margin:.4rem 0}}
@media (max-width:34rem){{.staplar .rad{{grid-template-columns:1fr 3.5rem}} .staplar .etikett{{grid-column:1 / -1}} .staplar .spar{{grid-column:1}}}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(11rem,1fr));gap:.6rem;margin:.6rem 0}}
.tile{{border:1px solid var(--ram);border-radius:8px;padding:.5rem .8rem}} .tile b{{display:block;font-size:1.5rem}} .tile span{{color:var(--dov);font-size:.85rem}}
.staplar .rad{{display:grid;grid-template-columns:minmax(8rem,16rem) 1fr 3.5rem;gap:.5rem;align-items:center;margin:.15rem 0}}
.staplar .etikett{{font-size:.92rem;overflow-wrap:anywhere}}
.staplar .spar{{display:block;height:.7rem}} .staplar .stapel{{display:block;height:.7rem;background:var(--bar);border-radius:0 4px 4px 0}}
.staplar .antal{{text-align:right;font-variant-numeric:tabular-nums}}
table{{border-collapse:collapse;width:100%;font-size:.9rem}} th,td{{text-align:left;padding:.25rem .5rem;border-bottom:1px solid var(--ram)}}
details{{margin:.5rem 0}} summary{{cursor:pointer}}
</style></head><body>
<div class="topp"><a href="/?lang={sprak}">&larr; {_e(t["tillbaka"])}</a><a href="/statistik?lang={andra_kod}" hreflang="{andra_kod}">{_e(andra_namn)}</a></div>
<h1>{_e(t["titel"])}</h1>
<p>{_e(t["intro"])}</p>

<h2>{_e(t["besok_rub"].format(n=len(dagar)))}</h2>
<div class="diagramrum" tabindex="0" role="group" aria-label="{_e(t['besok_rub'].format(n=len(dagar)))}">{stapeldiagram(dagar, t)}</div>
<p class="meta">{_e(t["besok_not"])}</p>
<details><summary>{_e(t["tabell"])}</summary><table>
<tr><th>{_e(t["dag"])}</th><th>{_e(t["unika"])}</th><th>{_e(t["sidv"])}</th><th>{_e(t["brunnar"])}</th>{avv_rubrik}<th>{_e(t["fel_dag"])}</th><th>{_e(t["gr_dag"])}</th></tr>{tabell}</table></details>

<h2>{_e(rubrik)}</h2>
<div class="tiles">{tiles}</div>

<h2>{_e(t["oppnas_rub"])}</h2>
<h3>{_e(t["steg"])}</h3>{stapelrader(steg, t)}
<h3>{_e(t["flikar"])}</h3>{stapelrader(flikar, t)}
<h3>{_e(t["atgarder"])}</h3>{stapelrader(atgarder, t)}
<h3>{_e(t["ovrigt"])}</h3>{stapelrader(ovrigt, t)}

<h2>{_e(t["strul_rub"])}</h2>{stapelrader(strul, t)}
{f'<h2>{_e(t["kamp_rub"])}</h2><table>{kamp}</table>' if kamp else ''}

<h2>{_e(t["def_rub"])}</h2><ul>{"".join(f"<li>{_e(x)}</li>" for x in defrader)}</ul>
<p class="meta">{_e(t["uppd"].format(t=data["uppdaterad"]))} {_e(t["forsta"].format(d=data["forsta_dag"] or "–"))}</p>
</body></html>"""
