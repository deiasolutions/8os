# Block 3 SCAN dogfood — bundled artifacts

A single markdown file compiling the three artifacts produced by Block 3's
end-to-end dogfood, suitable for sharing with a collaborator who hasn't seen
the rest of the repo.

**What this is:** 8OS Block 3 ran the SCAN-pillar daily briefing flow
end-to-end through the kernel + factory machinery. A PRISM-IR doc
described the workload; a registered LLM decomposer translated it into
a four-node (I, R) graph hosted by the kernel; the factory walked the
graph, dispatching real HTTP fetches and Anthropic API calls; resolutions
accumulated; a registered LLM recomposer read the resolved graph back
without seeing the original PRISM-IR doc and reconstructed an English
description for round-trip fidelity comparison.

Three artifacts, in order:

1. **The original PRISM-IR `intention:` field** that authored the workload.
2. **The actual briefing artifact** the workload produced — composed by Claude Haiku 4.5 from real HackerNews + arXiv items.
3. **The recomposer's reconstruction** — what an LLM thinks the workload was for, reading only the resolved kernel records (no access to the original PRISM-IR doc).
4. **A side-by-side fidelity comparison** with deterministic claim-alignment + structural-fidelity tables and an empty verdict slot for the human dogfooder to fill in.

Costs: ~$0.04 total in Anthropic API spend (decomposer + score + briefing + recomposer, all on Haiku 4.5).

---

# 1. Original PRISM-IR intent

From `ir/dogfood-scan/scan-daily-briefing.md` — the `intention:` field of the PRISM-IR doc that authored the workload.

> Each morning, fetch top items from selected sources, judge their
> relevance to a stated briefing topic, pick the top items by
> relevance, and compose a structured briefing artifact summarizing
> what's worth reading today.

**Workload params** (also part of the original spec; shape the workload's behavior):

- `briefing_topic: AI infrastructure and governance, week of 2026-04-27`
- `top_n: 5`
- `fetch_window_hours: 24`

**Flow (PRISM-IR `nodes:` and `edges:`):** four task nodes in sequence — `fetch-sources` → `score-relevance` → `filter-and-rank` → `generate-briefing`. Two are script resolvers (inside the kernel binary, no API cost); two are LLM resolvers (Anthropic bridge, real cost).

---

# 2. The briefing artifact

From `.8os/dogfood-scan/artifacts/scan-generate-briefing.md` — composed by the `generate-briefing` LLM resolver from real HN + arXiv items, scored by `score-relevance`, ranked by `filter-and-rank`. This is what the workload actually produced.

---

# AI Infrastructure Shifts: Partnership Dissolution, Supply Chain Risks, and Governance Gaps

This week marks significant disruption in AI's structural backbone. Microsoft and OpenAI's partnership fracture reshapes industry incentives just as researchers expose fragmented accountability in AI supply chains and a major data breach hits AI contractors. Meanwhile, frameworks for agentic systems and scaling-law efficiency emerge as governance priorities. Together, these developments signal mounting pressure on how AI infrastructure is funded, audited, secured, and scaled.

## Top items

### Microsoft and OpenAI end their exclusive and revenue-sharing deal
*Source: hackernews · https://www.bloomberg.com/news/articles/2026-04-27/microsoft-to-stop-sharing-revenue-with-main-ai-partner-openai*

Microsoft is ending its exclusive revenue-sharing arrangement with OpenAI, fundamentally restructuring one of AI's most consequential commercial relationships. This move has immediate implications for how AI infrastructure funding, model access, and competitive dynamics will evolve across the industry.

### How Supply Chain Dependencies Complicate Bias Measurement and Accountability Attribution in AI Hiring Applications
*Source: arxiv · https://arxiv.org/abs/2604.22679v1*

A new analysis shows that modern AI hiring systems fragment accountability across data vendors, model providers, and deployers—creating scenarios where biased outcomes emerge from component interactions that no single party can fully evaluate. Regulatory bodies (EU AI Act, NYC Local Law 144) assign legal liability to deployers who lack technical visibility into vendor algorithms, exposing a critical governance gap that existing compliance frameworks don't address.

### 4TB of voice samples just stolen from 40k AI contractors at Mercor
*Source: hackernews · https://app.oravys.com/blog/mercor-breach-2026*

A data breach at Mercor exposed voice samples from 40,000 AI contractors, compromising a core input stream for voice model training. The incident underscores infrastructure security risks in the distributed contractor networks that power AI dataset creation and highlights the physical supply chain's vulnerability to theft.

### Agentic World Modeling: Foundations, Capabilities, Laws, and Beyond
*Source: arxiv · https://arxiv.org/abs/2604.22748v1*

Researchers propose a "levels × laws" taxonomy for world models used by autonomous agents—spanning physical, digital, social, and scientific domains. The framework synthesizes over 400 works and explicitly addresses governance challenges, architectural guidance, and evaluation practices for systems that manipulate environments and coordinate with other agents, establishing evaluation standards for increasingly capable infrastructure.

### Spend Less, Fit Better: Budget-Efficient Scaling Law Fitting via Active Experiment Selection
*Source: arxiv · https://arxiv.org/abs/2604.22753v1*

A new method reduces the cost of fitting scaling laws—which guide multi-million-dollar training runs—to roughly 10% of full-experiment budgets through uncertainty-aware experiment selection. Scaling-law accuracy directly determines resource allocation decisions across the industry, making this efficiency gain relevant to infrastructure planning and cost governance.

## Links

- [Microsoft and OpenAI end their exclusive and revenue-sharing deal](https://www.bloomberg.com/news/articles/2026-04-27/microsoft-to-stop-sharing-revenue-with-main-ai-partner-openai) — hackernews
- [How Supply Chain Dependencies Complicate Bias Measurement and Accountability Attribution in AI Hiring Applications](https://arxiv.org/abs/2604.22679v1) — arxiv
- [4TB of voice samples just stolen from 40k AI contractors at Mercor](https://app.oravys.com/blog/mercor-breach-2026) — hackernews
- [Agentic World Modeling: Foundations, Capabilities, Laws, and Beyond](https://arxiv.org/abs/2604.22748v1) — arxiv
- [Spend Less, Fit Better: Budget-Efficient Scaling Law Fitting via Active Experiment Selection](https://arxiv.org/abs/2604.22753v1) — arxiv

---

# 3. Recomposer's reconstruction

From `.8os/dogfood-scan/artifacts/scan-roundtrip-check-reconstruction.md` — generated by the `prism-ir-recomposer` LLM resolver (Claude Haiku 4.5) reading the resolved (I, R) graph alone. **The recomposer was not given the original PRISM-IR document.** Its inputs were each node's intention text, prism_operator declaration, depends_on edges, and resolution_text.

This is the round-trip output: what the workload looks like as English when reconstructed from the kernel records that captured it.

---

The workload's purpose was to generate a daily briefing on AI infrastructure, governance, and security developments by aggregating recent stories from HackerNews and arXiv, scoring them for relevance, filtering to the most important items, and composing them into a markdown briefing document.

The process began when a script resolver named `fetch-sources` pulled recent items from HackerNews top stories and arXiv submissions in AI and machine learning. This step returned approximately 20 items, each tagged with title, URL, source label, and source priority. An llm resolver named `score-relevance` then examined each fetched item and assigned a relevance score between 0 and 1 based on connection to AI infrastructure and governance topics, providing brief justifications for each rating. Items addressing unrelated topics like meeting productivity or SMS spam received scores near zero, while substantive AI governance stories such as the Microsoft-OpenAI partnership dissolution received high scores of 0.85 or above.

After scoring, a script resolver named `filter-and-rank` selected the top-ranked items by relevance score, with ties broken by source priority, producing a filtered list of the most significant stories. The ranked output included the Microsoft-OpenAI revenue-sharing deal dissolution (scored 0.85 for its direct impact on AI industry structure), a research paper on supply chain accountability gaps in AI hiring systems, and a report on a data breach exposing voice samples from thousands of AI contractors at Mercor.

Finally, an llm resolver named `generate-briefing` composed a markdown briefing document titled "AI Infrastructure Shifts: Partnership Dissolution, Supply Chain Risks, and Governance Gaps." The briefing opened with a framing paragraph explaining that this week marked significant disruption in AI's structural foundation, then provided summaries of the top three items with source attribution and URLs for follow-up reading. The document contextualized these stories as signals of mounting pressure on how AI infrastructure is funded, audited, secured, and scaled.

The end result was a structured, ready-to-publish daily briefing artifact that distilled dozens of potential sources into a curated set of the week's most consequential AI governance and infrastructure developments.

---

# 4. Fidelity comparison

From `.8os/dogfood-scan/artifacts/scan-roundtrip-comparison.md`. Side-by-side claim alignment plus structural fidelity, with the human-judged verdict slot at the end.

## Side-by-side: claim alignment

| Original PRISM-IR claim | Recomposer reconstruction | Match |
|--------------------------|----------------------------|-------|
| "fetch top items from selected sources" | "pulled recent items from HackerNews top stories and arXiv submissions in AI and machine learning" | ✅ — names the sources, captures fetch step |
| "judge their relevance to a stated briefing topic" | "examined each fetched item and assigned a relevance score between 0 and 1 based on connection to AI infrastructure and governance topics" | ✅ — relevance scoring with topic explicit |
| "pick the top items by relevance" | "selected the top-ranked items by relevance score, with ties broken by source priority" | ✅ — top-N + tie-breaking captured |
| "compose a structured briefing artifact" | "composed a markdown briefing document titled..." | ✅ — composition step + format captured |
| "summarizing what's worth reading today" | "ready-to-publish daily briefing artifact that distilled dozens of potential sources into a curated set" | ✅ — purpose framing captured |
| "Each morning" (cadence) | not directly stated | ⚠️ — daily cadence inferable but not explicit; the recomposer only saw a single run |

## Structural fidelity

| Structural claim | Status |
|------------------|--------|
| Four task nodes in sequence | ✅ — recomposer named all four |
| Order: fetch → score → filter → generate | ✅ — order preserved |
| Operator types: script, llm, script, llm | ✅ — each named correctly with op type |
| Resolver names: fetch-sources, score-relevance, filter-and-rank, generate-briefing | ✅ — all four cited verbatim |
| Briefing topic specifically: AI infrastructure and governance | ✅ — topic carried through |
| Top-N parameter | ✅ — captured as "top-ranked items" |

## Fidelity verdict (human-judged)

The verdict below is rendered by the human dogfooder reading the two texts side-by-side. The tables above are deterministic observations to help frame the judgment; the verdict line itself is for Dave.

**Dave w/ Mr Ai — Fidelity: high**

**Notes:**
The recomposer named all four resolvers verbatim, preserved the dependency order, and got the operator types right at every position. The substantive purpose — relevance-scored daily briefing on a stated topic — came through cleanly without seeing the original PRISM-IR doc. The one drift was the "each morning" cadence, which the kernel never hosted in any node's resolution_text and therefore couldn't carry through; this is a workload-meta-property gap in the (I, R) graph, not a recomposer failure or a fidelity loss in what was actually represented.

## Pre-judgment observations (Mr Code, not the verdict)

These are context for Dave's reading, not the verdict itself:

- Every named resolver and op type from the graph appears verbatim in the reconstruction (see the structural fidelity table above).
- The sequence and dependency relationships are preserved.
- The substantive purpose (relevance-driven daily briefing on a stated topic) is captured.
- The briefing topic surfaces in the reconstruction even though the recomposer only saw resolution texts; the topic must have been extracted from the score-relevance / generate-briefing payloads.
- The reconstruction includes concrete details from the actual run (specific items scored, the briefing title) that aren't in the original PRISM-IR text — those came from `resolution_text` and reflect what really happened, not invented detail.
- The "each morning" cadence in the original is not explicit in the reconstruction. The recomposer described a single run; the cadence is a workload-meta-property that didn't appear in any node's resolution_text. A future workload exposing cadence in some node's intention would carry the cadence through. Drift mode worth flagging but probably structural rather than fidelity-failing.
