r"""
Fuzzy recall floor (FRIDAY_notes10_plan.md Phase 3, §5). Cluster C: "claude code"
vs a slug written as one word (`claudecodeupgrade`) — and the reverse, a merged
query against a separated slug. The keyword retriever's slug/title channel is now
separator-insensitive so a name still matches across spacing/underscores, while
the body min_score floor is untouched (an incidental single body hit is still
dropped — silence beats a weak guess).

Pure logic (no model): drive KeywordRetriever over planted notes.
"""

import pytest

from core.memory.keyword_retriever import KeywordRetriever


def _brain(tmp_path, notes: dict):
    """Write {rel_path: text} under a temp brain root and return it."""
    for rel, text in notes.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


def _paths(results):
    return [r.path for r in results]


@pytest.mark.upgrade
@pytest.mark.case("RECALL-001", "spaced query finds a merged-word slug "
                               "('claude code' -> claudecodeupgrade.md)")
def test_spaced_query_merged_slug(tmp_path):
    root = _brain(tmp_path, {
        "projects/claudecodeupgrade.md": "# Claudecodeupgrade\n\nUpgrade work.\n",
        "projects/unrelated.md": "# Unrelated\n\nSomething else entirely.\n",
    })
    r = KeywordRetriever(root)
    got = _paths(r.retrieve("claude code projects", top_k=4))
    assert "projects/claudecodeupgrade.md" in got, got


@pytest.mark.upgrade
@pytest.mark.case("RECALL-002", "merged-word query finds a SEPARATED slug "
                               "('claudecode' -> claude_code_upgrade.md) — the new direction")
def test_merged_query_separated_slug(tmp_path):
    root = _brain(tmp_path, {
        "projects/claude_code_upgrade.md": "# Claude Code Upgrade\n\nWork.\n",
        "projects/unrelated.md": "# Unrelated\n\nSomething else.\n",
    })
    r = KeywordRetriever(root)
    got = _paths(r.retrieve("claudecode", top_k=4))
    assert "projects/claude_code_upgrade.md" in got, got


@pytest.mark.upgrade
@pytest.mark.case("RECALL-003", "the min_score floor still drops an incidental "
                               "single BODY hit (no name match) — regression guard")
def test_body_floor_preserved(tmp_path):
    root = _brain(tmp_path, {
        "projects/widget_notes.md": "# Widget Notes\n\nWe mentioned a gadget once.\n",
    })
    r = KeywordRetriever(root)
    # 'gadget' appears once in the body and nowhere in the name/title -> below
    # the floor -> nothing returned (silence beats a weak guess).
    assert r.retrieve("gadget", top_k=4) == []


@pytest.mark.upgrade
@pytest.mark.case("RECALL-004", "the normalization covers the TITLE too, not just "
                               "the filename slug")
def test_title_normalized_match(tmp_path):
    root = _brain(tmp_path, {
        # Filename is terse; the real name lives in the title heading.
        "projects/os_rig.md": "# Orbit Sync Rig\n\n- **Status:** active\n\nBench.\n",
    })
    r = KeywordRetriever(root)
    got = _paths(r.retrieve("orbitsync", top_k=4))
    assert "projects/os_rig.md" in got, got
