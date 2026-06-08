# Daily Focus — Coding Guidelines & Requirements

## Coding Principles (highest to lowest priority)

### 1. Correctness & Completeness
Every code change must be correct and complete. Syntax must be error-free. Algorithm logic must be correct and thoroughly considered. Correctness and completeness are the highest priority.

### 2. Performance
Even as a static-site generator, performance matters — low algorithmic complexity AND low constant factors. Do not sacrifice performance for convenience.

### 3. Readability & Conciseness
Code must be clear and concise. Achieve the requirement with the smallest, simplest, cleanest change possible. This is NOT about laziness — avoid over-engineering, redundant code, premature abstractions, and unnecessary indirection.

### 4. Maintainability & Extensibility
The project will evolve. Avoid hardcoded constants and rigid logic. Design for extension and maintenance from the start.

## Thinking & Process Requirements

### Return to Fundamentals
When encountering a bug or behavior that does not match requirements, analyze the root cause — do not settle for surface-level patches. Ask whether a perfect solution exists. Never fall into the trap of treating symptoms rather than root causes.

### Embrace Difficulty
You have a sufficient token budget. Do not shy away from difficulty. Do not reach for simpler cover-up fallbacks after initial failure. Research deeply, learn from failure, and evolve with failure. Failure is acceptable — shallow workarounds are not.

### Debugging: Two-Part Output
When debugging, the output must be clear and cover exactly two aspects:
1. **What is the root cause?**
2. **What is the solution?**

Be clear and easy to understand. If the root cause you identified does not fully explain the observed phenomenon, the cause is wrong.

## Project Essentials

### Tech Stack
- **Language**: Python 3.14
- **Base**: [Horizon](https://github.com/Thysrael/Horizon) (MIT License, Python full-stack news pipeline)
- **Package manager**: `uv` (uv sync, uv run)
- **AI provider**: DeepSeek V4-Pro via OpenAI-compatible API (`https://api.deepseek.com`)
- **Testing**: pytest via `uv run pytest`

### Architecture
- `src/orchestrator.py` — main pipeline (fetch, dedup, score, filter, enrich, summarize, render)
- `src/ai/` — AI scoring (`analyzer.py`), enrichment (`enricher.py`), summarization (`summarizer.py`), prompts (`prompts.py`)
- `src/scrapers/` — data source scrapers (rss, hackernews, reddit, github, twitter, openbb, ossinsight, telegram)
- `src/models.py` — Pydantic v2 models (`Config`, `ContentItem`, `AIConfig`, etc.)
- `data/config-*.json` — edition-specific config files validated via `Config.model_validate()`

### Key Invariants
- All data flows through `ContentItem` — each pipeline step reads and writes fields on this model
- Config is validated by Pydantic at startup — malformed JSON is caught early
- AI calls use OpenAI-compatible protocol with configurable provider/model
- RSS image extraction writes to `metadata["candidate_images"]`, AI selection writes to `metadata["selected_images"]`
- Two editions: morning (time_window=14h, threshold=4.0) and evening (time_window=10h, threshold=4.0)
- GitHub Actions cron triggers: UTC 00:00 (morning) and UTC 12:00 (evening)

### Information Authenticity (HIGHEST PRINCIPLE)

**ALL information delivered to the user MUST be authentic, verifiable, and traceable to real sources.** This is the fundamental value proposition of Daily Focus.

- **Zero tolerance for fabricated content**: No fake news, no hallucinated details, no made-up dates or statistics. If the pipeline cannot produce reliable content, it must clearly signal uncertainty.
- **Every claim must be traceable**: Each news item's `whats_new`, `why_it_matters`, `background` is grounded in either the original article content or web search results. The `references` field lists the actual URLs used.
- **Demo content must be clearly labeled**: Any mock/demo data must be explicitly marked as such (e.g., `[DEMO]` prefix, or a visible banner). Never present fabricated content as real.
- **Anti-hallucination architecture**: ContentEnricher performs web search for each high-scoring item → AI prompt explicitly instructs "do NOT fabricate information, base only on provided content and search results" → `sources` field records which URLs were used → template renders "参考来源" with clickable links.
- **Pipeline integrity**: The production pipeline (RSS scraping → AI scoring → semantic dedup → web search enrichment → source attribution) is the ONLY source of truth. Direct human-written content is acceptable only for project documentation — never for news delivery.

### Pre-Report Validation (MANDATORY before reporting completion)
Before claiming any code change is "done", run the full test suite. Fix ALL errors until exit code 0.

**Validation command**:
```bash
cd /Users/sentinel/Documents/code/daily-focus && uv run pytest tests/ -v
```

**Success criteria**: Exit code 0, all tests pass, no failures or errors.

**Workflow**: validate → fix errors → re-validate → repeat until clean → then report completion. Never report completion without a clean validation pass.

### Multi-Agent Quality System (MANDATORY before every milestone release)

Before any milestone is declared "complete" or any demo is presented to the CEO, ALL teams (RD + QA) must participate in a coordinated quality review. This is not optional — it is the fundamental quality mechanism.

**Team Structure**:
```
CEO (用户)
 └─ CTO/Main (当前会话) — top-level orchestration, decision-making, risk identification
     ├─ RD Team (2 Builders)
     │   ├─ Builder 1 (Infra) — pipeline, AI, scraping, CI/CD, config
     │   └─ Builder 2 (Website) — templates, CSS, PWA, renderer, UX
     └─ QA Team (2 Reviewers)
         ├─ QA 1 (Testing) — pytest, coverage, regression, bug finding
         └─ QA 2 (Code Review) — correctness, design, extensibility, anti-shit-mountain
```

**Milestone Release Checklist** (ALL must pass before presenting to CEO):
1. **All RD agents** have completed their assigned work areas
2. **QA 1** runs full test suite → all tests pass, no regressions
3. **QA 2** reviews all changes for correctness, design, extensibility → zero critical issues
4. **QA 1** validates the demo HTML for structural correctness (DOCTYPE, noindex, dark mode, score badges, references, PWA)
5. **QA 2** reviews the demo content for quality (authenticity, completeness, professional appearance)
6. **Builder 2** verifies responsive design at 375px / 768px / 1440px
7. **Builder 1** verifies system integrity (imports, configs, workflows, git status)
8. **CTO/Main** collects all reports, resolves conflicts, makes final go/no-go decision

**Demo Content Requirements**:
- If using mock data: EVERY item must be clearly labeled `[DEMO]`
- If using real data: EVERY claim must have a traceable reference URL
- Never mix: fabricated content with real-looking presentation is deception
- Preferred: run a real pipeline (`uv run horizon --hours 1`) to produce authentic output

#### Convergence Criteria
- All tests pass (`uv run pytest tests/ -v`, exit 0)
- Config files pass Pydantic validation (`Config.model_validate()`)
- All 4 QA dimensions pass (tests, HTML structure, content authenticity, design)
- No dead code, no duplicated magic strings/numbers without shared constants
- No remaining `load()` calls where `class_name` suffices
- Demo content is either clearly labeled mock OR backed by real sources

**If anything needs changing, change it, then restart the review from Step 1.**

## Access Control (IRON RULE)

### Access Control (IRON RULE)

Role-based write permissions. Violations are not permitted under any circumstance.

| Role | Write Access | Read-Only |
|------|-------------|-----------|
| **CTO (Main Agent)** | NONE — decision-making and coordination only | All files |
| **RD Team (Builders)** | `src/`, `data/`, `docs/`, `scripts/`, `.github/`, `pyproject.toml`, `CLAUDE.md` | `tests/` |
| **QA Team (Reviewers)** | `tests/` ONLY | All source files |

- CTO must NEVER edit source code, config, templates, or tests directly.
- RD must NEVER write or modify test files.
- QA must NEVER write or modify source code.
- Cross-boundary changes must be delegated to the appropriate team via Agent.

The CTO's role is to: read code to understand state, make architectural decisions, assign tasks to RD/QA agents, collect reports, and escalate to CEO when needed. Think of CTO as the manager who reviews code but never commits.

---

## Important Guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
