from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from quant_eam.registry.cards import create_card_from_run, list_cards, promote_card, show_card
from quant_eam.registry.errors import RegistryInvalid
from quant_eam.registry.storage import default_registry_root
from quant_eam.registry.triallog import record_trial

EXIT_OK = 0
EXIT_USAGE_OR_ERROR = 1
EXIT_INVALID = 2


def _print_json(obj) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m quant_eam.registry.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_rec = sub.add_parser("record-trial", help="Record a run trial into registry trial_log.jsonl (append-only).")
    p_rec.add_argument("--dossier", required=True, help="Dossier directory path.")

    p_card = sub.add_parser("create-card", help="Create an experience card from a Gate PASS run.")
    p_card.add_argument("--run-id", required=True, help="Run id (must exist in trial log; run record-trial first).")
    p_card.add_argument("--title", required=True, help="Card title.")
    p_card.add_argument("--if-exists", choices=["fail", "noop"], default="fail")

    p_prom = sub.add_parser("promote-card", help="Promote a card status (event-sourced).")
    p_prom.add_argument("--card-id", required=True)
    p_prom.add_argument("--new-status", required=True, choices=["draft", "challenger", "champion", "retired"])
    p_prom.add_argument("--allow-skip", action="store_true", help="Allow skipping intermediate states (default false).")

    sub.add_parser("list-cards", help="List cards (computed effective status).")

    p_show = sub.add_parser("show-card", help="Show a card base record + events.")
    p_show.add_argument("--card-id", required=True)

    parser.add_argument(
        "--registry-root",
        default=None,
        help="Registry root directory (default: env EAM_REGISTRY_ROOT or ${EAM_ARTIFACT_ROOT}/registry).",
    )

    args = parser.parse_args(argv)

    try:
        rr = Path(args.registry_root) if args.registry_root else default_registry_root()

        if args.cmd == "record-trial":
            ev = record_trial(dossier_dir=Path(args.dossier), registry_root=rr, if_exists="noop")
            _print_json(ev)
            return EXIT_OK

        if args.cmd == "create-card":
            card = create_card_from_run(
                run_id=str(args.run_id),
                registry_root=rr,
                title=str(args.title),
                if_exists=str(args.if_exists),
            )
            _print_json(card)
            return EXIT_OK

        if args.cmd == "promote-card":
            ev = promote_card(
                card_id=str(args.card_id),
                new_status=str(args.new_status),
                registry_root=rr,
                allow_skip=bool(args.allow_skip),
            )
            _print_json(ev)
            return EXIT_OK

        if args.cmd == "list-cards":
            _print_json({"cards": list_cards(registry_root=rr)})
            return EXIT_OK

        if args.cmd == "show-card":
            _print_json(show_card(registry_root=rr, card_id=str(args.card_id)))
            return EXIT_OK

        print(json.dumps({"error": "unknown command"}, sort_keys=True), file=sys.stderr)
        return EXIT_USAGE_OR_ERROR
    except RegistryInvalid as e:
        _print_json({"error": str(e)})
        return EXIT_INVALID
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return EXIT_USAGE_OR_ERROR


if __name__ == "__main__":
    raise SystemExit(main())

