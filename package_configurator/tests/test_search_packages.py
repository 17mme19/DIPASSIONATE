from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from package_configurator.search_packages import main


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class SearchPackagesTests(unittest.TestCase):
    def test_search_prints_matching_package(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "--project-root",
                    str(PROJECT_ROOT),
                    "--sub-family",
                    "LFBGA",
                    "--terminal-count",
                    "225",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("AKB", output.getvalue())
        self.assertIn("Matches: 1", output.getvalue())

    def test_search_reports_no_match(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "--project-root",
                    str(PROJECT_ROOT),
                    "--terminal-count",
                    "999",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.getvalue().strip(), "No matching packages found.")

    def test_structured_search_prints_matching_package(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "--project-root",
                    str(PROJECT_ROOT),
                    "--structured",
                    "--terminal-count",
                    "144",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("6RW", output.getvalue())
        self.assertIn("Matches: 1", output.getvalue())


if __name__ == "__main__":
    unittest.main()
