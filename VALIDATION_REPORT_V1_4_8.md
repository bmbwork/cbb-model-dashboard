# Validation Report — v1.4.8

Validation performed before patch packaging:

- Current GitHub `main` was verified as website v1.4.7 and the exact sportsbook Admin block/import/version markers targeted by the transformer were confirmed against the live raw `app.py`.
- Python source compilation under the available build runtime: passed.
- Python 3.12 grammar compatibility (`ast.parse(..., feature_version=(3, 12))`): passed for patch Python sources and the transformed app fixture.
- Owls unified-response adapter tests: **8 passed**.
- Unified NCAAB odds request path, Bearer auth, and query controls: passed.
- Multi-book event coalescing, including cross-book home/away designation reversal: passed.
- DraftKings reference line + deterministic named-book fallback: passed.
- Broad/sharp/retail spread diagnostics: passed.
- Explicit `decision` role persistence through market-record serialization: passed.
- Betting split fields remain blank in odds rows: passed.
- Board home/away translation for a reversed provider designation: passed.
- Patch transformation fixture against the exact v1.4.7 Admin markers: passed.
- Static removal checks for active Odds API imports, secrets, provider references, URL, and UI copy: passed.
- Installer shell syntax validation: passed.
- Full disposable-Git installer exercise: **passed** (`git pull` → transform → compile → Python 3.12 grammar gate → pytest → commit → push).
- Disposable installer suite: **10 passed**; pushed remote HEAD matched local HEAD.
- Installer removes validation-generated `__pycache__`/bytecode before staging; verified no cache artifacts were committed.
- Patch archive integrity: verified after build.

The build container does not contain a native Python 3.12 interpreter, so the local unit/E2E runs used the available Python 3.13.5 runtime plus an explicit Python 3.12 grammar gate. The installer prefers an exact Python 3.12 interpreter, then falls back to an available project/system Python 3.12+ runtime. It always runs compilation plus the Python 3.12 grammar-compatibility gate. When the selected local runtime contains the repository test dependencies, it also runs the full repository pytest suite before committing and pushing. Any pre-push validation/push failure restores the repository to its pre-patch commit.
