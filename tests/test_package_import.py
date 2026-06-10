from contextlib import redirect_stdout
from io import StringIO
from unittest import TestCase

from gupiao import __version__
from gupiao.cli import main


class PackageImportTest(TestCase):
    def test_package_version(self) -> None:
        self.assertEqual(__version__, "0.2.0")

    def test_cli_version(self) -> None:
        stdout = StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(main(["--version"]), 0)
        self.assertEqual(stdout.getvalue().strip(), "0.2.0")
