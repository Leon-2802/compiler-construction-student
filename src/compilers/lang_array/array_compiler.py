from common.wasm import *
from lang_array.array_astAtom import *
import lang_array.array_ast as plainAst
import lang_array.array_tychecker as array_tychecker
import lang_array.array_transform as array_transform
from lang_array.array_compilerSupport import *
from common.compilerSupport import *
# import common.utils as utils


cfg_global: CompilerConfig;

def compileModule(m: plainAst.mod, cfg: CompilerConfig) -> WasmModule:
    """
    Compiles the given module.
    """
    vars = array_tychecker.tycheckModule(m)
    ctx = array_transform.Ctx()
    global cfg_global
    cfg_global = cfg
    stmtsAtom = array_transform.transStmts(m.stmts, ctx)
    instrs = compileStmts(stmtsAtom)
    idMain = WasmId('$main')
    locals: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(x), mapVarType(i.ty)) for x,i in vars.items()]
    locals.extend(Locals.decls())
    locals.extend([(identToWasmId(x), mapVarType(i)) for x,i in ctx.freshVars.items()])
    return WasmModule(imports=wasmImports(cfg.maxMemSize),
        exports=[WasmExport("main", WasmExportFunc(idMain))],
        globals=Globals.decls(),
        data=Errors.data(),
        funcTable=WasmFuncTable([]),
        funcs=[WasmFunc(idMain, [], None, locals, instrs)])



def compileStmts(stmts: list[stmt]) -> list[WasmInstr]:
    wasmInstructs: list[WasmInstr] = []
    loop_counter: dict[str, int] = {}
    for s in stmts:
         a = matchType(s, loop_counter)
         wasmInstructs.extend(a)
    return wasmInstructs
        

def matchType(s: stmt, loop_counter: dict[str, int]) -> list[WasmInstr]:
    wasmInstructs: list[WasmInstr] = []
    match s:
        case StmtExp(e):
            wasmInstructs.extend(compileExp(e))
        case IfStmt(cond, thenBody, elseBody):
            wasmInstructs.extend(compileIfStmt(cond, thenBody, elseBody))
        case WhileStmt(cond, body):
            wasmInstructs.extend(compileWhileStmt(cond, body, loop_counter))
        case SubscriptAssign(_left, _index, _right):
            #TODO Check that i is not out-of-bounds
            # Compute address of element at index i
            # Store value
            pass
            
        case Assign(x, e):
            wasmInstructs.extend(compileExp(e))
            wasmInstructs.append(WasmInstrVarLocal("set", identToWasmId(x)))

    return wasmInstructs


def compileExp(exp: exp) -> list[WasmInstr]:
    wasmInstructs: list[WasmInstr] = []
    match exp:
        case AtomExp(e):
            wasmInstructs.extend(compileAtomExp(e))
        case Call(name, args):
            #TODO call in relation to array? See Typing Rules -> Expressions for Larray
            if name.name == "len": # len is compiled seperately, as it is not a default Wasm function
                for arg in args:
                    wasmInstructs.extend(compileExp(arg))
                wasmInstructs.extend(arrayLenInstrs())  # Get length of array
            else:
                wasmInstructs.extend(compileCall(name, args))
        case UnOp(op, arg):
            wasmInstructs.extend(compileUnaryOp(op, arg))
        case BinOp(left, op, right):
            wasmInstructs.extend(compileBinaryOp(left, op, right))
        case ArrayInitStatic(elemInit):
            elemInitTy: ty = elemInit[0].ty if elemInit[0].ty is not None else Int()  # Default to Int if no type is given
            # compute the length of the array:
            itemsCount: int = 0
            for item in elemInit:
                if item.ty is not None:
                    if item.ty != elemInitTy:
                        raise ValueError(f"All elements in ArrayInitStatic must have the same type, but found {item.ty} and {elemInitTy}")
                itemsCount += 1
            len: atomExp = IntConst(itemsCount, elemInitTy)  # Length of the array is the number of elements in elemInit
            compileInitArray(len, elemInitTy, cfg_global) # Initialize the array -> address of the array is on top of stack
            #TODO set each element individually
            pass
        case ArrayInitDyn(len, elemInit):
            elemInitTy: ty = elemInit.ty if elemInit.ty is not None else Int()  # Default to Int if no type is given
            compileInitArray(len, elemInitTy, cfg_global) # Initialize the array -> address of the array is on top of stack
            #TODO set all elements to the same value
            pass
        case Subscript(array, index):
            #TODO check if index in bounds using arrayLenInstrs()
            # Check that i is not out-of-bounds
            # Compute address of element at index i
            # Read from memory
            wasmInstructs.extend(arrayOffsetInstrs(array, index))

    return wasmInstructs

# if and while: --------------------------------------------------------------------------
def compileIfStmt(cond: exp, thenBody: list[stmt], elseBody: list[stmt]) -> list[WasmInstr]:
    wasmInstructs: list[WasmInstr] = []
    wasmInstructs.extend(compileExp(cond))
    thenBodyInstr: list[WasmInstr] = compileStmts(thenBody) 
    elseBodyInstr: list[WasmInstr] = compileStmts(elseBody)
    wasmInstructs.append(WasmInstrIf(None, thenBodyInstr, elseBodyInstr))
    return wasmInstructs

def compileWhileStmt(cond: exp, body: list[stmt], loop_counter: dict[str, int]) -> list[WasmInstr]:
    wasmInstructs: list[WasmInstr] = []
    loop_start_label: str = generateUniqueLabel('$loop_start', loop_counter)
    loop_exit_label: str = generateUniqueLabel('$loop_exit', loop_counter)
    blockBodyInstr: list[WasmInstr] = []
    loopBodyInstr: list[WasmInstr] = []

    # Compile the condition
    loopBodyInstr.extend(compileExp(cond))

    # Compile the body of the loop
    ifBodyInstr: list[WasmInstr] = compileStmts(body)
    ifBodyInstr.append(WasmInstrBranch(WasmId(loop_start_label), False))

    # Handle the else body (exit the loop)
    elseBodyInstr: list[WasmInstr] = [WasmInstrBranch(WasmId(loop_exit_label), False)]

    # Assemble the loop body instructions
    loopBodyInstr.append(WasmInstrIf(None, ifBodyInstr, elseBodyInstr))
    blockBodyInstr.append(WasmInstrLoop(WasmId(loop_start_label), loopBodyInstr))

    # Assemble the block body instructions
    wasmInstructs.append(WasmInstrBlock(WasmId(loop_exit_label), None, blockBodyInstr))
    return wasmInstructs

# ----------------------------------------------------------------------------------------



# Array specific: -------------------------------------------------------------------------

def compileInitArray(lenExp: atomExp, elemTy: ty, cfg: CompilerConfig) -> list[WasmInstr]:
    """
    Generates code to initialize an array without initializing the elements.
    Leaves the address of the array on top of stack.
    """
    wasmInstructs: list[WasmInstr] = []

    wasmInstructs.extend(compileAtomExp(lenExp)) # compile length expression
    wasmInstructs.append(WasmInstrConvOp('i64.extend_i32_u')) #TODO convert to i64 may be unnecessary
    wasmInstructs.append(WasmInstrVarLocal("set", WasmId('$n'))) # store length in local variable $n


    # check length: length must be between zero and max array size -> construct if-condition:
    ifCond: list [WasmInstr] = []
    ifCond.append(WasmInstrVarLocal("get", WasmId('$n'))) # get length of array from local variable $n
    ifCond.append(WasmInstrConst('i32', 0))
    ifCond.append(WasmInstrIntRelOp('i32', 'gt_s')) # -> check > 0
    # store check for <= maxLength seperately...
    right: list[WasmInstr] = []
    right.append(WasmInstrVarLocal("get", WasmId('$n'))) # get length of array from local variable $n
    right.append(WasmInstrConst('i32', cfg.maxArraySize))
    right.append(WasmInstrIntRelOp('i32', 'le_s')) # -> check <= maxArraySize
    ifCond.append(WasmInstrIf('i32', right, [WasmInstrConst('i32', 0)])) # connect both checks with AND
    wasmInstructs.extend(ifCond) # put if condition on top of stack

    # Add if and else body instructions for error case
    thenInstr: list[WasmInstr] = []
    thenInstr.append(WasmInstrConst('i32', 0))
    thenInstr.append(WasmInstrConst('i32', 14))
    thenInstr.append(WasmInstrCall(WasmId('$print_err')))
    thenInstr.append(WasmInstrTrap()) # = unreachable -> stop execution
    elseInstr: list[WasmInstr] = []
    wasmInstructs.append(WasmInstrIf('i32', thenInstr, elseInstr))
    
    # Compute header: 
    wasmInstructs.append(WasmInstrVarGlobal("get", Globals.freePtr)) # save old value $@free_ptr (address of the array on top of stack)
    wasmInstructs.extend(arrayLenInstrs()) # get length of array
    if isinstance(elemTy, Array):
        m: Literal[3, 1] = 3
    else:
        m: Literal[3, 1] = 1
    wasmInstructs.extend(computeHeader(m)) 
    wasmInstructs.append(WasmInstrMem('i32', 'store')) # store header in memory

    # Move free_ptr and return array address
    wasmInstructs.append(WasmInstrVarGlobal("get", Globals.freePtr)) # move free_ptr
    wasmInstructs.extend(arrayLenInstrs()) # get length of array
    wasmInstructs.append(WasmInstrConvOp('i32.wrap_i64')) # convert to i32
    if (isinstance(elemTy, Int)):
        wasmInstructs.append(WasmInstrConst('i32', 8)) # 8 bytes for Int -> i64
    else:
        wasmInstructs.append(WasmInstrConst('i32', 4)) # 4 bytes for Bools or Arrays
    wasmInstructs.append(WasmInstrNumBinOp('i32', 'mul')) # multiply length by size of element type
    wasmInstructs.append(WasmInstrConst('i32', 4)) # add 4 bytes for header
    wasmInstructs.append(WasmInstrNumBinOp('i32', 'add')) # add length to free_ptr
    wasmInstructs.append(WasmInstrVarGlobal("get", Globals.freePtr)) # get address of the array
    wasmInstructs.append(WasmInstrNumBinOp('i32', 'add')) # add the space required by the array to $@free_ptr
    wasmInstructs.append(WasmInstrVarGlobal("set", Globals.freePtr)) # save new $@free_pt
    # -> now the old value of $@free_ptr (the array address) is on top of stack.

    return wasmInstructs

def arrayLenInstrs() -> list[WasmInstr]:
    """
    Generates code that expects the array address on top of stack and puts the length on top of stack
    """
    wasmInstructs: list[WasmInstr] = []
    wasmInstructs.append(WasmInstrMem('i32', 'load')) # load array header
    wasmInstructs.append(WasmInstrConst('i32', 4))
    wasmInstructs.append(WasmInstrNumBinOp('i32', 'shr_u')) # shift right by 4 bit to get the length
    wasmInstructs.append(WasmInstrConvOp('i64.extend_i32_u')) # convert to i64
    return wasmInstructs

def arrayOffsetInstrs(arrayExp: atomExp, indexExp: atomExp) -> list[WasmInstr]:
    #Returns instructions that places the memory offset for a certain array element on top of stack.
    wasmInstructs: list[WasmInstr] = []
    #TODO logic here
    return wasmInstructs

# ---------------------------------------------------------------------------------------------

def compileAtomExp(ae: atomExp) -> list[WasmInstr]:
    wasmInstructs: list[WasmInstr] = []
    match ae:
        case IntConst(val):
            wasmInstructs.append(WasmInstrConst('i64', val))
        case BoolConst(val):
            boolToNumericalVal: int = 0
            if val == True:
                boolToNumericalVal = 1
            wasmInstructs.append(WasmInstrConst('i32', boolToNumericalVal))
        case Name(val):
            wasmInstructs.append(WasmInstrVarLocal("get", identToWasmId(val)))
    return wasmInstructs


def compileCall(name: ident, args: list[exp]) -> list[WasmInstr]:
    wasmInstructs: list[WasmInstr] = []
    isBool: bool = any(mapVarType(tyOfExp(arg)) == 'i32' for arg in args)
    for arg in args:
        wasmInstructs.extend(compileExp(arg))
    if isBool == True:
        wasmInstructs.append(WasmInstrCall(boolIdentToWasmId(name)))
    else:
        wasmInstructs.append(WasmInstrCall(intIdentToWasmId(name)))
    return wasmInstructs


def compileUnaryOp(op: unaryop, arg: exp) -> list[WasmInstr]:
    wasmInstructs: list[WasmInstr] = []
    match op:
        case USub():
            wasmInstructs.append(WasmInstrConst('i64', 0))
            wasmInstructs.extend(compileExp(arg))
            wasmInstructs.append(WasmInstrNumBinOp('i64', 'sub'))
        case Not():
            wasmInstructs.extend(compileExp(arg))
            wasmInstructs.append(WasmInstrConst('i32', 1))
            wasmInstructs.append(WasmInstrNumBinOp('i32', 'xor'))

    return wasmInstructs


def compileBinaryOp(left: exp, op: binaryop, right: exp) -> list[WasmInstr]:
    wasmInstructs: list[WasmInstr] = []
    match op:
        case Add():
            wasmInstructs.extend(compileExp(left))
            wasmInstructs.extend(compileExp(right))
            wasmInstructs.append(WasmInstrNumBinOp('i64', 'add')) 
        case Sub():
            wasmInstructs.extend(compileExp(left))
            wasmInstructs.extend(compileExp(right))
            wasmInstructs.append(WasmInstrNumBinOp('i64', 'sub')) 
        case Mul():
            wasmInstructs.extend(compileExp(left))
            wasmInstructs.extend(compileExp(right))
            wasmInstructs.append(WasmInstrNumBinOp('i64', 'mul'))
        case And():
            wasmInstructs.extend(compileExp(left))
            wasmInstructs.append(WasmInstrIf('i32', compileExp(right), [WasmInstrConst('i32', 0)]))
        case Or():
            wasmInstructs.extend(compileExp(left))
            wasmInstructs.append(WasmInstrIf('i32', [WasmInstrConst('i32', 1)], compileExp(right)))
        case Less():
            wasmInstructs.extend(compileExp(left))
            wasmInstructs.extend(compileExp(right))
            wasmInstructs.append(WasmInstrIntRelOp('i64', 'lt_s'))
        case LessEq():
            wasmInstructs.extend(compileExp(left))
            wasmInstructs.extend(compileExp(right))
            wasmInstructs.append(WasmInstrIntRelOp('i64', 'le_s'))
        case Greater():
            wasmInstructs.extend(compileExp(left))
            wasmInstructs.extend(compileExp(right))
            wasmInstructs.append(WasmInstrIntRelOp('i64', 'gt_s'))
        case GreaterEq():
            wasmInstructs.extend(compileExp(left))
            wasmInstructs.extend(compileExp(right))
            wasmInstructs.append(WasmInstrIntRelOp('i64', 'ge_s'))
        case Eq():
            if (mapVarType(tyOfExp(left)) != mapVarType(tyOfExp(right))):
                emptyInstr: list[WasmInstr] = []
                return emptyInstr
            else:
                wasmInstructs.extend(compileExp(left))
                wasmInstructs.extend(compileExp(right))
                wasmInstructs.append(WasmInstrIntRelOp(mapVarType(tyOfExp(left)), 'eq')) 
        case NotEq():
            if (mapVarType(tyOfExp(left)) != mapVarType(tyOfExp(right))):
                emptyInstr: list[WasmInstr] = []
                return emptyInstr
            else:
                wasmInstructs.extend(compileExp(left))
                wasmInstructs.extend(compileExp(right))
                wasmInstructs.append(WasmInstrIntRelOp(mapVarType(tyOfExp(left)), 'ne')) 
        case Is():
            #TODO implement logic
            # check if one array is same -> meaning same address
            pass
    return wasmInstructs


def computeHeader(M: int) -> list[WasmInstr]:
    """
    Computes the header for an array in WebAssembly.
    Assumes length is on top of stack.
    The header consists of:
    Length | Kind | Pointer | GC enabled
    """
    wasmInstructs: list[WasmInstr] = []
    wasmInstructs.append(WasmInstrConvOp('i32.wrap_i64'))
    wasmInstructs.append(WasmInstrConst('i32', 4))
    wasmInstructs.append(WasmInstrNumBinOp('i32', 'shl'))  # shift left by 4 bits
    wasmInstructs.append(WasmInstrConst('i32', M))  # kind
    wasmInstructs.append(WasmInstrNumBinOp('i32', 'xor'))  # combine length and kind
    return wasmInstructs



def mapVarType(var_type: ty) -> Literal['i64', 'i32']:
    """
    Maps a variable type from the symbol table to a WebAssembly value type.
    """
    if isinstance(var_type, Int):
        return 'i64'
    else:
        return 'i32'
    
    
def tyOfExp(e: exp) -> ty:
    match e.ty:
        case None:
            raise ValueError('Expression has type None')
        case Void():
            raise ValueError('Expression has type Void')
        case NotVoid(t):
            return t
        
 
def identToWasmId(x: ident) -> WasmId:
    return WasmId('$' + x.name)


def boolIdentToWasmId(x: ident) -> WasmId:
    if x.name == "print":
        return WasmId('$print_bool')
    elif x.name == "input_int":
        return WasmId('$input_i32')
    else:
        return WasmId('$' + x.name)
    
    
def intIdentToWasmId(x: ident) -> WasmId:
    if x.name == "print":
        return WasmId('$print_i64')
    elif x.name == "input_int":
        return WasmId('$input_i64')
    else:
        return WasmId('$' + x.name)   
    

def generateUniqueLabel(prefix: str, counter: dict[str, int]) -> str:
    if prefix not in counter:
        counter[prefix] = 0
    counter[prefix] += 1
    return f"{prefix}_{counter[prefix]}"     