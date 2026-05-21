---
id: 8OS-BLOCK-1-SPEC
version: 1.0.0
status: accepted
kind: derivation
scope: project
domain: 8os/representation
authored_by: Q88N + Claude (Block 2.8 derivation)
authored_on: 2026-04-27
supersedes: 8OS-BLOCK-1-SPEC v0.2.0
superseded_by: null
depends_on: 8OS-KERNEL-SPEC v0.1.0
revisit_when: implementation surfaces a contradiction with the eight axioms or with this representation, or a domain need surfaces that the prediction-economics machinery cannot express
provenance: Block 2.7 implementation surfaced no axiom-level contradictions with v0.2. Block 2.8 takes up the prediction-economics work deferred from v0.2, adding projection types and a kernel-internal resolver through which the kernel reasons about whether to reason.
---

# 8OS Block 1 Specification v1.0

> **Active spec is v1.0.1-partial.** This v1.0.0 document remains the
> base; the active representation is v1.0.0 amended by
> [`8OS-BLOCK-1-SPEC-v1.0.1-PARTIAL.md`](./8OS-BLOCK-1-SPEC-v1.0.1-PARTIAL.md),
> which adds (1) projection-declared `target_subdirectory:` honored by
> `kernel.ir.new`, (2) mandatory `authored_via` on every (I, R) with SDK
> default `outside`, and (3) per-version body seal semantics. Read this
> document for the v1.0 mechanics; read v1.0.1-partial for the
> amendments that ship in the current kernel binary.

## What this document is

This is the on-disk representation specification for 8OS, version 1.0. It supersedes v0.2.0 additively. It preserves the sixteen-operation SDK contract, the nine kernel projection types, and the three kernel-internal resolvers from v0.2 verbatim, and adds the projection types and resolver through which the kernel can reason about whether to reason.

v1.0 makes one principled addition: **the kernel acquires the vocabulary to reason about predictions, value-of-information, calibration policies, and the holdout discipline that keeps predictors honest**. These mechanisms are opt-in. A v0.2 repo remains a valid v1.0 repo until it chooses to declare a calibration policy or author a prediction (I, R).

The new mechanisms compose with v0.2 through additive changes only: three new projection types, one new kernel-internal resolver, four new optional fields on existing v0.2 projection types, one new field on the tier 3 event schema. No v0.2 operation is modified. No v0.2 projection type is modified beyond gaining optional fields. No v0.2 data format requires migration.

## Why v1.0 exists

v0.2 gave the kernel a complete content model and a complete configuration model, but it left a question unanswered: when the kernel encounters an intention with multiple candidate resolvers — some cheap and uncertain, some expensive and reliable — how does it decide? v0.2 specified `kernel.selector` but its strategy was implicit. The selector picked resolvers; nothing told it whether to pick cheap and accept uncertainty, pick expensive and pay the cost, or pick a cheap predictor first and conditionally escalate.

That decision is itself an (I, R), per axiom 5. The kernel reasoning about which resolver to use is the kernel applying axioms 1–4 to its own selection logic. v1.0 makes that reasoning explicit. The selector consults a value-of-information resolver. The VOI resolver reads stakes from the intention, predictor calibration from the predictor's resolver, and the candidate ground-truth resolver's current cost. It returns an expected-value number. The selector picks accordingly.

The same mechanism extends naturally to the discipline that keeps predictors honest. Predictors drift. A predictor that was 85% accurate last quarter may be 70% accurate this quarter for reasons the system can detect only by holding out some decisions and running both predictor and ground-truth. Calibration policies declare how often to do that. The calibrator (already present in v0.2 for capability-vector updates) extends to consume the resulting (predicted, actual) pairs and update predictor calibration over time.

The principled path holds throughout. New projection types do not motivate new typed operations. The selector remains one operation; the strategy it uses is configurable. New resolvers are `_kernel.resolver` (I, R)s authored through `kernel.self` at bootstrap. The kernel surface stays at sixteen operations.

## Status of v0.2.0

v0.2.0 is superseded but referenced. The sixteen-operation SDK contract from v0.2 §4 is preserved unchanged in v1.0. The five configuration projection types and four operation-output projection types from v0.2 §3 are preserved unchanged. The three kernel-internal resolvers from v0.2 are preserved unchanged. The cogito bridge mechanics from v0.2 §2.4 are preserved unchanged.

v1.0 adds. It does not remove. It does not modify. Implementations targeting v0.2 continue to work; the v1.0 mechanisms activate when the v0.2 repo authors its first calibration policy or first prediction (I, R).

There is no v1.0 migration script (unlike v0.1→v0.2). Migration is the no-op described in §7.

---

## Section 0 — Framing that precedes the mechanics

Two properties of the v1.0 design must be made explicit before the machinery is specified, so neither is lost in the spec's mechanical framing.

### 0.1 Predictors need not be LLMs

**The prediction-economics machinery in v1.0 is resolver-shaped, not LLM-shaped.** It does not assume LLM predictors. Any resolver registered with cost lower than its candidate ground-truth resolver, with declared `predictor_calibration` referencing the resolver itself, can serve as a predictor. Statistical models, rule-based heuristics, lookup tables, learned surrogates from axiom 7's substitution mechanism, human glances at low-stakes decisions — all qualify.

**The machinery is opt-in.** A scope without a calibration policy operates in v0.2 mode with no behavioral change. The selector picks resolvers by cost and capability vectors as in v0.2. VOI is never consulted. Calibration is the v0.2 calibrator's existing capability-vector work, unchanged.

**The machinery degrades gracefully when predictors are unavailable.** If a registered predictor's bridge fails at runtime, v0.2's existing failure-handling captures the failure as a tier 3 event and the selector falls back to its next candidate. If no predictor is registered for a scope, the selector goes directly to the candidate ground-truth resolver — the economic loop collapses to "always escalate," a degenerate but valid configuration.

**Air-gapped configurations are valid.** The kernel's design does not depend on external LLM access for any of its eight axioms or for the prediction-economics machinery. A fully air-gapped kernel can run the loop with deterministic computations as inside resolvers, humans as outside resolvers via the human bridge, and statistical models trained from event-ledger history as inside surrogates per axiom 7.

The remainder of this spec describes the machinery in resolver-neutral terms. Examples use LLMs because they are the common case, not because the machinery requires them.

### 0.2 Bridge sovereignties

v0.2 §2.4 grounded two foundational sovereignties: the kernel's via cogito, the project's primary human via #NOKINGS sovereignty. v1.0's prediction-economics machinery makes visible a third category that has been present in the design since axiom 0 but has not previously been named: **bridge sovereignties**.

When the kernel reaches outside through a bridge — to an LLM, a human consulted in this moment, an external API, a physics simulator, an empirical test — it cannot verify the outside source's output against any kernel-internal source of truth. The kernel records what the outside said and reasons over the record. The outside is sovereign over its own output at the moment that output is produced. This is true of every bridge:

- **The LLM bridge.** The LLM produces; the kernel records. Later observation may inform calibration; immediate sovereignty over the output is the LLM's.
- **The human-in-the-moment bridge.** A human consulted at runtime answers a question; the kernel records the answer as authored by the human. The human is sovereign over what they said when they said it.
- **The API bridge.** An external service responds; the service is sovereign over its response. The kernel records what was returned.
- **The simulator bridge.** A physics or process simulator computes from its own laws and returns a result; the simulator is sovereign over the result it produced.

The pattern: **the outside speaks; the inside records and reasons later.** The kernel can later observe whether one bridge's outputs systematically diverge from another's (this is what calibration is). The kernel cannot say one bridge is right and another wrong. It can say: "in N prior cases, predictor A's outputs diverged from ground-truth resolver B's outputs by such-and-such pattern." Both A and B remain sovereign over their own outputs. The kernel just has more information about the relationship between them.

This reframes what the prediction-economics machinery is doing. When VOI says "the predictor's prediction is good enough; don't escalate," the kernel is choosing **which sovereignty to consult**. The predictor (an LLM, a heuristic, a surrogate) is sovereign over its prediction. The ground-truth resolver (a human, an empirical test, a simulator) is sovereign over its resolution. VOI is the kernel's calculation of which sovereignty to invoke given cost and stakes. Calibration is the kernel's accumulated observation of relationships among sovereigns' outputs over time. There is no kernel-internal source of truth; there are only sovereigns whose outputs the kernel records and reasons over.

This is not a new property of the kernel. Axiom 0 named the inside/outside boundary; axiom 6 specified that resolutions carry provenance recording who or what produced them. v1.0 makes explicit what was already true: every resolver, especially every bridged resolver, holds local sovereignty over its own outputs. The foundational sovereignties (cogito, primary human) and the bridge sovereignties together form the kernel's complete authority graph. The kernel's job is to honor every sovereign's outputs as authored, observe relationships among them empirically, and choose among them according to declared policy.

The implications for §3.6 (puddle-or-galaxy) and §3.7 (stakes-unknown) are spelled out where those sections are specified.

---

## Section 1 — On-disk representation (additive)

The v0.2 folder structure is preserved. v1.0 adds no new directories under `ir/_kernel/`. The new projection types (`_kernel.prediction`, `_kernel.calibration-policy`, `_kernel.calibration-policy-proposal`) author (I, R)s in user scopes alongside other tier-1 content, not in `_kernel`. Their projection-definition (I, R)s live under `ir/_kernel/projection/` like the v0.2 projection definitions.

### 1.1 No folder structure changes

The v0.2 §1.1 folder tree is preserved without modification. v1.0 introduces no new top-level directories, no new `.8os/` subdirectories, and no new conventions for where (I, R)s of new projection types are stored. They are stored in their authoring scope, per v0.2 §1.4.

### 1.2 Vendored projection bodies

`.8os/projections/_kernel/<type>.yml` gains three new files at v1.0 init: `prediction.yml`, `calibration-policy.yml`, and `calibration-policy-proposal.yml`. These are vendored body schemas for the three new kernel projection types, sealed at kernel ship per v0.2's discipline for the existing nine types.

---

## Section 2 — (I, R) frontmatter schema (additive clarifications)

The v0.2 frontmatter schema is preserved. v1.0 adds optional fields to two v0.2 projection types and clarifies stakes inheritance.

### 2.1 Optional `cost_model` field on `_kernel.resolver`

A `_kernel.resolver` (I, R) may declare an optional `cost_model` field describing how its cost varies with invocation parameters. Values:

- `cost_model: fixed` (default; matches v0.2 behavior). Cost is the declared `cost` vector, regardless of how the resolver is invoked.
- `cost_model: linear-in-depth`. Cost is a function of a `depth_budget` parameter passed at invocation time. The `cost` field is interpreted as `static`; an additional `cost_per_depth_unit` field declares the variable component. Effective cost per invocation is `cost + cost_per_depth_unit × depth_budget` for each currency.

The `depth_budget` unit is resolver-defined. For LLM resolvers it is typically tokens or reasoning steps. For Monte Carlo simulators it is sample count. For exhaustive checkers it is search depth. The unit is documented in the resolver's body prose, not constrained by the kernel.

When the selector consults a resolver with `cost_model: linear-in-depth`, the selector also picks a `depth_budget` value and passes it as part of the invocation. The resolver is contractually obligated to honor the budget or refuse the invocation with a structured error. Resolvers without `cost_model` declared default to `fixed`, preserving v0.2 behavior.

`cost_model: piecewise` is reserved for future versions but not specified in v1.0. v1.0 ships only `fixed` and `linear-in-depth`.

### 2.2 Optional `stakes_defaults` field on `_kernel.scope`

A `_kernel.scope` (I, R) may declare an optional `stakes_defaults` field carrying default stakes values for intentions authored under that scope. The shape matches the per-intention `stakes` field specified in §3.1. Intentions in the scope inherit defaults; intentions may override per-instance.

If a scope declares no `stakes_defaults` and an intention authored under it carries no `stakes` field, stakes are treated as **unknown**. VOI's behavior on unknown stakes is specified in §3.7: it returns a value that causes the selector to escalate rather than predict. This is the conservative default. Authors who want to predict cheaply must explicitly declare low stakes — the system makes this declaration visible rather than assuming it.

### 2.3 Optional `stakes` field on intentions

Any (I, R) about which prediction may be authored may carry an optional `stakes` field in its frontmatter. The shape:

```yaml
stakes:
  false_positive_cost: {clock_ms, coin_usd, carbon_g}
  false_negative_cost: {clock_ms, coin_usd, carbon_g}
  reversibility: irreversible | reversible_within_<duration> | reversible
  consequence_scope: project | downstream
```

All four fields are optional within the `stakes` block. Missing fields default to scope `stakes_defaults`; missing scope defaults render the field unknown; unknown fields propagate to VOI per §3.7.

The four fields support honest VOI computation:

- **`false_positive_cost`** and **`false_negative_cost`** capture asymmetric loss. False positives and false negatives almost always have different costs in real decisions. A bare scalar magnitude collapses too much information for VOI to do useful math.
- **`reversibility`** affects effective stakes. A reversible decision has lower effective cost-of-being-wrong than an irreversible one of the same nominal magnitude. `reversible_within_<duration>` accepts ISO 8601 durations.
- **`consequence_scope`** affects whose 3Cs are at risk. `project` means costs fall on the kernel's project. `downstream` means costs propagate to parties outside the project (users, regulators, dependent systems). VOI weights downstream costs higher than project costs by a policy-declared factor.

---

## Section 3 — The three new kernel projection types

v1.0 introduces three new kernel projection types: two configuration projections and one operation-output projection. They are vendored at v1.0 init alongside the nine v0.2 types.

After v1.0 the kernel's complete projection-type set is:

- **Five v0.2 configuration projections** (unchanged): `_kernel.scope`, `_kernel.projection`, `_kernel.resolver`, `_kernel.bridge`, `_kernel.surrogate-lineage`.
- **Four v0.2 operation-output projections** (unchanged): `_kernel.tier3-event`, `_kernel.authorization`, `_kernel.resolver-selection`, `_kernel.capability-update`.
- **Two v1.0 configuration projections** (new): `_kernel.prediction`, `_kernel.calibration-policy`.
- **One v1.0 operation-output projection** (new): `_kernel.calibration-policy-proposal`.

Twelve total. Each new type is specified below.

### 3.1 `_kernel.prediction`

**Purpose**: record a prediction about an intention's resolution, authored by a predictor resolver, before (and instead of, or alongside) the candidate ground-truth resolver runs.

**Projection-declared frontmatter extensions**:

- `subject_intention: <ir-id>` — the intention being predicted about.
- `predicted_resolution: <free-form value>` — the predictor's claim about how the intention resolves. Shape varies by intention type: boolean for yes/no questions, numeric for continuous outcomes, structured object for richer predictions. The kernel does not constrain the shape; the prediction's projection-types may declare additional projection types that further constrain it.
- `probability: <number 0–1> | null` — the predictor's reported confidence. Null for predictors that do not produce calibrated probabilities (e.g., deterministic rule-based heuristics). VOI handles null by treating the prediction as unconditionally certain, which makes the prediction's output the resolution if the selector picks predict-only.
- `predictor: <resolver-id>` — references the `_kernel.resolver` (I, R) that produced the prediction. The predictor's calibration is read from this referenced resolver, not inlined.
- `predictor_calibration: <ir-id> | null` — optional reference to a more specific `_kernel.capability-update` (I, R) that overrides the predictor resolver's general calibration with one specific to this domain or stakes tier. Null defaults to the predictor's general capability vector.

The prediction (I, R) does not carry an `escalation_cost` field. Escalation cost is a property of the candidate ground-truth resolver, looked up at VOI consultation time from that resolver's current (calibrator-maintained) cost vector. See §3.7.

**Body shape**: free-form prose describing the predictor's reasoning, optional. The mechanical prediction is in the frontmatter.

**Authority**: matches the predictor's authority. LLM predictors typically produce `convention` predictions; rule-based predictors with sovereign-authored rules may produce `hard`; learned surrogates produce `convention` or `uncalibrated` depending on the surrogate's validation history.

**On-disk location**: `ir/<scope>/_predictions/<prediction-id>.md` where `<scope>` is the scope of the subject intention. Filename suffix `.prediction.md` (declared by the projection definition).

**Bootstrap**: `8os init` creates no predictions. They emerge from selector activity once a calibration policy is in effect.

### 3.2 `_kernel.calibration-policy`

**Purpose**: declare, for a scope or domain, how the kernel invests in keeping its predictors honest. The policy specifies what predictor is being calibrated against what ground-truth resolver, when holdouts fire, when recalibration triggers, and what signal to fall back to when ground-truth is impractical.

**Projection-declared frontmatter extensions**:

- `policy_id: <slug>` — must equal the (I, R)'s `id`. Symmetry with v0.2 projections that carry a body-self-description id.
- `applies_to_scope: <scope-id>` — the scope this policy governs. Predictions and decisions in this scope and its subscopes are subject to the policy.
- `applies_to_domain: <domain-string> | null` — optional domain restriction within the scope. Null means all domains.
- `predictor: <resolver-id>` — the resolver being calibrated.
- `ground_truth_resolver: <resolver-id> | null` — the resolver whose outputs serve as actuals for calibration. Null means no practical ground-truth resolver exists for this domain (the muddy-puddle-or-distant-galaxy case; see §3.6).
- `calibration_signal: ground_truth | proxy` — what evidence the calibrator uses to update predictor calibration. `ground_truth` requires a non-null `ground_truth_resolver`; `proxy` requires a `proxy_specification` field.
- `proxy_specification: {kind: peer-agreement | supersession-rate | outcome-correlation | holdout-against-ensemble, params: {...}}` — required when `calibration_signal: proxy`. Specifies which non-ground-truth signal to use and how to compute it.
- `holdout_rate: <number 0–1>` — fraction of decisions in the policy's domain that run both predictor and ground-truth (or both predictor and proxy comparator) for calibration evidence. Zero means no holdouts (predictor's outputs are accepted without verification). One means every decision runs both.
- `recalibration_trigger: {kind: count | time | drift-threshold, params: {...}}` — when the calibrator should consume accumulated (predicted, actual) pairs and produce a capability-update or proposal. `count: N` means after every N pairs. `time: <duration>` means at fixed intervals. `drift-threshold: <number>` means whenever observed calibration error exceeds the threshold.
- `ground_truth_timeout: <duration> | null` — when `calibration_signal: ground_truth`, how long to wait for actuals before falling back to a proxy signal. Null means wait indefinitely. The fallback behavior is specified in §3.6.

**Body shape**: free-form prose describing the policy's purpose, the rationale for chosen rates and triggers, links to relevant standing authorizations. Optional but recommended for non-trivial policies.

**Authority**: `hard` only. Calibration policies bind system behavior across many resolutions and persist across project lifetime; they are sovereignty-shaped and require hard authority for authoring and supersession.

**On-disk location**: `ir/<scope>/_calibration-policies/<policy-id>.md`. Filename suffix `.policy.md`.

**Bootstrap**: `8os init` creates no calibration policies. A scope without a policy operates in v0.2 mode (no predictions, no VOI consultation, no calibration corpus).

### 3.3 `_kernel.calibration-policy-proposal` (operation-output)

**Purpose**: record the calibrator's proposal to update a calibration policy in response to observed evidence. Proposals are not effective; they are queued, and become effective via standing authorization (per §3.4) or runtime countersignature.

**Projection-declared frontmatter extensions**:

- `proposal_id: <slug>` — must equal the (I, R)'s `id`.
- `target_policy: <policy-id>` — the calibration policy this proposal recommends superseding.
- `proposed_changes: {<field>: <new-value>, ...}` — the specific changes recommended. Typically `holdout_rate` adjustments, but may include any field of the target policy.
- `evidence_summary: {observation_count, period_start, period_end, observed_calibration_error, observed_drift, ...}` — structured summary of the calibrator's evidence.
- `proposed_by: <resolver-id>` — the calibrator resolver that produced the proposal. Always `kernel.calibrator` in v1.0; reserved for future calibrators.
- `proposed_on: <iso-8601>` — when the calibrator authored the proposal.
- `status: pending | approved | rejected | superseded` — lifecycle state. Begins `pending`; transitions to `approved` on authorization match or runtime countersignature, `rejected` on explicit rejection by sovereign, `superseded` if the calibrator authors a newer proposal for the same policy before this one is acted on.
- `effective_supersession: <ir-id> | null` — when `status: approved`, the actual supersession (I, R) on the target policy that the calibrator authored after approval. Null otherwise.

**Body shape**: free-form prose with the calibrator's analysis and rationale. Recommended for non-trivial proposals so the sovereign can review reasoning.

**Authority**: `convention`. Proposals by themselves bind nothing; they are evidence the sovereign considers.

**On-disk location**: `ir/<scope>/_calibration-proposals/<proposal-id>.md`. Filename suffix `.proposal.md`.

**Bootstrap**: vendored at v1.0 init.

### 3.4 Standing authorizations for calibration-policy supersession

A standing authorization (using v0.2's existing `_kernel.authorization` projection from §3.6.2) may pre-grant approval for calibration-policy proposals matching defined conditions. The authorization's `authorized_action` is `supersede-calibration-policy`; its `authorized_subject` is one or more `_kernel.calibration-policy` (I, R) ids; its body specifies the conditions under which proposals automatically attain `approved` status.

Example shape (the body's structure is convention; the authorization mechanism itself is unchanged from v0.2):

```yaml
authorized_action: supersede-calibration-policy
authorized_subject: [calibration-policy-lending-default]
granted_by: human-q88n
granted_on: 2026-04-27T12:00:00Z
expires_on: null
conditions:
  - field: holdout_rate
    change_within: 0.05
  - field: holdout_rate
    requires_min_observations: 1000
  - field: holdout_rate
    requires_p_value: 0.05
```

When the calibrator authors a proposal, the kernel's authorization machinery (v0.2 §3.6.2 unchanged) checks the proposal against any standing authorizations covering the target policy. If a standing authorization matches all the proposal's conditions, the proposal's `status` transitions to `approved` and the calibrator is dispatched to author the actual supersession (I, R) on the target policy. The supersession's provenance points to both the proposal and the matched authorization.

Proposals not matching any standing authorization remain `pending` until a sovereign authors either (a) an explicit countersignature authorization specific to that proposal, or (b) a broader standing authorization that retroactively covers it.

### 3.5 Capability-vector updates remain calibrator-authority alone

Updates to a resolver's capability vector — the work `kernel.calibrator` already performs in v0.2 via `_kernel.capability-update` — remain calibrator-authority alone. v1.0 does not require sovereign approval for capability-vector updates. The reasoning: capability vectors are parameters within strategy; calibration policies are strategy. The calibrator tunes parameters within the policy the sovereign set; the calibrator does not change the policy itself without approval.

v1.0 extends `kernel.calibrator`'s capability-update authority to also cover **cost-vector updates** on resolvers. The justification is symmetric: cost vectors, like capability vectors, are empirical parameters that the kernel observes through tier 3 events and refines per axiom 5's empirical refinement clause. The mechanism is identical — the calibrator authors a `_kernel.capability-update` (I, R) whose `updated_capabilities` field carries cost-vector changes alongside or instead of σ/π/α/ρ changes. The projection's existing `previous_capabilities` and `updated_capabilities` shapes are extended to include optional cost-vector fields.

### 3.6 The puddle-or-galaxy case

Some intentions have ground-truth resolvers that would not terminate within practical limits — proofs over unbounded input classes, predictions about long-run system behavior, policy outcomes ten years out. From the kernel's vantage point at any given moment, these are indistinguishable from intentions whose ground-truth resolver simply has not produced its actual yet. Both produce identical observations: silence in the (predicted, actual) pair.

The kernel does not distinguish them. It cannot. Per §0.2, the kernel has no internal source of truth that would let it determine whether an absent actual is delayed or impossible. The honest position is to acknowledge this and design the mechanism around indistinguishability rather than around a distinction the kernel cannot draw.

Both cases are handled by the same mechanism, which is the kernel choosing among bridge sovereignties when its originally-named ground-truth sovereign has not produced output:

- The candidate ground-truth resolver is registered with its true cost — possibly very large — in its `_kernel.resolver` (I, R). VOI consults that cost honestly. For sufficiently expensive resolvers, VOI computes "do not escalate" with high confidence regardless of stakes.
- The calibration policy declares either `calibration_signal: ground_truth` with a `ground_truth_timeout` after which it falls back to a proxy signal, or `calibration_signal: proxy` from the start. Proxy signals are *other sovereigns* whose outputs the kernel consults when the originally-named ground-truth sovereign has not produced output:
  - **Peer agreement** — what other predictor sovereigns say about the same intention.
  - **Supersession rate** — how often later authoring sovereigns overturn this prediction.
  - **Outcome correlation** — what the world's own outputs (downstream observable events) say.
  - **Holdout against an ensemble** — what an ensemble of predictors collectively says.
- When the timeout elapses with no actual, the calibrator switches to consulting the proxy sovereigns. If the originally-named ground-truth sovereign ever does produce output after the timeout, that output supersedes the proxy-derived calibration; the kernel does not close the door on late actuals.

The framing is deliberate: the kernel is not falling back to "approximations" of truth when ground-truth is impractical. It is consulting different sovereigns when the originally-named one has not spoken. Each sovereign — original ground-truth, peer predictors, supersession authors, the world's own downstream events — is sovereign over its own outputs. The calibrator records what each said and reasons over the record. Truth-determination is not the kernel's job.

The puddle and the distant galaxy are treated identically because the kernel's epistemic position toward both is identical: silence from one sovereign, the option to consult others, the discipline to honor late arrivals if and when they come. The calibration policy's `ground_truth_timeout` and proxy fallback express this discipline in machinery the calibrator can run.

### 3.7 Stakes-unknown defaults to escalate

When VOI is consulted with stakes-unknown for an intention (no `stakes` field on the intention, no `stakes_defaults` on its scope, no inheritance ancestor that declares them), VOI returns a value that causes the selector to escalate rather than predict. This is the conservative default.

Two reasons compose to make this the right default. The first is operational: a naive default of "low stakes" would cause the system to predict cheaply for high-stakes decisions whose stakes were forgotten or not yet declared. That is exactly the failure mode the prediction-economics machinery exists to prevent. Defaulting to "stakes unknown → escalate" makes silent under-protection impossible. Authors who want to predict cheaply must declare low stakes explicitly. The system makes the declaration visible rather than assuming it.

The second reason is epistemic, and follows from §0.2's framing. When VOI weighs predict-only against escalate, it is choosing between consulting the predictor sovereign (cheaper, locally less authoritative) and the candidate ground-truth sovereign (more expensive, locally more authoritative). The choice depends on stakes — at low stakes, deferring to the cheaper sovereign is rational; at high stakes, the more authoritative sovereign is worth the cost. With stakes unknown, the kernel does not have the information needed to justify deferring to the less authoritative sovereign. The principled response is to consult the more authoritative one.

Stakes-unknown-defaults-to-escalate is therefore not just a safety mechanism. It is the kernel's expression of epistemic humility: in the absence of information that would justify economizing on authority, defer to the more authoritative source.

This default is not adjustable per-resolver or per-call. It is a property of `kernel.voi`'s vendored definition and changes only via supersession of `kernel.voi` (which requires hard authority).

---

## Section 4 — The new kernel-internal resolver: `kernel.voi`

v1.0 adds one kernel-internal resolver, joining the three from v0.2 (`kernel.selector`, `kernel.gatekeeper`, `kernel.calibrator`). After v1.0 the kernel ships four internal resolvers; the count is not load-bearing on the spec, only the principled-path discipline that they are all `_kernel.resolver` (I, R)s vendored at bootstrap through `kernel.self`.

### 4.1 `kernel.voi` — definition

**Purpose**: compute the expected value of escalation given a prediction, a candidate ground-truth resolver, and stakes. Pure inside resolver. Vendored at bootstrap through `kernel.self`.

**Inputs (passed at invocation)**:

- The prediction (I, R), referenced by id. VOI reads `predicted_resolution`, `probability`, `predictor`, `predictor_calibration`.
- The candidate ground-truth resolver, referenced by id. VOI reads the resolver's current cost vector (which the calibrator keeps fresh per §3.5 and v0.2 §3.6.4) and capability vector.
- The intention (I, R), referenced by id. VOI reads `stakes` from the intention's frontmatter or inherits from scope `stakes_defaults`.
- The active calibration policy, referenced by id (when one is in effect). VOI reads `holdout_rate` to determine whether the current decision is a calibration sample.

**Output**: a structured value `{recommended_strategy, expected_value_predict_only, expected_value_escalate, expected_value_run_both, rationale}` where `recommended_strategy ∈ {predict-only, predict-then-conditional-escalate, escalate-directly, run-both-with-comparison}`.

**Cost vector (vendored)**: near-zero. `{clock_ms: <1, coin_usd: 0, carbon_g: <0.01}`. VOI is pure computation over kernel-managed (I, R)s.

**Capability vector (vendored)**: `{<voi-domain>: {sigma: 1.0, pi: 1.0, alpha: 1.0, rho: 1.0}}`. VOI is deterministic given its inputs; its capability is bounded by the inputs' accuracy, not by VOI itself. The calibrator may later refine this if VOI's recommendations are observed to produce decisions that diverge from sovereign judgment, in which case VOI's `rho` (reliability) would be refined downward and the calibrator may emit a calibration-policy-proposal touching VOI's behavior.

**Bridge**: null. VOI is an inside resolver.

**Bootstrap**: `8os init` (at v1.0) creates the `kernel.voi` `_kernel.resolver` (I, R) under `ir/_kernel/resolver/` alongside the three v0.2 internal resolvers.

### 4.2 VOI's behavior on stakes-unknown

Per §3.7, when stakes are unknown, VOI returns a structured value with `recommended_strategy: escalate-directly` and `rationale: stakes-unknown-default`. The selector observes the recommendation and proceeds accordingly.

### 4.3 VOI's behavior on calibration-sample selection

The selector's decision to run a holdout (rather than honor VOI's recommendation) is governed by the calibration policy's `holdout_rate`, not by VOI. The selector consults VOI for its recommendation and separately consults the policy for whether the current decision is a sampled holdout. If holdout, the selector overrides VOI's recommendation with `run-both-with-comparison`. If not holdout, the selector follows VOI. VOI itself does not implement holdout sampling; it computes value under the assumption that the recommendation will be followed, leaving the holdout decision to the selector and policy.

### 4.4 VOI event emission

When `kernel.voi` is consulted, the consultation does not emit its own tier 3 event. Instead, the parent `kernel.selector` invocation's tier 3 event is extended to include the VOI consultation's inputs, output, and rationale as a structured field. This avoids flooding the event log with VOI events on hot paths while preserving full auditability — every selector decision shows the VOI reasoning that produced it. The tier 3 event schema gains an optional `voi_consultation` field for this purpose; the field is absent when no VOI consultation occurred.

---

## Section 5 — Expanded roles for `kernel.selector` and `kernel.calibrator`

v0.2's specifications for `kernel.selector` and `kernel.calibrator` are preserved. v1.0 adds responsibilities to each.

### 5.1 `kernel.selector` — expanded

In addition to v0.2's responsibilities (reading resolver cost and capability vectors, picking a resolver per axiom 5), the selector in v1.0:

- **Consults `kernel.voi`** when an active calibration policy declares a predictor for the intention's scope and domain. The consultation passes the predictor's most-recent prediction (or a freshly-authored one if none exists), the candidate ground-truth resolver, the intention's stakes, and the policy. VOI returns a recommendation.
- **Picks a `depth_budget`** when consulting a resolver with `cost_model: linear-in-depth`. The depth-search strategy in v1.0 is a coarse grid: shallow / medium / deep at resolver-declared values (the resolver's body specifies the grid points; the selector picks one). Sovereign may override the strategy via a standing authorization. Future versions may specify finer-grained depth selection.
- **Honors the calibration policy's holdout sampling.** When the policy's `holdout_rate` indicates the current decision is a calibration sample, the selector overrides VOI's recommendation with `run-both-with-comparison`.
- **Enforces purpose-partitioned budgets.** When budget enforcement is active (via standing authorization), the selector tracks separately decision-purpose and holdout-purpose escalation costs and refuses to dispatch escalations that would exceed their respective budgets. See §6 for the tier 3 event extension that supports this.
- **Checks standing authorizations against calibrator proposals.** When the calibrator authors a `_kernel.calibration-policy-proposal`, the selector (or the kernel's authorization machinery; the implementation is free to choose) checks the proposal against standing authorizations and, on match, dispatches the calibrator to author the supersession.

The selector remains one operation: `kernel.selector.select`. Its strategy is configurable through the calibration policy and standing authorizations. v1.0 introduces no new operation.

### 5.2 `kernel.calibrator` — expanded

In addition to v0.2's responsibilities (consuming the calibration corpus and updating resolver capability vectors via `_kernel.capability-update`), the calibrator in v1.0:

- **Updates resolver cost vectors** through the same `_kernel.capability-update` mechanism, with `updated_capabilities` carrying cost-vector changes alongside σ/π/α/ρ changes. v0.2's projection definition for `_kernel.capability-update` is extended to allow this; the extension is additive (existing capability-update records remain valid; cost-vector fields are new optional additions).
- **Authors `_kernel.calibration-policy-proposal` records** when accumulated evidence suggests a calibration policy should be updated. Proposals carry the calibrator's analysis and recommended changes. The calibrator does not author the supersession directly; that requires authorization match or runtime countersignature per §3.4.
- **Authors the supersession (I, R) on a calibration policy** after the calibrator's proposal attains `approved` status. The supersession's provenance points to the approved proposal and the matched authorization.
- **Consumes the calibration corpus** built from prediction (I, R)s and their corresponding ground-truth resolution (I, R)s. The corpus is reconstructed by query at calibrator runtime (per §6.1's index), not maintained as denormalized state. Calibrator queries the index, gets back the (predicted, actual) pairs for the predictor it is calibrating, and computes calibration metrics.

The calibrator remains a single resolver. v1.0 does not introduce a new operation; the calibrator's expanded responsibilities are dispatched through the kernel's existing resolver-invocation machinery.

---

## Section 6 — Indexes and tier 3 events (additive)

v0.2's twelve indexes and the tier 3 event JSONL schema are preserved. v1.0 adds one new index and one new event field.

### 6.1 New index: calibration corpus

A thirteenth regenerable index is added to the `.8os/index/` roster: **calibration-corpus**. The index maps `(predictor_id, scope, domain)` triples to ordered lists of `(prediction_id, ground_truth_resolution_id, predicted_value, actual_value, predicted_at, actual_at)` tuples.

The index is rebuilt by `8os reindex` from prediction (I, R)s and their resolved-ground-truth resolution (I, R)s. The mapping from prediction to ground-truth is by `subject_intention` — the prediction names the intention; the ground-truth resolution that resolves the intention via the candidate resolver named in the active policy is the actual.

For predictions whose actual has not yet arrived, the tuple's `actual_value` and `actual_at` are null. Calibrator queries with `actual_value IS NOT NULL` get the resolved corpus.

The index is regenerable: drop it, rebuild from (I, R)s, no information loss. The kernel's append-only discipline is preserved — no prediction (I, R) is mutated when its actual arrives; the relationship is reconstructed by query.

### 6.2 New event field: `escalation_purpose`

Tier 3 events for resolver-invocation operations gain an optional `escalation_purpose` field. Values:

- `escalation_purpose: decision` — the invocation is an escalation triggered by VOI's recommendation; it is informing this specific decision.
- `escalation_purpose: holdout` — the invocation is an escalation triggered by the calibration policy's holdout sampling; its outputs feed the calibration corpus.
- `escalation_purpose: none` — the invocation is not an escalation. Direct resolutions where no predictor was consulted, or invocations of the predictor itself, carry this value.

The field is absent in v0.2-format events; absence is treated as `none` for backward compatibility. v1.0 events written by v1.0 selectors include the field on every resolver invocation.

The 3Cs ledger maintains running totals partitioned by `escalation_purpose`. Standing authorizations may declare separate budgets per purpose, enforced by the selector at dispatch time per §5.1.

In the `run-both-with-comparison` case (calibration holdout), the cost split is mechanical: the predictor's invocation that would have happened anyway is `escalation_purpose: none` (it is the predictor doing its job); the ground-truth resolver's invocation that would not have happened without the holdout is `escalation_purpose: holdout`. The decision the system acts on uses whichever output the policy specifies; the cost partitioning is independent of that.

### 6.3 Optional `voi_consultation` field on selector events

Per §4.4, tier 3 events for `kernel.selector.select` invocations gain an optional `voi_consultation` field carrying the VOI consultation's inputs, output, and rationale when VOI was consulted. The field is absent when VOI was not consulted (no calibration policy in effect for the scope/domain). v1.0 implementations consult VOI under the conditions in §5.1 and emit the field accordingly.

---

## Section 7 — Migration from v0.2.0 to v1.0

A v0.2.0 repo migrates to v1.0 with no data migration. The migration is the no-op described below.

### 7.1 Migration steps, in order

1. **Upgrade the kernel binary** from v0.2 to v1.0. The new binary recognizes the three new projection types and the new internal resolver.
2. **Run `8os reindex`** (existing operation, unchanged). This regenerates the twelve v0.2 indexes plus the new calibration-corpus index from §6.1. The new index is initially empty (no predictions exist yet in a v0.2 repo).
3. **At first v1.0 init invocation against an existing v0.2 repo, or at next `8os reindex`**, the kernel vendors the three new kernel projection-type definitions (`_kernel.prediction`, `_kernel.calibration-policy`, `_kernel.calibration-policy-proposal`) under `ir/_kernel/projection/` and the one new kernel-internal resolver (`kernel.voi`) under `ir/_kernel/resolver/`. These are authored through `kernel.self` at hard authority, identically to the v0.2 vendored content.
4. **No tier 3 event is emitted for the v0.2→v1.0 transition itself.** v1.0 makes no observable change to existing data; the transition is the kernel binary recognizing new vocabulary the existing data does not yet use. When the repo's first prediction or calibration policy is authored, that authoring is the observable v1.0 event.

### 7.2 No migration script

Unlike v0.1→v0.2, v1.0 ships no migration script. The migration is a kernel-binary upgrade plus reindex. Implementations that need to fold the new vendored content into a running v0.2 repo can do so by re-running `8os init` against the existing repo (which is already idempotent per v0.2 §7.2's discipline) or by running `8os reindex` after upgrading the binary.

### 7.3 Existing tests

The tests passing under v0.2 remain valid under v1.0. v1.0 adds tests covering: prediction (I, R) authoring and validation; calibration policy authoring with `calibration_signal: ground_truth | proxy` and proxy specification validation; calibration-policy-proposal authoring by the calibrator; standing authorization match against proposals; supersession authoring by the calibrator after approval; VOI consultation by the selector; depth budget selection for `cost_model: linear-in-depth` resolvers; stakes-unknown defaulting to escalate; calibration corpus index regeneration; tier 3 event `escalation_purpose` partitioning.

The v1.0 acceptance criterion is: all v0.2 tests pass unchanged; new v1.0 tests pass; CI passes the index-drift check (now covering thirteen indexes).

---

## Section 8 — What v1.0 does not do

Surfacing constraints v1.0 declines to address, so future blocks know they are open:

- **v1.0 does not specify the surrogate training pipeline.** Prediction (I, R)s and the calibration corpus are training data. The pipeline that consumes them and produces trained surrogates is a future block. The `kernel.surrogate.train` interface stub from v0.1.0, preserved unchanged through v0.2, is preserved unchanged through v1.0.
- **v1.0 does not specify the factory.** The bee runtime, dispatch loop, and parallel resolver-invocation machinery remain Block 3.
- **v1.0 does not specify self-modification competition.** The operational test of one resolver's predictions superseding another's is for after v1.0 ships and the factory exists.
- **v1.0 does not ship `cost_model: piecewise`.** Only `fixed` and `linear-in-depth` are specified. Piecewise is reserved for future versions when an actual non-linear-cost resolver demonstrates the need.
- **v1.0 does not introduce a "decision" projection type.** Stakes are a property of intentions, not of separately-projected decisions. If future blocks require explicit decision projections, the change is additive.
- **v1.0 does not specify finer-grained depth selection strategies.** The selector picks from the resolver's coarse-grid declared depth points. Continuous optimization over depth is reserved for future versions.
- **v1.0 does not respecify the sixteen operations from v0.2.** It clarifies the selector and calibrator's responsibilities; it does not rewrite the operations.

---

## Section 9 — Resolved open questions

The four explicitly-open questions from the prediction-economics conversation:

- **Naming (`_kernel.estimate` vs `_kernel.prediction`)**: resolved to `_kernel.prediction` by §3.1. Vocabulary coherence with `kernel.voi`, calibration corpus, predictor calibration.
- **Depth-cost for LLM predictors**: resolved by §2.1's optional `cost_model: linear-in-depth` field on `_kernel.resolver`. Selector picks both resolver and depth budget when applicable.
- **Cosmological-bound intentions**: resolved by §3.6. No new mechanism; calibration policy's `calibration_signal` field plus `ground_truth_timeout` carry the load. Spec foregrounds puddle-vs-galaxy indistinguishability.
- **Stakes interface**: resolved by §2.2 and §2.3. Structured stakes on intentions with scope-level defaults; stakes-unknown defaults to escalate per §3.7.

The five additional decisions:

- **Forward-link vs query-reconstruction**: resolved by §6.1 to query reconstruction via a regenerable calibration-corpus index. Append-only discipline preserved.
- **VOI as resolver vs strategy module**: resolved by §4.1 to resolver. Vendored at bootstrap. Event emission batched per §4.4.
- **`escalation_cost` field on prediction**: resolved by §3.1 (field absent) and §3.7 (VOI looks up resolver's current cost). `kernel.calibrator`'s spec extends to cost-vector updates per §5.2.
- **Calibration policy supersession authority**: resolved by §3.3 and §3.4 to permissive-C. Calibrator emits proposals; standing authorizations or runtime countersignatures attain effective supersession. Capability-vector updates (and now cost-vector updates) remain calibrator-authority alone per §3.5.
- **Holdout vs decision cost budgets**: resolved by §6.2 to separate budgets via `escalation_purpose` partitioning on tier 3 events.

No new open questions are introduced by v1.0.

---

## Section 10 — Status

This is **v1.0.0**. It locks the prediction-economics vocabulary: prediction (I, R)s, calibration policies, the VOI resolver, calibration-policy proposals with sovereign-or-standing-authorization approval, depth-parameterized cost models, structured stakes with scope inheritance, calibration corpus as regenerable index, purpose-partitioned escalation budgets.

Future versions may add projection types, resolvers, cost-model variants, depth-selection strategies, decision projections, or other refinements. They should preserve the principle that *every artifact the kernel manages is an (I, R)* and that *the kernel's reasoning about its own reasoning is itself (I, R)-shaped*. Departures from these principles indicate a flaw in the principles or a flaw in the design, to be resolved by amendment with explicit axiom-level reasoning.

The next block (Block 3) implements the factory: bee resolvers as `_kernel.resolver` (I, R)s, dispatch logic as production rules expressed as (I, R)s, the loop that watches the (I, R) graph for unresolved nodes and routes them to selected resolvers per axiom 5 and the v1.0 prediction-economics machinery.

---

*End of Block 1 specification v1.0. Authored in Block 2.8. Supersedes v0.2.0 additively.*
