"""
QueryEvaluator - Compiles tag expressions to SPARQL queries.

Architecture:
  - Tokenizer: Split expression into tokens
  - Parser: Build AST with operator precedence
  - ASTEvaluator: Compile AST to SPARQL and execute against RDF graph
"""

import re
from RDFHandler import HTFS
from rdflib.namespace import SKOS

# Module-level constants for Parser
VALID_OPERATORS = set(['|', '&', '~'])
LEFT_PAREN = '('
RIGHT_PAREN = ')'


class Tokenizer:
    @staticmethod
    def tokenize(querystr: str) -> list[str]:
        tokens = re.findall("[()&|~]|[a-zA-Z0-9]+", querystr)
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
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

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
        if tok == LEFT_PAREN:
            self._next()
            node = self.parse_or()
            assert self._peek() == RIGHT_PAREN, "Mismatched parentheses"
            self._next()
            return node
        elif tok is not None and tok not in VALID_OPERATORS:
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


class ASTEvaluator:
    """
    Compiles an AST into a single SPARQL query and executes it.

    The TagService passed in must have a `db` attribute (DatabaseManager)
    which has an `rdf` attribute (RDFHandler) with a `graph` attribute.
    """

    def __init__(self, tag_service):
        self.th = tag_service
        self.db = tag_service.db
        # Ensure RDF is connected/loaded
        self.db.rdf.connect()
        self.g = self.db.rdf.graph
        self._var_counter = 0

    def _next_var(self):
        self._var_counter += 1
        return f"?tag{self._var_counter}"

    def _resolve_tag_to_id(self, tag_name: str) -> str:
        """Resolve a tag name to its RDF URI (htfs:tag_{id})."""
        tag_id = self.db.get_tag_id(tag_name)
        if tag_id < 0:
            return None
        return f"htfs:tag_{tag_id}"

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
            tag_uri = self._resolve_tag_to_id(node.value)
            if tag_uri is None:
                # Tag doesn't exist; add a clause that filters out everything
                return "FILTER(false)\n"
            var = self._next_var()
            return f"?resource htfs:hasTag {var} .\n{var} skos:broader* {tag_uri} .\n"

    def eval(self, node: ASTNode) -> list:
        self._var_counter = 0
        pattern = self._compile(node)
        query = f"""
        SELECT DISTINCT ?resource WHERE {{
            {pattern}
        }}
        """
        results = self.g.query(query, initNs={"htfs": HTFS, "skos": SKOS})
        resource_urls = []
        seen = set()
        for row in results:
            resource_uri = str(row.resource)
            try:
                resource_id = int(resource_uri.split("_")[-1])
            except (ValueError, IndexError):
                continue
            url = self.db.get_resource_url(resource_id)
            if url and url not in seen:
                seen.add(url)
                resource_urls.append(url)
        return resource_urls


class QueryEvaluator:
    """
    Evaluate tag expressions against the RDF graph.

    Usage:
        qe = QueryEvaluator(tag_service)
        results = qe.evaluate("(proj1|proj2)&research&~draft")
    """

    def __init__(self, th):
        self.th = th

    def evaluate(self, expression: str) -> list:
        tokens = Tokenizer.tokenize(expression)
        parser = Parser(tokens)
        ast = parser.parse()
        evaluator = ASTEvaluator(self.th)
        result_urls = evaluator.eval(ast)
        return result_urls
