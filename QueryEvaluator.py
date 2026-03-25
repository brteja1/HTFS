import TagService
import re


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
    
from RDFHandler import HTFS
from rdflib.namespace import SKOS

class ASTEvaluator:
    """Compiles an AST into a single SPARQL query and executes it."""

    def __init__(self, tag_handler: TagService.TagService):
        self.th = tag_handler
        self.g = tag_handler.db_manager.graph
        self._var_counter = 0

    def _next_var(self):
        self._var_counter += 1
        return f"?tag{self._var_counter}"

    def _compile(self, node: ASTNode) -> str:
        if node is None:
            return ""
        if node.value == '&':
            return self._compile(node.left) + self._compile(node.right)
        elif node.value == '|':
            left = self._compile(node.left)
            right = self._compile(node.right)
            return f"{{ {left} }} UNION {{ {right} }}\n"
        elif node.value == '~':
            inner = self._compile(node.left)
            return f"FILTER NOT EXISTS {{ {inner} }}\n"
        else:
            var = self._next_var()
            tag_uri = f"htfs:tag_{node.value}"
            return f"?resource htfs:hasTag {var} .\n{var} skos:broader* {tag_uri} .\n"

    def eval(self, node: ASTNode) -> list:
        self._var_counter = 0
        pattern = self._compile(node)
        query = f"""
        SELECT DISTINCT ?url WHERE {{
            ?resource a htfs:Resource ;
                      htfs:url ?url .
            {pattern}
        }}
        """
        results = self.g.query(query, initNs={"htfs": HTFS, "skos": SKOS})
        return [str(row.url) for row in results]

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