The risk register under **Risk** holds every hazard (HAZ-001 and so on) for each device, scored before and after risk controls. Score = severity × probability, each on a 1–5 scale.

| Score | Level | What it means |
| --- | --- | --- |
| 1–4 | Acceptable (green) | Can be accepted as it is |
| 5–9 | Reduce as far as possible (amber) | Add controls; accepting it needs a benefit-risk rationale |
| 10–25 | Unacceptable (red) | Must be reduced; accepting it needs a benefit-risk rationale |

| Severity |  | Probability |  |
| --- | --- | --- | --- |
| 1 | Negligible | 1 | Improbable |
| 2 | Minor | 2 | Remote |
| 3 | Serious | 3 | Occasional |
| 4 | Critical | 4 | Probable |
| 5 | Catastrophic | 5 | Frequent |

These are the default thresholds. Your administrator can change them to match your risk management plan; check they agree before relying on the colours.

## Add and control a hazard

1. **Risk → New hazard**. Choose the device, then describe the hazard, the sequence of events, the hazardous situation and the harm, choose the software item involved, then score severity and probability before controls.
2. **Add control** for each risk control. Choose its type (inherent safety by design, protective measure, or information for safety) and link the Change Request that implements it.
3. When a control is proven to work, add the verification evidence and tick **Verified**.
4. Score the residual severity and probability.

## Accept the residual risk

QA accepts the residual risk with a signature. The **Next steps** panel lists anything that still blocks acceptance:

- residual risk not scored;
- no controls, when the initial risk wasn't acceptable;
- any control not yet verified;
- residual risk above acceptable without a benefit-risk rationale.

An accepted hazard is locked. To change it, QA clicks **Reopen** with a reason, for example a new complaint. A hazard that no longer applies can be retired with a signed reason.
