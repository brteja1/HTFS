import os
import sqlite3
import logging

logobj = logging.getLogger(__name__)
#logobj.setLevel(logging.error)


import os
import sqlite3

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """Establish a connection to the database."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
        return self.conn

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def initialize_schema(self):
        """Create tables and indexes if the database is new."""
        conn = self.connect()
        cursor = conn.cursor()
        # Create TAGS table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS TAGS (
                ID INTEGER PRIMARY KEY NOT NULL,
                TAGNAME TEXT NOT NULL
            );
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS TAGNAME_INDEX ON TAGS(TAGNAME);')
        # Insert dummy tag if not exists
        cursor.execute('INSERT OR IGNORE INTO TAGS (ID, TAGNAME) VALUES (0, "dummy");')

        # Create TAGLINKS table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS TAGLINKS (
                TAGID INTEGER NOT NULL,
                TAGPARENTID INTEGER NOT NULL
            );
        ''')
        cursor.execute('INSERT OR IGNORE INTO TAGLINKS (TAGID, TAGPARENTID) VALUES (0, 0);')

        # Create RESOURCES table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS RESOURCES (
                ID INTEGER PRIMARY KEY NOT NULL,
                URL TEXT NOT NULL
            );
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS URL_INDEX ON RESOURCES(URL);')
        cursor.execute('INSERT OR IGNORE INTO RESOURCES (ID, URL) VALUES (0, "dummy");')

        # Create RESOURCELINKS table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS RESOURCELINKS (
                RESID INTEGER NOT NULL,
                TAGID INTEGER NOT NULL
            );
        ''')
        cursor.execute('INSERT OR IGNORE INTO RESOURCELINKS (RESID, TAGID) VALUES (0, 0);')

        conn.commit()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


import logging

logobj = logging.getLogger(__name__)

class TagRepository:
    def __init__(self, db_manager : DatabaseManager):
        self.conn = db_manager.conn

    def get_tag_id(self, tag_name) -> int:
        query = "SELECT ID FROM TAGS WHERE TAGNAME=?;"
        res = self.conn.execute(query, (tag_name,))
        row = res.fetchone()
        return row[0] if row else -1

    def get_tag_name(self, tag_id) -> str:
        query = "SELECT TAGNAME FROM TAGS WHERE ID=?;"
        res = self.conn.execute(query, (tag_id,))
        row = res.fetchone()
        return row[0] if row else ""

    def get_tag_list(self) -> list:
        query = "SELECT TAGNAME FROM TAGS WHERE ID > 0;"
        res = self.conn.execute(query)
        return [row[0] for row in res]

    def add_tag(self, tag_name) -> bool:
        if self.get_tag_id(tag_name) > 0:
            return False
        res = self.conn.execute("SELECT max(ID) FROM TAGS;")
        row = res.fetchone()
        max_tag_id = row[0] if row and row[0] is not None else 0
        new_tag_id = max_tag_id + 1
        query = "INSERT INTO TAGS VALUES (?, ?);"
        self.conn.execute(query, (new_tag_id, tag_name))
        self.conn.commit()
        return True

    def rename_tag(self, tag_name, new_tag_name) -> bool:
        if self.get_tag_id(new_tag_name) > 0:
            return False
        tag_id = self.get_tag_id(tag_name)
        if tag_id < 0:
            return False
        query = "UPDATE TAGS SET TAGNAME=? WHERE ID=?;"
        self.conn.execute(query, (new_tag_name, tag_id))
        self.conn.commit()
        return True

    def link_tag(self, tag_name, tag_parent_name) -> bool:
        src_tag_id = self.get_tag_id(tag_name)
        parent_tag_id = self.get_tag_id(tag_parent_name)
        if src_tag_id < 0 or parent_tag_id < 0:
            logobj.error("tags not in db")
            return False
        query = "INSERT INTO TAGLINKS VALUES (?, ?);"
        self.conn.execute(query, (src_tag_id, parent_tag_id))
        self.conn.commit()
        return True

    def unlink_tag(self, tag_name, tag_parent_name) -> bool:
        src_tag_id = self.get_tag_id(tag_name)
        parent_tag_id = self.get_tag_id(tag_parent_name)
        if src_tag_id < 0 or parent_tag_id < 0:
            logobj.error("tags not in db")
            return False
        query = "DELETE FROM TAGLINKS WHERE TAGID=? AND TAGPARENTID=?;"
        self.conn.execute(query, (src_tag_id, parent_tag_id))
        self.conn.commit()
        return True

    def get_parent_tags_by_id(self, tag_id) -> list:
        query = "SELECT TAGPARENTID FROM TAGLINKS WHERE TAGID=?;"
        res = self.conn.execute(query, (tag_id,))
        return [row[0] for row in res]

    def get_parent_tags(self, tag_name) -> list:
        tag_id = self.get_tag_id(tag_name)
        parent_ids = self.get_parent_tags_by_id(tag_id)
        return [self.get_tag_name(pid) for pid in parent_ids]

    def get_child_tags_by_id(self, tag_id) -> list:
        query = "SELECT TAGID FROM TAGLINKS WHERE TAGPARENTID=?;"
        res = self.conn.execute(query, (tag_id,))
        return [row[0] for row in res]

    def get_child_tags(self, tag_name) -> list:
        tag_id = self.get_tag_id(tag_name)
        child_ids = self.get_child_tags_by_id(tag_id)
        return [self.get_tag_name(cid) for cid in child_ids]

    def get_downstream_tags_by_id(self, tag_id) -> list:
        traverse_ids = [tag_id]
        downstream_ids = []
        visited_ids = set()
        while traverse_ids:
            node_id = traverse_ids.pop(0)
            if node_id in visited_ids:
                continue
            visited_ids.add(node_id)
            child_ids = self.get_child_tags_by_id(node_id)
            for cid in child_ids:
                downstream_ids.append(cid)
                traverse_ids.append(cid)
        return downstream_ids

    def get_downstream_tags(self, tag_name) -> list:
        tag_id = self.get_tag_id(tag_name)
        downstream_tagids = self.get_downstream_tags_by_id(tag_id)
        return [self.get_tag_name(dtid) for dtid in downstream_tagids]

    def get_tag_closure(self, tags: list[str]) -> list[str]:
        tags_closure = []
        for tag in tags:
            tagid = self.get_tag_id(tag)
            if tagid < 0:
                logobj.warning("tag %s not present in the db", tag)
                continue
            tags_closure.append(tag)
            downstreamtags = self.get_downstream_tags(tag)
            tags_closure.extend(downstreamtags)
        return list(set(tags_closure))
    

class ResourceRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.conn = db_manager.conn

    def add_resource(self, resource_url) -> int:
        res = self.conn.execute("SELECT max(ID) FROM RESOURCES;")
        row = res.fetchone()
        max_res_id = row[0] if row and row[0] is not None else 0
        new_res_id = max_res_id + 1
        query = "INSERT INTO RESOURCES VALUES (?, ?);"
        self.conn.execute(query, (new_res_id, resource_url))
        self.conn.commit()
        return new_res_id

    def get_resource_id(self, resource_url) -> int:
        query = "SELECT ID FROM RESOURCES WHERE URL=?;"
        res = self.conn.execute(query, (resource_url,))
        row = res.fetchone()
        return row[0] if row else -1

    def get_resource_url(self, res_id) -> str:
        query = "SELECT URL FROM RESOURCES WHERE ID=?;"
        res = self.conn.execute(query, (res_id,))
        row = res.fetchone()
        return row[0] if row else ""

    def get_resource_ids(self) -> list:
        query = "SELECT ID FROM RESOURCES WHERE ID > 0;"
        res = self.conn.execute(query)
        return [row[0] for row in res]

    def update_resource_url_by_id(self, resource_id, resource_url):
        query = "UPDATE RESOURCES SET URL=? WHERE ID=?;"
        self.conn.execute(query, (resource_url, resource_id))
        self.conn.commit()

    def update_resource_url(self, resource_url, new_resource_url):
        res_id = self.get_resource_id(resource_url)
        if res_id < 0:
            logobj.error("resource not tracked")
            return
        self.update_resource_url_by_id(res_id, new_resource_url)

    def update_resource_sub_url(self, sub_resource_url, update_url):
        res_ids = self.get_resource_ids_containing_url(sub_resource_url)
        for res_id in res_ids:
            url = self.get_resource_url(res_id)
            url = url.replace(sub_resource_url, update_url, 1)
            self.update_resource_url_by_id(res_id, url)

    def get_resource_ids_containing_url(self, sub_resource_url) -> list:
        query = "SELECT ID FROM RESOURCES WHERE URL LIKE ?"
        res = self.conn.execute(query, (f"%{sub_resource_url}%",))
        return [row[0] for row in res]

    def del_resource(self, resource_url):
        res_id = self.get_resource_id(resource_url)
        if res_id < 0:
            logobj.warning("resource not tracked")
            return
        # Remove all tag links for this resource
        self.del_all_resource_tags(res_id)
        query = "DELETE FROM RESOURCES WHERE ID=?;"
        self.conn.execute(query, (res_id,))
        self.conn.commit()

    def del_all_resource_tags(self, resource_id):
        query = "DELETE FROM RESOURCELINKS WHERE RESID=?;"
        self.conn.execute(query, (resource_id,))
        self.conn.commit()

    def get_resource_tags_by_id(self, resource_id) -> list:
        query = "SELECT TAGID FROM RESOURCELINKS WHERE RESID=?;"
        res = self.conn.execute(query, (resource_id,))
        return [row[0] for row in res]

    def get_resource_tags(self, resource_url) -> list:
        res_id = self.get_resource_id(resource_url)
        return self.get_resource_tags_by_id(res_id)

    def add_resource_tag_by_id(self, resource_id, tag_id):
        current_tags = self.get_resource_tags_by_id(resource_id)
        if tag_id not in current_tags:
            query = "INSERT INTO RESOURCELINKS VALUES (?, ?);"
            self.conn.execute(query, (resource_id, tag_id))
            self.conn.commit()

    def get_resources_by_tag_id(self, tag_ids) :
        resource_ids = []
        for tid in tag_ids :
            query = "SELECT RESID FROM RESOURCELINKS WHERE TAGID=?;"
            res = self.conn.execute(query, (tid,))
            res_ids = [row[0] for row in res]
            resource_ids.extend(res_ids)
        resource_ids = list(set(resource_ids))
        return resource_ids    

    def del_resource_tag_by_id(self, resource_id, tag_id):
        current_tags = self.get_resource_tags_by_id(resource_id)
        if tag_id in current_tags:
            query = "DELETE FROM RESOURCELINKS WHERE RESID=? AND TAGID=?;"
            self.conn.execute(query, (resource_id, tag_id))
            self.conn.commit()

    def add_resource_tags(self, resource_url, tag_ids):
        res_id = self.get_resource_id(resource_url)
        if res_id < 0:
            logobj.error("resource not tracked")
            return []
        unsuccessful_tags = []
        for tag_id in tag_ids:
            if tag_id > 0:
                self.add_resource_tag_by_id(res_id, tag_id)
            else:
                unsuccessful_tags.append(tag_id)
        return unsuccessful_tags

    def del_resource_tags(self, resource_url, tag_ids):
        res_id = self.get_resource_id(resource_url)
        if res_id < 0:
            logobj.error("resource not tracked")
            return
        for tag_id in tag_ids:
            if tag_id > 0:
                self.del_resource_tag_by_id(res_id, tag_id)
            else:
                logobj.error("tag not in db")


