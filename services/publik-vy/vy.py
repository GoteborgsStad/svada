"""
vy.py – den publika vyns HTML (server-renderad, inga externa beroenden).

Vyn har ett enda syfte: att `dcat:accessURL` för Distribution B ska gå att
FÖLJA. En människa som klickar "Gå till resurs" i en dataportal ska landa på
något läsbart, inte på ett NGSI-LD-protokollfel (gapanalys G9).

Ingen CSS-fil, ingen JavaScript, inga typsnitt utifrån – allt inline, samma
hållning som skördarens vy (services/harvester/vy.py).
"""

import html
import os
import re

STIL = """
:root { color-scheme: light dark; }
body { font-family: system-ui, sans-serif; margin: 0 auto; max-width: 62rem;
       padding: 1.5rem; line-height: 1.5; }
h1 { margin-bottom: 0.2rem; }
.underrubrik { color: #666; margin-top: 0; }
.ruta { border: 1px solid #ccc; border-radius: 6px; padding: 0.8rem 1rem;
        margin: 1rem 0; }
.öppen { border-color: #1b6b2b; }
.märke { display: inline-block; border-radius: 999px; padding: 0 0.6rem;
         font-size: 0.8rem; border: 1px solid currentColor; color: #1b6b2b; }
table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
/* Smal skärm: tabellen rullar för sig själv, sidan rullar inte i sidled (gränssnittstestet L6). */
@media (max-width: 700px) { table { display: block; overflow-x: auto; max-width: 100%; } }
pre, code, h1, h2, p, td { overflow-wrap: anywhere; }
th, td { text-align: left; vertical-align: top; padding: 0.3rem 0.5rem;
         border-bottom: 1px solid #ddd; }
td.tal { text-align: right; font-variant-numeric: tabular-nums; }
code, pre { font-family: ui-monospace, monospace; font-size: 0.85rem; }
pre { white-space: pre-wrap; word-break: break-word; background: #0001;
      padding: 0.6rem; border-radius: 4px; }
footer { color: #666; font-size: 0.85rem; margin-top: 2rem; }
.aterstall { margin: 0 0 0.8rem; font-size: 0.85rem; text-align: right; opacity: 0.85; }
.aterstall.snart { border: 1px solid #c98a00; background: #c98a0026; padding: 0.15rem 0.5rem; border-radius: 4px; text-align: left; font-weight: 650; font-size: 0.95rem; opacity: 1; }
.aterstall.nu { border: 2px solid #8a1c16; background: #b3261e; color: #fff; padding: 0.15rem 0.65rem; border-radius: 6px; text-align: left; font-weight: 750; font-size: 1.2rem; font-variant-numeric: tabular-nums; opacity: 1; }
.aterstall small { font-weight: 500; opacity: .85; }
@keyframes aterpuls { 0%, 100% { box-shadow: 0 0 0 0 rgba(179,38,30,.55); } 50% { box-shadow: 0 0 0 6px rgba(179,38,30,0); } }
@media (prefers-reduced-motion: no-preference) { .aterstall.sista { animation: aterpuls 1.2s ease-in-out infinite; } }
.aterstall[hidden] { display: none; }
.aterstallrad { display: flex; justify-content: flex-end; align-items: center; gap: 0.4rem; margin: 0 0 0.8rem; }
.aterstallrad .aterstall { margin: 0; }
.aterstallinfo { width: 1.5rem; height: 1.5rem; padding: 0; border-radius: 50%; border: 1.5px solid currentColor; background: transparent; color: inherit; font: 700 0.85rem/1 system-ui, sans-serif; cursor: pointer; opacity: 0.8; }
.aterstallinfo[hidden] { display: none; }
dialog.aterstalldialog { border: 1px solid #8884; border-radius: 12px; padding: 0; width: min(34rem, calc(100vw - 32px)); background: Canvas; color: CanvasText; }
dialog.aterstalldialog::backdrop { background: rgb(0 0 0 / .35); }
.aterstalldialog .adh { display: flex; align-items: center; gap: 0.6rem; padding: 0.8rem 1rem; border-bottom: 1px solid #8884; }
.aterstalldialog h2 { margin: 0; font-size: 1.05rem; }
.aterstalldialog .adh button { margin-left: auto; cursor: pointer; }
.aterstalldialog #adt { padding: 0.8rem 1rem 1rem; font-size: 0.9rem; }
.aterstalldialog ul { margin: 0; padding-left: 1.2rem; display: grid; gap: 0.35rem; }
@media (max-width: 700px) { dialog.aterstalldialog { margin: auto 0 0; width: 100vw; max-width: 100vw; border-radius: 12px 12px 0 0; } }
"""


def e(text):
    return html.escape("" if text is None else str(text))


def _sida(titel, kropp, sprak="sv"):
    return (
        f"<!doctype html><html lang=\"{sprak}\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{e(titel)}</title><style>{STIL}</style></head>"
        f"<body>{_aterstall(sprak)}{kropp}</body></html>"
    )


def _aterstall(sprak):
    """Nedräkning till den nattliga återställningen (samma beteende som i kontrollrummet): servern anger nästa tidpunkt och sin tid.
    Klockslaget visas i besökarens egen tidszon. ?aterstall=<minuter> simulerar lägena (190, 12, 4, 0.5, -2)."""
    sv = sprak == "sv"
    return ('<div class="aterstallrad"><div id="aterstall" class="aterstall" hidden></div>'
            '<button type="button" class="aterstallinfo" id="aterstallinfo" hidden aria-haspopup="dialog" aria-label="__OM__" title="__OM__">?</button></div>'
            '<dialog class="aterstalldialog" id="aterstalldialog" aria-labelledby="adr"><div class="adh"><h2 id="adr"></h2>'
            '<button type="button" id="aterstallstang">__STANG__</button></div><div id="adt"></div></dialog>'
            '<script>' + _ATERSTALL_JS + '</script>'
            ).replace("__SV__", "true" if sv else "false").replace(
                "__OM__", "Om nollställningen" if sv else "About the reset").replace("__STANG__", "Stäng" if sv else "Close")


_ATERSTALL_JS = r"""(function(){
var SV=__SV__,el=document.getElementById("aterstall"),kn=document.getElementById("aterstallinfo"),dlg=document.getElementById("aterstalldialog"),info=null,fs=0;
function T(a,b){return SV?a:b}
function tid(d,tz){try{return new Intl.DateTimeFormat(SV?"sv-SE":"en-GB",{hour:"2-digit",minute:"2-digit",hourCycle:"h23",timeZone:tz||undefined}).format(d)}catch(e){return info.klockslag}}
function zon(d,tz){try{var p=new Intl.DateTimeFormat("en-GB",{timeZoneName:"short",hour:"2-digit",timeZone:tz||undefined}).formatToParts(d);for(var i=0;i<p.length;i++)if(p[i].type==="timeZoneName")return p[i].value}catch(e){}return ""}
function rest(m){if(m<1)return T("mindre än 1 min","less than 1 min");var h=Math.floor(m/60);return h?h+" h "+(m%60)+" min":m+" min"}
function mmss(k){var t=Math.max(0,Math.ceil(k/1000));return Math.floor(t/60)+":"+("0"+(t%60)).slice(-2)}
function rita(){if(!info){el.hidden=true;kn.hidden=true;return}
var kvar=Date.parse(info.nastaUtc)-(Date.now()+fs),m=Math.ceil(kvar/60000),
pagar=kvar<=0&&kvar>-info.varaktighetMin*60000,nu=!pagar&&kvar<=300000,snart=!pagar&&!nu&&kvar<=900000;el.hidden=false;kn.hidden=false;
el.className="aterstall"+(pagar||nu?" nu":snart?" snart":"")+(nu&&kvar<=60000?" sista":"");
var sim=info.sim?" <small>("+T("simulering","simulation")+")</small>":"",kl=tid(new Date(info.nastaUtc));
if(pagar)el.textContent=T("Demon nollställs just nu. Sidan kan vara otillgänglig i några minuter; ladda om den sedan.","The demo is being reset right now. The page may be unavailable for a few minutes; reload it afterwards.");
else if(nu)el.innerHTML=T("Demon nollställs om ","The demo is reset in ")+mmss(kvar)+T(". Allt data raderas.",". All data is deleted.")+sim;
else el.innerHTML=T("Nollställs ","Resets ")+kl+" · "+T("om ","in ")+rest(m)+sim;
if(kvar<=-info.varaktighetMin*60000&&!info.sim)hamta()}
function oppna(){if(!info)return;var d=new Date(info.nastaUtc),tz=info.tz||"Europe/Stockholm",lokal=tid(d),server=tid(d,tz),lika=lokal===server&&zon(d)===zon(d,tz);
var nar=lika?T("klockan "+server+" ("+zon(d,tz)+")","at "+server+" ("+zon(d,tz)+")"):T("klockan "+lokal+" i din tidszon ("+zon(d)+"), det vill säga "+server+" svensk tid","at "+lokal+" in your time zone ("+zon(d)+"), which is "+server+" Swedish time");
document.getElementById("adr").textContent=T("Varför nollställs demon?","Why is the demo reset?");
document.getElementById("adt").innerHTML="<p>"+T("Nästa nollställning är ","The next reset is ")+nar+T(", och sedan varje natt.", ", and then every night.")+"</p><ul><li>"
+T("Demon är delad och återställs varje natt så att nästa besökare börjar rent. Den här vyn bara läser data; du kan inte ändra något här.","The demo is shared and reset every night so the next visitor starts clean. This view only reads data; you cannot change anything here.")+"</li><li>"
+T("Sidan kan vara otillgänglig i cirka 10 minuter medan den nollställs; den visar då en väntesida som laddar om sig själv.","The page may be unavailable for about 10 minutes during the reset; it then shows a waiting page that reloads by itself.")+"</li></ul>";
dlg.showModal()}
kn.addEventListener("click",oppna);
dlg.addEventListener("click",function(e){if(e.target===dlg||e.target.id==="aterstallstang")dlg.close()});
function hamta(){var q=new URLSearchParams(location.search).get("aterstall");
if(q!==null&&q.trim()!==""&&!isNaN(Number(q))){info={nastaUtc:new Date(Date.now()+Number(q)*60000).toISOString(),klockslag:"04:00",tz:"Europe/Stockholm",varaktighetMin:10,sim:true};fs=0;rita();return}
fetch("/api/aterstallning").then(function(r){return r.json()}).then(function(d){
if(!d||!d.nastaUtc){info=null}else{info=d;fs=Date.parse(d.nuUtc)-Date.now()}rita()}).catch(function(){})}
hamta();setInterval(rita,1000);setInterval(hamta,600000)})();"""


def _s(sprak, sv, en):
    return sv if sprak == "sv" else en


def _sprakval(sprak, sokvag):
    """Språkbyte som bevarar sidan: ?lang=sv|en."""
    return ("<p class=\"underrubrik\">" + _s(sprak, "Språk: ", "Language: ")
            + ("<a href=\"%s?lang=en\">English</a> · <b>Svenska</b>" % sokvag if sprak == "sv"
               else "<b>English</b> · <a href=\"%s?lang=sv\">Svenska</a>" % sokvag) + "</p>")


DEMO_VERSION = os.environ.get("SVADA_VERSION", "okänd")


def _sidfot(mintaka_publik, katalog_url, sprak="sv"):
    return (
        "<footer><p>" + _s(sprak,
            "Göteborgs Stad · Modellerad bräddata, Distribution B "
            "(K0R1T1, öppna data). Vyn kopierar inget: den läser direkt ur "
            "stadens egen kontextplattform.",
            "City of Gothenburg · Modelled overflow data, Distribution B "
            "(K0R1T1, open data). The view copies nothing: it reads directly from "
            "the city's own context platform.") + "</p>"
        "<p>" + _s(sprak, "Maskinellt gränssnitt: ", "Machine interface: ")
        + f"<code>{e(mintaka_publik)}</code> "
        + _s(sprak, "(NGSI-LD Temporal API, kräver <code>Accept: application/json</code>).",
             "(NGSI-LD Temporal API, requires <code>Accept: application/json</code>).")
        + "</p><p>" + _s(sprak, "Version ", "Version ") + f'<span id="demoversion">{e(DEMO_VERSION)}</span></p></footer>'
    )


_ATTRIBUT = {
    "observedAt": ("Observerad (UTC)", "Observed (UTC)"),
    "overflowVolumeM3": ("Bräddad volym (m³)", "Overflow volume (m³)"),
    "overflowDurationMin": ("Bräddtid (min)", "Overflow duration (min)"),
    "overflowPeakM3S": ("Högsta bräddflöde (m³/s)", "Peak overflow rate (m³/s)"),
    "inflowMeanM3S": ("Medeltillrinning (m³/s)", "Mean inflow (m³/s)"),
    "inflowPeakM3S": ("Högsta tillrinning (m³/s)", "Peak inflow (m³/s)"),
    "inflowVolumeM3": ("Tillrinningsvolym (m³)", "Inflow volume (m³)"),
    "waterLevelMaxM": ("Högsta vattennivå (m)", "Maximum water level (m)"),
}


def _attributrubrik(namn, sprak):
    sv, en = _ATTRIBUT.get(namn, (namn, namn))
    return sv if sprak == "sv" else en


def _tal(v, sprak):
    """Decimaltal med komma på svenska och punkt på engelska (kontrollrummet skriver 1 239,72; den publika vyn skrev 591.53)."""
    t = str(v)
    return t.replace(".", ",") if sprak == "sv" and re.fullmatch(r"-?\d+\.\d+", t) else t


def landning(brunnar, mintaka_publik, katalog_url, fonster, egen_url, sprak="sv"):
    """Startsidan: vad distributionen är + tabell med senaste värdet per brunn."""
    rader = []
    for b in brunnar:
        rader.append(
            "<tr>"
            f"<td><a href=\"/brunnar/{e(b['id'])}?lang={sprak}\">{e(b['id'])}</a></td>"
            f"<td class=\"tal\">{e(_tal(b['overflowVolumeM3'], sprak))}</td>"
            f"<td class=\"tal\">{e(_tal(b['overflowDurationMin'], sprak))}</td>"
            f"<td>{e(b['observedAt'])}</td>"
            "</tr>")
    tabell = (
        "<table><thead><tr><th>" + _s(sprak, "Bräddbrunn", "Overflow chamber") + "</th>"
        "<th>" + _s(sprak, "Bräddad volym (m³)", "Overflow volume (m³)") + "</th>"
        "<th>" + _s(sprak, "Varaktighet (min)", "Duration (min)") + "</th>"
        "<th>" + _s(sprak, "Dygnets slut (observedAt, UTC)", "End of the day (observedAt, UTC)") + "</th></tr></thead>"
        f"<tbody>{''.join(rader)}</tbody></table>"
        if rader else
        "<p>" + _s(sprak,
            "Inga modellerade värden finns ännu i stadens kontextplattform. Kör en leverans (steg 4) och ladda om.",
            "There are no modelled values yet in the city's context platform. Run a delivery (step 4) and reload.")
        + "</p>")

    intro = _s(
        sprak,
        "Modellerad bräddning från stadens spillvattennät, beräknad av en förenklad modell i PoC:en (den riktiga "
        "Future City Flow hos DHI är en hydrodynamisk modell). <strong>Brunnarnas egna koordinater ingår inte</strong> "
        "i den här distributionen; utsläppspunkt och mottagande vattendrag (recipient) finns kvar. Den fullständiga "
        "distributionen, med brunnarnas position, är icke-offentlig och kräver godkännande från Kretslopp och Vatten.",
        "Modelled overflow from the city's sewer network, calculated by a simplified model in the PoC (the real "
        "Future City Flow at DHI is a hydrodynamic model). <strong>The chambers' own coordinates are not included</strong> "
        "in this distribution; the discharge point and the receiving watercourse (recipient) remain. The full "
        "distribution, with the chambers' positions, is non-public and requires approval from Kretslopp och Vatten.")
    sidan_visar = _s(
        sprak,
        f"Sidan visar <strong>senaste modellerade dygnet per bräddbrunn</strong> i fönstret från {e(fonster)} och framåt.",
        f"The page shows <strong>the latest modelled day per overflow chamber</strong> in the window from {e(fonster)} onwards.")

    maskinellt = _s(
        sprak,
        "Den här sidan är en läsbar representation. Samma värden hämtas som JSON antingen härifrån eller direkt från stadens NGSI-LD Temporal API:",
        "This page is a readable representation. The same values are fetched as JSON either from here or directly from the city's NGSI-LD Temporal API:")
    temporal = _s(
        sprak,
        "Temporal-API:et svarar <strong>400</strong> på en webbläsares <code>Accept: text/html</code> – därför finns den här vyn.",
        "The Temporal API answers <strong>400</strong> to a browser's <code>Accept: text/html</code> – that is why this view exists.")
    kropp = f"""
<h1>{_s(sprak, 'Modellerad bräddata – öppna data', 'Modelled overflow data – open data')}</h1>
<p class="underrubrik">{_s(sprak, 'Göteborgs Stads publika vy av Distribution B', "The City of Gothenburg's public view of Distribution B")} ·
<span class="märke">K0R1T1 · PUBLIC · CC BY 4.0</span></p>
{_sprakval(sprak, "/brunnar")}
<div class="ruta öppen">
<p>{intro}</p>
<p>{sidan_visar}</p>
</div>

{tabell}

<div class="ruta">
<h2>{_s(sprak, 'Hämta samma data maskinellt', 'Fetch the same data by machine')}</h2>
<p>{maskinellt}</p>
<pre>curl -H 'Accept: application/json' '{e(egen_url)}'

curl -H 'Accept: application/json' '{e(mintaka_publik)}'</pre>
<p>{temporal}</p>
</div>
{_sidfot(mintaka_publik, katalog_url, sprak)}
"""
    return _sida(_s(sprak, "Modellerad bräddata – öppna data (Göteborgs Stad)", "Modelled overflow data – open data (City of Gothenburg)"), kropp, sprak)


def brunn(brunns_id, serie, mintaka_publik, katalog_url, sprak="sv"):
    """Tidsserien för en enskild bräddbrunn."""
    if not serie:
        kropp = (f"<h1>{e(brunns_id)}</h1>"
                 "<p>" + _s(sprak, "Ingen modellerad tidsserie finns för den här brunnen.", "There is no modelled time series for this chamber.") + "</p>"
                 f"<p><a href=\"/brunnar?lang={sprak}\">" + _s(sprak, "Tillbaka till listan", "Back to the list") + "</a></p>"
                 + _sidfot(mintaka_publik, katalog_url, sprak))
        return _sida(f"{brunns_id} – " + _s(sprak, "ingen data", "no data"), kropp, sprak)

    kolumner = ["observedAt"] + [k for k in serie[0] if k != "observedAt"]
    # Rubrik på läsarens språk med API-attributets namn kvar i <code> (maskinläsare ska känna igen kolumnen).
    thead = "".join(f"<th>{e(_attributrubrik(k, sprak))} <code>{e(k)}</code></th>" for k in kolumner)
    rader = []
    for punkt in serie:
        celler = []
        for k in kolumner:
            klass = "" if k == "observedAt" else " class=\"tal\""
            celler.append(f"<td{klass}>{e(punkt.get(k) if k == 'observedAt' else _tal(punkt.get(k), sprak))}</td>")
        rader.append("<tr>" + "".join(celler) + "</tr>")

    kropp = f"""
<h1>{e(brunns_id)}</h1>
<p class="underrubrik">{_s(sprak, 'Modellerad tidsserie', 'Modelled time series')} · {len(serie)} {_s(sprak, 'dygn', 'days')} ·
<span class="märke">K0R1T1 · PUBLIC</span></p>
<p><a href="/brunnar?lang={sprak}">&larr; {_s(sprak, 'Alla bräddbrunnar', 'All overflow chambers')}</a></p>
<table><thead><tr>{thead}</tr></thead><tbody>{''.join(rader)}</tbody></table>
{_sidfot(mintaka_publik, katalog_url, sprak)}
"""
    return _sida(f"{brunns_id} – " + _s(sprak, "modellerad bräddata", "modelled overflow data"), kropp, sprak)
