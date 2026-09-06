#include "rcsp_data.hpp"
#include "rcsp_interface.hpp"
#include <fstream>
#include <iostream>
#include <memory>
#include <ostream>
#include <sstream>
#include <string>
#include <cstring>
#include <utility>
#include <vector>

struct Vertex {
  int id;
  double cons_lb, cons_ub;
  std::vector<int> ng_set;
};

struct Arc {
  int id;
  double cons;
  double cost;
  int tailVertexId;
  int headVertexId;
};

struct Graph {
  std::vector<Vertex> vertices;
  std::vector<Arc> arcs;
};

int runPricing_cpp(bcp_rcsp::SolverInterface *solver, bcp_rcsp::SolverInput &si,
                   bcp_rcsp::SolverOutput *&solver_output,
                   int *nb_output_arcs) {
  solver_output = new bcp_rcsp::SolverOutput();
  *nb_output_arcs = 0;
  if (solver->runPricing(si, *solver_output) &&
      !solver_output->solPts.empty()) {
    for (auto &p : solver_output->solPts)
      *nb_output_arcs += (int)p->arcIds.size();
    return (int)solver_output->solPts.size();
  } else {
    for (auto &p : solver_output->solPts)
      delete p;
    return 0;
  }
}

int runPricing(Graph &graph) {

  int res_id = 0;
  int src_id = 0;
  int snk_id = graph.vertices.size() - 1;

  std::vector<std::unique_ptr<bcp_rcsp::ResourceConstParameters>> resources;
  resources.push_back(
      std::make_unique<bcp_rcsp::StandardMainResourceConstParameters>(res_id,
                                                                      1.0));
  bcp_rcsp::GraphData *g = new bcp_rcsp::GraphData(0, std::move(resources),
                                                   graph.vertices.size() - 2);
  g->sourceVertexId = src_id;
  g->sinkVertexId = snk_id;

  // creating vertices
  for (auto &vertex : graph.vertices) {

    g->vertices.push_back(g->createVertexData(vertex.id));
    bcp_rcsp::VertexData &rcsp_vertex_data = g->vertices[vertex.id];
    rcsp_vertex_data.setResourceParams(
        res_id, new bcp_rcsp::StandardResourceVertexParameters(vertex.cons_lb,
                                                               vertex.cons_ub));
    if (vertex.id != src_id && vertex.id != snk_id) {
      rcsp_vertex_data.elemSetIds.push_back(vertex.id - 1);
      for (int neighbor : vertex.ng_set)
        rcsp_vertex_data.ngNeighbourhood.push_back(neighbor - 1);
    }
  }

  // creating arcs
  std::vector<double> arcid_to_redcost;
  int arcId = 0;
  for (auto &arc : graph.arcs) {
    g->arcs.push_back(g->createArcData(arcId));
    bcp_rcsp::ArcData &rcsp_arc_data = g->arcs[arcId];
    rcsp_arc_data.tailVertexId = arc.tailVertexId;
    rcsp_arc_data.headVertexId = arc.headVertexId;
    rcsp_arc_data.setResourceParams(
        res_id, new bcp_rcsp::StandardResourceArcParameters(arc.cons));
    rcsp_arc_data.varIdToCostAndCoeff[arc.id] = std::make_pair(arc.cost, 1.0);
    arcid_to_redcost.push_back(arc.cost);

    arcId++;
  }

  // running the pricing solver
  g->generatePreprocessedInfo();
  bcp_rcsp::SolverParameters params;
  params.maxNumOfLabelsInEnumeration = 0;
  params.printLevel = 0;
  params.maxNumOfColsPerExactIteration = 50;
  bcp_rcsp::Data data(*g, params);
  bcp_rcsp::SolverInterface *si = createAndPrepareMetaSolver(data);
  int nbVars = graph.arcs.size();
  bcp_rcsp::SolverInput sin(nbVars);
  sin.colGenPhase = 0; // exact pricing
  memcpy(&sin.varRedCosts[0], &arcid_to_redcost[0], nbVars * sizeof(double));
  bcp_rcsp::SolverOutput *output;
  int nb_out_arcs = 0;
  std::cout << "Running the pricing solver..." << std::endl;
  int nb_paths = runPricing_cpp(si, sin, output, &nb_out_arcs);
  std::cout << "Returned " << nb_paths << " paths with " << nb_out_arcs
            << " arcs" << std::endl;

  std::vector<std::vector<int>> pathsFound; // each path is a vector of arc ids
  for (bcp_rcsp::Solution *sol : output->solPts) {

    std::vector<int> path;
    for (auto arcId : sol->arcIds) {
      path.push_back(g->arcs[arcId].tailVertexId);
    }
    int lastArcId = sol->arcIds.back();
    path.push_back(g->arcs[lastArcId].headVertexId);

    pathsFound.push_back(path);

    std::cout << "path: ";
    for (auto vert : path) {
      std::cout << vert << " ";
    }
    std::cout << "\n";
    std::cout << "accumulated consumptions: ";
    for (auto cons :
         sol->getResourceSolution<bcp_rcsp::StandardResourceSolution>(res_id)
             ->consumption) {
      std::cout << cons << " ";
    }
    std::cout << "\n";
    std::cout << "reduced cost:" << si->computeReducedCost(*sol, sin)
              << std::endl;
    return 0; // Print only the first path
  }

  return 0;
}

Graph readInstance(const std::string &filepath) {
  Graph graph;
  std::ifstream file(filepath);
  if (!file.is_open()) {
    std::cerr << "Error: could not open file " << filepath << std::endl;
    std::exit(1);
  }

  std::string line;
  int nbVertices, nbArcs, source, sink;

  while (std::getline(file, line)) {
    if (line.empty() || line[0] == '#')
      continue;
    std::istringstream iss(line);
    iss >> nbVertices >> nbArcs >> source >> sink;
    break;
  }

  // skip comment line before nodes
  while (std::getline(file, line)) {
    if (line.empty() || line[0] == '#')
      continue;
    break;
  }

  // first non-comment line is already a node line
  for (int i = 0; i < nbVertices; i++) {
    if (i > 0) {
      std::getline(file, line);
      while (line.empty() || line[0] == '#')
        std::getline(file, line);
    }
    std::istringstream iss(line);
    Vertex v;
    iss >> v.id >> v.cons_lb >> v.cons_ub;
    graph.vertices.push_back(v);
  }

  // skip comment line before arcs
  while (std::getline(file, line)) {
    if (line.empty() || line[0] == '#')
      continue;
    break;
  }

  // first non-comment line is already an arc line
  for (int i = 0; i < nbArcs; i++) {
    if (i > 0) {
      std::getline(file, line);
      while (line.empty() || line[0] == '#')
        std::getline(file, line);
    }
    std::istringstream iss(line);
    Arc a;
    iss >> a.id >> a.tailVertexId >> a.headVertexId >> a.cost >> a.cons;
    graph.arcs.push_back(a);
  }

  file.close();
  return graph;
}

int main(int argc, char *argv[]) {
  if (argc < 2) {
    std::cerr << "Usage: " << argv[0] << " <instance_file>" << std::endl;
    return 1;
  }

  Graph graph = readInstance(argv[1]);

  std::cout << "Read " << graph.vertices.size() << " vertices and "
            << graph.arcs.size() << " arcs" << std::endl;

  return runPricing(graph);
}
