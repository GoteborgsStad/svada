/*
 * SVADA PoC – hävning av avtal (avtalsgiltighet). KONCEPT: docs/koncept/06-kov-gate.md.
 *
 * Providerns spärr vid överföringens start: en överföring under ett avtal som KoV har
 * hävt nekas. Det är det riktiga låset (hård regel 7: providern äger policyverkställigheten,
 * aldrig mottagaren). Mekanismen är EDC:s egen policymotor: en PolicyRuleFunction körs för
 * varje skyldighet (Duty) i avtalets policy i scopet transfer.process, och ett false fäller
 * hela överföringen. Distribution A:s policy bär skyldigheten svada:kovGodkannande, så spärren
 * gäller bara A. Distribution B har ingen sådan skyldighet och berörs inte.
 *
 * Verifierat i EDC 0.17.0:s källa: PolicyEvaluator.visitDuty anropar varje duty-regelfunktion
 * och lägger ett RuleProblem om den returnerar false; TransferProcessPolicyContext bär avtalet
 * (contractAgreement()).
 */

package se.goteborg.svada.edc.kov;

import org.eclipse.edc.connector.controlplane.contract.spi.policy.TransferProcessPolicyContext;
import org.eclipse.edc.policy.engine.spi.PolicyRuleFunction;
import org.eclipse.edc.policy.model.Duty;
import org.eclipse.edc.spi.monitor.Monitor;

import static se.goteborg.svada.edc.odrl.SvadaOdrlExtension.ACTION_KOV_GODKANNANDE;

public class HavdAvtalSparr implements PolicyRuleFunction<Duty, TransferProcessPolicyContext> {

    private final KovGate gate;
    private final Monitor monitor;

    public HavdAvtalSparr(KovGate gate, Monitor monitor) {
        this.gate = gate;
        this.monitor = monitor;
    }

    @Override
    public boolean evaluate(Duty duty, TransferProcessPolicyContext context) {
        var action = duty.getAction();
        if (action == null || !ACTION_KOV_GODKANNANDE.equals(action.getType())) {
            return true;    // inte KoV-skyldigheten: inte vår sak
        }
        var avtal = context.contractAgreement();
        if (avtal == null) {
            return true;
        }
        var havning = gate.havning(avtal.getId());
        if (havning == null) {
            return true;
        }
        var skal = "Avtalet " + avtal.getId() + " har hävts av KoV (" + havning.orsak() + ", "
                + havning.tid() + "). Nya överföringar under avtalet nekas.";
        context.reportProblem(skal);
        monitor.warning("KoV-GATE: överföring nekad. " + skal);
        return false;
    }

    @Override
    public String name() {
        return "HavdAvtalSparr";
    }
}
