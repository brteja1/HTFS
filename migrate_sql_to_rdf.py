#!/usr/bin/env python3
"""One-time migration script: converts .tagfs.db (SQLite) to .tagfs.ttl (RDF/Turtle)."""

import os
import sys
import sqlite3
from rdflib import Graph, Namespace, Literal, RDF
from rdflib.namespace import SKOS, XSD

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
    tag_id_to_name = {}
    max_tag_id = 0
    for tag_id, tag_name in tags:
        tag_id_to_name[tag_id] = tag_name
        tag_uri = HTFS[f"tag_{tag_name}"]
        g.add((tag_uri, RDF.type, SKOS.Concept))
        g.add((tag_uri, SKOS.prefLabel, Literal(tag_name)))
        g.add((tag_uri, HTFS.id, Literal(tag_id, datatype=XSD.integer)))
        max_tag_id = max(max_tag_id, tag_id)

    # --- Tag links ---
    cursor.execute("SELECT TAGID, TAGPARENTID FROM TAGLINKS WHERE TAGID > 0 AND TAGPARENTID > 0;")
    for child_id, parent_id in cursor.fetchall():
        child_name = tag_id_to_name.get(child_id)
        parent_name = tag_id_to_name.get(parent_id)
        if child_name and parent_name:
            g.add((HTFS[f"tag_{child_name}"], SKOS.broader, HTFS[f"tag_{parent_name}"]))

    # --- Resources ---
    cursor.execute("SELECT ID, URL FROM RESOURCES WHERE ID > 0;")
    resources = cursor.fetchall()
    max_res_id = 0
    for res_id, url in resources:
        res_uri = HTFS[f"resource_{res_id}"]
        g.add((res_uri, RDF.type, HTFS.Resource))
        g.add((res_uri, HTFS.url, Literal(url)))
        g.add((res_uri, HTFS.id, Literal(res_id, datatype=XSD.integer)))
        max_res_id = max(max_res_id, res_id)

    # --- Resource-tag links ---
    cursor.execute("SELECT RESID, TAGID FROM RESOURCELINKS WHERE RESID > 0 AND TAGID > 0;")
    for res_id, tag_id in cursor.fetchall():
        tag_name = tag_id_to_name.get(tag_id)
        if tag_name:
            res_uri = HTFS[f"resource_{res_id}"]
            g.add((res_uri, HTFS.hasTag, HTFS[f"tag_{tag_name}"]))

    # --- Metadata counters ---
    g.add((HTFS.meta, HTFS.maxTagId, Literal(max_tag_id, datatype=XSD.integer)))
    g.add((HTFS.meta, HTFS.maxResourceId, Literal(max_res_id, datatype=XSD.integer)))

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
