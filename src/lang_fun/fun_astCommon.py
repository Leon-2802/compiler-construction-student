# AUTOMATICALLY GENERATED (2024-03-13 15:00:05)
from __future__ import annotations
from dataclasses import dataclass

type optional[T] = T | None

@dataclass(frozen=True)
class Ident:
    name: str

type ident = Ident
type string = str

@dataclass
class USub:
    pass

@dataclass
class Not:
    pass

type unaryop = USub | Not

@dataclass
class Add:
    pass

@dataclass
class Sub:
    pass

@dataclass
class Mul:
    pass

@dataclass
class Less:
    pass

@dataclass
class LessEq:
    pass

@dataclass
class Greater:
    pass

@dataclass
class GreaterEq:
    pass

@dataclass
class Eq:
    pass

@dataclass
class NotEq:
    pass

@dataclass
class Is:
    pass

@dataclass
class And:
    pass

@dataclass
class Or:
    pass

type binaryop = Add | Sub | Mul | Less | LessEq | Greater | GreaterEq | Eq | NotEq | Is | And | Or

@dataclass
class Int:
    pass

@dataclass
class Bool:
    pass

@dataclass
class Array:
    elemTy: ty

@dataclass
class Fun:
    params: list[ty]
    result: resultTy

type ty = Int | Bool | Array | Fun

@dataclass
class NotVoid:
    ty: ty

@dataclass
class Void:
    pass

type resultTy = NotVoid | Void

@dataclass
class Var:
    pass

@dataclass
class UserFun:
    pass

@dataclass
class BuiltinFun:
    pass

type scope = Var | UserFun | BuiltinFun

@dataclass
class FunParam:
    var: ident
    ty: ty

type funParam = FunParam