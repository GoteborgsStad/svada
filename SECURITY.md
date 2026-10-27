# Säkerhet / Security

**Svenska.** Svada-mini är en demonstration med medvetna förenklingar (simulerad intygsutfärdare utan eIDAS-förankring, återkallelselistor i minnet,
EDC-lager i minnet, en hävningsregel som inte finns i Dataspace Protocol, och en lösenordsgrind som är en enkel skyddsnivå för en demo). Använd den inte för
riktiga data och exponera den inte mot internet utan att först läsa `docs/08-drift-identitet-skalning.md`.

**Ingen säkerhetsprocess.** Projektet har inte de förutsättningar som en säkerhetspolicy förutsätter: det finns ingen utsedd säkerhetsansvarig, ingen garanterad privat kanal för sårbarhetsrapporter, ingen svarstid, inga säkerhetsuppdateringar och ingen hantering av CVE:er. Hittar du en sårbarhet kan du kontakta Björn Hagström via [GitHub](https://github.com/bjornhagstrom), men vi utlovar varken svar eller åtgärd. Lägg helst inte detaljer som underlättar ett utnyttjande i ett publikt ärende.

**English.** Svada-mini is a demonstration with deliberate simplifications (a simulated credential issuer not anchored in eIDAS, revocation lists in memory,
in-memory EDC stores, a revocation rule that does not exist in the Dataspace Protocol, and a password gate that is a basic protection for a demo). Do not use
it for real data and do not expose it to the internet without first reading `docs/08-drift-identitet-skalning.md`.

**No security process.** The project does not have the conditions a security policy presupposes: no designated security contact, no guaranteed private channel for vulnerability reports, no response time, no security updates and no CVE handling. If you find a vulnerability you can contact Björn Hagström via [GitHub](https://github.com/bjornhagstrom), but we promise neither a reply nor a fix. Preferably do not put details that make an exploit easier in a public issue.
