---
authored_by: prism-ir-decomposer
authored_on: '2026-04-28T02:12:12.311Z'
authored_via: anthropic
authority_level: convention
collapsed_summary: Select the top-N items by relevance score, breaking ties by source priority, and return the ranked list.
depends_on:
- scan-score-relevance
expanded_into: null
id: scan-filter-and-rank
kind: ir-node
parent: scan-daily-briefing
projection_types: []
resolution_event: 01KQ8XQY5GD1GN7Q85JRF3NZGQ
resolved_at: '2026-04-28T02:12:27.440Z'
resolver: filter-and-rank
revalidate_trigger: null
scope: dogfood-scan
status: resolved
superseded_by: null
supersedes: null
surrogate_of: null
tier: 1
valid_through: null
visible_to:
- dogfood-scan
---

# Intention

Select the top-N items by relevance score, breaking ties by source priority, and return the ranked list.

```yaml
prism_operator:
  op: script
  resolver: filter-and-rank
  model: null
```

# Resolution

{"items": [{"title": "Microsoft and OpenAI end their exclusive and revenue-sharing deal", "url": "https://www.bloomberg.com/news/articles/2026-04-27/microsoft-to-stop-sharing-revenue-with-main-ai-partner-openai", "abstract": "", "source": "hackernews", "source_priority": 1, "id": "hn-47921248", "score": 0.85, "reason": "Major AI infrastructure governance issue: Microsoft and OpenAI ending exclusive revenue-sharing deal directly impacts AI industry structure."}, {"title": "How Supply Chain Dependencies Complicate Bias Measurement and Accountability Attribution in AI Hiring Applications", "url": "https://arxiv.org/abs/2604.22679v1", "abstract": "The increasing adoption of AI systems in hiring has raised concerns about algorithmic bias and accountability, prompting regulatory responses including the EU AI Act, NYC Local Law 144, and Colorado's AI Act. While existing research examines bias through technical or regulatory lenses, both perspectives overlook a fundamental challenge: modern AI hiring systems operate within complex supply chains where responsibility fragments across data vendors, model developers, platform providers, and deploying organizations. This paper investigates how these dependency chains complicate bias evaluation and accountability attribution. Drawing on literature review and regulatory analysis, we demonstrate that fragmented responsibilities create two critical problems. First, bias emerges from component interactions rather than isolated elements, yet proprietary configurations prevent integrated evaluation. A resume parser may function without bias independently but contribute to discrimination when integrated with specific ranking algorithms and filtering thresholds. Second, information asymmetries mean deploying organizations bear legal responsibility without technical visibility into vendor-supplied algorithms, while vendors control implementations without meaningful disclosure requirements. Each stakeholder may believe they are compliant; nevertheless, the integrated system may produce biased outcomes. Analysis of implementation ambiguities reveals these challenges in practice. We propose", "source": "arxiv", "source_priority": 2, "id": "arxiv-2604.22679v1", "score": 0.8, "reason": "Supply chain dependencies in AI hiring bias directly address governance, accountability attribution, and regulatory compliance challenges."}, {"title": "4TB of voice samples just stolen from 40k AI contractors at Mercor", "url": "https://app.oravys.com/blog/mercor-breach-2026", "abstract": "", "source": "hackernews", "source_priority": 1, "id": "hn-47919630", "score": 0.75, "reason": "Data breach of voice samples from AI contractors raises critical AI infrastructure security and governance concerns."}, {"title": "Agentic World Modeling: Foundations, Capabilities, Laws, and Beyond", "url": "https://arxiv.org/abs/2604.22748v1", "abstract": "As AI systems move from generating text to accomplishing goals through sustained interaction, the ability to model environment dynamics becomes a central bottleneck. Agents that manipulate objects, navigate software, coordinate with others, or design experiments require predictive environment models, yet the term world model carries different meanings across research communities. We introduce a \"levels x laws\" taxonomy organized along two axes. The first defines three capability levels: L1 Predictor, which learns one-step local transition operators; L2 Simulator, which composes them into multi-step, action-conditioned rollouts that respect domain laws; and L3 Evolver, which autonomously revises its own model when predictions fail against new evidence. The second identifies four governing-law regimes: physical, digital, social, and scientific. These regimes determine what constraints a world model must satisfy and where it is most likely to fail. Using this framework, we synthesize over 400 works and summarize more than 100 representative systems spanning model-based reinforcement learning, video generation, web and GUI agents, multi-agent social simulation, and AI-driven scientific discovery. We analyze methods, failure modes, and evaluation practices across level-regime pairs, propose decision-centric evaluation principles and a minimal reproducible evaluation package, and outline architectural guidance, open problems, and governance challenges. The resulting roadmap connect", "source": "arxiv", "source_priority": 2, "id": "arxiv-2604.22748v1", "score": 0.75, "reason": "Comprehensive framework for agentic world modeling governance, architectural guidance, and AI system evaluation principles directly address infrastructure and governance."}, {"title": "Spend Less, Fit Better: Budget-Efficient Scaling Law Fitting via Active Experiment Selection", "url": "https://arxiv.org/abs/2604.22753v1", "abstract": "Scaling laws are used to plan multi-million-dollar training runs, but fitting those laws can itself cost millions. In modern large-scale workflows, assembling a sufficiently informative set of pilot experiments is already a major budget-allocation problem rather than a routine preprocessing step. We formulate scaling-law fitting as budget-aware sequential experimental design: given a finite pool of runnable experiments with heterogeneous costs, choose which runs to execute so as to maximize extrapolation accuracy in a high-cost target region. We then propose an uncertainty-aware method for sequentially allocating experimental budget toward the runs most useful for target-region extrapolation. Across a diverse benchmark of scaling-law tasks, our method consistently outperforms classical design-based baselines, and often approaches the performance of fitting on the full experimental set while using only about 10% of the total training budget. Our code is available at https://github.com/PlanarG/active-sl.", "source": "arxiv", "source_priority": 2, "id": "arxiv-2604.22753v1", "score": 0.6, "reason": "Scaling law fitting optimization addresses efficient AI training resource allocation, relevant to infrastructure optimization."}], "total_input_count": 20, "top_n": 5}
