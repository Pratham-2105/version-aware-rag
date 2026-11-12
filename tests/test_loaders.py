from jarvis.ingest.loaders import load_vault


def test_load_vault_skips_non_notes(tmp_path):
    (tmp_path / "plan.md").write_text("# Plan\nship it", encoding="utf-8")
    (tmp_path / "photo.png").write_bytes(b"\x89PNG\r\n\x1a\n fake image")
    (tmp_path / "old_notepad.md").write_bytes("caf\xe9".encode("latin-1"))
    (tmp_path / "skip").mkdir()
    (tmp_path / "skip" / "ignored.md").write_text("# no", encoding="utf-8")

    files = load_vault(tmp_path, verbose=False)

    assert list(files) == ["plan.md"]


def test_load_vault_strips_bom(tmp_path):
    (tmp_path / "bom.md").write_bytes(b"\xef\xbb\xbf# Title\nbody")
    files = load_vault(tmp_path, verbose=False)
    assert files["bom.md"].startswith("# Title")