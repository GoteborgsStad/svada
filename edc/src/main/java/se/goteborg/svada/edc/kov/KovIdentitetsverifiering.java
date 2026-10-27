/*
 * SVADA PoC – verifierbar DCP-identitet, steg 6 (docs/koncept/C1-identitet.md).
 *
 * ===================================================================
 * VARFÖR DEN HÄR KLASSEN BEHÖVS
 * ===================================================================
 * docs/koncept/C1-identitet.md, tabellen över de tre attesttyperna:
 * "SvadaRoleCredential ... KovController kräver denna innan godkänn/avslå
 * accepteras – detta är den delen som fullt ut stänger arkitekturinvariant
 * 4, inte bara det loggade rollnamnet." Fram till verifieringssteget skyddades
 * KovController.godkann()/avsla() ENBART av de nyckelskyddade management-API:ernas delade
 * management-nyckel (web.http.management.auth.*) – vem som helst med den
 * nyckeln kunde godkänna/avslå, och beslutsfattarens "roll" var bara en
 * konfigurationssträng (svada.kov.rollinnehavare) som loggades, aldrig
 * bevisades. Den här klassen stänger det gapet: den KRÄVER att anroparen
 * bevisar, via ett verifierat DCP-presentation-utbyte, att den faktiskt
 * innehar ett SvadaRoleCredential med rätt "role"-claim – exakt samma
 * kryptografiska mekanism som STEG 5 redan verifierade fullt ut för
 * DSP-lagrets katalog-/förhandlingsflöde.
 *
 * ===================================================================
 * MEKANISMEN – ÅTERANVÄNDER EDC:S EGEN IdentityService, INTE EN EGEN
 * ===================================================================
 * IdentityService.verifyJwtToken(participantContextId, token, context) är
 * EXAKT samma SPI-metod som EDC:s eget DSP-lager anropar för varje
 * inkommande protokollanrop (se ProtocolTokenValidatorImpl i
 * control-plane-aggregate-services, uppströms) – den körda
 * implementationen (DcpIdentityService, decentralized-claims-service)
 * gör HELA DCP-cykeln åt oss: extraherar presentation-access-token-claimet
 * ur det inkommande self-issued-tokenet, frågar avsändarens CredentialService
 * (Presentation Query) efter de begärda scopen, verifierar den returnerade
 * Verifiable Presentation kryptografiskt (signatur, trusted issuer), och
 * paketerar de verifierade attesten som en ClaimToken. Vi återanvänder
 * alltså SAMMA beprövade väg som redan bär hela förhandlings-/
 * transferflödet – ingen egen, parallell kryptoimplementation.
 *
 * Scopet vi begär, org.eclipse.dspace.dcp.vc.type:SvadaRoleCredential:read,
 * är samma sträng som edc.iam.dcp.scopes.roll.value i
 * edc/konfig/provider.properties (STEG 5) – samma litterala DCP-scope-
 * format, bara begärt manuellt här i stället för att härledas ur en
 * ODRL-policy.
 *
 * ===================================================================
 * HUR EN KoV-OPERATÖR FAKTISKT FÅR ETT TOKEN ATT PRESENTERA
 * ===================================================================
 * Anroparen (Kretslopp och Vatten, som Stadens IdentityHub-instans redan
 * har utfärdat ett SvadaRoleCredential till, se STEG 4) måste FÖRST hämta
 * ett self-issued token från Stadens EGEN inbäddade STS:
 *
 *   POST http://identity-hub-stad:29199/api/sts/token   (form-urlencoded)
 *     grant_type=client_credentials
 *     client_id=<Stadens DID, SVADA_PARTICIPANT_DID_STAD>
 *     client_secret=<SVADA_STS_CLIENT_SECRET_STAD>
 *     audience=<DHI:s DID, EDC_PROVIDER_ID>
 *     bearer_access_scope=org.eclipse.dspace.dcp.vc.type:SvadaRoleCredential:read
 *
 * och skicka svarets access_token som Authorization: Bearer-header till
 * POST /management/kov/forhandlingar/{id}/godkann|avsla. STS-porten
 * (29199) är MEDVETET inte publicerad mot host (se compose.stad.yml) –
 * anropet måste alltså göras inifrån Stadens förtroendegräns (t.ex.
 * exec:at i en container på stad-internal), exakt den avgränsning
 * arkitekturen kräver: ingen utanför Staden kan mynta ett token åt
 * Kretslopp och Vatten-rollen. tests/lib.sh:s hamta_kov_token() gör precis
 * detta (docker exec i svada-edc-consumer, som redan ligger på
 * stad-internal tillsammans med identity-hub-stad).
 *
 * ===================================================================
 * FÖRSVAR I DJUP, INTE ETT BYTE MOT ETT ANNAT
 * ===================================================================
 * Den delade management-nyckeln (de nyckelskyddade management-API:erna) tas INTE bort – den skyddar
 * fortfarande TRANSPORTLAGRET (vem som helst utan nyckeln avvisas redan
 * av EDC:s inbyggda web.http.management.auth innan anropet ens når den
 * här klassen). Det den här klassen lägger till är BEVISET för VEM,
 * bortom att bara känna till en delad hemlighet.
 * ===================================================================
 */

package se.goteborg.svada.edc.kov;

import org.eclipse.edc.iam.verifiablecredentials.spi.model.VerifiableCredential;
import org.eclipse.edc.policy.model.Policy;
import org.eclipse.edc.spi.iam.IdentityService;
import org.eclipse.edc.spi.iam.TokenRepresentation;
import org.eclipse.edc.spi.iam.VerificationContext;
import org.eclipse.edc.spi.result.Result;

import java.util.List;
import java.util.Objects;

public class KovIdentitetsverifiering {

    /**
     * DCP-scopet för SvadaRoleCredential – samma litterala sträng som
     * edc.iam.dcp.scopes.roll.value i edc/konfig/provider.properties
     * (STEG 5), återanvänd här för ett manuellt presentation-utbyte i
     * stället för ett ODRL-policyhärlett.
     */
    public static final String ROLL_SCOPE = "org.eclipse.dspace.dcp.vc.type:SvadaRoleCredential:read";

    private static final String VC_TYP_ROLL = "SvadaRoleCredential";
    /** DcpDefaultServicesExtension.CLAIMTOKEN_VC_KEY, uppströms – ej beroendedeklarerad enbart för en konstant. */
    private static final String CLAIM_VC = "vc";
    private static final String CLAIM_ROLE = "role";

    private final IdentityService identityService;
    private final String egetParticipantId;
    private final String kravdRollinnehavare;

    public KovIdentitetsverifiering(IdentityService identityService, String egetParticipantId,
                                     String kravdRollinnehavare) {
        this.identityService = identityService;
        this.egetParticipantId = egetParticipantId;
        this.kravdRollinnehavare = kravdRollinnehavare;
    }

    /**
     * Verifierar Authorization-headerns self-issued DCP-token mot
     * avsändarens IdentityHub och kontrollerar att den bär ett
     * SvadaRoleCredential vars "role"-claim matchar den konfigurerade
     * Data Rights Holder-rollen.
     *
     * @return Result.success(den verifierade rollen) eller Result.failure(orsak).
     */
    /**
     * Ett felmeddelande som bär sin språkoberoende kod och sina parametrar FÖRE den svenska texten:
     * {@code \u0001kod\u0001nyckel=värde;nyckel=värde\u0001text}. Result.failure kan bara bära en sträng, så
     * KovController tar isär den igen (se {@link #delaFel}) och svarar med kod, parametrar och text.
     */
    static String kodatFel(String kod, java.util.Map<String, String> parametrar, String text) {
        var p = new StringBuilder();
        parametrar.forEach((k, v) -> p.append(p.length() > 0 ? ";" : "").append(k).append('=')
                .append(v == null ? "" : v.replace("\u0001", " ").replace(";", ",")));
        return "\u0001" + kod + "\u0001" + p + "\u0001" + text;
    }

    /** Delar ett felmeddelande från {@link #kodatFel}: [kod, parametrar som sträng, text]; utan kod: [null, "", text]. */
    static String[] delaFel(String detalj) {
        if (detalj != null && detalj.startsWith("\u0001")) {
            var delar = detalj.split("\u0001", 4);
            if (delar.length == 4) {
                return new String[] {delar[1], delar[2], delar[3]};
            }
        }
        return new String[] {null, "", detalj};
    }

    public Result<String> verifiera(String authorizationHeader) {
        if (authorizationHeader == null || authorizationHeader.isBlank()) {
            return Result.failure(kodatFel("kov.authorization_saknas", java.util.Map.of("rolltyp", VC_TYP_ROLL),
                    "Authorization-header saknas – ett godkänn-/avslå-anrop måste "
                    + "bära ett self-issued DCP-token som bevisar avsändarens " + VC_TYP_ROLL + "."));
        }

        var token = TokenRepresentation.Builder.newInstance().token(authorizationHeader).build();
        var context = VerificationContext.Builder.newInstance()
                .policy(Policy.Builder.newInstance().build())
                .scopes(List.of(ROLL_SCOPE))
                .build();

        var verifiering = identityService.verifyJwtToken(egetParticipantId, token, context);
        if (verifiering.failed()) {
            return Result.failure(kodatFel("kov.dcp_misslyckades",
                    java.util.Map.of("orsak", String.valueOf(verifiering.getFailureDetail())),
                    "DCP-verifiering av avsändarens token misslyckades: " + verifiering.getFailureDetail()));
        }

        var claimToken = verifiering.getContent();
        var vcLista = claimToken.getListClaim(CLAIM_VC);
        if (vcLista == null) {
            return Result.failure(kodatFel("kov.inga_attest", java.util.Map.of("rolltyp", VC_TYP_ROLL),
                    "Verifieringen lyckades men gav inga attest alls – inget "
                    + VC_TYP_ROLL + " kunde hittas."));
        }

        var funnenRoll = vcLista.stream()
                .filter(o -> o instanceof VerifiableCredential)
                .map(o -> (VerifiableCredential) o)
                .filter(vc -> vc.getType().contains(VC_TYP_ROLL))
                .flatMap(vc -> vc.getCredentialSubject().stream())
                .map(subjekt -> subjekt.getClaims().get(CLAIM_ROLE))
                .filter(Objects::nonNull)
                .map(Object::toString)
                .findFirst();

        if (funnenRoll.isEmpty()) {
            return Result.failure(kodatFel("kov.inget_rollintyg", java.util.Map.of("rolltyp", VC_TYP_ROLL),
                    "Avsändaren presenterade inget verifierat " + VC_TYP_ROLL
                    + " – ett giltigt self-issued token räcker inte, KoV-beslut kräver ett "
                    + "attest för Data Rights Holder-rollen."));
        }

        if (!kravdRollinnehavare.equals(funnenRoll.get())) {
            return Result.failure(kodatFel("kov.fel_roll",
                    java.util.Map.of("funnen", funnenRoll.get(), "kravd", kravdRollinnehavare),
                    ("Avsändarens verifierade roll är '%s', men KoV-gaten kräver "
                    + "'%s'.").formatted(funnenRoll.get(), kravdRollinnehavare)));
        }

        return Result.success(funnenRoll.get());
    }
}
