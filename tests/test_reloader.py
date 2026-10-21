import os
import subprocess
import sys
import time

from whoop_mcp import reloader


def test_snapshot_and_changed(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "a.cpython.py").write_text("")
    before = reloader.snapshot(tmp_path)
    assert list(before) == [str(tmp_path / "a.py")]
    assert reloader.changed(before, reloader.snapshot(tmp_path)) == []

    os.utime(tmp_path / "a.py", (time.time() + 5, time.time() + 5))
    (tmp_path / "b.py").write_text("")
    after = reloader.snapshot(tmp_path)
    assert reloader.changed(before, after) == [str(tmp_path / "a.py"), str(tmp_path / "b.py")]


def test_pid_alive():
    assert reloader.pid_alive(os.getpid())
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    assert not reloader.pid_alive(p.pid)


def test_supervisor_stops_child_when_parent_exits(tmp_path):
    parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.5)"])
    marker = tmp_path / "child.pid"
    child = [sys.executable, "-c", f"import os, time; open(r'{marker}', 'w').write(str(os.getpid())); time.sleep(60)"]
    t0 = time.time()
    assert reloader.supervise(child, parent_pid=parent.pid) == 0
    assert time.time() - t0 < 10
    assert not reloader.pid_alive(int(marker.read_text()))
