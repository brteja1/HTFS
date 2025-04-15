import TagHandler
import re
from functools import lru_cache


# Implementation of shuning yard algorithm
class QueryEvaluator:
    OPERATORS = {'|': 0, '~': 0, '&': 1}
    VALID_OPERATORS = set(['|', '&', '~'])
    LEFT_PAREN = '('
    RIGHT_PAREN = ')'

    def __init__(self, th: TagHandler.TagHandler) :
        self.th = th
        self.operators = []
        self.values = []
        self.fullresources = []

    def tokenize(self, querystr: str) -> list[str] :
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

    def evaluate_query(self, expression):
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
