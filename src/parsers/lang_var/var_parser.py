from common.wasm import *
from lang_var.var_ast import *
from lark import ParseTree
from parsers.common import *

grammarFile = "./src/parsers/lang_var/var_grammar.lark"


#test: scripts/run-tests -k 'test_varParser'

def parseModule(args: ParserArgs) -> mod:
    parseTree = parseAsTree(args, grammarFile, 'mod')
    ast = parseTreeToModuleAst(parseTree)
    log.debug(f'AST: {ast}')
    return ast


def parseTreeToModuleAst(t: ParseTree) -> mod:
    match t.data:
        case "mod":
            module = Module(parseTreeToStmtListAst(asTree(t.children[0])))
        case _: raise ValueError("parsetree not of type lvar")
    return module

def parseTreeToStmtListAst(t: ParseTree) -> list[stmt]:
    stmts: list[stmt] = []

    match t.data:
        case "stmt_list":
            for c in t.children:
                stmts.append(parseTreeToStmtAst(asTree(c)))
        case _: raise ValueError("parsetree not of type stmt_list")

    return stmts

def parseTreeToStmtAst(t: ParseTree) -> stmt:
    statement: stmt
    match t.data:
        case "stmt_exp":
            statement = StmtExp(parseTreeToExpAst(asTree(t.children[0])))
        case "stmt_assign":
            return parseTreeToAssign(asTree(t.children[0]))
        case _: raise ValueError("parsetree not of type stmt_exp or assign")

    return statement

def parseTreeToAssign(t: ParseTree) -> stmt:
    match t.data:
        case "assign":
            return Assign(Ident(asToken(t.children[0]).value), parseTreeToExpAst(asTree(t.children[1])))
        case _: raise ValueError("parstree not of type assign in parseTreeToAssign")


def parseTreeToExpAst(t: ParseTree) -> exp:
    match t.data:
        case 'cname_exp':
            return Name(Ident(str(t.children[0])))
        case 'int_exp':
            return IntConst(int(asToken(t.children[0])))
        case 'add_exp':
            e1, e2 = [asTree(c) for c in t.children]
            return BinOp(parseTreeToExpAst(e1), Add(), parseTreeToExpAst(e2))
        case 'sub_exp':
            e1, e2 = [asTree(c) for c in t.children]
            return BinOp(parseTreeToExpAst(e1), Sub(), parseTreeToExpAst(e2))
        case 'mul_exp':
            e1, e2 = [asTree(c) for c in t.children]
            return BinOp(parseTreeToExpAst(e1), Mul(), parseTreeToExpAst(e2))
        case 'exp_1' | 'exp_2' | 'paren_exp':
            return parseTreeToExpAst(asTree(t.children[0]))
        case 'usub_exp':
            return UnOp(USub(), parseTreeToExpAst(asTree(t.children[0])))
        case 'call_exp':
            iden: Ident = Ident(str(t.children[0]))
            args: list[exp] = parseTreeToExpListAst(asTree(t.children[1]))
            return Call(iden, args)
        case kind:
            raise Exception(f'unhandled parse tree of kind {kind} for exp: {t}')
        
def parseTreeToExpListAst(t: ParseTree) -> list[exp]:
    exps: list[exp] = []

    match t.data:
        case 'arg_list':
            for c in t.children:
                exps.append(parseTreeToExpAst(asTree(c)))
        case _: raise ValueError("parsetree not of type arg_list")
    
    return exps
