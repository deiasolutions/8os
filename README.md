# 8OS

The kernel of an intention-driven runtime. Every decision is an (Intention, Resolution) pair; 8OS hosts the (I, R) graph and runs programs written in [PRISM-IR](https://github.com/deiasolutions/prism-ir).

## Status

- Kernel spec **v0.2** — nine axioms (axiom 0 + 1–8); axiom 8 (Reflexivity) ratified in Block 5.0 (2026-05-03).
- Active representation spec: **Block-1 v1.2** — seventeen-operation SDK contract.
- Binary: **`v1.2.0`**. Tier A complete; tier B sequenced; surrogate work on its own track (see overview §14 for the order).
- Tests: 444 passing + 2 skipped (editable-install first — see Install).

## Documents

| Document | Purpose |
|---|---|
| [`docs/8OS-OVERVIEW-v3.md`](docs/8OS-OVERVIEW-v3.md) | Canonical overview. Start here. |
| [`docs/8OS-AXIOMS-PLAIN-LANGUAGE.md`](docs/8OS-AXIOMS-PLAIN-LANGUAGE.md) | Plain-English register and glossary. The vocabulary doorway. |
| [`docs/spec/8OS-KERNEL-SPEC-v0.2.md`](docs/spec/8OS-KERNEL-SPEC-v0.2.md) | Active nine-axiom kernel spec (axiom 0 + 1–8). v0.1 preserved for lineage. |
| [`docs/spec/8OS-BLOCK-1-SPEC-v1_2.md`](docs/spec/8OS-BLOCK-1-SPEC-v1_2.md) | Active on-disk representation and SDK contract. v1.1 preserved for lineage. |
| [`docs/spec/PRISM-IR-SPEC-v1.1.md`](docs/spec/PRISM-IR-SPEC-v1.1.md) | The projection language spec. Canonical home is at [`deiasolutions/prism-ir`](https://github.com/deiasolutions/prism-ir); co-resident here for build reference. |
| [`docs/spec/8OS-SDK-REFERENCE-v1.md`](docs/spec/8OS-SDK-REFERENCE-v1.md) | Index of the SDK operations and which canonical spec defines each. |

Earlier representation specs and patch files are preserved on disk for lineage; v1.2 is the active text.

## Demos

The empirical witness for the substrate's load-bearing claim — that the (I, R) primitive carries across paradigms. Three structurally distinct uses of the same kernel:

- **[`lsystem-demo`](https://github.com/deiasolutions/lsystem-demo)** — deterministic decomposer + browser-driven outside-call adapter. Renders Lindenmayer fractals end-to-end.
- **[SCAN dogfood](docs/demos/scan.md)** — LLM-mediated decomposer + real HTTP fetches. Produces a daily-briefing artifact. ~$0.04 per run.
- **[`decomposition-strategy-demo`](https://github.com/deiasolutions/decomposition-strategy-demo)** — programs producing programs at runtime, hosted by the same substrate. Self-composition.

Three different decomposers (deterministic / LLM / program-authored). Three different outside-call profiles. One kernel, one primitive.

## Install

Requires Python 3.13+ and [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/deiasolutions/8os.git
cd 8os
uv venv
uv pip install -e .
```

Run the test suite:

```bash
uv run pytest
```

## Contributing

8OS development proceeds in numbered blocks (`Block N.M`) against the v1.1 spec. Open questions and gaps are logged in [`docs/open-questions.md`](docs/open-questions.md).

For changes of any size: surface design before implementation. Locked decisions live in the spec, not in code. The (I, R) discipline applies to the project itself — every change is a resolution to an intention, and the intention should be authored before the resolution.

## Author

Q88N — [GitHub @daaaave-atx](https://github.com/daaaave-atx) · [LinkedIn](https://www.linkedin.com/in/daaaave-atx)

## License

Apache 2.0. See [`LICENSE`](LICENSE).
