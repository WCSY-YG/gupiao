from gupiao import __version__
from gupiao.cli import main


def test_package_version() -> None:
    assert __version__ == "0.1.0"


def test_cli_version(capsys) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "0.1.0"
