import os
import unittest
from TagService import TagService

class TestTagService(unittest.TestCase):
    TEST_DB = "testdb.db.test"

    def setUp(self):
        # run in folder where this test file is located
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        # remove the test database if it exists
        if os.path.exists(self.TEST_DB):
            os.remove(self.TEST_DB)
        self.ts = TagService(self.TEST_DB)
        self.ts.initialize()


    def test_tag_and_resource_operations(self):
        # Add tags and link them
        self.ts.add_tag("eresources")
        self.ts.add_tag("books")
        self.ts.add_tag("articles")
        self.ts.add_tag("researchpaper")
        self.ts.link_tag("books", "eresources")
        self.ts.link_tag("articles", "eresources")
        self.ts.link_tag("researchpaper", "articles")

        self.ts.add_tag("topics")
        self.ts.add_tag("mathematics")
        self.ts.add_tag("appliedmathematics")
        self.ts.add_tag("calculus")
        self.ts.add_tag("physics")
        self.ts.link_tag("mathematics", "topics")
        self.ts.link_tag("physics", "topics")
        self.ts.link_tag("appliedmathematics", "mathematics")
        self.ts.link_tag("calculus", "mathematics")

        pids = self.ts.get_tag_list()
        self.assertIn("books", pids)
        parent_tags = self.ts.get_tag_closure(["articles"])
        self.assertIn("articles", parent_tags)
        tid = self.ts.get_tag_id("books")
        self.assertTrue(isinstance(tid, int) and tid > 0)
        tname = self.ts.get_tag_name(tid)
        self.assertEqual(tname, "books")
        cids = self.ts.get_tag_closure(["eresources"])
        self.assertIn("books", cids)
        dids = self.ts.get_tag_closure(["topics"])
        self.assertIn("mathematics", dids)

        res_path = "/this/is/dummy/path"
        self.ts.add_resource(res_path)
        rid = self.ts.get_resource_id(res_path)
        self.assertTrue(isinstance(rid, int) and rid > 0)
        self.ts.add_resource_tags(res_path, ["books", "calculus"])
        tags = self.ts.get_resource_tags(res_path)
        self.assertIn("books", tags)
        self.assertIn("calculus", tags)

if __name__ == '__main__':
    unittest.main()