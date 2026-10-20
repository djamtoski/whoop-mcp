import zipfile
from datetime import date

from whoop_mcp import demo, export


def test_flatten():
    assert export.flatten({"a": 1, "b": {"c": 2, "d": {"e": 3}}, "l": [1]}) == {
        "a": 1, "b.c": 2, "b.d.e": 3, "l": "[1]"}


def test_monthly_summary():
    raw = demo.generate(end=date(2026, 10, 20), days=60)
    months = export.monthly_summary(raw)
    assert [m["month"] for m in months] == ["2026-08", "2026-09", "2026-10"]
    sep = months[1]
    assert sep["days_with_recovery"] == 30
    assert sep["avg_recovery"] is not None and sep["avg_hrv_ms"] is not None
    assert {"swim", "bike", "run"} <= set(sep["training"])


def test_write_csv_union_columns(tmp_path):
    p = tmp_path / "x.csv"
    export.write_csv(p, [{"a": 1}, {"a": 2, "b": {"c": 3}}])
    assert p.read_text(encoding="utf-8").splitlines() == ["a,b.c", "1,", "2,3"]


def test_import_app_export_only_csv_and_no_traversal(tmp_path):
    z = tmp_path / "whoop.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("my_whoop_data/physiological_cycles.csv", "Cycle start time,Recovery score %\n2026-10-20,52\n")
        zf.writestr("../../evil.csv", "x\n1\n")
        zf.writestr("readme.txt", "ignored")
    res = export.import_app_export(z, tmp_path / "exp")
    assert res["files"]["physiological_cycles.csv"]["rows"] == 1
    assert (tmp_path / "exp" / "app_export" / "evil.csv").exists()
    assert not (tmp_path / "evil.csv").exists()
    assert "readme.txt" not in res["files"]
