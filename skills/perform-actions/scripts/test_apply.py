import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import apply


def test_backup_file_copies_and_does_not_clobber(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text("original")
    b1 = apply.backup_file(str(p))
    assert open(b1).read() == "original"
    p.write_text("changed")
    b2 = apply.backup_file(str(p))
    assert b1 != b2
    assert open(b1).read() == "original"
    assert open(b2).read() == "changed"


def test_compute_diff_unified():
    d = apply.compute_diff("a\nb\n", "a\nc\n", "f.md")
    assert "-b" in d and "+c" in d and "f.md" in d


def test_apply_edit_backs_up_then_writes(tmp_path):
    p = tmp_path / "mem.md"
    p.write_text("old\n")
    res = apply.apply_edit(str(p), "new\n")
    assert open(p).read() == "new\n"
    assert open(res["backed_up_to"]).read() == "old\n"


def test_apply_edit_is_atomic_no_temp_left(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text("old\n")
    apply.apply_edit(str(p), "new\n")
    assert open(p).read() == "new\n"
    assert not (tmp_path / "CLAUDE.md.tmp").exists()  # temp consumed by os.replace


def test_archive_capability_is_reversible(tmp_path):
    cap = tmp_path / "skills" / "dead-skill"
    cap.mkdir(parents=True)
    (cap / "SKILL.md").write_text("x")
    archive_dir = tmp_path / "archive"
    dest = apply.archive_capability(str(cap), str(archive_dir))
    assert not os.path.exists(str(cap))
    assert os.path.exists(os.path.join(dest, "SKILL.md"))
    apply.restore_capability(dest, str(cap))
    assert os.path.exists(os.path.join(str(cap), "SKILL.md"))


def test_archive_collision_preserves_both(tmp_path):
    archive_dir = tmp_path / "archive"
    a = tmp_path / "a" / "foo.md"; a.parent.mkdir(parents=True); a.write_text("FIRST")
    d1 = apply.archive_capability(str(a), str(archive_dir))
    b = tmp_path / "b" / "foo.md"; b.parent.mkdir(parents=True); b.write_text("SECOND")
    d2 = apply.archive_capability(str(b), str(archive_dir))
    assert d1 != d2
    assert open(d1).read() == "FIRST"   # first archived copy NOT overwritten
    assert open(d2).read() == "SECOND"


def test_no_destructive_delete_exists():
    assert not hasattr(apply, "delete_capability")
    assert not hasattr(apply, "delete_file")
