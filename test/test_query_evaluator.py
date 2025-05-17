import unittest
from QueryEvaluator import QueryEvaluator, QueryOptimizer
import TagHandler

import os

class TestQueryEvaluator(unittest.TestCase):
    def setUp(self):
        self.th = TagHandler.TagHandler('.tagfs.db.test')
        self.qe = QueryEvaluator(self.th)
        # Add some tags and resources for testing
        self.th.add_tag('a')
        self.th.add_tag('b')
        self.th.add_tag('c')
        self.th.add_resource('res1')
        self.th.add_resource('res2')
        # Link resources to tags as needed for your logic

    def tearDown(self):
        self.th = None
        self.qe = None
        #delete the test database file if it exists        
        if os.path.exists('.tagfs.db.test'):
            os.remove('.tagfs.db.test')

    def test_fully_parenthesize(self):
        expr = 'a & b | ~c'
        paren = self.qe.fully_parenthesize_expression(expr)
        self.assertIsInstance(paren, str)
        self.assertIn('(', paren)

    def test_optimizer(self):
        expr = '~(~a)'
        optimized = QueryOptimizer.optimize(expr, QueryEvaluator.tokenize, QueryEvaluator.VALID_OPERATORS, QueryEvaluator.LEFT_PAREN, QueryEvaluator.RIGHT_PAREN)
        self.assertIn('a', optimized)

    def test_basic_eval(self):
        # This is a placeholder; you should expand with real logic
        expr = 'a & b'
        result = self.qe.evaluate_query(expr)
        self.assertIsInstance(result, list)

if __name__ == '__main__':
    unittest.main()
