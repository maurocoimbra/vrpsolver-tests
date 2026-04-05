from __future__ import annotations

import json
from itertools import product
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from rcsp import RCSP

from mip import BINARY, CONTINUOUS, CBC, MINIMIZE, Model, OptimizationStatus, xsum

def _as_neighbor_set(v: Union[Set[str], List[str], Tuple[str, ...]]) -> Set[str]:
    return set(v)

def read_instance(filename):
    with open(filename, 'r') as f:
        lines = [line.strip() for line in f.readlines()]

    # skip comment lines
    idx = 0
    def next_data_line():
        nonlocal idx
        while idx < len(lines) and (lines[idx].startswith('#') or lines[idx] == ''):
            idx += 1
        data = lines[idx]
        idx += 1
        return data

    # First block: general info
    # nbVertices, maxArcId, nbElementaritySets, nbPackingSets, nbCoveringSets,
    # symmetricCase, backwardSearchIsUsed, zeroReducedCostThreshold
    parts = next_data_line().split()
    nb_vertices = int(parts[0])
    max_arc_id = int(parts[1])

    # Second block: resources info
    # nbMainResources, nbDisposableResources, nbStandardResources, bidirectionalBorderValue
    parts = next_data_line().split()
    nb_main_resources = int(parts[0])

    # The actual number of distinct resources in the file equals nb_main_resources
    nb_resources = nb_main_resources

    # Read vertex info
    lb = {}  # resource consumption lower bounds per vertex
    ub = {}  # resource consumption upper bounds per vertex
    for i in range(nb_vertices):
        parts = next_data_line().split()
        vert_alg_id = int(parts[0])

        # Resource bounds line: lb ub bucketStep (for each main resource)
        res_parts = next_data_line().split()
        pos = 0
        for r in range(nb_resources):
            lb[(vert_alg_id, r)] = float(res_parts[pos])
            ub[(vert_alg_id, r)] = float(res_parts[pos + 1])
            pos += 3  # lb, ub, bucketStep

        # nbInMemoryOfElemSets
        next_data_line()

    # Read arc info
    num_arcs_line = next_data_line()
    num_arcs = int(num_arcs_line.split()[0])

    arcs = []
    costs = {}
    resource_cost = {}
    for a in range(num_arcs):
        # arcId, tailVertAlgId, headVertAlgId, elemSetId, packSetId, covSetId, reducedCost, totalCost
        parts = next_data_line().split()
        arc_id = int(parts[0])
        tail = int(parts[1])
        head = int(parts[2])
        reduced_cost = float(parts[6])

        arcs.append((tail, head))
        costs[arc_id] = reduced_cost

        # resource consumption: one value per resource on a single line
        res_parts = next_data_line().split()
        for r in range(nb_resources):
            resource_cost[(arc_id, r)] = float(res_parts[r])

        # nbInMemoryOfElemSets
        next_data_line()
        # nbBuckArcIntrvs + intervals
        next_data_line()

    source = 0
    sink = nb_vertices - 1

    return arcs, resource_cost, costs, lb, ub, source, sink


def _vertex_id_to_letter_label(v: int) -> str:
    """Map integer vertex id to label: 0->A, 1->B, ..., 25->Z, 26->AA, ..."""
    if v < 0:
        raise ValueError(f"vertex id must be non-negative, got {v}")
    n = v + 1
    chars: List[str] = []
    while n:
        n, r = divmod(n - 1, 26)
        chars.append(chr(ord("A") + r))
    return "".join(reversed(chars))


def adapt_instance_to_cell8(arcs, resource_cost, costs, lb, ub, source, sink):
    # String vertex ids as letters (0->A, 1->B, ...) for cell8-style problems
    vertices = sorted({v for arc in arcs for v in arc})
    # Ensure source/sink included
    if source not in vertices:
        vertices.insert(0, source)
    if sink not in vertices:
        vertices.append(sink)

    vlabel = {v: _vertex_id_to_letter_label(v) for v in vertices}

    # arcs: dict node -> set(neighbors)
    arcs_dict = {vlabel[v]: set() for v in vertices}
    for arc_id, (t, h) in enumerate(arcs):
        arcs_dict[vlabel[t]].add(vlabel[h])

    # resource_cost and costs: dict node -> dict(neighbor -> value)
    resource_cost_dict = {vlabel[v]: {} for v in vertices}
    costs_dict = {vlabel[v]: {} for v in vertices}
    for arc_id, (t, h) in enumerate(arcs):
        tail = vlabel[t]
        head = vlabel[h]
        # use arc_id keys from costs/resource_cost
        # resource_cost keyed by (arc_id, r). We assume single resource r=0
        rc = resource_cost.get((arc_id, 0), 0.0)
        c = costs.get(arc_id, 0.0)
        resource_cost_dict[tail][head] = rc
        costs_dict[tail][head] = c

    # lb/ub expected as dict vertex->value (example had single resource per vertex)
    lb_dict = {}
    ub_dict = {}
    for (vert, r), val in lb.items():
        lb_dict[vlabel[vert]] = val
    for (vert, r), val in ub.items():
        ub_dict[vlabel[vert]] = val

    # ng_set: neighbor-exclusion sets, default empty sets; keep conservative default
    ng_set = {vlabel[v]: set() for v in vertices}

    source_label = vlabel[source]
    sink_label = vlabel[sink]

    return {
        "source": source_label,
        "sink": sink_label,
        "arcs": arcs_dict,
        "resource_cost": resource_cost_dict,
        "costs": costs_dict,
        "lb": lb_dict,
        "ub": ub_dict,
        "ng_set": ng_set,
        "big_m": 100,
        "max_seconds": 300,
        "write_lp": None
    }

def load_problem(path: Optional[str], raw: Optional[str] = None) -> Dict[str, Any]:
    """Load problem from a JSON file path or raw string (stdin)."""
    text = open(path, encoding="utf-8").read()
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