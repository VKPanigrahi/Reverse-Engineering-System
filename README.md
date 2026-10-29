# Reframe — Reverse Engineering Workspace

A local-first starting point for understanding reference products and planning personalized alternatives. Python 3.12+; no third-party dependencies or paid API keys.

## Run

```sh
cd /workspace/Reverse-Engineering-System
python3 server.py
```

Open `http://127.0.0.1:8000` in a browser when running locally. The server binds to loopback only. `PORT` changes the port; `RES_DATA_DIR` changes the SQLite storage directory (default `.data/`). Stop with Ctrl+C. Projects survive restarts; back up `.data/projects.db` when the server is stopped.

## First workflow

1. Create a project with its goal, optional reference URL, and one requested feature per line.
2. Inspect the reference to capture its HTML title, description, and visible headings.
3. Generate a specification with requested features, acceptance guidance, assumptions, questions, and implementation milestones.
4. Export a ZIP containing JSON research records and a Markdown specification.

The UI identifies observed evidence separately from user requirements and assumptions. Baseline feature planning is deterministic. Optional architecture reasoning is described below. The export is a planning artifact, not a generated application.

## Validate

```sh
python3 -m unittest discover -s tests -v
node --check web/app.js
```

Tests use isolated temporary storage and an actual HTTP server for project creation, research persistence, planning, exports, validation, and static routes. Remote inspection is mocked in the integration test; parser and URL restrictions have separate tests.

## Current scope and limitations

This is the research/specification foundation, not a system capable of reproducing arbitrary applications. It fetches static public HTML only; it does not execute JavaScript, log in, discover backend code, or verify feature behavior. Fetches have a timeout, size limit, redirect validation, and private-address checks. DNS preflight checks are not a complete defense against DNS rebinding; keep this single-user tool local and use network-level egress isolation before exposing it or using untrusted references. Existing HTTP proxy and TLS trust settings are respected.

No authentication or multi-user isolation is provided. Do not expose the server publicly. Reference content is displayed as escaped text, never executed as instructions. External platforms can deny automated access; use supported APIs and authorized content access for integrations.

## Next implementation milestones

- Browser-based evidence capture and workflow recording in an isolated research environment.
- Broader model support, model budget controls, and explicit specification approval checkpoints.
- Editable/approved specifications and executable domain-specific acceptance tests.
- Sandboxed code generation, execution, repair loops, and downloadable application artifacts.
- Deployment validation and cost reporting.

A useful target is coverage of an agreed feature specification, measured by functional tests, rather than a universal percentage of a reference platform.

## Multi-repository investigation

Open any project and use **Investigate reference repositories** with one to four public GitHub URLs. Git must be installed and HTTPS access to `github.com` and `codeload.github.com` must work through your configured proxy. No GitHub token is required for public repositories in the managed environment.

The pipeline resolves exact commits, inspects bounded archives without extracting or executing donor code, and records manifests, declarations, imports, test declarations, and documentation headings. The evidence matrix connects requested requirements to source candidates, documentation leads, or gaps. Successful profiles are checkpointed and reused on retry; select **Fetch latest commits** to refresh them. Operations are serialized; a second mutation receives HTTP 409 while investigation is running.

For architecture reasoning, expand **Prompt handoff**, send that prompt to your chosen assistant, and paste its JSON response. The server rejects unknown citations, duplicate/missing requirements, and malformed proposals. Alternatively run Ollama locally with an already-installed model and start this app with `RES_OLLAMA_MODEL=<model-name> python3 server.py`; **Ask local model** calls only `127.0.0.1:11434`. The adapter is covered by mocked transport tests, but inference with a real local model has not been validated in this environment. Handoff responses are labeled user-supplied; the app does not verify which assistant produced them.

ZIP exports now include the full investigation, requirement matrix, model prompt, and any validated proposal under `research/`. [Source study](docs/REPOSITORY_STUDY.md) records which upstream files informed the implementation.

Limits: 20 MB downloaded archive, 40 MB declared expanded file content, 20,000 archive entries, 800 analyzed files, 150 KB per file, 3 MB selected text per repository. Dotfiles, symlinks, and common dependency/build directories are excluded. Do not provide repositories containing sensitive source: selected declarations and documentation appear in exports and prompts. No external model receives them automatically. GitHub archives may include other large assets and be rejected; submodules and Git LFS objects are not fetched.
