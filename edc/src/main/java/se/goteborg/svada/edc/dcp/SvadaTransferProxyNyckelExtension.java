/*
 * SVADA PoC – transfer-proxy-nyckel för överföring och mottagning, omdöpt och avgränsad i steg 5 av den verifierbara DCP-identiteten,
 * kvarvarande förenkling stängd i en separat, fristående commit EFTER att
 * den verifierbara DCP-identiteten markerades klar.
 * KONCEPT: docs/koncept/C1-identitet.md
 *
 * ===================================================================
 * HISTORIK (för sammanhanget – inte längre en öppen förenkling).
 * ===================================================================
 * Den här extensionen hette tidigare MockIamSeedExtension och beskrevs
 * som en del av PoC:ens "mock-IAM" tillsammans med iam-mock-modulen. Det
 * var en sammanblandning: nyckelparet här har ALDRIG haft något med
 * DSP-lagrets deltagaridentitet att göra (den frågan - "vem är
 * motparten i förhandlingen?" - är helt löst av den verifierbara DCP-identitetens riktiga
 * DCP-verifiering, se se.goteborg.svada.edc.dcp.SvadaDcpIdentityExtension
 * och edc/build.gradle.kts där iam-mock är helt bortplockad).
 *
 * Det HÄR nyckelparet används enbart av DATAPLANET för att signera/
 * verifiera transfer-proxy-tokens (edc.transfer.proxy.token.*.alias i
 * edc/konfig/*.properties) - de kortlivade JWT:er som skyddar den
 * publika /public-endpointen när en consumer hämtar data efter en
 * lyckad transfer (överföring och mottagning). Det är en SEPARAT mekanism från DSP-lagrets
 * identitetsverifiering.
 *
 * Steg 5 av den verifierbara DCP-identiteten lämnade nyckelparet hårdkodat (publikt, identiskt i
 * provider och consumer, samma testnyckel som i Eclipse EDC:s officiella
 * exempel) med motiveringen att en riktig lösning låg utanför fasens
 * omfattning. Ett fynd under STEG 7 visade att
 * fixen var mindre än väntat: `edc/build.gradle.kts` har redan
 * `org.eclipse.edc:data-plane-iam` som beroende, och den modulens
 * DefaultDataPlaneAccessTokenServiceImpl läser redan nyckelmaterialet
 * via VAULT-ALIASEN nedan (aldrig hårdkodat i den generiska EDC-koden) -
 * den enda förenklingen satt HÄR, i vilket nyckelvärde som seedades.
 *
 * Verifierat innan den här ändringen (läsning av uppströmskällan
 * connector-0.17.0, ingen produktionskod): org.eclipse.edc.keys.keyparsers.PemParser (den
 * generiska EDC-koden som läser vaultens nyckelalias) accepterar både
 * "-----BEGIN PUBLIC KEY-----" (X.509 SubjectPublicKeyInfo, vad
 * PublicKey.getEncoded() ger för RSA-nycklar i Java) och
 * "-----BEGIN PRIVATE KEY-----" (PKCS8, vad PrivateKey.getEncoded() ger)
 * - exakt samma format som redan användte i det hårdkodade nyckelparet,
 * och för en RSA-privatnyckel härleds den matchande publika nyckeln ur
 * dess CRT-parametrar. Ett rent, i Java inbyggt KeyPairGenerator-anrop
 * räcker alltså - ingen extra certifikatgenerering, inget nytt beroende.
 *
 * Nyckelparet genereras nu SLUMPMÄSSIGT VID VARJE UPPSTART, unikt per
 * instans (provider och consumer får VARSITT, precis som deras did:web-
 * nycklar redan är unika per instans sedan STEG 3). Detta är säkert
 * eftersom transfer-proxy-token-mekanismen är SJÄLVSTÄNDIG per part: den
 * instans som utfärdar ett token (när en consumer hämtar data från
 * DENNA instans /public-endpoint efter en lyckad transfer) är samma
 * instans som senare verifierar det - ingen annan part behöver någonsin
 * känna till eller lita på detta nyckelpar. Det är alltså INTE samma
 * klass av risk som den 5-minuters DID-resolver-cachen (STEG 7,
 * Upptäckt 3): den cachen var farlig eftersom ANDRA parter cachade ett
 * nyckelvärde de behövde lita på; det här nyckelparet lämnar aldrig sin
 * egen process.
 * ===================================================================
 */

package se.goteborg.svada.edc.dcp;

import org.eclipse.edc.runtime.metamodel.annotation.Inject;
import org.eclipse.edc.spi.security.Vault;
import org.eclipse.edc.spi.system.ServiceExtension;
import org.eclipse.edc.spi.system.ServiceExtensionContext;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.NoSuchAlgorithmException;
import java.util.Base64;

public class SvadaTransferProxyNyckelExtension implements ServiceExtension {

    /** EDC:s hemlighetslager – in-memory i PoC:en (resursstrategin, hård regel 3). */
    @Inject
    private Vault vault;

    /** Aliaset som konfigfilerna pekar ut för den publika nyckeln. */
    private static final String PUBLIC_KEY_ALIAS = "public-key";
    /** Aliaset som konfigfilerna pekar ut för den privata nyckeln. */
    private static final String PRIVATE_KEY_ALIAS = "private-key";

    private static final String RSA_ALGORITM = "RSA";
    private static final int RSA_NYCKELLANGD_BITS = 2048;
    private static final int PEM_RADLANGD = 64;

    @Override
    public String name() {
        return "SVADA transfer-proxy-nyckel (RSA-nyckelpar genererat vid uppstart, per instans)";
    }

    @Override
    public void initialize(ServiceExtensionContext context) {
        var nyckelpar = genereraNyckelpar();

        vault.storeSecret(PUBLIC_KEY_ALIAS, tillPem("PUBLIC KEY", nyckelpar.getPublic().getEncoded()));
        vault.storeSecret(PRIVATE_KEY_ALIAS, tillPem("PRIVATE KEY", nyckelpar.getPrivate().getEncoded()));

        context.getMonitor().info(
                "Transfer-proxy-nyckelpar (RSA " + RSA_NYCKELLANGD_BITS + " bitar) genererat vid uppstart och "
                        + "lagrat i vaulten (aliasen '" + PUBLIC_KEY_ALIAS + "'/'" + PRIVATE_KEY_ALIAS + "'). "
                        + "Unikt per instans/omstart – signerar och verifierar enbart dataplanets EGNA "
                        + "transfer-proxy-tokens (se klasskommentaren), aldrig ett värde en annan part behöver lita på.");
    }

    private static KeyPair genereraNyckelpar() {
        try {
            var generator = KeyPairGenerator.getInstance(RSA_ALGORITM);
            generator.initialize(RSA_NYCKELLANGD_BITS);
            return generator.generateKeyPair();
        } catch (NoSuchAlgorithmException e) {
            // RSA är obligatoriskt i varje JCE-provider sedan Java 8 - kan i praktiken
            // aldrig inträffa, men ett tydligt, förklarat fel är bättre än ett kryptiskt
            // NPE senare om det ändå skulle hända i en avvikande JVM-miljö.
            throw new IllegalStateException(
                    "RSA-algoritmen saknas i JVM:en - kan inte generera transfer-proxy-nyckelpar", e);
        }
    }

    private static String tillPem(String nyckeltyp, byte[] derKodadNyckel) {
        var encoder = Base64.getMimeEncoder(PEM_RADLANGD, "\n".getBytes());
        var base64 = encoder.encodeToString(derKodadNyckel);
        return "-----BEGIN " + nyckeltyp + "-----\n" + base64 + "\n-----END " + nyckeltyp + "-----\n";
    }
}
