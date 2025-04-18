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
            thenBodyInstr: list[WasmInstr] = compileStmts(thenBody)
            elseBodyInstr: list[WasmInstr] = compileStmts(elseBody)
            wasmInstructs.append(WasmInstrIf(mapVarType(tyOfExp(cond)), thenBodyInstr, elseBodyInstr))
        case WhileStmt(cond, body):
            bodyInstr: list[WasmInstr] = compileStmts(body)
            wasmInstructs.append(WasmInstrLoop())
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
            wasmInstructs.append(WasmInstrConst('i32', val))
        case Name(val):
            wasmInstructs.append(WasmInstrVarLocal("get", identToWasmId(val)))
        case Call(name, args):
            isInt: bool = False
            for arg in args:
                if (mapVarType(tyOfExp(arg)) == 'i64'):
                    isInt = True
                wasmInstructs.extend(compileExp(arg))
            if (isInt == True):
                wasmInstructs.append(WasmInstrCall(intIdentToWasmId(name)))
            else:
                wasmInstructs.append(WasmInstrCall(boolIdentToWasmId(name)))
        case UnOp(op, arg):
            wasmInstructs.append(WasmInstrConst('i64', 0))
            wasmInstructs.extend(compileExp(arg))
            wasmInstructs.append(WasmInstrNumBinOp('i64', unaryOpToLiteral(op)))
        case BinOp(left, op, right):
            wasmInstructs.extend(compileExp(left))
            wasmInstructs.extend(compileExp(right))
            wasmInstructs.append(WasmInstrNumBinOp(mapVarType(tyOfExp(left)), binaryOpToLiteral(op)))
        # Bool and Int operations: Gleich, Ungleich, print

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
            raise ValueError('exp has type None')
        case Void():
            raise ValueError('exp has type Void')
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

def binaryOpToLiteral(op: binaryop) -> Literal['add', 'sub', 'mul', 'shr_u', 'shl', 'xor']:
    match op:
        case Add():
            return 'add'
        case Sub():
            return 'sub'
        case Mul():
            return 'mul'
        case Less():

        
def unaryOpToLiteral(op: unaryop) -> Literal['add', 'sub']:
    match op:
        case USub():
            return 'sub'
        case Not():
