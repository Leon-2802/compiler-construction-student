from assembly.common import *
from assembly.graph import Graph
import assembly.tac_ast as tac


# 1. Note the process for translating WASM to TAC to MIPS assembly in simple words
# 2. Draw pipeline
# 3. Then focus on the indivual steps of the pipeline

# Testing:
# scripts/run-tests -k test_liveStart (call function names of test_liveness.py)

def instrDef(instr: tac.instr) -> set[tac.ident]:
    """
    Returns the set of identifiers defined by some instrucution.
    """
    match instr:
        case tac.Assign(x, _):
            return {x}
        case tac.Call(var, tac.Ident('$input_i64'), _):
            if var is not None:
                return set({var})
            else:
                return set()
        case _:
            return set()

def instrUse(instr: tac.instr) -> set[tac.ident]:
    """
    Returns the set of identifiers used by some instrucution.
    """
    match instr:
        case tac.Assign(_, e):
            return getExpIdents(e)
        case tac.Call(_, tac.Ident('$print_i64'), args):
            primSet: set[tac.ident] = set()
            for p in args:
                pIdent = getPrimIdent(p)
                if pIdent != tac.Ident(''):
                    primSet.add(pIdent)
            return primSet
        case tac.GotoIf(prim, _):
            return set({getPrimIdent(prim)})
        case _:
            return set()

def getExpIdents(e: tac.exp) -> set[tac.ident]:
    match e:
        case tac.Prim(p):
            primSet: set[tac.ident] = set()
            primIdent = getPrimIdent(p)
            if primIdent != tac.Ident(''):
                primSet.add(primIdent)
            return primSet
        case tac.BinOp(left, _, right):
            combinedSet: set[tac.ident] = set()
            leftIdent = getPrimIdent(left)
            rightIdent = getPrimIdent(right)
            if leftIdent != tac.Ident(''):
                combinedSet.add(leftIdent)
            if rightIdent != tac.Ident(''):
                combinedSet.add(rightIdent)
            return combinedSet

def getPrimIdent(p: tac.prim) -> tac.ident:
    match p:
        case tac.Name(v):
            return v
        case tac.Const(v):
            return tac.Ident('')
            
# Each individual instruction has an identifier. This identifier is the tuple
# (index of basic block, index of instruction inside the basic block)
type InstrId = tuple[int, int]

class InterfGraphBuilder:
    def __init__(self):
        # self.before holds, for each instruction I, to set of variables live before I.
        self.before: dict[InstrId, set[tac.ident]] = {}
        # self.after holds, for each instruction I, to set of variables live after I.
        self.after: dict[InstrId, set[tac.ident]] = {}

    def liveStart(self, bb: BasicBlock, s: set[tac.ident]) -> set[tac.ident]:
        """
        Given a set of variables s and a basic block bb, liveStart computes
        the set of variables live at the beginning of bb, assuming that s
        are the variables live at the end of the block.

        Essentially, you have to implement the subalgorithm "Computing L_start" from
        slide 46 here. You should update self.after and self.before while traversing
        the instructions of the basic block in reverse.
        """
        n: int = len(bb.instrs)
        for i in range(n - 1, -1, -1):
            instrId: InstrId = (bb.index, i)
            instr: tac.instr = bb.instrs[i]

            # Update self.after and self.before
            if i == n - 1:
                self.after[instrId] = s
            else:
                self.after[instrId] = self.before.get((bb.index, i + 1), set())

            self.before[instrId] = (self.after[instrId] - (instrDef(instr))).union(instrUse(instr))

        
        l_start: set[tac.ident] = self.before.get((bb.index, 0), set())
        return l_start


    def liveness(self, g: ControlFlowGraph):
        """
        This method computes liveness information and fills the sets self.before and
        self.after.

        You have to implement the algorithm for computing liveness in a CFG from
        slide 46 here.
        """
        # Initialize IN[B] = ∅ for all vertices B of the CFG
        insets: dict[int, set[tac.ident]] = {v: set() for v in g.vertices}

        changes: bool = True
        while changes == True:
            changes = False
            for v in g.vertices:
                out: set[tac.ident] = set()
                for w in g.succs(v):
                    out = out.union(insets[w])
                x = self.liveStart(g.getData(v), out)
                if x != insets[v]:
                    changes = True
                insets[v] = x


    def __addEdgesForInstr(self, instrId: InstrId, instr: tac.instr, interfG: InterfGraph):
        """
        Given an instruction and its ID, adds the edges resulting from the instruction
        to the interference graph.

        You should implement the algorithm specified on the slide
        "Computing the interference graph" (slide 50) here.
        """

        # Check if the instruction is a move operation
        moveInstr = None
        isMoveOperation: bool = isinstance(instr, tac.Assign) and isinstance(instr.right, tac.Name)
        if isMoveOperation == True:
            moveInstr = next(iter(instrUse(instr)))

        # get x
        set_x: set[tac.ident] = instrDef(instr)
        if set_x:
            # Get y
            set_y: set[tac.ident] = self.after.get(instrId, set())
            if set_y:
                # For every ident x in set of idents
                for xVar in set_x:
                    # For every ident y in set of idents
                    for yVar in set_y:
                        # If x and y are different and live at the same time, add an edge
                        if xVar != yVar:
                            interfG.addEdge(xVar, yVar)
                        # If the instruction is a move operation, check if yVar equals the move instruction
                        if isMoveOperation and yVar == moveInstr:
                            # skip, bc xVar and yVar share the same register
                            continue

        #test/test_liveness.py:133: in interfGraphTest
    #pytest.fail(f'Expected conflict {c} not in interference graph. realConflicts={realConflicts}')
    #E   Failed: Expected conflict ('$c', '$n') not in interference graph. realConflicts=[('$c', '$i'), ('$i', '$c')]

    def build(self, g: ControlFlowGraph) -> InterfGraph:
        """
        This method builds the interference graph. It performs three steps:

        - Use liveness to fill the sets self.before and self.after.
        - Setup the interference graph as an undirected graph containing all variables
          defined or used by any instruction of any basic block. Initially, the
          graph does not have any edges.
        - Use __addEdgesForInstr to fill the edges of the interference graph.
        """

        # fill sets self.before and self.after
        self.liveness(g)
        
        # init set with all variables
        allVars: set[tac.ident] = set()
        # init interference graph
        interfG: InterfGraph = Graph[tac.ident, None]('undirected')

        # for each set of idents in self.after and self.before
        for identSet in self.after.values():
            # update set with union of itself and set of idents
            allVars.update(identSet)
        
        for identSet in self.before.values():
            # update set with union of itself and set of idents
            allVars.update(identSet)

        # make sure no variables are missing
        for bb in g.values:
            # for every instruction in the basic block
            for instr in bb.instrs:
                # update variables set
                allVars.update(instrDef(instr))
                allVars.update(instrUse(instr))

        # for all unique variables defined or used by any instruction of any block
        for var in allVars:
            # add vertex
            interfG.addVertex(var, None)
        
        # for every vertex (= basic block)
        for bb in g.values:
            for i, instr in enumerate(bb.instrs):
                # add edges
                self.__addEdgesForInstr((bb.index, i), instr, interfG)

        return interfG

def buildInterfGraph(g: ControlFlowGraph) -> InterfGraph:
    builder = InterfGraphBuilder()
    return builder.build(g)