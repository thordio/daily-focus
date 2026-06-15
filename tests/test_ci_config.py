"""Tests for GitHub Actions workflow configuration files.

Ensures the consolidated workflow YAML file is valid and free of dead code.

The system has been consolidated from two editions (morning + evening) to a
single daily edition.  Only ``daily-focus-morning.yml`` remains (the evening
workflow was removed).
"""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"

WORKFLOW_YML = WORKFLOW_DIR / "daily-focus-morning.yml"

# Expected cron for the single daily edition: UTC 05:43 = Beijing 13:43
EXPECTED_CRON = "43 5 * * *"


def _read_workflow(path: Path) -> str:
    """Read a workflow YAML file, raising a clear error if missing."""
    assert path.exists(), f"Workflow file not found: {path}"
    return path.read_text(encoding="utf-8")


def _parse_workflow(path: Path) -> dict:
    """Parse a workflow YAML file, returning the dict."""
    raw = _read_workflow(path)
    return yaml.safe_load(raw)


def _get_on_data(doc: dict) -> dict:
    """Get the ``on:`` trigger data, handling PyYAML's ``on`` → ``True`` quirk."""
    return doc.get("on") or doc.get(True) or {}


def _steps_text(raw: str) -> str:
    """Return the text of all ``run:`` steps joined together for dead-code checks."""
    doc = yaml.safe_load(raw)
    steps = doc.get("jobs", {}).get("generate", {}).get("steps", [])
    return "\n".join(s.get("run", "") for s in steps if isinstance(s, dict))


# --- File existence ---


def test_workflow_file_exists() -> None:
    """The consolidated workflow file exists."""
    assert WORKFLOW_YML.exists()


def test_evening_workflow_removed() -> None:
    """Evening workflow file has been removed (consolidated to single edition)."""
    evening_yml = WORKFLOW_DIR / "daily-focus-evening.yml"
    assert not evening_yml.exists(), (
        "Evening workflow should have been removed during "
        "consolidation to a single daily edition."
    )


# --- No dead cp commands ---


def test_workflow_no_dead_cp() -> None:
    """Workflow has no ``cp data/config`` dead-code steps."""
    raw = _read_workflow(WORKFLOW_YML)
    steps_run = _steps_text(raw)
    assert "cp data/config" not in steps_run, (
        "Found dead 'cp data/config' command in workflow. "
        "This was removed in the fix — if it reappears, the capper "
        "config-copy pattern has been re-introduced."
    )


def test_workflow_no_period_flag() -> None:
    """Single-edition workflow no longer passes ``--period`` flag."""
    raw = _read_workflow(WORKFLOW_YML)
    assert "--period" not in raw, (
        "The consolidated workflow should not pass --period flag, "
        "as there is only a single daily edition."
    )


# --- Valid YAML ---


def _check_workflow_valid_yaml(path: Path) -> None:
    """Validate that a workflow file is structurally sound YAML."""
    raw = _read_workflow(path)
    assert yaml.safe_load(raw) is not None, f"Failed to parse YAML: {path}"

    doc = _parse_workflow(path)
    assert isinstance(doc, dict), "Workflow must be a YAML mapping"
    assert "name" in doc, "Workflow must have a 'name' key"

    # PyYAML YAML 1.1 quirk: 'on:' key is parsed as boolean True.
    # Accept both string 'on' and boolean True.
    has_on_key = "on" in doc or True in doc
    assert has_on_key, "Workflow must have an 'on' (trigger) key"

    on_data = _get_on_data(doc)
    assert isinstance(on_data, dict), "'on' must be a mapping"

    assert "jobs" in doc, "Workflow must have a 'jobs' key"

    # Check job structure
    jobs = doc["jobs"]
    assert "generate" in jobs, "Must have a 'generate' job"
    gen = jobs["generate"]
    assert "runs-on" in gen, "Job must specify 'runs-on'"
    assert "steps" in gen, "Job must have 'steps'"
    assert isinstance(gen["steps"], list), "Steps must be a list"
    assert len(gen["steps"]) > 0, "Job must have at least one step"


def test_workflow_valid_yaml() -> None:
    """Workflow is valid YAML with expected top-level keys."""
    _check_workflow_valid_yaml(WORKFLOW_YML)


# --- Cron schedule ---


def test_workflow_cron_schedule() -> None:
    """Workflow has the expected cron schedule."""
    doc = _parse_workflow(WORKFLOW_YML)
    on_data = _get_on_data(doc)
    schedule = on_data.get("schedule", [])
    assert len(schedule) > 0, "Workflow must have a schedule"
    cron = schedule[0].get("cron", "")
    assert cron == EXPECTED_CRON, (
        f"Expected cron '{EXPECTED_CRON}' (UTC 05:43 = Beijing 13:43), "
        f"got '{cron}'"
    )
    # Verify we only have one cron entry (single daily edition)
    assert len(schedule) == 1, (
        f"Expected exactly 1 cron schedule for single daily edition, "
        f"got {len(schedule)}"
    )


# --- Step sanity checks ---


def test_workflow_has_deploy_step() -> None:
    """Workflow includes the GitHub Pages deploy step."""
    doc = _parse_workflow(WORKFLOW_YML)
    steps = doc["jobs"]["generate"]["steps"]
    step_names = [s.get("name", "") for s in steps if isinstance(s, dict)]
    assert "Deploy to GitHub Pages" in step_names, (
        "Workflow must have a 'Deploy to GitHub Pages' step"
    )


def test_workflow_uses_hours_24() -> None:
    """Workflow runs with ``--hours 24`` (single daily edition covers full day)."""
    raw = _read_workflow(WORKFLOW_YML)
    assert "--hours 24" in raw, (
        "Single-edition workflow must pass '--hours 24' "
        "to cover the full 24-hour window"
    )


def test_workflow_has_uv_setup_step() -> None:
    """Workflow includes the uv installation step."""
    doc = _parse_workflow(WORKFLOW_YML)
    steps = doc["jobs"]["generate"]["steps"]
    step_names = [s.get("name", "") for s in steps if isinstance(s, dict)]
    assert "Install uv" in step_names or "install uv" in " ".join(step_names).lower(), (
        "Workflow must have an 'Install uv' step"
    )


def test_workflow_deepseek_api_key_env() -> None:
    """Workflow sets DEEPSEEK_API_KEY environment variable."""
    raw = _read_workflow(WORKFLOW_YML)
    assert "DEEPSEEK_API_KEY" in raw, (
        "Workflow must use DEEPSEEK_API_KEY secret"
    )


def test_workflow_no_evening_references() -> None:
    """Workflow contains no references to 'evening' edition."""
    raw = _read_workflow(WORKFLOW_YML)
    assert "evening" not in raw.lower(), (
        "Consolidated workflow should not reference the evening edition"
    )
