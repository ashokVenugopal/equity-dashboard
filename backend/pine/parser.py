"""
Pine Script Parser.

Parses a token stream into an AST of assignment statements.
Each statement is: identifier = expression
Expressions support: function calls, arithmetic (+, -, *, /), ternary (? :), comparisons.
"""
from dataclasses import dataclass
from typing import List, Optional, Union

from .lexer import Token, TokenType


# ── AST Nodes ──

@dataclass
class NumberLiteral:
    value: float

@dataclass
class Identifier:
    name: str

@dataclass
class FunctionCall:
    name: str
    args: list  # List of expression nodes

@dataclass
class BinaryOp:
    op: str
    left: object
    right: object

@dataclass
class TernaryOp:
    condition: object
    true_expr: object
    false_expr: object

@dataclass
class UnaryMinus:
    operand: object

@dataclass
class Assignment:
    name: str
    expr: object

Expression = Union[NumberLiteral, Identifier, FunctionCall, BinaryOp, TernaryOp, UnaryMinus]


# ── Parser ──

class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def parse(self) -> List[Assignment]:
        """Parse all statements."""
        statements = []
        self._skip_newlines()
        while not self._at_end():
            stmt = self._parse_statement()
            if stmt:
                statements.append(stmt)
            self._skip_newlines()
        return statements

    def _parse_statement(self) -> Optional[Assignment]:
        """Parse: identifier = expression"""
        if self._peek().type != TokenType.IDENTIFIER:
            return None
        if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].type == TokenType.ASSIGN:
            name_token = self._advance()
            self._advance()  # skip =
            expr = self._parse_expression()
            return Assignment(name=name_token.value, expr=expr)
        # Bare expression (ignored in v1)
        self._parse_expression()
        return None

    def _parse_expression(self):
        """Parse ternary: expr ? expr : expr"""
        left = self._parse_or()
        if self._peek().type == TokenType.QUESTION:
            self._advance()
            true_expr = self._parse_expression()
            self._expect(TokenType.COLON)
            false_expr = self._parse_expression()
            return TernaryOp(condition=left, true_expr=true_expr, false_expr=false_expr)
        return left

    def _parse_or(self):
        left = self._parse_and()
        while self._peek().type == TokenType.OR:
            self._advance()
            right = self._parse_and()
            left = BinaryOp(op="or", left=left, right=right)
        return left

    def _parse_and(self):
        left = self._parse_comparison()
        while self._peek().type == TokenType.AND:
            self._advance()
            right = self._parse_comparison()
            left = BinaryOp(op="and", left=left, right=right)
        return left

    def _parse_comparison(self):
        left = self._parse_additive()
        while self._peek().type in (TokenType.GT, TokenType.LT, TokenType.GTE, TokenType.LTE, TokenType.EQ, TokenType.NEQ):
            op_token = self._advance()
            right = self._parse_additive()
            left = BinaryOp(op=op_token.value, left=left, right=right)
        return left

    def _parse_additive(self):
        left = self._parse_multiplicative()
        while self._peek().type in (TokenType.PLUS, TokenType.MINUS):
            op_token = self._advance()
            right = self._parse_multiplicative()
            left = BinaryOp(op=op_token.value, left=left, right=right)
        return left

    def _parse_multiplicative(self):
        left = self._parse_unary()
        while self._peek().type in (TokenType.STAR, TokenType.SLASH):
            op_token = self._advance()
            right = self._parse_unary()
            left = BinaryOp(op=op_token.value, left=left, right=right)
        return left

    def _parse_unary(self):
        if self._peek().type == TokenType.MINUS:
            self._advance()
            operand = self._parse_primary()
            return UnaryMinus(operand=operand)
        return self._parse_primary()

    def _parse_primary(self):
        token = self._peek()

        if token.type == TokenType.NUMBER:
            self._advance()
            return NumberLiteral(value=float(token.value))

        if token.type == TokenType.IDENTIFIER:
            self._advance()
            # Check if it's a function call
            if self._peek().type == TokenType.LPAREN:
                self._advance()  # skip (
                args = []
                if self._peek().type != TokenType.RPAREN:
                    args.append(self._parse_expression())
                    while self._peek().type == TokenType.COMMA:
                        self._advance()
                        args.append(self._parse_expression())
                self._expect(TokenType.RPAREN)
                return FunctionCall(name=token.value, args=args)
            return Identifier(name=token.value)

        if token.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return expr

        raise SyntaxError(f"Unexpected token {token.type.name} '{token.value}' at line {token.line}, col {token.col}")

    def _peek(self) -> Token:
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def _expect(self, expected: TokenType) -> Token:
        token = self._advance()
        if token.type != expected:
            raise SyntaxError(f"Expected {expected.name}, got {token.type.name} '{token.value}' at line {token.line}")
        return token

    def _at_end(self) -> bool:
        return self.tokens[self.pos].type == TokenType.EOF

    def _skip_newlines(self):
        while self.pos < len(self.tokens) and self.tokens[self.pos].type == TokenType.NEWLINE:
            self.pos += 1
