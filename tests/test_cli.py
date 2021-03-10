import subprocess
import pytest
import ringmaster.version as version

def test_version():
    capture = subprocess.check_output(
        "ringmaster --version",
        shell=True
    )
    assert bytes(version.__version__, "utf-8") in capture


def test_bad_command():
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.check_output(
            "ringmaster --bad-command",
            shell=True
        )