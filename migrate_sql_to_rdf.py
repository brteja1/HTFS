#!/usr/bin/env python3
"""One-time migration script: converts .tagfs.db (SQLite) to a minimal .tagfs.ttl."""

import os
import sys
import sqlite3
from rdflib import Graph, Namespace
from rdflib.namespace import SKOS

HTFS = Namespace("http://htfs.example.org/ontology#")


def migrate(db_path, ttl_path):
    if not os.path.exists(db_path):
        print(f"Error: SQLite database not found: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    g = Graph()
    g.bind("htfs", HTFS)
    g.bind("skos", SKOS)

    # --- Tags ---
    cursor.execute("SELECT ID, TAGNAME FROM TAGS WHERE ID > 0;")
    tags = cursor.fetchall()
    tag_ids = {tag_id for tag_id, _ in tags}

    # --- Tag links ---
    cursor.execute("SELECT TAGID, TAGPARENTID FROM TAGLINKS WHERE TAGID > 0 AND TAGPARENTID > 0;")
    for child_id, parent_id in cursor.fetchall():
        if child_id in tag_ids and parent_id in tag_ids:
            g.add((HTFS[f"tag_{child_id}"], SKOS.broader, HTFS[f"tag_{parent_id}"]))

    # --- Resources ---
    cursor.execute("SELECT ID, URL FROM RESOURCES WHERE ID > 0;")
    resources = cursor.fetchall()
    resource_ids = {res_id for res_id, _ in resources}

    # --- Resource-tag links ---
    cursor.execute("SELECT RESID, TAGID FROM RESOURCELINKS WHERE RESID > 0 AND TAGID > 0;")
    for res_id, tag_id in cursor.fetchall():
        if res_id in resource_ids and tag_id in tag_ids:
            res_uri = HTFS[f"resource_{res_id}"]
            g.add((res_uri, HTFS.hasTag, HTFS[f"tag_{tag_id}"]))

    conn.close()

    g.serialize(destination=ttl_path, format="turtle")
    print(f"Migrated {len(tags)} tags, {len(resources)} resources to {ttl_path}")
    return True


if __name__ == "__main__":
    if len(sys.argv) == 3:
        db_path, ttl_path = sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 1:
        db_path = ".tagfs.db"
        ttl_path = ".tagfs.ttl"
    else:
        print(f"Usage: {sys.argv[0]} [input.db output.ttl]")
        sys.exit(1)

    success = migrate(db_path, ttl_path)
    sys.exit(0 if success else 1)
