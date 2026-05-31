# Ethians v2.0 — Coding Guidelines & Requirements

## Coding Principles (highest to lowest priority)

### 1. Correctness & Completeness
Every code change must be correct and complete. Syntax must be error-free: Godot IDE may lock files, causing the Edit tool to fail — if falling back to python/sed for file edits, be extremely careful not to introduce parser errors. Algorithm logic must be correct and thoroughly considered. Correctness and completeness are the highest priority.

### 2. Performance
Even for a 2D game, performance requirements are strict. Always find the optimal approach — low algorithmic complexity AND low constant factors. Do not sacrifice performance for convenience.

### 3. Readability & Conciseness
Code must be clear and concise. Achieve the requirement with the smallest, simplest, cleanest change possible. This is NOT about laziness — avoid over-engineering, redundant code, premature abstractions, and unnecessary indirection.

### 4. Maintainability & Extensibility
Gameplay will evolve significantly. Avoid hardcoded constants and rigid logic. Design for extension and maintenance from the start, so the codebase does not become a "mountain of shit" over time.

## Thinking & Process Requirements

### Return to Fundamentals
When encountering a bug or behavior that does not match requirements, analyze the root cause — do not settle for surface-level patches. Ask whether a perfect solution exists. Never fall into the trap of treating symptoms rather than root causes.

### Embrace Difficulty
You have a sufficient token budget. The user often asks deep, challenging, and cutting-edge questions. Do not shy away from difficulty. Do not reach for simpler cover-up fallbacks after initial failure. Research deeply, learn from failure, and evolve with failure. Failure is acceptable — shallow workarounds are not.

### Debugging: Two-Part Output
When debugging, the output must be clear and cover exactly two aspects:
1. **What is the root cause?**
2. **What is the solution?**

Be clear and easy to understand. If the root cause you identified does not fully explain the observed phenomenon, the cause is wrong. Remind yourself of this on every debugging task.

## Project Essentials

- **Engine**: Godot 4.5, GL Compatibility renderer
- **Architecture**: Entity-Component-Action, data-driven via `.tres` resources
- **Autoloads**: `SignalBus` (signals), `Fonts` (font resources)
- **Full architecture reference**: `/godot-project-reference` skill (load on demand when implementing or modifying game features)

### Key Invariants
- Components are child Nodes (not Resources) — they get `_ready()`, `_process()`, tree access
- Item stacking: by item name in inventory, by key on ground
- AI state machine: `entity.ai_component = new_component` swaps behavior at runtime
- Async input: `await menu.item_selected` / `await reticle.position_selected` uses DUMMY input handler state
- `FighterComponent.die()` checks `is_inside_tree()` to avoid emitting messages during map cleanup
- `call_deferred()` required for state transitions after async operations to avoid re-entrancy
- Spatial hash `(x << 10) + y` — limits Y to 0-1023
- Entity queries (`get_blocking_entity_at_location`, `get_actor_at_location`) are O(n) — be mindful in hot paths
- `ConfusedEnemyAI._ready()` swaps `entity.ai_component` — relies on `_ready` firing before next `perform()`

### Pre-Report Validation (MANDATORY before reporting completion)
Before claiming any code change is "done" or "ready to test", run Godot headless validation. Fix ALL errors until exit code 0 with zero SCRIPT ERROR lines.

**Godot binary**: `/Users/sentinel/Downloads/Godot.app/Contents/MacOS/Godot`

**Validation command**:
```bash
/Users/sentinel/Downloads/Godot.app/Contents/MacOS/Godot --headless --path /Users/sentinel/Desktop/Ethians --quit 2>&1; echo "EXIT: $?"
```

**Success criteria**: Exit code 0, no `SCRIPT ERROR` or `Compile Error` lines in output.

**Workflow**: validate → fix errors → re-validate → repeat until clean → then report completion. Never report completion without a clean validation pass.

### Multi-Agent Code Review (MANDATORY before every commit)

Before any commit, run a two-stage multi-agent review. **Do not skip or shortcut either stage.** Each stage iterates to convergence: fix all findings, re-run the stage, repeat until zero actionable findings remain. If code changes during fixes, review restarts.

Budget is unlimited. Be objective — do not hesitate to modify code when issues are found.

#### Stage 1 — Correctness & Design Review (3 agents)
Launch 3 agents in parallel:
1. **Main agent** (the current conversation) — ongoing implementation work
2. **Discussion agent 1** — correctness: bugs, edge cases, null safety, state consistency, logic errors
3. **Discussion agent 2** — design: architecture, extensibility, pattern consistency, coupling, separation of concerns

These three agents form a "code supervisory committee." Their focus: correctness first, then design optimality. Iterate until all findings are resolved.

#### Stage 2 — Code Craft Review (2 agents)
Launch 2 agents in parallel, focused on engineering quality:
1. **Craft agent A** — readability, conciseness, redundancy, elegance, naming, comments
2. **Craft agent B** — system fit, extensibility, architectural coherence, consistency with codebase conventions

These agents ensure the code is clean, maintainable, and well-integrated. Iterate until all findings are resolved.

#### Convergence Criteria
- All agents report zero new actionable findings
- Headless validation passes (exit 0, no SCRIPT ERROR)
- No remaining `load()` calls where `class_name` suffices
- No duplicated magic strings/numbers without shared constants
- No dead code

**If anything needs changing, change it, then restart the review from Stage 1.**

---

# Important Guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

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