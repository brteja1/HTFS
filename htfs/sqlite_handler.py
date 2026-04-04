import os
import sqlite3
import logging

logobj = logging.getLogger(__name__)


class SQLiteManager:
    """SQLite manager for fast ID lookups - url↔id, name↔id mappings."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def initialize_schema(self):
        conn = self.connect()
        cursor = conn.cursor()

        # TAGS table: name ↔ id mapping
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS TAGS (
                ID INTEGER PRIMARY KEY NOT NULL,
                TAGNAME TEXT NOT NULL UNIQUE
            );
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS TAGNAME_INDEX ON TAGS(TAGNAME);')

        # RESOURCES table: url ↔ id mapping
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS RESOURCES (
                ID INTEGER PRIMARY KEY NOT NULL,
                URL TEXT NOT NULL UNIQUE
            );
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS URL_INDEX ON RESOURCES(URL);')

        # ID sequences
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ID_SEQUENCES (
                NAME TEXT PRIMARY KEY,
                MAX_ID INTEGER NOT NULL DEFAULT 0
            );
        ''')
        cursor.execute('INSERT OR IGNORE INTO ID_SEQUENCES (NAME, MAX_ID) VALUES ("TAG", 0);')
        cursor.execute('INSERT OR IGNORE INTO ID_SEQUENCES (NAME, MAX_ID) VALUES ("RESOURCE", 0);')

        conn.commit()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class TagRepository:
    """SQLite-based tag repository for fast name↔id lookups."""

    def __init__(self, db_manager: SQLiteManager):
        self.db_manager = db_manager

    @property
    def conn(self):
        return self.db_manager.conn

    def get_tag_id(self, tag_name) -> int:
        query = "SELECT ID FROM TAGS WHERE TAGNAME=?;"
        res = self.conn.execute(query, (tag_name,))
        row = res.fetchone()
        return row[0] if row else -1

    def get_tag_name(self, tag_id) -> int:
        query = "SELECT TAGNAME FROM TAGS WHERE ID=?;"
        res = self.conn.execute(query, (tag_id,))
        row = res.fetchone()
        return row[0] if row else ""

    def get_tag_list(self) -> list:
        query = "SELECT TAGNAME FROM TAGS WHERE ID > 0 ORDER BY TAGNAME;"
        res = self.conn.execute(query)
        return [row[0] for row in res]

    def get_tag_ids(self) -> list:
        """Return all tag IDs."""
        query = "SELECT ID FROM TAGS WHERE ID > 0;"
        res = self.conn.execute(query)
        return [row[0] for row in res]

    def add_tag(self, tag_name) -> bool:
        if self.get_tag_id(tag_name) > 0:
            return False

        # Get next ID from sequence
        cursor = self.conn.execute(
            "SELECT MAX_ID FROM ID_SEQUENCES WHERE NAME='TAG';"
        )
        row = cursor.fetchone()
        new_id = (row[0] if row else 0) + 1

        self.conn.execute(
            "INSERT INTO TAGS (ID, TAGNAME) VALUES (?, ?);",
            (new_id, tag_name)
        )
        self.conn.execute(
            "UPDATE ID_SEQUENCES SET MAX_ID=? WHERE NAME='TAG';",
            (new_id,)
        )
        self.conn.commit()
        return new_id

    def add_tag_with_id(self, tag_name, tag_id) -> bool:
        """Add a tag with a pre-allocated ID (for RDF sync)."""
        if self.get_tag_id(tag_name) > 0:
            return False
        self.conn.execute(
            "INSERT INTO TAGS (ID, TAGNAME) VALUES (?, ?);",
            (tag_id, tag_name)
        )
        # Update sequence if this ID is higher
        self.conn.execute(
            "UPDATE ID_SEQUENCES SET MAX_ID=? WHERE NAME='TAG' AND MAX_ID < ?;",
            (tag_id, tag_id)
        )
        self.conn.commit()
        return True

    def rename_tag(self, tag_name, new_tag_name) -> bool:
        if self.get_tag_id(new_tag_name) > 0:
            return False
        tag_id = self.get_tag_id(tag_name)
        if tag_id < 0:
            return False
        self.conn.execute(
            "UPDATE TAGS SET TAGNAME=? WHERE ID=?;",
            (new_tag_name, tag_id)
        )
        self.conn.commit()
        return True

    def delete_tag(self, tag_id) -> bool:
        """Delete a tag by ID."""
        if tag_id < 0:
            return False
        cursor = self.conn.execute("DELETE FROM TAGS WHERE ID=?;", (tag_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def get_max_tag_id(self) -> int:
        """Get the current max tag ID from sequences."""
        cursor = self.conn.execute(
            "SELECT MAX_ID FROM ID_SEQUENCES WHERE NAME='TAG';"
        )
        row = cursor.fetchone()
        return row[0] if row else 0


class ResourceRepository:
    """SQLite-based resource repository for fast url↔id lookups."""

    def __init__(self, db_manager: SQLiteManager):
        self.db_manager = db_manager

    @property
    def conn(self):
        return self.db_manager.conn

    def get_resource_id(self, resource_url) -> int:
        query = "SELECT ID FROM RESOURCES WHERE URL=?;"
        res = self.conn.execute(query, (resource_url,))
        row = res.fetchone()
        return row[0] if row else -1

    def get_resource_url(self, resource_id) -> str:
        query = "SELECT URL FROM RESOURCES WHERE ID=?;"
        res = self.conn.execute(query, (resource_id,))
        row = res.fetchone()
        return row[0] if row else ""

    def get_resource_ids(self) -> list:
        query = "SELECT ID FROM RESOURCES WHERE ID > 0;"
        res = self.conn.execute(query)
        return [row[0] for row in res]

    def add_resource(self, resource_url) -> int:
        if self.get_resource_id(resource_url) > 0:
            return -1

        cursor = self.conn.execute(
            "SELECT MAX_ID FROM ID_SEQUENCES WHERE NAME='RESOURCE';"
        )
        row = cursor.fetchone()
        new_id = (row[0] if row else 0) + 1

        self.conn.execute(
            "INSERT INTO RESOURCES (ID, URL) VALUES (?, ?);",
            (new_id, resource_url)
        )
        self.conn.execute(
            "UPDATE ID_SEQUENCES SET MAX_ID=? WHERE NAME='RESOURCE';",
            (new_id,)
        )
        self.conn.commit()
        return new_id

    def add_resource_with_id(self, resource_url, resource_id) -> bool:
        """Add a resource with a pre-allocated ID (for RDF sync)."""
        if self.get_resource_id(resource_url) > 0:
            return False
        self.conn.execute(
            "INSERT INTO RESOURCES (ID, URL) VALUES (?, ?);",
            (resource_id, resource_url)
        )
        # Update sequence if this ID is higher
        self.conn.execute(
            "UPDATE ID_SEQUENCES SET MAX_ID=? WHERE NAME='RESOURCE' AND MAX_ID < ?;",
            (resource_id, resource_id)
        )
        self.conn.commit()
        return True

    def delete_resource(self, resource_url) -> bool:
        res_id = self.get_resource_id(resource_url)
        if res_id < 0:
            return False
        self.conn.execute("DELETE FROM RESOURCES WHERE ID=?;", (res_id,))
        self.conn.commit()
        return res_id

    def update_resource_url(self, old_url, new_url) -> bool:
        res_id = self.get_resource_id(old_url)
        if res_id < 0:
            return False
        if self.get_resource_id(new_url) > 0:
            return False
        self.conn.execute(
            "UPDATE RESOURCES SET URL=? WHERE ID=?;",
            (new_url, res_id)
        )
        self.conn.commit()
        return True

    def get_max_resource_id(self) -> int:
        """Get the current max resource ID from sequences."""
        cursor = self.conn.execute(
            "SELECT MAX_ID FROM ID_SEQUENCES WHERE NAME='RESOURCE';"
        )
        row = cursor.fetchone()
        return row[0] if row else 0

    # Note: Resource-Tag links are now managed by RDFHandler
    # These are kept for compatibility but should not be used
