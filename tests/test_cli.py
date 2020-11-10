import subprocess
import pytest

def test_version():
    capture = subprocess.check_output(
        "ringmaster --version",
        shell=True
    )
    assert b"0.0.0" in capture


def test_bad_command():
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.check_output(
            "ringmaster --bad-command",
            shell=True
        )