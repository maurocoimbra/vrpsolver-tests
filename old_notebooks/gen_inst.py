import random
import math
from subprocess import call
import os

def generate_inst(nbVertices, graph_density):

    # generate random number between 0 and 1
    arcs = []
    for i in range(nbVertices - 1):
        for j in range(1,nbVertices):
            if i != j and random.random() < graph_density:
                arcs.append((i, j))

    # For each vertex
    verts_info = []
    bucketsStep = random.uniform(1.0, 2.0)
    for i in range(nbVertices):
        resConsumptionLB = 0.0
        resConsumptionUB = 200.0
        if i != 0 and i != nbVertices - 1:
            resConsumptionLB = random.uniform(0.0, 50.0)
            resConsumptionUB = resConsumptionLB + random.uniform(50.0, 100.0)
        verts_info.append(((resConsumptionLB,resConsumptionUB),bucketsStep))
        

    maxArcId = len(arcs) - 1
    arcs_info = []
    for arcId in range(maxArcId):
        reducedCost = random.uniform(-3.0, -1.0)
        resConsumption = random.uniform(0.5, 1.0)
        tailVertAlgId = arcs[arcId][0]
        bounds = verts_info[tailVertAlgId][0]
        step = verts_info[tailVertAlgId][1]
        nbBuckets = int(math.ceil((bounds[1] - bounds[0])/step))
        arcs_info.append((reducedCost, resConsumption, nbBuckets))

    return verts_info, arcs, arcs_info

def generate_file(verts_info, arcs, arcs_info, 
                  zeroReducedCostThreshold, filename):
    nbVertices = len(verts_info)
    nbElementaritySets = nbPackingSets = nbVertices - 2
    nbMainResources = nbDisposableResources = nbStandardResources = 1

    maxArcId = len(arcs) - 1
    with open(filename, 'w') as f:
        # First block with general information
        f.write("# _nbVertices >> maxArcId >> _nbElementaritySets >> _nbPackingSets >> _nbCoveringSets >> symmetricCase\n")
        f.write("# >> _backwardSearchIsUsed >> _zeroReducedCostThreshold ;\n")
        f.write("# \n")
        f.write(f"{nbVertices} {maxArcId} {nbElementaritySets} {nbPackingSets} {0} {0} {0} {zeroReducedCostThreshold}\n")
        f.write("# _nbMainResources >> _nbDisposableResources >> _nbStandardResources >> _bidirectionalBorderValue;\n")
        f.write("# \n")
        f.write(f"{nbMainResources} {nbDisposableResources} {nbStandardResources} {0}\n")

        # For each vertex
        f.write("# for each vertex:\n")
        f.write("#   vertAlgId >> vertId >> elemSetId >> packSetId >> covSetId >> otherBuckDomMaxDepth;\n")
        f.write("#   resConsumptionLB[resAlgId] >> resConsumptionUB[resAlgId]; for each resource; and bucketSteps[resAlgId] if resource is main\n")
        f.write("#   >> nbInMemoryOfElemSets\n")
        for i in range(nbVertices):
            vertAlgId = i
            vertId = i
            if (i == 0):
                elemSetId = nbElementaritySets
                packSetId = nbPackingSets
            elif (i == nbVertices - 1):
                elemSetId = nbElementaritySets
                packSetId = nbPackingSets
            else:
                elemSetId = i - 1
                packSetId = i - 1
            covSetId = - 1
            otherBuckDomMaxDepth = 0
            
            f.write(f"{vertAlgId} {vertId} {elemSetId} {packSetId} {covSetId} {otherBuckDomMaxDepth}\n")
            resConsumptionLB,resConsumptionUB = verts_info[i][0]
            bucketsStep = verts_info[i][1]
            
            f.write(f"{resConsumptionLB} {resConsumptionUB} {bucketsStep}\n")
            nbInMemoryOfElemSets = 0
            f.write(f"{nbInMemoryOfElemSets}\n")

        # For each arc
        f.write("# for each arc:\n")
        f.write("#   >> arcId >> tailVertAlgId >> headVertAlgId >> elemSetId >> packSetId >> covSetId >> reducedCost >> totalCost\n")
        f.write("#    >> resConsumption[resAlgId]; for each resource\n")
        f.write("#     ifs >> nbInMemoryOfElemSets; -> then read memory\n")
        f.write("#     >> nbBuckArcIntrvs > then read intervals\n")
        f.write(f"{maxArcId}\n")
        for arcId in range(maxArcId):
            tailVertAlgId = arcs[arcId][0]
            headVertAlgId = arcs[arcId][1]
            elemSetId = nbElementaritySets
            packSetId = covSetId = -1
            reducedCost = arcs_info[arcId][0]
            totalCost = 0
            
            f.write(f"{arcId} {tailVertAlgId} {headVertAlgId} {elemSetId} {packSetId} {covSetId} {reducedCost} {totalCost}\n")
            resConsumption = arcs_info[arcId][1]
            
            f.write(f"{resConsumption}\n")
            nbInMemoryOfElemSets = 0
            f.write(f"{nbInMemoryOfElemSets}\n")
            # print(" arcs ", bounds[tailVertAlgId][1], bounds[tailVertAlgId][0], steps[tailVertAlgId])
            nbBuckets = arcs_info[arcId][2]
            f.write(f"1 0 {nbBuckets-1}\n")

        # For cuts
        f.write("# nbCuts\n")
        f.write("# cutId >> cutClass >> curDualVal >> numRows >> fiveOrMoreRowsType >> denominator\n")
        f.write("# packing sets, arc_memory, mem_size -> read memory\n")
        f.write("0\n")

def get_results(inst_id):
    os.makedirs("output", exist_ok=True)
    with open("output/inst" + str(inst_id) + ".out", 'r') as f:
        for line in f:
            if "RCSP solver solution with cost " in line:
                return True, float(line.split(":")[0].split("cost")[-1])
    return False, 0.0

def run_one_instance(inst_id, nb_verts, density):
    verts_info, arcs, arcs_info = generate_inst(nb_verts, density)
    generate_file(verts_info, arcs, arcs_info, 0.0, "data/inst" + str(inst_id) + ".txt")
    call("./rcsp_solver data/inst" + str(inst_id) + ".txt > output/inst" + str(inst_id) + ".out", shell=True)
    feas, cost = get_results(inst_id)
    print("Feasible: ", feas, " Cost: ", cost)

    

run_one_instance(1, 6, 0.5)
