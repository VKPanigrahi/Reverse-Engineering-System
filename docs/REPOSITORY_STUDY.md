# Repository study and implementation decisions

This study inspected the supplied GitHub topic page and selected source files from five projects. It is a source-level architectural comparison, not a claim to have executed or verified every upstream feature. No upstream code or dependencies were incorporated into this project.

## Sources inspected

| Repository / inspected revision | Files read | Finding and consequence |
| --- | --- | --- |
| [wtsxdev/reverse-engineering](https://github.com/wtsxdev/reverse-engineering/tree/b25498551c6d7110685896078afeb27097aa1e24) | Entire `README.md`, `package.json` | A curated tool/resource catalog. Its test script formats Markdown; it does not implement an agent or app reproduction engine. Use it to classify research methods rather than as an application framework. |
| [AIshihzong/awesome-reverse-engineer-anything](https://github.com/AIshihzong/awesome-reverse-engineer-anything/tree/641331f4bdbe1a6cd7199d5d0215397bc6ae246d) | README sections covering official resources, showcases, app cases, evaluations; `docs/is-it-rea.md` excerpts | Distinguishes documented tool usage from unconfirmed claims and emphasizes measured comparisons. Our UI labels static evidence, documentation claims, candidates, gaps, and unverified proposals explicitly. Its benchmark summaries were not independently reproduced. |
| [sickpyramid/ReaFuse](https://github.com/sickpyramid/ReaFuse/tree/c64502a2827832c042d894ba90dc678a95772cb1) | `src/pipeline.mjs`, `profile.mjs`, `verify.mjs`, `schemas.mjs`, `brain.mjs` provider/cache sections, acquisition excerpts, `package.json` | A concrete staged pipeline: intake, static profiling, specification cards, fusion, contract creation, generation, verification, bounded repair. Profiles never execute donor code. Contracts and generated tests are separate. We implemented checkpointed intake, bounded profiling, evidence-linked requirements, structured architecture proposals, and export. Generation and repair are deliberately still unimplemented. |
| [glauberlima/open-scrantic](https://github.com/glauberlima/open-scrantic/tree/274ad3e8bfd3fbc054fd0b32f78f08420f326dcf) | `docs/ARCHITECTURE.md` layering/startup/time sections, `examples/snapshot.rs`, README excerpts, `Cargo.toml` | A specialized Rust reconstruction, not a general app generator. Its separation of assets, deterministic engine, and presentation makes headless tests possible. Evidence cites original locations. We separated acquisition, analysis, synthesis, and transport so analysis can be tested with fixed fixtures. Original assets and matching toolchains would be needed to validate this upstream implementation. |
| [morluto/rea](https://github.com/morluto/rea/tree/8188497f13477918f2b696689c3598b65f11a7c5) | `src/application/investigation/EvidenceLedger.ts` admission/import sections, `src/domain/evidenceReference.ts`, `evidenceCompletionLedger.ts` schemas and summary | Evidence identities, explicit unknowns, schema validation, and separate completion outcomes are core primitives. We created stable commit/file/line evidence IDs and validate proposal citations against retained records. We have not integrated REA's native/binary tools or implemented its authenticated evidence format. |

## Implemented architecture

- `engine/repositories.py`: validated GitHub identities; exact HEAD resolution; commit-addressed archive acquisition; no extraction or code execution; bounded file selection; Python AST and heuristic JS/TS/Rust declarations/imports; manifests, dependencies, test declarations, license declarations, and file/line evidence.
- `engine/investigation.py`: checkpoint each repository, retain failures alongside successes, retry failed references, reuse successful pinned profiles, explicit refresh to fetch current HEAD.
- `engine/synthesis.py`: lexical requirement-to-evidence matching; statuses never imply runtime verification; draft acceptance criteria; structured prompt handoff and optional local Ollama inference; proposal coverage/citation validation.
- `server.py`: persistence, serialized mutations, research/design endpoints, ZIP exports.
- `web/app.js`: multi-reference intake, module/dependency inspection, evidence matrix, local-model and prompt-handoff controls, proposal review.

## What this does not establish

A matching symbol is a lead, not proof that the requested behavior exists. README headings are claims. Test names prove test declarations were found, not that the tests ran or passed. A validated model response has a valid structure and known citations; it can still reason incorrectly. License labels are declarations, not a legal compatibility assessment. Sampling and heuristic parsing can miss relevant code. The tool does not currently crawl website interactions, reconstruct unavailable backends, generate applications, or execute generated acceptance contracts.

The next meaningful implementation is to replace draft contracts with reviewed concrete input/output cases and add isolated implementation/verification stages. Measure completed requirements against those contracts, not against a claimed universal reproduction percentage.
