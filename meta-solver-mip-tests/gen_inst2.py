import random
import os
from subprocess import call


def generate_inst(nbVertices, graph_density):
    arcs = []
    for i in range(nbVertices - 1):
        for j in range(1, nbVertices):
            if i != j and random.random() < graph_density:
                arcs.append((i, j))

    verts_info = []
    for i in range(nbVertices):
        resConsumptionLB = 0.0
        resConsumptionUB = 200.0
        if i != 0 and i != nbVertices - 1:
            resConsumptionLB = random.uniform(0.0, 50.0)
            resConsumptionUB = resConsumptionLB + random.uniform(50.0, 100.0)
        verts_info.append((resConsumptionLB, resConsumptionUB))

    arcs_info = []
    for arcId in range(len(arcs)):
        cost = random.uniform(-3.0, -1.0)
        resConsumption = random.uniform(0.5, 1.0)
        arcs_info.append((cost, resConsumption))

    return verts_info, arcs, arcs_info


def generate_file(verts_info, arcs, arcs_info, filename):
    nbVertices = len(verts_info)
    source = 0
    sink = nbVertices - 1
    nbArcs = len(arcs)

    with open(filename, 'w') as f:
        f.write("# nbVertices nbArcs source sink\n")
        f.write(f"{nbVertices} {nbArcs} {source} {sink}\n")

        f.write("# nodes: id lowerBound upperBound\n")
        for i in range(nbVertices):
            lb, ub = verts_info[i]
            f.write(f"{i} {lb} {ub}\n")

        f.write("# arcs: id tail head cost resourceCost\n")
        for arcId in range(nbArcs):
            tail, head = arcs[arcId]
            cost, resCost = arcs_info[arcId]
            f.write(f"{arcId} {tail} {head} {cost} {resCost}\n")


def get_results(inst_id):
    os.makedirs("output", exist_ok=True)

    with open("output/inst" + str(inst_id) + ".out", 'r') as f:
        for line in f:
            if "RCSP solver solution with cost " in line:
                return True, float(line.split(":")[0].split("cost")[-1])
    return False, 0.0


def run_one_instance(inst_id, nb_verts, density):
    verts_info, arcs, arcs_info = generate_inst(nb_verts, density)
    generate_file(verts_info, arcs, arcs_info, "data/1inst" + str(inst_id) + ".txt")
    print("generated file")


run_one_instance(1, 6, 0.5)
