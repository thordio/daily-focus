"""Tests for GitHub Actions workflow configuration files.

Ensures workflow YAML files are valid and free of dead code.

Note: PyYAML (YAML 1.1) parses the ``on:`` key as boolean ``True``,
so we handle both ``"on"`` and ``True`` when looking up the trigger key.
"""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"

MORNING_YML = WORKFLOW_DIR / "daily-focus-morning.yml"
EVENING_YML = WORKFLOW_DIR / "daily-focus-evening.yml"


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


# --- No dead cp commands ---


def test_morning_workflow_no_dead_cp():
    """Morning workflow has no ``cp data/config`` dead-code steps."""
    raw = _read_workflow(MORNING_YML)
    steps_run = _steps_text(raw)
    assert "cp data/config" not in steps_run, (
        "Found dead 'cp data/config' command in morning workflow. "
        "This was removed in the fix — if it reappears, the capper "
        "config-copy pattern has been re-introduced."
    )


def test_evening_workflow_no_dead_cp():
    """Evening workflow has no ``cp data/config`` dead-code steps."""
    raw = _read_workflow(EVENING_YML)
    steps_run = _steps_text(raw)
    assert "cp data/config" not in steps_run, (
        "Found dead 'cp data/config' command in evening workflow. "
        "This was removed in the fix — if it reappears, the capper "
        "config-copy pattern has been re-introduced."
    )


# --- Valid YAML ---


def _check_workflow_valid_yaml(path: Path):
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


def test_morning_workflow_valid_yaml():
    """Morning workflow is valid YAML with expected top-level keys."""
    _check_workflow_valid_yaml(MORNING_YML)


def test_evening_workflow_valid_yaml():
    """Evening workflow is valid YAML with expected top-level keys."""
    _check_workflow_valid_yaml(EVENING_YML)


# --- Step sanity checks ---


def test_morning_workflow_has_deploy_step():
    """Morning workflow includes the GitHub Pages deploy step."""
    doc = _parse_workflow(MORNING_YML)
    steps = doc["jobs"]["generate"]["steps"]
    step_names = [s.get("name", "") for s in steps if isinstance(s, dict)]
    assert "Deploy to GitHub Pages" in step_names, (
        "Morning workflow must have a 'Deploy to GitHub Pages' step"
    )


def test_evening_workflow_has_deploy_step():
    """Evening workflow includes the GitHub Pages deploy step."""
    doc = _parse_workflow(EVENING_YML)
    steps = doc["jobs"]["generate"]["steps"]
    step_names = [s.get("name", "") for s in steps if isinstance(s, dict)]
    assert "Deploy to GitHub Pages" in step_names, (
        "Evening workflow must have a 'Deploy to GitHub Pages' step"
    )


def test_morning_workflow_correct_period():
    """Morning workflow runs with ``--period morning``."""
    raw = _read_workflow(MORNING_YML)
    assert "--period morning" in raw, (
        "Morning workflow must pass '--period morning' to the horizon command"
    )


def test_evening_workflow_correct_period():
    """Evening workflow runs with ``--period evening``."""
    raw = _read_workflow(EVENING_YML)
    assert "--period evening" in raw, (
        "Evening workflow must pass '--period evening' to the horizon command"
    )
