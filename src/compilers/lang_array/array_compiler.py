from common.wasm import *
from lang_array.array_astAtom import *
import lang_array.array_ast as plainAst
import lang_array.array_tychecker as array_tychecker
import lang_array.array_transform as array_transform
from lang_array.array_compilerSupport import *
from common.compilerSupport import *


cfg_global: CompilerConfig;
loop_counter_global: dict[str, int];

def compileModule(m: plainAst.mod, cfg: CompilerConfig) -> WasmModule:
    """
    Compiles the given module.
    """
    vars = array_tychecker.tycheckModule(m)
    ctx = array_transform.Ctx()
    global cfg_global
    cfg_global = cfg
    global loop_counter_global 
    loop_counter_global = {} # initialize storage variable for loop counter
    stmtsAtom = array_transform.transStmts(m.stmts, ctx)
    instrs = compileStmts(stmtsAtom)
    idMain = WasmId('$main')
    locals: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(id), "i64" if type(ty) == Int else "i32") for id,ty in vars.types()]
    freshLocals: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(id), "i64" if type(ty) == Int else "i32") for id,ty in ctx.freshVars.items()]
    locals.extend(freshLocals)
    locals.extend(Locals.decls())
    return WasmModule(imports=wasmImports(cfg.maxMemSize),
        exports=[WasmExport("main", WasmExportFunc(idMain))],
        globals=Globals.decls(),
        data=Errors.data(),
        funcTable=WasmFuncTable([]),
        funcs=[WasmFunc(idMain, [], None, locals, instrs)])



def compileStmts(stmts: list[stmt]) -> list[WasmInstr]:
    wasmInstructs: list[WasmInstr] = []
    for s in stmts:
         a = matchType(s)
         wasmInstructs.extend(a)
    return wasmInstructs
        

def matchType(s: stmt) -> list[WasmInstr]:
    wasmInstructs: list[WasmInstr] = []
    match s:
        case StmtExp(e):
            wasmInstructs.extend(compileExp(e))
        case IfStmt(cond, thenBody, elseBody):
            wasmInstructs.extend(compileIfStmt(cond, thenBody, elseBody))
        case WhileStmt(cond, body):
            condInstr: list[WasmInstr] = compileExp(cond)
            bodyInstr: list[WasmInstr] = compileStmts(body)
            wasmInstructs.extend(compileWhileStmt(condInstr, bodyInstr))
        case SubscriptAssign(left, index, right):
            # check if index in bounds using arrayLenInstrs()
            # recieve address of element at index i on top of stack:
            wasmInstructs.extend(arrayOffsetInstrs(left, index))
            wasmInstructs.extend(compileExp(right)) # compile expression that will be assigned at given index
            # store result at index:
            match right.ty:
                case NotVoid(ty):
                    match ty:
                        case Int():
                            wasmInstructs.append(WasmInstrMem('i64', 'store'))
                        case _:
                            wasmInstructs.append(WasmInstrMem('i32', 'store'))
                case _:
                    raise ValueError()
            
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
            wasmInstructs.extend(compileCall(name, args))
        case UnOp(op, arg):
            wasmInstructs.extend(compileUnaryOp(op, arg))
        case BinOp(left, op, right):
            wasmInstructs.extend(compileBinaryOp(left, op, right))
        case ArrayInitStatic(elemInit):
            wasmInstructs.extend(compileInitArray(IntConst(len(elemInit)), asTy(elemInit[0].ty), cfg_global)) # Initialize the array -> address of the array is on top of stack
            elemsize: int = 8 if asTy(elemInit[0].ty) == Int() else 4
            dType: WasmValtype = "i64" if asTy(elemInit[0].ty) == Int() else "i32"
            # set each element individually:
            for index, elem in enumerate(elemInit): # loop over values that should be used for assignement
                wasmInstructs.append(WasmInstrVarLocal('tee', Locals.tmp_i32)) # set $@tmp_i32 to array address, leave it on top of stack
                wasmInstructs.append(WasmInstrVarLocal('get', Locals.tmp_i32))
                offset: int = 4 + elemsize * index
                wasmInstructs.append(WasmInstrConst('i32', offset)) 
                wasmInstructs.append(WasmInstrNumBinOp('i32', 'add')) # move by offset at given index
                wasmInstructs.extend(compileAtomExp(elem)) # compile value of elem
                wasmInstructs.append(WasmInstrMem(dType, 'store')) # initialize element at given index with value of elem -> address of current index on top of stack

        case ArrayInitDyn(length, elemInit):
            wasmInstructs.extend(compileInitArray(length, asTy(elemInit.ty), cfg_global)) # Initialize the array -> address of the array is on top of stack
            elementSize: int = 8 if asTy(elemInit.ty) == Int() else 4
            dType: WasmValtype = "i64" if asTy(elemInit.ty) == Int() else "i32"
            # set all elements to the same value -> loop to initialize the array elements
            wasmInstructs.append(WasmInstrVarLocal('tee', Locals.tmp_i32)) # set $@tmp_i32 to array address, leave it on top of stack
            wasmInstructs.append(WasmInstrVarLocal('get', Locals.tmp_i32))
            wasmInstructs.append(WasmInstrConst('i32', 4))
            wasmInstructs.append(WasmInstrNumBinOp('i32', 'add')) 
            wasmInstructs.append(WasmInstrVarLocal('set', Locals.tmp_i32)) # set $@tmp_i32 to the first array element
            # set up while loop for initialization:
            loopCond: list[WasmInstr] = []
            loopCond.append(WasmInstrVarLocal('get', Locals.tmp_i32))
            loopCond.append(WasmInstrVarGlobal('get', Globals.freePtr))
            loopCond.append(WasmInstrIntRelOp('i32', 'lt_u')) # compare against end of array
            bodyInstr: list[WasmInstr] = []
            bodyInstr.append(WasmInstrVarLocal('get', Locals.tmp_i32))
            bodyInstr.extend(compileAtomExp(elemInit)) # compile expression for the initial value
            bodyInstr.append(WasmInstrMem(dType, 'store')) # initialize array element
            bodyInstr.append(WasmInstrVarLocal('get', Locals.tmp_i32))
            bodyInstr.append(WasmInstrConst('i32', elementSize)) # 4 bytes for Bools or Arrays
            bodyInstr.append(WasmInstrNumBinOp('i32', 'add')) # add size of array element
            bodyInstr.append(WasmInstrVarLocal('set', Locals.tmp_i32)) # set $@tmp_i32 to next array element
            # wrap in while loop:
            wasmInstructs.extend(compileWhileStmt(loopCond, bodyInstr)) 

        case Subscript(array, index):
            # check if index in bounds using arrayLenInstrs()
            # recieve address of element at index i on top of stack:
            wasmInstructs.extend(arrayOffsetInstrs(array, index))
            # Read from memory:
            match array.ty:
                case Array(elemTy): 
                    if asTy(elemTy) == Int():
                        wasmInstructs.append(WasmInstrMem("i64","load"))
                    else:
                        wasmInstructs.append(WasmInstrMem("i32","load"))
                case _:
                    raise ValueError()

    return wasmInstructs

# if and while: --------------------------------------------------------------------------
def compileIfStmt(cond: exp, thenBody: list[stmt], elseBody: list[stmt]) -> list[WasmInstr]:
    wasmInstructs: list[WasmInstr] = []
    wasmInstructs.extend(compileExp(cond))
    thenBodyInstr: list[WasmInstr] = compileStmts(thenBody) 
    elseBodyInstr: list[WasmInstr] = compileStmts(elseBody)
    wasmInstructs.append(WasmInstrIf(None, thenBodyInstr, elseBodyInstr))
    return wasmInstructs

def compileWhileStmt(cond: list[WasmInstr], body: list[WasmInstr]) -> list[WasmInstr]:
    wasmInstructs: list[WasmInstr] = []
    loop_start_label: str = generateUniqueLabel('$loop_start')
    loop_exit_label: str = generateUniqueLabel('$loop_exit')
    blockBodyInstr: list[WasmInstr] = []
    loopBodyInstr: list[WasmInstr] = []

    # Compile the condition
    loopBodyInstr.extend(cond)

    # Compile the body of the loop
    ifBodyInstr: list[WasmInstr] = body
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

    elementSize: int = 8 if elemTy == Int() else 4 # store element size

    # check size: size must be between zero and max array size -> construct if-stmt instructions:
    # first check < 0:
    wasmInstructs.extend(compileLenOfArray(lenExp))
    wasmInstructs.append(WasmInstrConst('i32', 0))
    wasmInstructs.append(WasmInstrIntRelOp('i32', 'lt_s'))
    wasmInstructs.append(WasmInstrIf(None, Errors.outputError(Errors.arraySize) + [WasmInstrTrap()], []))
    # secondly check for < maxLength ...
    wasmInstructs.extend(compileLenOfArray(lenExp))
    wasmInstructs.append(WasmInstrConst('i32', elementSize))
    wasmInstructs.append(WasmInstrNumBinOp('i32', 'mul')) # multiply length by size of element type = size
    wasmInstructs.append(WasmInstrConst('i32', cfg.maxArraySize))
    wasmInstructs.append(WasmInstrIntRelOp('i32', 'gt_s'))
    wasmInstructs.append(WasmInstrIf(None, Errors.outputError(Errors.arraySize) + [WasmInstrTrap()], []))
    
    # Compute header: 
    wasmInstructs.append(WasmInstrVarGlobal("get", Globals.freePtr)) # save old value $@free_ptr (address of the array on top of stack)
    wasmInstructs.extend(compileLenOfArray(lenExp))
    if elemTy == Int() or elemTy == Bool():
        m: Literal[3, 1] = 1
    else:
        m: Literal[3, 1] = 3
    wasmInstructs.extend(computeHeader(m, False)) 
    wasmInstructs.append(WasmInstrMem('i32', 'store')) # store header in memory

    # Move free_ptr and return array address
    wasmInstructs.append(WasmInstrVarGlobal("get", Globals.freePtr)) # move free_ptr
    wasmInstructs.extend(compileLenOfArray(lenExp))
    wasmInstructs.append(WasmInstrConst('i32', elementSize))
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
    Generates code that expects the array address on top of stack and puts the length as an i64 value on top of stack
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

    elementSize = 8
    match arrayExp.ty:
        case Array(elemTy):
            elementSize = 8 if asTy(elemTy) == Int() else 4
        case _:
            raise ValueError
        
    # check index > 0
    wasmInstructs.extend(compileAtomExp(indexExp))
    wasmInstructs.append(WasmInstrConst('i64', 0))
    wasmInstructs.append(WasmInstrIntRelOp('i64', 'lt_s'))
    wasmInstructs.append(WasmInstrIf(None, Errors.outputError(Errors.arrayIndexOutOfBounds) + [WasmInstrTrap()], []))

    # check index <= arrayLength
    wasmInstructs.extend(compileAtomExp(arrayExp)) # put array addr on to of stack
    wasmInstructs.extend(arrayLenInstrs())
    wasmInstructs.extend(compileAtomExp(indexExp))
    wasmInstructs.append(WasmInstrIntRelOp('i64', 'le_s'))
    wasmInstructs.append(WasmInstrIf(None, Errors.outputError(Errors.arrayIndexOutOfBounds) + [WasmInstrTrap()], []))

    wasmInstructs.extend(compileAtomExp(arrayExp)) # get the array addr
    # compute offset-----
    wasmInstructs.extend(compileAtomExp(indexExp)) # get the index
    wasmInstructs.append(WasmInstrConvOp('i32.wrap_i64')) # convert to i32
    wasmInstructs.append(WasmInstrConst('i32', elementSize))
    wasmInstructs.append(WasmInstrNumBinOp('i32', 'mul'))
    wasmInstructs.append(WasmInstrConst('i32', 4))
    wasmInstructs.append(WasmInstrNumBinOp('i32', 'add')) # now on top of stack: offset of element
    # -------------------
    wasmInstructs.append(WasmInstrNumBinOp('i32', 'add')) # now on top of stack: address of element

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
    id: Ident = Ident("")
    isInt: bool = any(tyOfExp(arg) == Int() for arg in args)

    match name.name:
        case "print":
            if isInt == True:
                id = Ident("print_i64")
            else:
                id = Ident("print_bool")
        case "input_int":
            id = Ident("input_i64")
        case "len":
            for arg in args:
                wasmInstructs.extend(compileExp(arg))
            wasmInstructs.extend(arrayLenInstrs())
            return wasmInstructs
        case _:
            raise ValueError(f"Unknown function call {name.name}")
    
    for arg in args:
        wasmInstructs.extend(compileExp(arg))
    wasmInstructs.append(WasmInstrCall(identToWasmId(id)))

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
            wasmInstructs.extend(compileExp(left))
            wasmInstructs.extend(compileExp(right))
            if tyOfExp(left) == Int():
                wasmInstructs.append(WasmInstrIntRelOp('i64', 'eq')) 
            else:
                wasmInstructs.append(WasmInstrIntRelOp('i32', 'eq'))
        case NotEq():
            wasmInstructs.extend(compileExp(left))
            wasmInstructs.extend(compileExp(right))
            if tyOfExp(left) == Int():
                wasmInstructs.append(WasmInstrIntRelOp('i64', 'ne')) 
            else:
                wasmInstructs.append(WasmInstrIntRelOp('i32', 'ne'))
        case Is():
            # check if one array is same -> meaning same address
            wasmInstructs.extend(compileExp(left))
            wasmInstructs.extend(compileExp(right))
            wasmInstructs.append(WasmInstrIntRelOp('i32', 'eq'))
    return wasmInstructs


def computeHeader(M: int, convertToi32: bool) -> list[WasmInstr]:
    """
    Computes the header for an array in WebAssembly.
    Assumes length is on top of stack.
    The header consists of:
    Length | Kind | Pointer | GC enabled
    """
    wasmInstructs: list[WasmInstr] = []
    if convertToi32 == True:
        wasmInstructs.append(WasmInstrConvOp('i32.wrap_i64'))
    wasmInstructs.append(WasmInstrConst('i32', 4))
    wasmInstructs.append(WasmInstrNumBinOp('i32', 'shl'))  # shift left by 4 bits
    wasmInstructs.append(WasmInstrConst('i32', M))  # kind
    wasmInstructs.append(WasmInstrNumBinOp('i32', 'xor'))  # combine length and kind
    return wasmInstructs

def compileLenOfArray(lenExp: atomExp) -> list[WasmInstr]:
    """
    Compiles an atomic expression containing the length of an array to wasm, including a conversion from i64 to i32
    """
    wasmInstructs: list[WasmInstr] = compileAtomExp(lenExp)
    wasmInstructs.append(WasmInstrConvOp('i32.wrap_i64'))
    return wasmInstructs



def mapVarType(var_type: ty) -> Literal['i64', 'i32']:
    """
    Maps a variable type from the symbol table to a WebAssembly value type.
    """
    if type(var_type) == Int:
        return 'i64'
    elif type(var_type) == Array:
        return mapVarType(var_type.elemTy)
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
    

def generateUniqueLabel(prefix: str) -> str:
    global loop_counter_global
    if prefix not in loop_counter_global:
        loop_counter_global[prefix] = 0
    loop_counter_global[prefix] += 1
    return f"{prefix}_{loop_counter_global[prefix]}"     

def asTy(ty: Optional[ty]) -> ty:
    assert ty is not None
    return ty