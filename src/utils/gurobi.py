import os
import gurobipy as gp
from gurobipy import GRB
from typing import Dict, Any

def retrieve_path(model):
  # get only used arcs
  used_arcs = list()
  for var in model.getVars():
    if var.VarName.startswith("x") and round(var.X) == 1:
        used_arcs.append(var.VarName)

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
    model.write("./tmp_gurobi_model.lp")
    model = gp.read("./tmp_gurobi_model.lp")
    os.remove("./tmp_gurobi_model.lp")

    max_seconds = problem["max_seconds"]
    model.setParam("TimeLimit", max_seconds)
    model.optimize()

    status = model.Status

    out: Dict[str, Any] = {
        "status": str(status),
        "optimal": status == GRB.OPTIMAL,
        "has_solution": model.SolCount > 0,
    }

    if status in (GRB.INFEASIBLE, GRB.UNBOUNDED, GRB.INF_OR_UNBD):
        out["details"] = "No solution (infeasible/unbounded or solve failed)."
    elif model.SolCount == 0:
        out["details"] = "Optimization finished, but no feasible solution was found."
    else:
        out["objective_value"] = model.ObjVal
        path = retrieve_path(model)
        out["path"] = path
        out["ng_set_ok"] = check_ng_set(rcsp, path)

    return out