import TagHandler
import TagService
import re
from functools import lru_cache


class Tokenizer:
    @staticmethod
    def tokenize(querystr: str) -> list[str] :
        tokens = re.findall("[()&|~]|[a-z0-9]+", querystr)
        return tokens
    
class ASTNode:
    def __init__(self, value, left=None, right=None):
        self.value = value      # Operator or operand (e.g., '&', '|', '~', 'a')
        self.left = left        # Left child (ASTNode or None)
        self.right = right      # Right child (ASTNode or None)

    def __repr__(self):
        if self.value == '~':
            return f"~({self.left})"
        elif self.left and self.right:
            return f"({self.left} {self.value} {self.right})"
        else:
            return str(self.value)

class Parser:
    def __init__(self, tokens, valid_operators, left_paren, right_paren):
        self.tokens = tokens
        self.pos = 0
        self.valid_operators = valid_operators
        self.LEFT_PAREN = left_paren
        self.RIGHT_PAREN = right_paren

    def parse(self):
        return self.parse_or()

    def parse_or(self):
        node = self.parse_and()
        while self._peek() == '|':
            self._next()
            node = ASTNode('|', node, self.parse_and())
        return node

    def parse_and(self):
        node = self.parse_not()
        while self._peek() == '&':
            self._next()
            node = ASTNode('&', node, self.parse_not())
        return node

    def parse_not(self):
        if self._peek() == '~':
            self._next()
            return ASTNode('~', self.parse_not())
        else:
            return self.parse_atom()

    def parse_atom(self):
        tok = self._peek()
        if tok == self.LEFT_PAREN:
            self._next()
            node = self.parse_or()
            assert self._peek() == self.RIGHT_PAREN, "Mismatched parentheses"
            self._next()
            return node
        elif tok is not None and tok not in self.valid_operators:
            self._next()
            return ASTNode(tok)
        else:
            raise ValueError(f"Unexpected token: {tok}")

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _next(self):
        tok = self._peek()
        self.pos += 1
        return tok
    
# Implementation of shuning yard algorithm
class ASTEvaluator:
    def __init__(self, tag_handler : TagService.TagService):
        self.th = tag_handler

    def _eval(self, node : ASTNode) -> set:
        if node is None:
            return set()
        if node.value == '&':
            v1 = self._eval(node.left) 
            v2 = self._eval(node.right)
            return v1.intersection(v2)
        elif node.value == '|':
            v1 = self._eval(node.left) 
            v2 = self._eval(node.right)
            return v1.union(v2)
        elif node.value == '~':
            all_resources = set(self.th.get_resource_ids())
            v1 = self._eval(node.left)
            v = all_resources.difference(v1)
            return v
        else:
            # Operand: tag name
            return self._get_tag_closure(node.value)

    def eval(self, node : ASTNode) -> list:
        res = list(self._eval(node))
        res = list(map(self.th.get_resource_url, res))
        return res

    @lru_cache(maxsize=128)
    def _get_tag_closure(self, tag : str) -> set:
        tag_closure = self.th.get_tag_closure([tag])
        tag_closure_ids = list(map(self.th.get_tag_id, tag_closure))
        return set(self.th.resource_repo.get_resources_by_tag_id(tag_closure_ids))

# In your QueryEvaluator class, add a method to use the AST:
class QueryEvaluator:
    VALID_OPERATORS = set(['|', '&', '~'])
    LEFT_PAREN = '('
    RIGHT_PAREN = ')'

    def __init__(self, th: TagService.TagService):
        self.th = th

    def evaluate(self, expression : str) -> list:
        tokens = Tokenizer.tokenize(expression)
        parser = Parser(tokens, QueryEvaluator.VALID_OPERATORS, QueryEvaluator.LEFT_PAREN, QueryEvaluator.RIGHT_PAREN)
        ast = parser.parse()
        # Evaluate the AST
        evaluator = ASTEvaluator(self.th)
        result_ids = evaluator.eval(ast)
        return result_ids