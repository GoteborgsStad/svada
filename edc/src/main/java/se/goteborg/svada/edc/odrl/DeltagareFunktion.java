/*
 * SVADA PoC – ODRL-funktionen för deltagare; identitetskällan är sedan steg 5 den verifierade DCP-identiteten.
 *
 * Utvärderingsfunktion för ODRL-constrainten
 *
 *     leftOperand svada:deltagare  operator odrl:eq  rightOperand <StadensDID>
 *
 * på Distribution A:s permission "use". Den svarar på frågan "vilken
 * dataspace-deltagare begär avtalet?" och jämför med policyns högerled.
 * rightOperand är sedan den verifierbara DCP-identiteten (steg 5) Stadens FULLA DID (t.ex.
 * "did:web:identity-hub-stad%3A29197"), inte längre kortnamnet "stad" -
 * se nästa stycke för varför, och edc/bootstrap/policy-distribution-a.json
 * (platshållaren __STAD_DID__, ersatt av edc/bootstrap/registrera.py) för
 * var värdet faktiskt sätts.
 *
 * Funktionen körs på PROVIDER-sidan när consumern skickar sin
 * ContractRequestMessage (ContractValidationServiceImpl#validateInitialOffer
 * -> policyEngine.evaluate(contractPolicy, ContractNegotiationPolicyContext)).
 * Faller den blir förhandlingen TERMINATED direkt – det är ODRL som
 * verkställs, inte som dekoration.
 *
 * IDENTITETEN ÄR SEDAN DEN VERIFIERBARA DCP-IDENTITETEN KRYPTOGRAFISKT VERIFIERAD (inte längre
 * bara påstådd). context.participantAgent()
 * .getIdentity() nedan kommer numera från EDC:s DCP-verifiering (Decentralized
 * Claims Protocol): motpartens Verifiable Presentation kontrolleras kryptografiskt
 * mot en betrodd utfärdares (se edc.iam.trustedissuer.* i edc/konfig/*.properties)
 * signatur INNAN förhandlingen ens når den här funktionen.
 *
 * Identitetsvärdet är motpartens RIKTIGA DID, direkt från DCP-modulens EGEN
 * default-identitetskälla (ingen anpassad extraktionsfunktion registreras
 * längre – ett tidigare försök att låta identiteten vara den verifierade
 * VC:ns kortnamns-claim "participantId" ("stad"/"dhi") visade sig krocka
 * med EDC:s eget kontrollplan, som återanvänder samma
 * ParticipantAgent.getIdentity()-värde som mål-audience i self-issued-tokens
 * för DSP-återanrop – ett kortnamn är inte en giltig audience. Se
 * se.goteborg.svada.edc.dcp.SvadaDcpIdentityExtension:s klasskommentar för
 * hela felsökningskedjan och motiveringen. Denna funktions EGEN jämförelselogik är oförändrad – det är
 * bara vilket värde "deltagare" jämförs MOT (nu en DID i stället för ett
 * kortnamn) som ändrats.
 */

package se.goteborg.svada.edc.odrl;

import org.eclipse.edc.connector.controlplane.contract.spi.policy.ContractNegotiationPolicyContext;
import org.eclipse.edc.policy.engine.spi.AtomicConstraintRuleFunction;
import org.eclipse.edc.policy.model.Operator;
import org.eclipse.edc.policy.model.Permission;
import org.eclipse.edc.spi.monitor.Monitor;

public class DeltagareFunktion
        implements AtomicConstraintRuleFunction<Permission, ContractNegotiationPolicyContext> {

    private final Monitor monitor;

    public DeltagareFunktion(Monitor monitor) {
        this.monitor = monitor;
    }

    @Override
    public boolean evaluate(Operator operator, Object rightValue, Permission rule,
                            ContractNegotiationPolicyContext context) {
        var deltagare = context.participantAgent() == null
                ? null : context.participantAgent().getIdentity();
        var forvantad = rightValue == null ? null : rightValue.toString();

        boolean resultat;
        switch (operator) {
            case EQ -> resultat = forvantad != null && forvantad.equals(deltagare);
            case NEQ -> resultat = forvantad != null && !forvantad.equals(deltagare);
            default -> {
                // Bara eq/neq är meningsfulla för en identitet. Okända
                // operatorer ska inte tyst släppa igenom.
                context.reportProblem("svada:deltagare stöder bara eq/neq, fick "
                        + operator);
                resultat = false;
            }
        }

        // Loggas alltid: det är BEVISET för att regeln verkligen utvärderades
        // (dvs. att bindningen i RuleBindingRegistry finns). Verifieringens
        // testfall 4b.x letar efter den här raden i providerns logg.
        monitor.info("SVADA ODRL utvärderad: svada:deltagare " + operator + " '"
                + forvantad + "' mot deltagare '" + deltagare + "' => " + resultat);
        return resultat;
    }

    @Override
    public String name() {
        return "svada:deltagare";
    }
}
