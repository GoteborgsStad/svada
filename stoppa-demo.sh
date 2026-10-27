#!/usr/bin/env bash
# Stanger ner hela SVADA PoC-kedjan snyggt.
#
# VIKTIGT 1: anvander ALDRIG "-v" har. "down -v" raderar volymerna med
# brunnar/historik/katalog - da
# maste allt laddas/registreras om fran noll nasta gang. Vanlig "down" bara
# stannar och tar bort containrarna; data i volymerna ligger kvar, och
# starta-demo.sh far allt att fungera igen utan ombyggnad.
#
# VIKTIGT 2 (hittade 2026-09-21): "down" MASTE fa SAMMA --profile-flaggor
# som "up" fick, annars validerar Compose depends_on-grafen mot fel
# tjanstemangd och kastar samma "depends on undefined service ...: invalid
# compose project"-fel som vi sag pa uppstartssidan (edc-provider ->
# identity-hub-dhi, edc-consumer -> identity-hub-stad). Utan profilerna
# avbryts skriptet (set -e) INNAN nagon container hinner stoppas - det var
# darfor allt fortfarande kordes efter forsta versionen av det har skriptet.
# (restart: unless-stopped ar satt pa nastan alla tjanster, men det ar INTE
# orsaken har - "down" tar bort containrarna helt, policyn har ingenting
# att starta om. Policyn ar dock bra att kanna till av ett annat skal: om
# Mac:en somnar/vaknar eller Docker Desktop startar om under demon, kommer
# containrarna sjalva tillbaka - det ar en fordel, inte ett problem.)
#
# Det delade natverket "svada-dsp-public" skapades separat (en gang) och
# rors inte har - "down" tar inte bort externa natverk.
set -e
cd "$(dirname "$0")"

echo "== Stanger portaler + dashboard + FAIR =="
docker compose -f compose.kontrollrum.yml --profile dashboard --profile publik-ingang down

echo "== Stanger Org Staden (consumer) =="
docker compose -f compose.stad.yml --profile stad-dataplan --profile stad-identitet --profile stad-edc --profile stad-ingest down

echo "== Stanger Org DHI (provider) =="
docker compose -f compose.dhi.yml --profile dhi-fcf --profile dhi-identitet --profile dhi-edc down

echo "== Stanger Svadas utfardare (DSGA 0.1) =="
docker compose -f compose.dsga.yml --profile dsga-utfardare down

echo ""
echo "== Klart. Allt stoppat, ingen data raderad. =="
echo "== Starta igen nasta gang med: bash $(pwd)/starta-demo.sh =="
