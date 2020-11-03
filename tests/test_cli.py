import subprocess
import pytest

def test_version():
    subprocess.check_output(
        "ringmaster --version",
        shell=True
    )

def test_debug():
    capture = subprocess.check_output(
        "ringmaster --version --debug",
        shell=True
    )
    assert b"debug mode" in capture


def test_bad_command():
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.check_output(
            "ringmaster --bad-command",
            shell=True
        )