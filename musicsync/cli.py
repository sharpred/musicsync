from __future__ import annotations

import argparse
import sys

from . import config as config_mod
from . import import_owned, merge, pull, report, scan


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="musicsync")
    parser.add_argument("--config", default="musicsync.toml", help="Path to this machine's musicsync.toml")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scan", help="Scan this machine's music roots into snapshot.db")
    sub.add_parser("pull", help="(central only) Pull peers' snapshot.db over SSH")
    sub.add_parser("merge", help="(central only) Merge own + pulled snapshots into library.db")
    sub.add_parser("import-owned", help="(central only) Import Music.app Library.xml as the owned list")
    sub.add_parser("report", help="(central only) Generate the missing-tracks report")
    sub.add_parser("run-central", help="(central only) scan + pull + merge + import-owned + report")

    args = parser.parse_args(argv)
    cfg = config_mod.load_config(args.config)

    if args.command == "scan":
        scan.main(cfg)
    elif args.command == "pull":
        pull.pull(cfg)
    elif args.command == "merge":
        merge.merge(cfg)
    elif args.command == "import-owned":
        import_owned.import_owned(cfg)
    elif args.command == "report":
        report.write_reports(cfg)
    elif args.command == "run-central":
        scan.main(cfg)
        pull.pull(cfg)
        merge.merge(cfg)
        import_owned.import_owned(cfg)
        report.write_reports(cfg)

    return 0


if __name__ == "__main__":
    sys.exit(main())
