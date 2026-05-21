from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from utils.general import *
from utils import mip
from utils import gurobi
from utils.gen_inst2 import run_one_instance

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Solve an RCSP instance from a JSON problem file.")
    parser.add_argument(
        "--problem_txt",
        help="Path to TXT problem (omit to generate and solve inst99)",
    )
    parser.add_argument(
        "--problem-json",
        help="Path to JSON problem (overrides problem_txt when set)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write result JSON to this file (default: stdout)",
    )
    args = parser.parse_args(argv)

    if args.problem_json:
        problem = load_problem(args.problem_json)
    elif args.problem_txt:
        arcs_raw, resource_cost_raw, costs_raw, lb_raw, ub_raw, source_raw, sink_raw = read_instance(args.problem_txt)
        problem = adapt_instance_to_cell8(
            arcs_raw, resource_cost_raw, costs_raw, lb_raw, ub_raw, source_raw, sink_raw
        )
    else:
        inst_id = 99
        run_one_instance(inst_id, 5, 0.5)
        arcs_raw, resource_cost_raw, costs_raw, lb_raw, ub_raw, source_raw, sink_raw = read_instance(f"data/inst{inst_id}.txt")
        problem = adapt_instance_to_cell8(
            arcs_raw, resource_cost_raw, costs_raw, lb_raw, ub_raw, source_raw, sink_raw
        )

    rcsp, model = create_rcsp_model(problem)
    result = gurobi.solve_problem(rcsp, model, problem)
    text = json.dumps(result, indent=2)
    if args.output:
        open(args.output, "w", encoding="utf-8").write(text + "\n")
    else:
        print(text)
    return 0 if result.get("has_solution") else 1


if __name__ == "__main__":
    main()
