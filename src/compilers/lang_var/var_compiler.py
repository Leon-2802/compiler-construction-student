from lang_var.var_ast import *
from common.wasm import *
import lang_var.var_tychecker as var_tychecker
from common.compilerSupport import *
#import common.utils as utils

def compileModule(m: mod, cfg: CompilerConfig) -> WasmModule:
    """
    Compiles the given module.
    """
    vars = var_tychecker.tycheckModule(m)
    instrs = compileStmts(m.stmts)
    idMain = WasmId('$main')
    locals: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(x), 'i64') for x in vars]
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
            wasmInstructs.append(WasmInstrConst("i64", val))
        case Name(val):
            wasmInstructs.append(WasmInstrVarLocal("get", identToWasmId(val)))
        case Call(name, args):
            for arg in args:
                wasmInstructs.extend(compileExp(arg))
            wasmInstructs.append(WasmInstrCall(identToWasmId(name)))
        case UnOp(op, arg):
            wasmInstructs.append(WasmInstrConst("i64", 0))
            wasmInstructs.extend(compileExp(arg))
            wasmInstructs.append(WasmInstrNumBinOp("i64", unaryOpToLiteral(op)))
        case BinOp(left, op, right):
            wasmInstructs.extend(compileExp(left))
            wasmInstructs.extend(compileExp(right))
            wasmInstructs.append(WasmInstrNumBinOp("i64", binaryOpToLiteral(op)))

    return wasmInstructs

 
def identToWasmId(x: ident) -> WasmId:
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
        
def unaryOpToLiteral(op: unaryop) -> Literal['add', 'sub']:
    match op:
        case USub():
            return 'sub'