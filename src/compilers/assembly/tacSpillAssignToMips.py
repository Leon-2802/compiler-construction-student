import assembly.tacSpill_ast as tacSpill
import assembly.mips_ast as mips
from typing import *
from assembly.common import *
from assembly.mipsHelper import *
from common.compilerSupport import *

def primToMips(varName: str, p: tacSpill.prim) -> mips.instr:
    match p:
        case tacSpill.Const(v):
            return mips.LoadI(mips.Reg(varName), mips.Imm(v))
        case tacSpill.Name(var):
            return mips.Move(mips.Reg(varName), mips.Reg(var.name))

def assignToMips(i: tacSpill.Assign) -> list[mips.instr]:
    mipsInstrs: list[mips.instr] = []

    match i.right:
        case tacSpill.Prim(p):
            mipsInstrs.append(primToMips(i.var.name, p))
        case tacSpill.BinOp(left, op, right):
            match left:
                case tacSpill.Name(varLeft): 
                    match op.name:
                        case "ADD":
                            match right:
                                case tacSpill.Const(valRight):
                                    mipsInstrs.append(mips.OpI(mips.AddI(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Imm(valRight)))
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.Op(mips.Add(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg(varRight.name)))
                        case "SUB":
                            match right:
                                case tacSpill.Const(valRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t2'), mips.Imm(valRight)))
                                    mipsInstrs.append(mips.Op(mips.Sub(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg('$t2')))
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.Op(mips.Sub(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg(varRight.name)))
                        case "MUL":
                            match right:
                                case tacSpill.Const(valRight):
                                    # no mul with literal values -> need temporary register (use $t0)
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t2'), mips.Imm(valRight)))
                                    mipsInstrs.append(mips.Op(mips.Mul(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg('$t2')))
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.Op(mips.Mul(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg(varRight.name)))
                        case "EQ":
                            match right:
                                case tacSpill.Const(valRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t2'), mips.Imm(valRight)))
                                    mipsInstrs.append(mips.Op(mips.Eq(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg('$t2')))
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.Op(mips.Eq(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg(varRight.name)))
                        case "NE":
                            match right:
                                case tacSpill.Const(valRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t0'), mips.Imm(valRight)))
                                    mipsInstrs.append(mips.Op(mips.NotEq(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg('$t0')))
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.Op(mips.NotEq(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg(varRight.name)))
                        case "LT_S":
                            match right:
                                case tacSpill.Const(valRight):
                                    mipsInstrs.append(mips.OpI(mips.LessI(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Imm(valRight)))
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.Op(mips.Less(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg(varRight.name)))
                        case "GT_S":
                            match right:
                                case tacSpill.Const(valRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t0'), mips.Imm(valRight)))
                                    mipsInstrs.append(mips.Op(mips.Greater(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg('$t0')))
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.Op(mips.Greater(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg(varRight.name)))
                        case "LE_S":
                            match right:
                                case tacSpill.Const(valRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t0'), mips.Imm(valRight)))
                                    mipsInstrs.append(mips.Op(mips.LessEq(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg('$t0')))
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.Op(mips.LessEq(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg(varRight.name)))
                        case "GE_S":
                            match right:
                                case tacSpill.Const(valRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t0'), mips.Imm(valRight)))
                                    mipsInstrs.append(mips.Op(mips.GreaterEq(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg('$t0')))
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.Op(mips.GreaterEq(), mips.Reg(i.var.name), mips.Reg(varLeft.name), mips.Reg(varRight.name)))
                        case s:
                            raise ValueError(f'Unhandled operator: {s}')
                case tacSpill.Const(valLeft):
                    match op.name:
                        case "ADD":
                            match right:
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.OpI(mips.AddI(), mips.Reg(i.var.name), mips.Reg(varRight.name), mips.Imm(valLeft)))
                                case tacSpill.Const(valRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t1'), mips.Imm(valLeft)))
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t2'), mips.Imm(valRight)))
                                    mipsInstrs.append(mips.Op(mips.Add(), mips.Reg(i.var.name), mips.Reg('$t1'), mips.Reg('$t2')))
                        case "SUB":
                            match right:
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t2'), mips.Imm(valLeft)))
                                    mipsInstrs.append(mips.Op(mips.Sub(), mips.Reg(i.var.name), mips.Reg('$t2'), mips.Reg(varRight.name)))
                                case tacSpill.Const(valRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t1'), mips.Imm(valLeft)))
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t2'), mips.Imm(valRight)))
                                    mipsInstrs.append(mips.Op(mips.Sub(), mips.Reg(i.var.name), mips.Reg('$t1'), mips.Reg('$t2')))
                        case "MUL":
                            match right:
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t2'), mips.Imm(valLeft)))
                                    mipsInstrs.append(mips.Op(mips.Mul(), mips.Reg(i.var.name), mips.Reg('$t2'), mips.Reg(varRight.name)))
                                case tacSpill.Const(valRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t1'), mips.Imm(valLeft)))
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t2'), mips.Imm(valRight)))
                                    mipsInstrs.append(mips.Op(mips.Mul(), mips.Reg(i.var.name), mips.Reg('$t1'), mips.Reg('$t2')))
                        case "EQ":
                            match right:
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t0'), mips.Imm(valLeft)))
                                    mipsInstrs.append(mips.Op(mips.Eq(), mips.Reg(i.var.name), mips.Reg('$t0'), mips.Reg(varRight.name)))
                                case tacSpill.Const(valRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t0'), mips.Imm(valLeft)))
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t1'), mips.Imm(valRight)))
                                    mipsInstrs.append(mips.Op(mips.Eq(), mips.Reg(i.var.name), mips.Reg('$t0'), mips.Reg('$t1')))
                        case "NE":
                            match right:
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t0'), mips.Imm(valLeft)))
                                    mipsInstrs.append(mips.Op(mips.NotEq(), mips.Reg(i.var.name), mips.Reg('$t0'), mips.Reg(varRight.name)))
                                case tacSpill.Const(valRight):
                                    #TODO pass ok here?
                                    pass
                        case "LT_S":
                            match right:
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t0'), mips.Imm(valLeft)))
                                    mipsInstrs.append(mips.Op(mips.Less(), mips.Reg(i.var.name), mips.Reg('$t0'), mips.Reg(varRight.name)))
                                case tacSpill.Const(valRight):
                                    #TODO pass ok here?
                                    pass
                        case "GT_S":
                            match right:
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t0'), mips.Imm(valLeft)))
                                    mipsInstrs.append(mips.Op(mips.Greater(), mips.Reg(i.var.name), mips.Reg('$t0'), mips.Reg(varRight.name)))
                                case tacSpill.Const(valRight):
                                    #TODO pass ok here?
                                    pass
                        case "LE_S":
                            match right:
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t0'), mips.Imm(valLeft)))
                                    mipsInstrs.append(mips.Op(mips.LessEq(), mips.Reg(i.var.name), mips.Reg('$t0'), mips.Reg(varRight.name)))
                                case tacSpill.Const(valRight):
                                    #TODO pass ok here?
                                    pass
                        case "GE_S":
                            match right:
                                case tacSpill.Name(varRight):
                                    mipsInstrs.append(mips.LoadI(mips.Reg('$t0'), mips.Imm(valLeft)))
                                    mipsInstrs.append(mips.Op(mips.GreaterEq(), mips.Reg(i.var.name), mips.Reg('$t0'), mips.Reg(varRight.name)))
                                case tacSpill.Const(valRight):
                                    #TODO pass ok here?
                                    pass
                        case s:
                            raise ValueError(f'Unhandled operator: {s}')
                    
    return mipsInstrs