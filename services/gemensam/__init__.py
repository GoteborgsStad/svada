"""
gemensam – kod som DELAS av flera egenutvecklade tjänster i PoC:en.

Paketet kopieras in i de images som behöver det (se respektive Dockerfile,
byggkontext ./services). Innehåll:

  * Delade hjälpfunktioner (återställning, rensning, statistik). Den
    tidigare SHACL-valideringen av DCAT-AP hörde till CKAN och skördarna,
    som inte ingår i Svada-mini; dataprodukten beskrivs i DCAT i
    DSP-katalogen.
"""
