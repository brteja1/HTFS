import os
from TagService import TagService

def test():
    print("Initializing db..")
    testdb = "testdb.db.test"
    if os.path.exists(testdb):
        os.remove(testdb)
    ts = TagService(testdb)
    ts.initialize()

    # Add tags
    ts.add_tag("eresources")
    ts.add_tag("books")
    ts.add_tag("articles")
    ts.add_tag("researchpaper")
    ts.link_tag("books", "eresources")
    ts.link_tag("articles", "eresources")
    ts.link_tag("researchpaper", "articles")

    ts.add_tag("topics")
    ts.add_tag("mathematics")
    ts.add_tag("appliedmathematics")
    ts.add_tag("calculus")
    ts.add_tag("physics")
    ts.link_tag("mathematics", "topics")
    ts.link_tag("physics", "topics")
    ts.link_tag("appliedmathematics", "mathematics")
    ts.link_tag("calculus", "mathematics")

    pids = ts.get_tag_list()
    print("All tags:", pids)
    parent_tags = ts.get_tag_closure(["articles"])
    print("Tag closure for 'articles':", parent_tags)
    tid = ts.get_tag_id("books")
    print("ID for 'books':", tid)
    tname = ts.get_tag_name(tid)
    print("Name for tag id", tid, ":", tname)
    cids = ts.get_tag_closure(["eresources"])
    print("Tag closure for 'eresources':", cids)
    dids = ts.get_tag_closure(["topics"])
    print("Tag closure for 'topics':", dids)

    res_path = "/this/is/dummy/path"
    ts.add_resource(res_path)
    rid = ts.get_resource_id(res_path)
    print("Resource ID for", res_path, ":", rid)
    ts.add_resource_tags(res_path, ["books", "calculus"])
    tags = ts.get_resource_tags(res_path)
    print("Tags for resource", res_path, ":", tags)


if __name__ == '__main__':
    test()