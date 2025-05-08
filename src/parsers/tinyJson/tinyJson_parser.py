from parsers.common import *
from lark import *

type Json = str | int | dict[str, Json]

def ruleJson(toks: TokenStream) -> Json:
    return alternatives("json", toks, [ruleObject, ruleString, ruleInt])

def ruleObject(toks: TokenStream) -> dict[str, Json]:
    toks.ensureNext("LBRACE") # consume left brace
    obj = ruleEntryList(toks)
    toks.ensureNext("RBRACE") # consume right brace
    return obj

def ruleEntryList(toks: TokenStream) -> dict[str, Json]:
    if toks.lookahead().type == "STRING": # don't consume token in this case
        return ruleEntryListNotEmpty(toks)
    else:
        return {}

def ruleEntryListNotEmpty(toks: TokenStream) -> dict[str, Json]:
    e = ruleEntry(toks)
    d = {e[0]:e[1]}
    if toks.lookahead().type == "COMMA":
        toks.next() # consume comma
        d.update(ruleEntryListNotEmpty(toks))
        return d
    else:
        return d

def ruleEntry(toks: TokenStream) -> tuple[str, Json]:
    str = ruleString(toks)
    toks.ensureNext("COLON") # consume colon
    json = ruleJson(toks)
    return (str, json)


def ruleString(toks: TokenStream) -> str:
    s = toks.ensureNext("STRING").value
    s = s.strip('"')
    return s

def ruleInt(toks: TokenStream) -> int:
    i = toks.ensureNext("INT").value
    return int(i)

def parse(code: str) -> Json:
    parser = mkLexer("./src/parsers/tinyJson/tinyJson_grammar.lark")
    tokens = list(parser.lex(code))
    log.info(f'Tokens: {tokens}')
    toks = TokenStream(tokens)
    res = ruleJson(toks)
    toks.ensureEof(code)
    return res