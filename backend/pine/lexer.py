"""
Pine Script Lexer.

Tokenizes a Pine Script-like DSL into a stream of typed tokens.
Supports: identifiers, numbers, operators, parentheses, commas, assignment.
"""
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class TokenType(Enum):
    NUMBER = auto()
    IDENTIFIER = auto()
    ASSIGN = auto()       # =
    PLUS = auto()         # +
    MINUS = auto()        # -
    STAR = auto()         # *
    SLASH = auto()        # /
    LPAREN = auto()       # (
    RPAREN = auto()       # )
    COMMA = auto()        # ,
    GT = auto()           # >
    LT = auto()           # <
    GTE = auto()          # >=
    LTE = auto()          # <=
    EQ = auto()           # ==
    NEQ = auto()          # !=
    AND = auto()          # and
    OR = auto()           # or
    QUESTION = auto()     # ?
    COLON = auto()        # :
    NEWLINE = auto()
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int


_KEYWORDS = {"and": TokenType.AND, "or": TokenType.OR}

_PATTERNS = [
    (r"[ \t]+", None),                          # skip whitespace
    (r"#[^\n]*", None),                         # skip comments
    (r"//[^\n]*", None),                        # skip // comments
    (r"//@[^\n]*", None),                       # skip //@version directives
    (r"\n", TokenType.NEWLINE),
    (r"\d+\.?\d*", TokenType.NUMBER),
    (r">=", TokenType.GTE),
    (r"<=", TokenType.LTE),
    (r"==", TokenType.EQ),
    (r"!=", TokenType.NEQ),
    (r"=", TokenType.ASSIGN),
    (r"\+", TokenType.PLUS),
    (r"-", TokenType.MINUS),
    (r"\*", TokenType.STAR),
    (r"/", TokenType.SLASH),
    (r"\(", TokenType.LPAREN),
    (r"\)", TokenType.RPAREN),
    (r",", TokenType.COMMA),
    (r">", TokenType.GT),
    (r"<", TokenType.LT),
    (r"\?", TokenType.QUESTION),
    (r":", TokenType.COLON),
    (r"[a-zA-Z_][a-zA-Z0-9_]*", TokenType.IDENTIFIER),
]

_COMPILED = [(re.compile(p), t) for p, t in _PATTERNS]


def tokenize(source: str) -> List[Token]:
    """Tokenize Pine Script source into a list of tokens."""
    tokens = []
    line = 1
    col = 1
    pos = 0

    while pos < len(source):
        matched = False
        for regex, token_type in _COMPILED:
            m = regex.match(source, pos)
            if m:
                text = m.group(0)
                if token_type is not None:
                    if token_type == TokenType.NEWLINE:
                        tokens.append(Token(TokenType.NEWLINE, "\\n", line, col))
                        line += 1
                        col = 1
                    elif token_type == TokenType.IDENTIFIER and text in _KEYWORDS:
                        tokens.append(Token(_KEYWORDS[text], text, line, col))
                    else:
                        tokens.append(Token(token_type, text, line, col))
                        col += len(text)
                else:
                    col += len(text)
                pos = m.end()
                matched = True
                break

        if not matched:
            raise SyntaxError(f"Unexpected character '{source[pos]}' at line {line}, col {col}")

    tokens.append(Token(TokenType.EOF, "", line, col))
    return tokens
