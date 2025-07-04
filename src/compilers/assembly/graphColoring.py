from assembly.common import *
import assembly.tac_ast as tac
import common.log as log
from common.prioQueue import PrioQueue

def chooseColor(x: tac.ident, forbidden: dict[tac.ident, set[int]]) -> int:
    """
    Returns the lowest possible color for variable x that is not forbidden for x.
    """
    # start with the smallest color
    color = 0
    # find the smallest color not in the forbidden set for x
    while color in forbidden.get(x, set()):
        color += 1
    return color



def getAdjacent(u: tac.ident, g: InterfGraph) -> set[tac.ident]:
    """
    Returns the vertices that have an edge in common with u
    """
    adjacentVertices: set[tac.ident] = set()
    for e in g.edges:
        # check if the vertex u appears in the edge
        if u in e:
            # add the other vertex from the edge as an adjacent vertex
            if u == e[0]:
                adjacentVertices.add(e[1])
            elif u == e[1]:
                adjacentVertices.add(e[0])
    return adjacentVertices

def colorInterfGraph(g: InterfGraph, secondaryOrder: dict[tac.ident, int]={},
                     maxRegs: int=MAX_REGISTERS) -> RegisterMap:
    """
    Given an interference graph, computes a register map mapping a TAC variable
    to a TACspill variable. You have to implement the "simple graph coloring algorithm"
    from slide 58 here.

    - Parameter maxRegs is the maximum number of registers we are allowed to use.
    - Parameter secondaryOrder is used by the tests to get deterministic results even
      if two variables have the same number of forbidden colors.
    """
    log.debug(f"Coloring interference graph with maxRegs={maxRegs}")
    colors: dict[tac.ident, int] = {}
    forbidden: dict[tac.ident, set[int]] = {}
    q = PrioQueue(secondaryOrder)

    for v in g.vertices:
        # intialize the priority queue with each vertex having priority 0
        q.push(v, 0)
        # populate forbidden key dictionary with empty set for each vertex
        forbidden.update({v: set()})

    # Process each vertex in the priority queue
    while not q.isEmpty():
        # q.pop() returns the vertex of the interferenceGraph with the highest priority
        u = q.pop()
        # Choose the smallest available color for u
        color = chooseColor(u, forbidden)
        if color < maxRegs:
            # store color of vertex
            colors.update({u: color})
            # Update forbidden colors for adjacent vertices
            for v in getAdjacent(u, g):
                forbidden[v].add(color)
                # ! update priority for the adjacent variables
                q.incPrio(v, len(forbidden[v]))
        else:
            # If no color is available within maxRegs, spill this variable
            colors.update({u: (maxRegs+1)})  # Indicates that the variable needs to be spilled

    m = RegisterAllocMap(colors, maxRegs)
    return m
