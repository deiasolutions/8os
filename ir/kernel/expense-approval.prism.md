---
authored_by: q88n
authored_on: '2026-04-26T23:24:20.266Z'
authored_via: outside
authority_level: convention
collapsed_summary: Expense approval — categorize, then route to manager or finance based on amount.
depends_on: []
expanded_into: null
id: expense-approval
kind: ir-node
parent: null
projection_types:
- prism-ir
resolution_event: null
resolved_at: null
resolver: null
revalidate_trigger: null
scope: kernel
status: open
superseded_by: null
supersedes: null
surrogate_of: null
tier: 1
valid_through: null
visible_to:
- kernel
---

# Intention

PRISM-IR v1.1 Level 1 example: an expense approval flow.

The canonical PRISM-IR YAML body lives in the fenced block below. The 8OS
framtmatter `id` (above) and the PRISM-IR top-level `id` (in the body) match
exactly per v1.1 identity discipline.

Level 1 conformance is declared in the body because the current kernel
(8OS v0.1.0) does not yet accept arbitrary projection-specific frontmatter
additions through `kernel.ir.new` — see OPEN-Q-010 and the prism-ir projection
declaration at .8os/projections/prism-ir.yml.

```yaml
v: 1.1.0
prism: expense-approval
version: 1.1.0
conformance: level-1

id: expense-approval
name: Expense approval routing
domain: finance/expense
intention: |
  Categorize a submitted expense; route to direct manager when under threshold,
  or to finance review when over. Approval terminates the flow; rejection
  emits a rejection notice and ends.

failure_tolerance:
  classify: retry
  manager_review: escalate
  finance_review: escalate

constraints:
  - sla: classify completes within 5s
    fail: drop
    priority: low
  - sla: total flow under 24h
    fail: escalate
    priority: high

entities:
  - id: expense
    fields: [amount_usd, submitter_id, category, submitted_at]

events:
  - id: submitted
    on: expense.submitted_at

nodes:
  - id: start
    t: start
  - id: classify
    t: task
    o: { op: llm, resolver: claude-haiku-4-5 }
    out: [category, amount_bucket]
  - id: route
    t: decision
    cond: expense.amount_usd > 1000
  - id: manager_review
    t: task
    o: { op: human, tier: l2 }
  - id: finance_review
    t: task
    o: { op: human, tier: finance }
  - id: notify
    t: task
    o: { op: api, endpoint: notify.send }
  - id: end
    t: end

edges:
  - { s: start, t: classify }
  - { s: classify, t: route }
  - { s: route, t: finance_review, c: 'expense.amount_usd > 1000' }
  - { s: route, t: manager_review, c: 'expense.amount_usd <= 1000' }
  - { s: manager_review, t: notify }
  - { s: finance_review, t: notify }
  - { s: notify, t: end }

metrics:
  - id: cycle_time_p95
    expr: rate(classify -> end, p95)
  - id: approval_rate
    expr: count(end where approved) / count(start)
```
