from __future__ import annotations

import json
from itertools import product
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from rcsp import RCSP

from mip import BINARY, CONTINUOUS, CBC, MINIMIZE, Model, OptimizationStatus, xsum

def _as_neighbor_set(v: Union[Set[str], List[str], Tuple[str, ...]]) -> Set[str]:
    return set(v)

def load_problem(path: Optional[str], raw: Optional[str] = None) -> Dict[str, Any]:
    """Load problem from a JSON file path or raw string (stdin)."""
    text = raw if raw is not None else open(path, encoding="utf-8").read()
    data = json.loads(text)
    required = ("source", "sink", "arcs", "resource_cost", "costs", "lb", "ub", "ng_set")
    for k in required:
        if k not in data:
            raise KeyError(f"Missing required field: {k}")

    arcs: Dict[str, Set[str]] = {str(u): _as_neighbor_set(v) for u, v in data["arcs"].items()}
    ng_set: Dict[str, Set[str]] = {
        str(u): _as_neighbor_set(v) for u, v in data["ng_set"].items()
    }
    all_nodes: Set[str] = set(arcs.keys()) | {h for outs in arcs.values() for h in outs}
    for n in all_nodes:
        ng_set.setdefault(n, set())

    return {
        "source": str(data["source"]),
        "sink": str(data["sink"]),
        "arcs": arcs,
        "resource_cost": {u: {str(k): float(v) for k, v in d.items()} for u, d in data["resource_cost"].items()},
        "costs": {u: {str(k): float(v) for k, v in d.items()} for u, d in data["costs"].items()},
        "lb": {str(k): float(v) for k, v in data["lb"].items()},
        "ub": {str(k): float(v) for k, v in data["ub"].items()},
        "ng_set": ng_set,
        "big_m": float(data.get("big_m", 100)),
        "max_seconds": float(data.get("max_seconds", 300)),
        "write_lp": data.get("write_lp"),
    }

def remove_path(model, x, rcsp, node_list):
    replica_lists = [rcsp.rep[node] for node in node_list]
    # For each combination of replicas along the path
    for replica_path in product(*replica_lists):
        expr = 0
        for i in range(len(replica_path) - 1):
            src = replica_path[i]
            dst = replica_path[i + 1]
            expr += x[src][dst]
        model += expr <= len(node_list) - 2 # Arcs - 2

def build_model(rcsp: RCSP) -> Tuple[Model, Dict[str, Dict[str, Any]], Dict[str, Any], Dict[str, Dict[str, Any]]]:
    rcsp.replicate_graph_complete()

    model = Model(sense=MINIMIZE, solver_name=CBC)
    x = {i: {j: model.add_var(var_type=BINARY, name=f"x_{i}_{j}") for j in v} for i, v in rcsp.new_arcs.items()} # x['A1']['B2']
    y = {i: model.add_var(var_type=CONTINUOUS, name=f"y_{i}", lb=0.0) for i, v in rcsp.new_arcs.items()} # y['A1']
    z = {i: {j: model.add_var(var_type=BINARY, name=f"z_{i}_{j}") for j in rcsp.arcs.keys()} for i in rcsp.new_arcs.keys()} # x['A']['B']

    # Lower bound
    for i in rcsp.new_arcs:
        model += y[i] >= rcsp.new_lb[i]*xsum(x[j][i] for j in rcsp.delta_minus(rcsp.new_arcs, i)) # não sei se precisa desse somatório aqui

    # Upper bound
    for i in rcsp.new_arcs:
        model += y[i] <= rcsp.new_ub[i]

    # Resources
    for i, v in rcsp.new_arcs.items():
        for j in v:
            model += y[j] >= y[i] - rcsp.M*(1 - x[i][j]) + rcsp.new_resource_cost[i][j]

    # Removing paths for testing
    # remove_path(model, x, rcsp, ['A', 'C', 'B', 'C', 'B', 'F'])
    # remove_path(model, x, rcsp, ['A', 'B', 'C', 'B', 'C', 'F'])
    # remove_path(model, x, rcsp, ['A', 'C', 'D', 'C', 'F'])

    # Only 1 exits
    for i in rcsp.new_arcs:
        model += xsum(x[i][j] for j in rcsp.delta_plus(rcsp.new_arcs, i)) <= 1

    # Only 1 enters
    for j in rcsp.new_arcs:
        model += xsum(x[i][j] for i in rcsp.delta_minus(rcsp.new_arcs, j)) <= 1

    # Enters = Exits
    for j in rcsp.new_arcs:
        if j == rcsp.source or j == rcsp.sink:
            continue
        model += xsum(x[i][j] for i in rcsp.delta_minus(rcsp.new_arcs, j)) - xsum(x[j][k] for k in rcsp.delta_plus(rcsp.new_arcs, j)) == 0

    # Source
    model += xsum(x[rcsp.source][j] for j in rcsp.delta_plus(rcsp.new_arcs, rcsp.source)) == 1

    # Sink
    model += xsum(x[i][rcsp.sink] for i in rcsp.delta_minus(rcsp.new_arcs, rcsp.sink)) == 1

    # Replicando nos (acho que não precisa porque o grafo não é completo, já não existem arcos de um nó para suas réplicas)

    # Proibindo ciclos
    for i, v in rcsp.new_arcs.items():
        for j in v:
            if i == rcsp.source or j == rcsp.sink:
                continue
            model += x[i][j] <= 1 - z[i][rcsp.check_original(j)]

    # Proibindo ciclos
    for i, v in rcsp.new_arcs.items():
        for j in v:
            if i == rcsp.source or j == rcsp.sink:
                continue
            for k in rcsp.ng_set[rcsp.check_original(j)]:
                model += z[j][k] >= z[i][k] - (1 - x[i][j])

    # Proibindo ciclos
    for i in rcsp.new_arcs.keys():
        if i == rcsp.source or i == rcsp.sink:
            continue
        model += z[i][rcsp.check_original(i)] == 1

    # Objetivo
    model.objective = xsum(rcsp.new_costs[i][j]*x[i][j] for i, v in rcsp.new_arcs.items() for j in v)

    return model


def create_rcsp_model(problem: Dict[str, Any]) -> Dict[str, Any]:
    rcsp = RCSP(
        arcs=problem["arcs"],
        resource_cost=problem["resource_cost"],
        costs=problem["costs"],
        lb=problem["lb"],
        ub=problem["ub"],
        ng_set=problem["ng_set"],
        source=problem["source"],
        sink=problem["sink"],
        big_m=problem["big_m"],
    )
    model = build_model(rcsp)
    lp_path = problem.get("write_lp")
    if lp_path:
        model.write(lp_path)

    return rcsp, model