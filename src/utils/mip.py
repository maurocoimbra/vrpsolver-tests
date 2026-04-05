from mip import OptimizationStatus
from typing import Dict, Any

def retrieve_path(model):
  # get only used arcs
  used_arcs = list()
  for var in model.vars:
    if var.name.startswith("x"):
      if var.x == 1:
        used_arcs.append(var.name)

  # get path
  path = ["A"]
  entry = "A"
  while len(used_arcs):
    for name in used_arcs:
      if name.split("x_")[1].startswith(entry):
        entry = name.split("x_")[1].split("_")[1]
        path.append(entry[0])
        used_arcs.remove(name)
        break

  return path


def check_ng_set(rcsp, path):

  memory = set()

  for node in path:
    if node in memory:
      return False
    removed_nodes = list()
    for known_node in memory:
      if known_node not in rcsp.ng_set[node]:
        removed_nodes.append(known_node)
    for removed_node in removed_nodes:
      memory.remove(removed_node)
    memory.add(node)

  return True

def solve_problem(rcsp, model, problem):
    max_seconds = problem["max_seconds"]
    status = model.optimize(max_seconds=max_seconds)

    has_solution = getattr(model, "num_solutions", 0) > 0
    out: Dict[str, Any] = {
        "status": str(status),
        "optimal": status == OptimizationStatus.OPTIMAL,
        "has_solution": has_solution,
    }
    if has_solution:
        if model.objective_value is not None:
            out["objective_value"] = float(model.objective_value)
        path = retrieve_path(model)
        out["path"] = path
        out["ng_set_ok"] = check_ng_set(rcsp, path)

    return out