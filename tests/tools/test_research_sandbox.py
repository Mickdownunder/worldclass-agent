import pytest
from tools.research_sandbox import run_in_sandbox

def test_sandbox_success():
    code = "print('success')"
    res = run_in_sandbox(code, timeout_seconds=5)
    assert res.exit_code == 0
    assert "success" in res.stdout
    assert not res.timeout

def test_sandbox_syntax_error():
    code = "print('missing quote)"
    res = run_in_sandbox(code, timeout_seconds=5)
    assert res.exit_code != 0
    assert "SyntaxError" in res.stderr

def test_sandbox_timeout():
    code = "import time\nwhile True: time.sleep(1)"
    res = run_in_sandbox(code, timeout_seconds=2)
    assert res.exit_code != 0
    assert res.timeout
    assert "Sandbox Timeout Exceeded" in res.stderr

def test_sandbox_no_network():
    code = "import urllib.request\nurllib.request.urlopen('http://google.com')"
    res = run_in_sandbox(code, timeout_seconds=5)
    assert res.exit_code != 0
    assert "URLError" in res.stderr or "NameResolutionError" in res.stderr or "Temporary failure in name resolution" in res.stderr

def test_sandbox_memory_limit():
    # Attempt to allocate ~1GB of memory. Sandbox is limited to 512m.
    code = "a = bytearray(1024 * 1024 * 1000)"
    res = run_in_sandbox(code, timeout_seconds=5)
    assert res.exit_code != 0
    assert "MemoryError" in res.stderr or res.exit_code == 137 # 137 is OOM kill
