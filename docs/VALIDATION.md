# Validation results

- `python3 -m unittest discover -s tests -v`: 18 tests passed. Includes actual loopback HTTP tests for project creation, investigation, persistence, proposal validation, retained state after rejected citations, and ZIP export. Remote repositories and local-model transport are mocked in the automated suite.
- `node --check web/app.js`: passed.
- Live GitHub acquisition and synthesis: completed against `wtsxdev/reverse-engineering`, `sickpyramid/ReaFuse`, and `glauberlima/open-scrantic`, with no acquisition errors. Analyzed 115 selected files and collected 903 evidence records. Exact commits, budgets, phase events, and the requirement matrix are retained in `validation-sample.json`.
- Headless system Chromium + Playwright: created a project through the UI, submitted the wtsxdev repository, waited for completed investigation and the evidence matrix, and checked for browser JavaScript errors. Passed.
- No real local-model inference, upstream repository tests, generated-application execution, or production deployment was performed.

The app's deterministic candidate matching and schema-valid proposal acceptance do not establish behavioral correctness. Candidate coverage is distinct from verified-feature coverage, which remains zero until functional contracts execute.
