"""Sidan /nyheter: vad som är nytt i vilken version av demon.

Versionen har formen ÅÅÅÅ.MM.DD-N (datum och löpnummer samma dag) och sätts på ETT ställe: SVADA_VERSION i .env. Översta posten här ska
ha samma version (provet tests/version_enhet.py kontrollerar det). En ändring av beteende eller text som en besökare kan märka ger en ny
version och en ny post överst. Testrapporter anger vilken version de provat (den står i sidfoten och i /api/status).
"""
import html
import os
import re

VERSION = os.environ.get("SVADA_VERSION", "okänd")
MONSTER = re.compile(r"^\d{4}\.\d{2}\.\d{2}-\d+$")

# Nyast överst. (version, datum, [(svenska, engelska), ...])
NYHETER = [
    ("2026.10.23-11", "2026-10-26", [
        ("Raden \"Nästa\" tar slut med en tydlig text (\"Klart: du har gått igenom hela kedjan.\") när du sett analysen, i stället för att försvinna.",
         "The \"Next\" row now ends with a clear message (\"Done: you have been through the whole chain.\") once you have seen the analysis, instead of just disappearing."),
        ("Tangentbordet: Tab från länken i en ordförklaring fortsätter efter ordet i stället för att lämna sidan (Skift+Tab går tillbaka till ordet).",
         "Keyboard: Tab from the link in a term explanation continues after the term instead of leaving the page (Shift+Tab goes back to the term)."),
        ("Statistiksidan nämner inget lösenord när demon är öppen. Sidfotens \"Testläge\" i brunnsvyn slås på och av direkt med ?test=1 och ?test=0 (och finns även på felsidorna). Tiden för en hävning visas i din tid.",
         "The statistics page no longer mentions a password when the demo is open. The \"Test mode\" footer in the chambers view switches on and off immediately with ?test=1 and ?test=0 (and is also on the error pages). The time of a revocation is shown in your own time."),
    ]),
    ("2026.10.23-10", "2026-10-26", [
        ("Statistiken förklarar att antalet besökare är ett minimum: många datorer (inte bara många människor) med samma webbläsare på samma adress, till exempel i ett mötesrum, räknas som en besökare.",
         "The statistics page explains that the visitor count is a minimum: many computers (not just many people) with the same browser on one address, for example in a meeting room, count as one visitor."),
    ]),
    ("2026.10.23-9", "2026-10-24", [
        ("Avvisningskoder (till exempel brunns-gis-i-distribution-b) står kvar oförändrade på engelska, med det engelska namnet bredvid, så att de går att söka på i båda språken.",
         "Rejection codes (for example brunns-gis-i-distribution-b) stay unchanged in English, with the English name next to them, so they can be searched for in both languages."),
    ]),
    ("2026.10.23-8", "2026-10-23", [
        ("Felinjektionens säkerhetsnät är starkare: ett kvarlämnat läge städas före nästa besökares leverans och av städningen inom 15 sekunder, även efter en omstart.",
         "The fault injection safety net is stronger: a mode left behind is cleaned up before the next visitor's delivery and by the cleanup within 15 seconds, even after a restart."),
        ("Texten i fliken Felinjektion säger rätt sak oavsett variant. Länken till stadens åtkomstsida (cip.) följer språkvalet. Nollställningstiden anges i din egen tid.",
         "The text in the Fault injection tab is right in every variant. The link to the city's access page (cip.) follows the language choice. The reset time is given in your own time."),
    ]),
    ("2026.10.23-7", "2026-10-23", [
        ("Felinjektionen är nu ditt eget läge: den slås på i modellen bara medan din egen leverans körs och slås av direkt efteråt, så den påverkar ingen annan besökare.",
         "The fault injection is now your own mode: it is switched on in the model only while your own delivery runs and is switched off right after, so it does not affect any other visitor."),
        ("Stavningen är \"bräddata\" (med två d) överallt.",
         "The Swedish spelling is now \"bräddata\" (two d) everywhere."),
    ]),
    ("2026.10.23-6", "2026-10-23", [
        ("Efter Leverera A pekar \"Nästa\" på Analysera (steg 6) och raden tar slut när du öppnat det. \"Nästa: Förhandla A\" flyttar fokus till rätt knapp.",
         "After Deliver A, \"Next\" points to Analyse (step 6) and the row ends once you have opened it. \"Next: Negotiate A\" moves focus to the right button."),
        ("Ett avslag av en ny begäran medan ditt avtal gäller säger det i loggen, och \"Nästa\" går tillbaka dit du var.",
         "Rejecting a new request while your agreement is valid says so in the log, and \"Next\" goes back to where you were."),
        ("Felsidor: en okänd adress ger en riktig sida och ett konstigt avtals-id ger 404 i stället för fel. Stadens åtkomstsida (cip.) finns på engelska.",
         "Error pages: an unknown address gives a proper page and an odd agreement id gives 404 instead of an error. The city's access page (cip.) is available in English."),
        ("Språket följer sidan även när en annan flik har bytt språk. KoV-rutan ryms vid smalare fönster. Interna namn och sökvägar visas inte längre i loggar och exempel.",
         "The language follows the page even when another tab has switched language. The KoV box fits in narrower windows. Internal names and paths are no longer shown in logs and examples."),
        ("Fliken Felinjektion säger att den gäller alla besökare. Brunnsvyn visar Testläge i sidfoten.",
         "The Fault injection tab says it applies to all visitors. The chambers view shows Test mode in the footer."),
    ]),
    ("2026.10.23-5", "2026-10-23", [
        ("Steg 1 och ordlistan förklarar att datumet i batch-id:t (till exempel 2026-06-29) är det modellerade dygnet, inte när batchen kördes. Nytt begrepp: Modellerat dygn.",
         "Step 1 and the glossary explain that the date in the batch id (for example 2026-06-29) is the modelled day, not when the batch was run. New term: Modelled day."),
        ("Testläge för oss som provar: öppna sidan med ?test=1 så räknas inte besöket i statistiken (?test=0 avslutar).",
         "Test mode for those of us testing: open the page with ?test=1 and the visit is not counted in the statistics (?test=0 ends it)."),
    ]),
    ("2026.10.23-4", "2026-10-23", [
        ("Steg 6 startar med distribution A, och växlingen mellan A och B är en tydlig tvåvalsknapp med förklaring.",
         "Step 6 starts with distribution A, and switching between A and B is a clear two-way toggle with an explanation."),
        ("Kartan förbereds så fort steg 6 öppnas (biblioteket laddas och anslutningen till kartplattorna förbereds), så den visas snabbare.",
         "The map is prepared as soon as step 6 opens (the library loads and the connection to the map tiles is prepared), so it appears faster."),
        ("Utan ett gällande avtal visar A en vänlig förklaring i stället för ett larm.",
         "Without a current agreement, A shows a friendly explanation instead of an alert."),
    ]),
    ("2026.10.23-3", "2026-10-23", [
        ("Om-sidan redovisar att arbetet sker inom Vattendatalabbet, nämner finansiärerna, krediterar upphovspersonerna och länkar till projektet.",
         "The About page states that the work is done within the Swedish Water Data Lab, names the funders, credits the authors and links to the project."),
        ("Ordlistan: DCAT och DCP är egna begrepp, och fler begrepp länkar till sina standarder eller projekt.",
         "The glossary: DCAT and DCP are terms of their own, and more terms link to their standards or projects."),
        ("Om-sidan anger att demon följer DSSC Blueprint 3.0, med länk.",
         "The About page states that the demo follows the DSSC Blueprint 3.0, with a link."),
    ]),
    ("2026.10.23-2", "2026-10-23", [
        ("Fliken Jobb visar en snurra och \"Jobb N pågår\" medan ett jobb körs, och en snurra i jobblistan.",
         "The Jobs tab shows a spinner and \"Job N is running\" while a job runs, and a spinner in the job list."),
        ("När en connector just har startats om visas \"Connectorn är inte färdigstartad, försök igen om en stund\" i stället för ett rått HTTP 405.",
         "When a connector has just restarted, \"The connector has not finished starting, try again in a moment\" is shown instead of a raw HTTP 405."),
    ]),
    ("2026.10.23-1", "2026-10-23", [
        ("Versionsnummer i sidfoten och i /api/status, och den här sidan.",
         "Version number in the footer and in /api/status, and this page."),
        ("Ett avslag häver inget avtal i den delade demon, och texterna säger det. KoV häver med knappen \"KoV häver avtalet\".",
         "A rejection revokes no agreement in the shared demo, and the texts say so. KoV revokes with the \"KoV revokes the agreement\" button."),
        ("Brunnsvyn: en okänd brunn ger \"ingen data\" (404) i stället för ett tjänstefel.",
         "Chambers view: an unknown chamber gives \"no data\" (404) instead of a service error."),
        ("Avtalssidan visar attribueringsplikten (duty) som skyldighet.",
         "The agreement page shows the attribution duty as an obligation."),
        ("Statistiken visar serverfel och 429 per dag.",
         "Statistics show server errors and 429 responses per day."),
        ("Rättat: Esc stänger bara den lilla förklaringsrutan; \"Nästa\" ändras inte av ett misslyckat beslut; förklaringsrutan hamnar alltid inom fönstret.",
         "Fixed: Esc closes only the small explanation box; \"Next\" is not changed by a failed decision; the explanation box always stays inside the window."),
        ("Uppgraderade komponenter: Orion-LD 1.12, MongoDB 7, Mintaka 0.7, TimescaleDB (Apache-varianten), Caddy, Python.",
         "Upgraded components: Orion-LD 1.12, MongoDB 7, Mintaka 0.7, TimescaleDB (Apache variant), Caddy, Python."),
    ]),
]

T = {
    "sv": {"titel": "Nyheter", "rub": "Vad som är nytt", "nu": "Den här demon kör version", "tillbaka": "Kontrollrummet", "andra": ("English", "en"),
           "intro": "Varje ändring som en besökare kan märka får en ny version. Testrapporter anger vilken version de provat."},
    "en": {"titel": "What's new", "rub": "What's new", "nu": "This demo runs version", "tillbaka": "Control room", "andra": ("Svenska", "sv"),
           "intro": "Every change a visitor can notice gets a new version. Test reports state which version they tested."},
}


def sida(sprak="sv"):
    sprak = sprak if sprak in T else "sv"
    t = T[sprak]
    i = 0 if sprak == "sv" else 1
    e = html.escape
    poster = "".join(
        f'<h2>{e(v)} <span class="datum">{e(d)}</span></h2><ul>' + "".join(f"<li>{e(x[i])}</li>" for x in rader) + "</ul>"
        for v, d, rader in NYHETER)
    return f"""<!doctype html><html lang="{sprak}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(t["titel"])}</title><style>
:root{{color-scheme:light;--fg:#1d1d1d;--dov:#47504c}}
body{{background:#fff;color:var(--fg);font:16px/1.5 system-ui,sans-serif;max-width:46rem;margin:0 auto;padding:1rem 16px 3rem}}
h1{{margin:.6rem 0 .2rem}} h2{{margin:1.4rem 0 .3rem;font-size:1.1rem}} .datum{{color:var(--dov);font-weight:400;font-size:.9rem}}
.topp{{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap}} a{{color:#0848a6}} li{{margin:.25rem 0}}
</style></head><body>
<div class="topp"><a href="/?lang={sprak}">&larr; {e(t["tillbaka"])}</a><a href="/nyheter?lang={t["andra"][1]}" hreflang="{t["andra"][1]}">{e(t["andra"][0])}</a></div>
<h1>{e(t["rub"])}</h1>
<p>{e(t["nu"])} <b>{e(VERSION)}</b>. {e(t["intro"])}</p>
{poster}
</body></html>"""
