from __future__ import annotations

import json
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from gupiao.cli import main
from gupiao.data import DailyBar, SQLiteStore
from gupiao.data.local_daily_cache import (
    LocalDailyCacheImportConfig,
    import_local_daily_cache,
    iter_market_files,
    parse_daily_cache_file,
)


class LocalDailyCacheTest(TestCase):
    def test_iter_market_files_filters_by_date(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "market_2026-04-22.csv").write_text("code,name\n", encoding="utf-8")
            (source / "market_2026-04-23.csv").write_text("code,name\n", encoding="utf-8")
            (source / "notes.txt").write_text("", encoding="utf-8")

            files = iter_market_files(
                source,
                start=date(2026, 4, 23),
                end=date(2026, 4, 23),
            )

            self.assertEqual(files, [(date(2026, 4, 23), source / "market_2026-04-23.csv")])

    def test_parse_daily_cache_estimates_missing_volume(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "market_2026-04-22.csv"
            path.write_text(
                "\n".join(
                    [
                        "code,name,trade,open,changepercent,amount,high,low,settlement,turnoverratio",
                        "000001,平安银行,10,9.8,1.2,100000,10.2,9.7,9.9,1.5",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            parsed = parse_daily_cache_file(
                path,
                trade_date=date(2026, 4, 22),
                adjust="hfq",
                provider="local_daily_k",
            )

            self.assertEqual(parsed.rows_seen, 1)
            self.assertEqual(parsed.invalid_rows, 0)
            self.assertEqual(parsed.estimated_volume_rows, 1)
            self.assertEqual(parsed.bars[0][6], 10000.0)
            self.assertEqual(parsed.bars[0][10], "local_daily_k_estimated_volume")

    def test_import_daily_cache_ignores_existing_rows_by_default(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            db_path = Path(directory) / "market.sqlite"
            existing = DailyBar(
                symbol="000001",
                trade_date=date(2026, 4, 23),
                open=1.0,
                high=1.0,
                low=1.0,
                close=1.0,
                volume=1.0,
                amount=1.0,
                turnover=1.0,
                adjust="hfq",
                provider="akshare",
            )
            store = SQLiteStore(db_path)
            store.upsert_daily_bars([existing])
            (source / "market_2026-04-23.csv").write_text(
                "\n".join(
                    [
                        "code,name,trade,open,high,low,成交量,amount,turnoverratio",
                        "000001,平安银行,10,9.8,10.2,9.7,2000,100000,1.5",
                        "000002,万科A,20,19.5,20.3,19.4,3000,200000,2.0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = import_local_daily_cache(
                LocalDailyCacheImportConfig(source_dir=source, db_path=db_path)
            )

            self.assertEqual(result.files_imported, 1)
            self.assertEqual(result.rows_importable, 2)
            self.assertEqual(result.bars_written, 1)
            self.assertEqual(
                store.get_daily_bars("000001", adjust="hfq"),
                [existing],
            )
            self.assertEqual(store.get_daily_bars("000002", adjust="hfq")[0].volume, 3000.0)

    def test_cli_import_daily_cache_dry_run(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            (source / "market_2026-04-23.csv").write_text(
                "\n".join(
                    [
                        "code,name,trade,open,high,low,成交量,amount,turnoverratio",
                        "000001,平安银行,10,9.8,10.2,9.7,2000,100000,1.5",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            stdout = StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(
                    main(
                        [
                            "data",
                            "import-daily-cache",
                            "--source",
                            str(source),
                            "--db",
                            str(Path(directory) / "market.sqlite"),
                            "--dry-run",
                        ]
                    ),
                    0,
                )

            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["rows_importable"], 1)
            self.assertEqual(payload["bars_written"], 0)
