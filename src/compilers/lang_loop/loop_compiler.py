from lang_loop.loop_ast import *
from lang_loop.loop_interp import *
from common.wasm import *
from lang_loop.loop_tychecker import *
from common.compilerSupport import *
#import common.utils as utils


def compileModule(m: mod, cfg: CompilerConfig) -> WasmModule:
    """
    Compiles the given module.
    """
    vars: Symtab = tycheckModule(m)
    instrs = compileStmts(m.stmts)
    idMain = WasmId('$main')
    locals: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(x), mapVarType(i.ty)) for x,i in vars.items()]
    return WasmModule(imports=wasmImports(cfg.maxMemSize),
        exports=[WasmExport("main", WasmExportFunc(idMain))],
        globals=[],
        data=[],
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
            wasmInstructs.extend(compileExp(cond))
            thenBodyInstr: list[WasmInstr] = compileStmts(thenBody)
            elseBodyInstr: list[WasmInstr] = compileStmts(elseBody)
            wasmInstructs.append(WasmInstrIf(None, thenBodyInstr, elseBodyInstr))
        case WhileStmt(cond, body):
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
        case Assign(x, IntConst(n)):
            wasmInstructs.append(WasmInstrConst("i64", n))
            wasmInstructs.append(WasmInstrVarLocal("set", identToWasmId(x)))
        case Assign(x, e):
            wasmInstructs.extend(compileExp(e))
            wasmInstructs.append(WasmInstrVarLocal("set", identToWasmId(x)))

    return wasmInstructs


def compileExp(e: exp) -> list[WasmInstr]:
    wasmInstructs: list[WasmInstr] = []
    match e:
        case IntConst(val):
            wasmInstructs.append(WasmInstrConst('i64', val))
        case BoolConst(val):
            boolToNumericalVal: int = 0
            if val == True:
                boolToNumericalVal = 1
            wasmInstructs.append(WasmInstrConst('i32', boolToNumericalVal))
        case Name(val):
            wasmInstructs.append(WasmInstrVarLocal("get", identToWasmId(val)))
        case Call(name, args):
            wasmInstructs.extend(compileCall(name, args))
        case UnOp(op, arg):
            wasmInstructs.extend(compileUnaryOp(op, arg))
        case BinOp(left, op, right):
            wasmInstructs.extend(compileBinaryOp(left, op, right))

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