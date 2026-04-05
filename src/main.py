from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from utils.general import *
from utils import mip
from utils import gurobi

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Solve an RCSP instance from a JSON problem file.")
    parser.add_argument(
        "problem",
        nargs="?",
        help="Path to JSON problem (omit with --stdin)",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read problem JSON from standard input",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write result JSON to this file (default: stdout)",
    )
    args = parser.parse_args(argv)

    if args.stdin:
        raw = sys.stdin.read()
        problem = load_problem(None, raw=raw)
    elif args.problem:
        problem = load_problem(args.problem)
    else:
        parser.error("Provide a problem JSON file or --stdin")

    rcsp, model = create_rcsp_model(problem)
    result = gurobi.solve_problem(rcsp, model, problem)
    text = json.dumps(result, indent=2)
    if args.output:
        open(args.output, "w", encoding="utf-8").write(text + "\n")
    else:
        print(text)
    return 0 if result.get("has_solution") else 1


if __name__ == "__main__":
    raise SystemExit(main())
