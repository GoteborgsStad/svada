"""vy.py – gatewayens avslagssida (server-renderad, inga externa beroenden).

Sidan finns av samma skäl som den publika vyn (G9): en `dcat:accessURL` ska
gå att FÖLJA. Skillnaden är vad man ska landa på. Följer man Distribution B:s
adress ska man se data. Följer man Distribution A:s adress utan
KoV-godkännande ska man se ett begripligt NEJ – inte ett protokollfel och
inte, som före den här åtgärden, 91 brunnars koordinater.

Samma inline-stil som services/publik-vy/vy.py och services/harvester/vy.py.
"""

import html

STIL = """
:root { color-scheme: light dark; }
body { font-family: system-ui, sans-serif; margin: 0 auto; max-width: 54rem;
       padding: 1.5rem; line-height: 1.5; }
h1 { margin-bottom: 0.2rem; }
.underrubrik { color: #666; margin-top: 0; }
.ruta { border: 1px solid #ccc; border-radius: 6px; padding: 0.8rem 1rem;
        margin: 1rem 0; }
.stoppad { border-color: #a11; }
.öppen { border-color: #1b6b2b; }
.märke { display: inline-block; border-radius: 999px; padding: 0 0.6rem;
         font-size: 0.8rem; border: 1px solid currentColor; }
.märke.nej { color: #a11; }
.märke.ja { color: #1b6b2b; }
dl { display: grid; grid-template-columns: max-content 1fr; gap: 0.2rem 1rem;
     margin: 0; }
dt { color: #666; }
dd { margin: 0; }
code, pre { font-family: ui-monospace, monospace; font-size: 0.85rem; }
pre { white-space: pre-wrap; word-break: break-word; background: #0001;
      padding: 0.6rem; border-radius: 4px; }
footer { color: #666; font-size: 0.85rem; margin-top: 2rem; }
"""


def e(text):
    return html.escape("" if text is None else str(text))


# Läsbar rubrik för felkoden (koden själv står kvar bredvid, för den som söker i loggar eller kod).
ORSAKSTEXT = {"atkomst-kraver-godkannande": "Åtkomst kräver godkännande"}


ORSAKSTEXT_EN = {"atkomst-kraver-godkannande": "Access requires approval"}


def avslag(fel, sokvag, egen_publik, katalog_url, publik_vy_url,
           mintaka_publik, sprak="sv"):
    """HTML-svaret när någon följer Distribution A:s accessURL utan token. Svenska eller engelska (?lang=en eller kakan svada-sprak)."""
    en = sprak == "en"

    def t(sv, eng):
        return eng if en else sv
    orsak = (ORSAKSTEXT_EN if en else ORSAKSTEXT).get(fel.orsak, fel.orsak)
    # Felets förklarande text är svensk i gatewayen; på engelska visas en allmän mening och orsakskoden bredvid.
    detalj = "Access to Distribution A requires a current agreement." if en else fel.detalj
    TXT0 = t("""Åtkomsten följer det kontraktsavtal som förhandlats fram i dataspacet.
   Kretslopp och Vatten godkänner förhandlingen hos providern (DHI:s
   connector); först då finns ett avtal hos stadens connector. Växla avtalets
   id mot en åtkomsttoken och läs med den:""", """Access follows the contract agreement negotiated in the data space.
   Kretslopp och Vatten approves the negotiation at the provider (DHI's
   connector); only then does an agreement exist at the city's connector. Exchange the
   agreement id for an access token and read with it:""")
    TXT1 = t("""Notera att NGSI-LD:s <code>/entities</code> aldrig svarar på en obegränsad
   fråga – ett <code>type=</code> eller <code>id=</code> krävs, annars ger
   Orion-LD <code>400 Too broad query</code> oavsett token. Exemplet ovan
   hämtar A:s värden för alla 91 brunnar (brunnens position ligger i registret, typen <code>SewerOverflowWeir</code>); för en enskild brunn, byt ut hela frågesträngen
   mot en sökväg av formen
   <code>/ngsi-ld/v1/entities/urn:ngsi-ld:SewerOverflowModelA:&lt;id&gt;</code>.""", """Note that NGSI-LD's <code>/entities</code> never answers an unbounded
   query – a <code>type=</code> or <code>id=</code> is required, otherwise
   Orion-LD returns <code>400 Too broad query</code> whatever the token. The example above
   fetches A's values for all 91 chambers (the chamber's position is in the register, type <code>SewerOverflowWeir</code>); for a single chamber, replace the whole query string
   with a path of the form
   <code>/ngsi-ld/v1/entities/urn:ngsi-ld:SewerOverflowModelA:&lt;id&gt;</code>.""")
    TXT2 = t("""Skillnaden mellan A och B är verkställd här, i stadens egen gateway –
     inte enbart beskriven i DHI:s katalog. Datat lämnar aldrig staden.
     Åtkomst till A kräver ett gällande avtal: hävs det nekar gatewayen.""", """The difference between A and B is enforced here, in the city's own gateway –
     not merely described in DHI's catalogue. The data never leaves the city.
     Access to A requires a current agreement: if it is revoked, the gateway refuses.""")
    TXT3 = t("samma modellerade bräddata utan brunnarnas GIS (K0R1T1). Fri användning och vidarespridning med attribution. Ingen token behövs.",
             "the same modelled overflow data without the chambers' GIS (K0R1T1). Free use and redistribution with attribution. No token needed.")
    kropp = f"""
<p style="text-align:right;margin:0"><a href="?lang={'sv' if en else 'en'}">{t('English', 'Svenska')}</a></p>
<h1>{t('Åtkomst nekad', 'Access denied')}</h1>
<p class="underrubrik">{t('Göteborgs Stads kontextplattform (CIP)', 'City of Gothenburg context platform (CIP)')} ·
   {t('Modellerad bräddata, Distribution A', 'Modelled overflow data, Distribution A')}</p>

<div class="ruta stoppad">
  <p><span class="märke nej">NON_PUBLIC</span>
     <strong>{e(orsak)}</strong> <code>{e(fel.orsak)}</code></p>
  <p>{e(detalj)}</p>
  <dl>
    <dt>{t('Begärd resurs', 'Requested resource')}</dt><dd><code>{e(sokvag)}</code></dd>
    <dt>{t('Informationsklass', 'Information class')}</dt><dd>K1R1T1</dd>
    <dt>{t('Åtkomsträtt (accessRights)', 'Access rights (accessRights)')}</dt>
    <dd><code>http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC</code></dd>
    <dt>{t('Rättighetsinnehavare (data rights holder)', 'Data rights holder')}</dt><dd>Kretslopp och Vatten, {t('Göteborgs Stad', 'City of Gothenburg')}</dd>
    <dt>ODRL</dt><dd>prohibition: distribute, publish</dd>
  </dl>
</div>

<h2>{t('Så får du åtkomst', 'How to get access')}</h2>
<p>{TXT0}</p>
<pre>curl -X POST {e(egen_publik)}/auktorisation \\
     -H 'Content-Type: application/json' \\
     -d '{{"contractAgreementId": "&lt;{t('avtalets id', 'agreement id')}&gt;"}}'

curl -H 'Authorization: Bearer &lt;token&gt;' \\
     '{e(egen_publik)}/ngsi-ld/v1/entities?type=SewerOverflowModelA&amp;limit=1000'</pre>
<p>{TXT1}</p>

<h2>{t('Söker du öppna data?', 'Looking for open data?')}</h2>
<div class="ruta öppen">
  <p><span class="märke ja">PUBLIC</span> <strong>Distribution B</strong> –
     {TXT3}</p>
  <p>{t('Läsbar vy', 'Readable view')}: <a href="{e(publik_vy_url)}/brunnar">{e(publik_vy_url)}/brunnar</a><br>
     {t('Maskinellt gränssnitt', 'Machine interface')}: <code>{e(mintaka_publik)}/temporal/entities</code>
     (NGSI-LD Temporal API, <code>Accept: application/json</code>)</p>
</div>

<footer>
  <p>{TXT2}</p>
</footer>
"""
    return (
        f"<!doctype html><html lang=\"{'en' if en else 'sv'}\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{t('Åtkomst nekad', 'Access denied')} – Distribution A (non-public)</title>"
        f"<style>{STIL}</style></head><body>{kropp}</body></html>"
    )
