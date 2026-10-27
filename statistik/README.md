# Statistik

Caddy skriver en JSON-åtkomstlogg till `statistik/logg/access.log` (rotation: 20 MiB, högst 60 filer, rålogg i 7 dygn). Loggen bär inga hemligheter
(kaka, lösenord och auktoriseringshuvud tas bort) och IP-adressen kapas till /24 (IPv4) och /48 (IPv6); porten tas bort.
Katalogen är git-ignorerad, ligger utanför nollställningen och utanför `svada-*`-volymerna.

Kontrollrummets sida `/statistik` (öppen, sv/en, länkad i sidfoten) visar siffrorna och bygger på samma kod som rapporten. Händelseräknaren sparar dagssummor i `statistik/data/` (bara tal), och dagssummorna ur loggen sparas där också så att historiken finns kvar när rålogg roterats bort.

Rapporten (ingen beroende utöver Python 3):

    python3 tools/statistik-rapport.py --ut statistik/rapport                  # tabell + dagligt.csv + senaste.md (och uppdaterar statistik/data)
    python3 tools/statistik-rapport.py --utesluta 1.2.3.0/24 --ut statistik/rapport   # utesluta egna adresser (kapade, /24)

Prov: `tests/statistik_enhet.py` (K26), K27 i `tests/verify_kedjevy.sh` (sidan och händelseräknaren) och 9.12 i `tests/verify_ap9.sh` (loggen).

På servern (vid synk, efter projektägarens ja): katalogen skapas av `compose` vid start; lägg ett dagligt cron-jobb som kör rapporten.
Kampanjlänkar: lägg `?k=webinar` på utskickade länkar; kampanjen räknas utan att något sparas om personen.

## Testläge: skilj ut vår egen provning

Öppna vilken sida som helst på demon med **`?test=1`** (till exempel `https://din-demo.example.org/?test=1`). Då sätts kakan `svada-test` för hela domänen (alla underdomäner), och sidfoten säger "Testläge". Med kakan räknas varken sidvisningar eller händelser (steg, flikar, åtgärder, JS-fel) i statistiken. `?test=0` avslutar testläget.

* **Loggen:** Caddy skriver fältet `test` ("1" när kakan finns) i åtkomstloggen; själva kakan tas bort ur loggen som alla andra kakor. `gemensam/statistik.py` hoppar över rader med `test=1` och själva `?test=1`-anropet (som sätter kakan).
* **Händelserna:** kontrollrummet räknar inte `/api/handelse` från en webbläsare med kakan.
* **Webbläsartester:** Playwright, curl och andra skript räknas redan som robotar. En webbläsare som styrs av en annan person eller av Claude i Chrome är en vanlig besökare, så öppna `?test=1` först. Webbläsarens kakburk är per webbläsare (inte per flik): en inkognitoflik behöver sin egen `?test=1`.
* **Alternativ:** `STATISTIK_UTESLUT` utesluter en hel adress (kapad till /24), men tar också bort dina vanliga besök och påverkar inte händelserna.
