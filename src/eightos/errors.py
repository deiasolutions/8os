"""Stable error codes per Block 1 spec section 7.3."""

from __future__ import annotations


class KernelError(Exception):
    """An expected, structured kernel error mapped to a stable error code.

    Carries the fields needed to render a Block 1 §7.2 error envelope.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        axiom_violated: int | None = None,
        input_field: str | None = None,
        offending_value: object | None = None,
        suggested_action: str | None = None,
        extra_context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.axiom_violated = axiom_violated
        self.input_field = input_field
        self.offending_value = offending_value
        self.suggested_action = suggested_action
        self.extra_context = extra_context or {}


# Stable error codes — Block 1 §7.3.
SCHEMA_INVALID = "SCHEMA_INVALID"
KERNEL_OUTPUT_INVALID = "KERNEL_OUTPUT_INVALID"
NOT_FOUND = "NOT_FOUND"
ALREADY_EXISTS = "ALREADY_EXISTS"
INVALID_STATE = "INVALID_STATE"
AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
AUTHORITY_INSUFFICIENT = "AUTHORITY_INSUFFICIENT"
SCOPE_VIOLATION = "SCOPE_VIOLATION"
DEPENDENCY_BROKEN = "DEPENDENCY_BROKEN"
INDEX_DRIFT = "INDEX_DRIFT"
ATOMICITY_FAILURE = "ATOMICITY_FAILURE"
ATOMICITY_FAILURE_PARTIAL = "ATOMICITY_FAILURE_PARTIAL"
BRIDGE_UNREACHABLE = "BRIDGE_UNREACHABLE"
# Block 3 Piece 3: bridge function (under src/eightos/bridges/) raised
# during outside-contact dispatch via kernel.bridge.cross.
BRIDGE_FAILED = "BRIDGE_FAILED"
EVENT_WRITE_FAILED_AFTER_CROSSING = "EVENT_WRITE_FAILED_AFTER_CROSSING"
KERNEL_VERSION_MISMATCH = "KERNEL_VERSION_MISMATCH"
# v1.0.1-partial Amendment 1: rejected when a record carries multiple
# projection_types declaring conflicting `target_subdirectory:` values.
CONFLICTING_PROJECTION_TARGETS = "CONFLICTING_PROJECTION_TARGETS"
# Block 4.2 / v1.1 §18.1: cancel-specific lifecycle codes. The other ops
# still use the generic NOT_FOUND / INVALID_STATE / AUTHORITY_INSUFFICIENT
# codes; the IR-prefixed taxonomy from v1.1 §18.1 is folded in only as new
# ops land. Migrating existing ops to IR-prefixed codes is a separate cleanup.
IR_ALREADY_CANCELLED = "IR_ALREADY_CANCELLED"
IR_NOT_CANCELLABLE = "IR_NOT_CANCELLABLE"
CANCELLATION_AUTHORITY_INSUFFICIENT = "CANCELLATION_AUTHORITY_INSUFFICIENT"
# Emitted on pending outside-call ops queued against a cancelled (I, R).
# Reserved for kernel.outside.http (v1.1 §11); not yet emitted by Block 4.2
# because the existing kernel.bridge.cross is synchronous (no queue to drop
# from).
IR_CANCELLED = "IR_CANCELLED"
# Block 4.3 / v1.1 §18.6: emitted by classification-based policy gating when
# a write or resolve is rejected because the (I, R)'s `data_classification`
# is incompatible with the destination scope's policy. Reserved for the
# policy-evaluation phase; not yet emitted by Block 4.3 because
# `_kernel.policy` machinery (v1.1 §8) isn't implemented in this binary.
CLASSIFICATION_VIOLATION = "CLASSIFICATION_VIOLATION"
# Block 4.4 / v1.1 §18.1: rejected at `kernel.ir.new` time when a
# convention- or uncalibrated-authority record carries a `visible_when`
# predicate. Per v1.1 §4.4: visibility predicates encode access control,
# which is sovereignty-shaped and therefore restricted to hard-authority
# records. `kernel.reindex --check` enforces the same invariant on disk
# as defense-in-depth.
VISIBILITY_PREDICATE_NOT_PERMITTED = "VISIBILITY_PREDICATE_NOT_PERMITTED"
# Block 4.4 / v1.1 §18.1: emitted by `kernel.ir.get` when the target's
# `visible_when` predicate evaluates false against the caller context.
# `kernel.ir.list` and `kernel.ir.deps` filter invisible records silently
# (no error). The same code is also returned for axiom-3 scope-visibility
# failures per v1.1 §3.9 — callers handling visibility rejection don't need
# to distinguish the two reasons.
IR_NOT_VISIBLE = "IR_NOT_VISIBLE"
# Block 4.6 / v1.1 §3.2 (per BLOCK-4.5-SPEC-AMENDMENTS Amendment 4): emitted
# by `kernel.ir.new` when a `supersedes:` input points at an (I, R) whose
# status is not `cancelled`. Path A: supersede-with-replacement is the
# canonical reversal path for cancelled records only; for living records
# (open / resolved / stale), use kernel.ir.supersede instead. The
# missing-target case reuses generic NOT_FOUND per Block 4.6 F1 (the
# spec-text reading of "IR_NOT_FOUND" is treated as the existing generic
# code; migrating the broader "id doesn't exist" surface to IR-prefixed
# codes is a separate cleanup block per Block 4.4 F4).
IR_SUPERSEDES_TARGET_NOT_CANCELLED = "IR_SUPERSEDES_TARGET_NOT_CANCELLED"
# Block 4.7 / v1.1 §18.5: emitted by the policy-evaluation phase when an
# applicable `_kernel.policy` decision is `deny`. The error context carries
# the policy id that produced the deny so callers can surface it.
POLICY_DENIED = "POLICY_DENIED"
# Block 4.7 / v1.1 §18.5: emitted by the policy-evaluation phase when an
# applicable `_kernel.policy` decision is `defer`. The error context
# carries the deferred-to role id; an authorization from a holder of that
# role permits the op to proceed (resubmit with `authorization_id`).
POLICY_REQUIRES_AUTHORIZATION = "POLICY_REQUIRES_AUTHORIZATION"
# Block 4.8 / v1.1 §18.6: kernel.outside.http surface. Reachability and
# governance failures distinct from the legacy bridge.cross codes.
# OUTSIDE_UNREACHABLE: outside service did not respond (DNS, connect-time,
# transport-level failure). Distinct from BRIDGE_UNREACHABLE which retains
# the legacy semantics for kernel.bridge.cross's bridge-resolver path.
OUTSIDE_UNREACHABLE = "OUTSIDE_UNREACHABLE"
# Block 4.8 / v1.1 §11.2: applicable policy denied the outside call before
# transport. Error context carries the policy id and (where applicable)
# the destination identifier the policy refused.
OUTSIDE_CALL_DENIED = "OUTSIDE_CALL_DENIED"
# Block 4.8 / v1.1 §11.5: kernel-level queue cutoff elapsed before the
# call was served; the kernel drops the queued call with this code rather
# than attempting transport. PRISM-IR programs supply the meaning of the
# cutoff (hard SLA, soft preference, escalation trigger); the kernel
# respects the timestamp without interpretation.
EXPIRES_AT_PASSED = "EXPIRES_AT_PASSED"
# Block 4.8 / v1.1 §11.2: cost ceiling on the standing authorization (or
# applicable budget policy) exceeded by this call's expected or measured
# cost. Distinct from RATE_LIMIT_EXHAUSTED which is rate-shaped.
BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
# Block 4.8 / v1.1 §11.2: outside service returned a rate-limit signal
# (typically HTTP 429), or a kernel-side rate budget rejected the call
# before transport. Block 4.8 ships the pass-through path (external
# 429 -> RATE_LIMIT_EXHAUSTED); kernel-side rate budgets are deferred.
RATE_LIMIT_EXHAUSTED = "RATE_LIMIT_EXHAUSTED"
# Block 4.8 / v1.1 §11.2: request payload exceeds kernel-imposed size
# limits. Kernel rejects pre-transport.
PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
# Block 4.8 / v1.1 §13.3 + §18.4: lease check (op_pipeline phase 2) found
# an active `_kernel.lease` record on the target scope or (I, R), held by
# another writer. Op rejects pre-commit. Distinct from AUTHORITY_INSUFFICIENT
# which is identity-shaped; LEASE_HELD is coordination-shaped.
LEASE_HELD = "LEASE_HELD"
# Block 4.8 / v1.1 §18.4: operation against a `_kernel.lease` whose
# `valid_through` has elapsed. Caller must re-acquire (typically by
# authoring a new lease record) before retrying the op.
LEASE_EXPIRED = "LEASE_EXPIRED"
