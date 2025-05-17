import stat
import TagHandler
import re
from functools import lru_cache
import collections


# Implementation of shuning yard algorithm
class QueryEvaluator:
    OPERATORS = {'|': 0, '~': 1, '&': 0}
    VALID_OPERATORS = set(['|', '&', '~'])
    LEFT_PAREN = '('
    RIGHT_PAREN = ')'

    def __init__(self, th: TagHandler.TagHandler) :
        self.th = th
        self.operators = []
        self.values = []
        self.fullresources = []

    @staticmethod
    def tokenize(querystr: str) -> list[str] :
        tokens = re.findall("[()&|~]|[a-z0-9]+", querystr)
        return tokens

    def peek(self) :
        return self.operators[-1] if self.operators else None

    def apply_operator(self) :
        operator = self.operators.pop()
        assert(operator in QueryEvaluator.VALID_OPERATORS)
        if operator == "&" :
            v1 = self.values.pop()
            v2 = self.values.pop()
            self.values.append(v1.intersection(v2))
        elif operator == "|" :
            v1 = self.values.pop()
            v2 = self.values.pop()
            self.values.append(v1.union(v2))
        elif operator == "~" :
            v1 = self.values.pop()
            if len(self.fullresources) == 0 :
                self.fullresources = set(self.th.get_resource_ids())
            self.values.append(self.fullresources.difference(v1))

    def greater_precedence(self, op1, op2) -> bool:
        return QueryEvaluator.OPERATORS[op1] > QueryEvaluator.OPERATORS[op2]

    def validate_expression(self, expression: str) -> bool:
        """Validates query expression for balanced parentheses and valid operators"""
        stack = []
        for char in expression:
            if char == self.LEFT_PAREN:
                stack.append(char)
            elif char == self.RIGHT_PAREN:
                if not stack:
                    return False
                stack.pop()
        return len(stack) == 0

    def fully_parenthesize_expression(self, expression: str) -> str:
        """Ensures the logical expression is fully parenthesized."""
        tokens = QueryEvaluator.tokenize(expression)
        output = []
        operators = []

        for token in tokens:
            if token not in QueryEvaluator.VALID_OPERATORS and token not in (QueryEvaluator.LEFT_PAREN, QueryEvaluator.RIGHT_PAREN):
                output.append(token)
            elif token == QueryEvaluator.LEFT_PAREN:
                operators.append(token)
            elif token == QueryEvaluator.RIGHT_PAREN:
                while operators and operators[-1] != QueryEvaluator.LEFT_PAREN:
                    op = operators.pop()
                    if op == "~":
                        operand = output.pop()
                        output.append(f"({op}{operand})")
                    else:
                        right = output.pop()
                        left = output.pop()
                        output.append(f"({left} {op} {right})")
                operators.pop()  # Remove the '('
            else:  # Operator
                while (operators and operators[-1] != QueryEvaluator.LEFT_PAREN and
                       self.greater_precedence(operators[-1], token)):
                    op = operators.pop()
                    if op == "~":
                        operand = output.pop()
                        output.append(f"({op}{operand})")
                    else:
                        right = output.pop()
                        left = output.pop()
                        output.append(f"({left} {op} {right})")
                operators.append(token)

        while operators:
            op = operators.pop()
            if op == "~":   
                operand = output.pop()
                output.append(f"({op}{operand})")
            else:
                right = output.pop()
                left = output.pop()
                output.append(f"({left} {op} {right})")

        print(output)
        return output[0]

    def evaluate_query(self, expression):
        expression = self.fully_parenthesize_expression(expression)  # Ensure full parenthesization
        assert(self.validate_expression(expression))
        tokens = self.tokenize(expression)
        self.values = []
        self.operators = []
        for token in tokens:
            if token == QueryEvaluator.LEFT_PAREN:
                self.operators.append(token)
            elif token == QueryEvaluator.RIGHT_PAREN:
                top = self.peek()
                while top is not None and top != QueryEvaluator.LEFT_PAREN:
                    self.apply_operator()
                    top = self.peek()
                self.operators.pop()  # Discard the '('
            elif token[0] not in QueryEvaluator.VALID_OPERATORS:
                r = self.get_tag_closure(token)
                self.values.append(r)            
            else:
                # Operator
                top = self.peek()
                while top is not None and top != QueryEvaluator.LEFT_PAREN and self.greater_precedence(top, token):
                    self.apply_operator()
                    top = self.peek()
                self.operators.append(token)
        while self.peek() is not None:
            self.apply_operator()
        res = list(map(self.th.get_resource_url, self.values[0]))
        return res
    
    @lru_cache(maxsize=128)
    def get_tag_closure(self, tag: str) -> set[str]:
        tag_closure = self.th.get_tag_closure([tag])
        tag_closure_ids = list(map(self.th.get_tag_id, tag_closure))
        return set(self.th.get_resources_by_tag_id(tag_closure_ids))


class QueryOptimizer:
    """Optimizes infix logical expressions by minimizing NOT operations using AST rewriting."""

    class Node:
        def __init__(self, value, left=None, right=None):
            self.value = value
            self.left = left
            self.right = right
        def __str__(self):
            if self.value == '~':
                return f"~({self.left})"
            elif self.value in ('&', '|'):
                return f"({self.left} {self.value} {self.right})"
            else:
                return str(self.value)

    @staticmethod
    def optimize(expr: str, tokenize, valid_operators, left_paren, right_paren) -> str:
        tokens = tokenize(expr)
        ast, _ = QueryOptimizer._parse_expr(tokens, valid_operators, left_paren, right_paren)
        print(ast)
        optimized_ast = QueryOptimizer._rewrite(ast)
        return str(optimized_ast)

    @staticmethod
    def _parse_expr(tokens, valid_operators, left_paren, right_paren, min_prec=0):
        # Pratt parser for infix logic
        def get_prec(op):
            return {'~': 1, '&': 0, '|': 0}.get(op, -1)
        def is_unary(op):
            return op == '~'
        pos = 0
        def parse_atom():
            nonlocal pos
            if pos >= len(tokens):
                raise ValueError('Unexpected end of input')
            token = tokens[pos]
            if token == left_paren:
                pos += 1
                node, _ = QueryOptimizer._parse_expr(tokens[pos:], valid_operators, left_paren, right_paren)
                # Find matching right paren
                depth = 1
                i = pos
                while i < len(tokens):
                    if tokens[i] == left_paren:
                        depth += 1
                    elif tokens[i] == right_paren:
                        depth -= 1
                        if depth == 0:
                            break
                    i += 1
                pos = i + 1
                return node
            elif token == '~':
                pos += 1
                operand = parse_atom()
                return QueryOptimizer.Node('~', left=operand)
            else:
                pos += 1
                return QueryOptimizer.Node(token)
        lhs = parse_atom()
        while pos < len(tokens):
            op = tokens[pos]
            if op not in valid_operators or is_unary(op):
                break
            prec = get_prec(op)
            if prec < min_prec:
                break
            pos += 1
            rhs, _ = QueryOptimizer._parse_expr(tokens[pos:], valid_operators, left_paren, right_paren, prec + 1)
            # Advance pos by how many tokens were consumed in rhs
            rhs_tokens = QueryOptimizer._count_tokens(rhs)
            pos += rhs_tokens
            lhs = QueryOptimizer.Node(op, left=lhs, right=rhs)
        return lhs, pos

    @staticmethod
    def _count_tokens(node):
        # Helper to count tokens in a subtree
        if node is None:
            return 0
        if node.value in ('&', '|'):
            return 1 + QueryOptimizer._count_tokens(node.left) + QueryOptimizer._count_tokens(node.right)
        elif node.value == '~':
            return 1 + QueryOptimizer._count_tokens(node.left)
        else:
            return 1

    @staticmethod
    def _rewrite(node):
        # Recursively apply De Morgan's laws, double negation, and tautology/contradiction simplifications
        if node is None:
            return None
        if node.value == '~':
            child = QueryOptimizer._rewrite(node.left)
            # ~~A => A
            if child.value == '~':
                return QueryOptimizer._rewrite(child.left)
            # ~(A & B) => ~A | ~B
            if child.value == '&':
                return QueryOptimizer.Node('|', left=QueryOptimizer._rewrite(QueryOptimizer.Node('~', left=child.left)),
                                             right=QueryOptimizer._rewrite(QueryOptimizer.Node('~', left=child.right)))
            # ~(A | B) => ~A & ~B
            if child.value == '|':
                return QueryOptimizer.Node('&', left=QueryOptimizer._rewrite(QueryOptimizer.Node('~', left=child.left)),
                                             right=QueryOptimizer._rewrite(QueryOptimizer.Node('~', left=child.right)))
            return QueryOptimizer.Node('~', left=child)
        elif node.value == '|':
            left = QueryOptimizer._rewrite(node.left)
            right = QueryOptimizer._rewrite(node.right)
            # a | ~a => a (tautology)
            if (isinstance(left, QueryOptimizer.Node) and isinstance(right, QueryOptimizer.Node)):
                if left.value == '~' and str(left.left) == str(right):
                    return right
                if right.value == '~' and str(right.left) == str(left):
                    return left
            return QueryOptimizer.Node('|', left=left, right=right)
        elif node.value == '&':
            left = QueryOptimizer._rewrite(node.left)
            right = QueryOptimizer._rewrite(node.right)
            # a & ~a => ~a (contradiction, but for now just return left or right)
            if (isinstance(left, QueryOptimizer.Node) and isinstance(right, QueryOptimizer.Node)):
                if left.value == '~' and str(left.left) == str(right):
                    return QueryOptimizer.Node('~', left=right)
                if right.value == '~' and str(right.left) == str(left):
                    return QueryOptimizer.Node('~', left=left)
            return QueryOptimizer.Node('&', left=left, right=right)
        else:
            return node
