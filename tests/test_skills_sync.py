from agent_harness.skills_sync import MARKER, sync_skills


def _make_skill(root, name, body="# s"):
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")
    return d


def test_sync_copies_and_marks(tmp_path):
    src, dst = tmp_path / "skills", tmp_path / "target"
    _make_skill(src, "ticket-triage")
    result = sync_skills(src, dst)
    assert result.synced == ["ticket-triage"]
    assert (dst / "ticket-triage" / MARKER).exists()
    assert (dst / "ticket-triage" / "SKILL.md").exists()


def test_resync_overwrites_own_dirs(tmp_path):
    src, dst = tmp_path / "skills", tmp_path / "target"
    _make_skill(src, "ticket-triage", body="v1")
    sync_skills(src, dst)
    (src / "ticket-triage" / "SKILL.md").write_text("v2", encoding="utf-8")
    result = sync_skills(src, dst)
    assert result.synced == ["ticket-triage"]
    assert (dst / "ticket-triage" / "SKILL.md").read_text(encoding="utf-8") == "v2"


def test_never_clobbers_foreign_skill(tmp_path):
    src, dst = tmp_path / "skills", tmp_path / "target"
    _make_skill(src, "fix-bug", body="ours")
    _make_skill(dst, "fix-bug", body="the user's own skill")  # no marker
    result = sync_skills(src, dst)
    assert result.skipped == ["fix-bug"]
    assert (dst / "fix-bug" / "SKILL.md").read_text(encoding="utf-8") == "the user's own skill"


def test_ignores_non_skill_dirs(tmp_path):
    src, dst = tmp_path / "skills", tmp_path / "target"
    (src / "not-a-skill").mkdir(parents=True)
    result = sync_skills(src, dst)
    assert result.synced == []
