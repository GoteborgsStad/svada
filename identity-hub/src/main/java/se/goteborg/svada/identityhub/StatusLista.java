/*
 * SVADA PoC – statuslista för återkallelse av intyg.
 *
 * KONCEPT: docs/koncept/C1-identitet.md
 *
 * Svadas utfärdare (samordningsrollen, DSGA 0.1) håller EN bitsträngslista (W3C Bitstring Status
 * List, syfte "revocation"). Varje utfärdat medlems- och deltagarintyg får ett eget index i
 * listan och pekar på listan med ett credentialStatus-fält. Sätts en bit är intyget återkallat.
 * Connectorernas verifierare (EDC:s IsNotRevoked) hämtar listan och nekar presentationer med
 * återkallade intyg: parten är utesluten ur dataspacet tills biten rensas.
 *
 * MEDVETEN FÖRENKLING: listan ligger i utfärdarens minne och nollställs när utfärdaren startas
 * om (intygen utfärdas ändå om vid start). Ingen part kan ansöka om, eller invända mot, en
 * återkallelse; det hör till regelboken (G15). Utfärdaren är inte förankrad i eIDAS.
 */
package se.goteborg.svada.identityhub;

import org.eclipse.edc.iam.verifiablecredentials.spi.model.revocation.BitString;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

public final class StatusLista {

    /** Minst 16 kB enligt W3C-specifikationen (131 072 bitar), så att listan inte avslöjar hur många intyg som finns. */
    public static final int STORLEK_BITAR = 131_072;

    private static final StatusLista INSTANS = new StatusLista();

    private final BitString bitar = BitString.Builder.newInstance().size(STORLEK_BITAR).build();
    private final Map<String, Integer> index = new LinkedHashMap<>();
    private final Map<String, String> mottagare = new LinkedHashMap<>();   // id -> DID
    private String url;
    private Supplier<String> signerare;

    public static StatusLista instans() {
        return INSTANS;
    }

    /** Anropas av utfärdaren vid start: listans publika adress, hur den signeras och vilka mottagare som finns. */
    public synchronized void konfigurera(String url, Supplier<String> signerare, Map<String, String> mottagare) {
        this.url = url;
        this.signerare = signerare;
        this.mottagare.clear();
        this.mottagare.putAll(mottagare);
        this.index.clear();
    }

    public synchronized boolean aktiv() {
        return url != null && signerare != null;
    }

    public synchronized String url() {
        return url;
    }

    /** Index för ett intyg (subjekt + typ); tilldelas första gången och är sedan stabilt under körningen. */
    public synchronized int indexFor(String subjektDid, String typ) {
        return index.computeIfAbsent(subjektDid + "|" + typ, k -> index.size());
    }

    /** Sätter eller rensar återkallelsebiten för mottagarens intyg. Returnerar false om intyget inte finns. */
    public synchronized boolean satt(String mottagarId, String typ, boolean aterkallat) {
        var did = mottagare.get(mottagarId);
        if (did == null) {
            return false;
        }
        var i = index.get(did + "|" + typ);
        if (i == null) {
            return false;
        }
        bitar.set(i, aterkallat);
        return true;
    }

    /** Den kodade listan (gzip + base64) som läggs i statuslisteintygets credentialSubject. */
    public synchronized String kodad() {
        var resultat = BitString.Writer.newInstance().write(bitar);
        if (resultat.failed()) {
            throw new IllegalStateException("Kunde inte koda statuslistan: " + resultat.getFailureDetail());
        }
        return resultat.getContent();
    }

    /** Statuslisteintyget som en signerad JWT. */
    public String signeradLista() {
        Supplier<String> s;
        synchronized (this) {
            s = signerare;
        }
        if (s == null) {
            throw new IllegalStateException("Statuslistan är inte konfigurerad");
        }
        return s.get();
    }

    public synchronized List<Map<String, Object>> poster() {
        var ut = new ArrayList<Map<String, Object>>();
        for (var m : mottagare.entrySet()) {
            for (var e : index.entrySet()) {
                if (e.getKey().startsWith(m.getValue() + "|")) {
                    var post = new LinkedHashMap<String, Object>();
                    post.put("mottagare", m.getKey());
                    post.put("subjekt", m.getValue());
                    post.put("typ", e.getKey().substring(m.getValue().length() + 1));
                    post.put("index", e.getValue());
                    post.put("aterkallat", bitar.get(e.getValue()));
                    ut.add(post);
                }
            }
        }
        return ut;
    }
}
