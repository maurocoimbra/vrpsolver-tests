import math
from typing import Mapping, Union, Set, List, Tuple, Dict, Any

GraphAdj = Mapping[str, Union[Set[str], List[str], Tuple[str, ...]]]

class RCSP:

  def __init__(self, arcs, resource_cost, costs, lb, ub, ng_set, source, sink, big_m = 100):
    self.arcs = arcs
    self.resource_cost = resource_cost
    self.costs = costs
    self.lb = lb
    self.ub = ub
    self.ng_set = ng_set
    self.source = source
    self.sink = sink

    self.M = big_m

    # vão ser preenchidos quando você chamar replicate_graph_complete()
    self.new_arcs: Dict[str, Set[str]] = {}
    self.new_costs: Dict[str, Dict[str, Any]] = {}
    self.new_resource_cost: Dict[str, Dict[str, Any]] = {}
    self.new_lb: Dict[str, Any] = {}
    self.new_ub: Dict[str, Any] = {}
    self.rep: Dict[str, list[str]] = {}

  def delta_minus(self, arcs, objective):
    result = []
    for i, v in arcs.items():
      for j in v:
        if j == objective:
          result.append(i)
    return result

  def delta_plus(self, arcs, objective):
    result = []
    for i, v in arcs.items():
      for j in v:
        if i == objective:
          result.append(j)
    return result

  def check_original(self, objective):
    for i,v in self.rep.items():
      for j in v:
        if j == objective:
          return i

  def calculate_clones(self):
    # soma do menor custo de entrada e menor custo de saída por nó
    d = dict()

    for arc in self.arcs:
      if arc == self.source or arc == self.sink:
        continue

      min_in = self.M
      enter = self.delta_minus(self.arcs, arc)
      for i in enter:
        min_in = min(min_in, self.resource_cost[i][arc])

      min_out = self.M
      exit = self.delta_plus(self.arcs, arc)
      for i in exit:
        min_out = min(min_out, self.resource_cost[arc][i])

      d[arc] = max(math.ceil(self.ub[arc] / (min_in + min_out)), 1)

    return d

  from typing import Dict, List, Tuple

  def replicate_graph_complete(self):
    clone_counts = self.calculate_clones()

    # 1) Ordem original dos nós: a ordem de inserção das chaves do dict é estável em Python 3.7+
    nodes: List[str] = list(self.arcs.keys())
    node_order = {n: i for i, n in enumerate(nodes)}  # pra ordenar vizinhos de forma determinística

    # internos na ordem original
    internal = [v for v in nodes if v not in {self.source, self.sink}]

    # mapeia nó original -> lista de réplicas (ou ele mesmo p/ source/sink)
    rep: Dict[str, List[str]] = {self.source: [self.source], self.sink: [self.sink]}
    for v in internal:
      k = clone_counts.get(v, 1)
      rep[v] = [f"{v}{i}" for i in range(1, k + 1)]

    # 2) new_nodes em lista, preservando ordem:
    #    source, depois internos (com suas réplicas), depois sink (se existirem nessa ordem no nodes, melhor respeitar nodes)
    new_nodes: List[str] = []
    for v in nodes:
      new_nodes.extend(rep[v])

    # 3) cria estruturas novas preservando ordem de iteração
    self.new_arcs = {v: [] for v in new_nodes}           # lista para manter ordem dos vizinhos
    self.new_costs = {v: {} for v in new_nodes}
    self.new_resource_cost = {v: {} for v in new_nodes}
    self.new_lb = {}
    self.new_ub = {}
    self.rep = rep

    # bounds (ordem estável)
    for v in nodes:
      for rv in rep[v]:
        self.new_lb[rv] = self.lb[v]
        self.new_ub[rv] = self.ub[v]

    # helper: adiciona aresta preservando ordem e sem duplicar
    def add_arc(ru: str, rv: str, u: str, v: str):
      # evita duplicata mantendo lista (O(d)), mas mantém ordem
      if rv not in self.new_arcs[ru]:
        self.new_arcs[ru].append(rv)
      self.new_costs[ru][rv] = self.costs[u][v]
      self.new_resource_cost[ru][rv] = self.resource_cost[u][v]

    # helper: iteração de vizinhos com ordem determinística
    def iter_neighbors(u: str):
      neigh = self.arcs.get(u, [])
      if isinstance(neigh, (list, tuple)):
        return neigh
      # se for set (ou qualquer iterável sem ordem), ordenar pelo node_order
      return sorted(neigh, key=lambda x: node_order.get(x, 10**9))

    # arestas na ordem dos nós + ordem dos vizinhos
    for u in nodes:
      for v in iter_neighbors(u):
        pairs: List[Tuple[str, str]] = []

        if u == self.source and v not in {self.source, self.sink}:
          pairs = [(self.source, rv) for rv in rep[v]]

        elif v == self.sink and u not in {self.source, self.sink}:
          pairs = [(ru, self.sink) for ru in rep[u]]

        elif u not in {self.source, self.sink} and v not in {self.source, self.sink}:
          pairs = [(ru, rv) for ru in rep[u] for rv in rep[v]]

        else:
          pairs = [(ru, rv) for ru in rep[u] for rv in rep[v]]

        for ru, rv in pairs:
          add_arc(ru, rv, u, v)