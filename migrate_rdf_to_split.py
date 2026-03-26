#!/usr/bin/env python3
"""
Migration script: Convert old RDF-only format to new split SQLite+RDF format.

Old format:
  - .tagfs.ttl: Contains tag names, resource URLs, hierarchy, and links

New format:
  - .tagfs.db: SQLite with TAGS (id↔name), RESOURCES (id↔url), ID_SEQUENCES
  - .tagfs.ttl: RDF with only skos:broader (hierarchy) and htfs:hasTag (resource-tag links)

Usage:
    python migrate_rdf_to_split.py /path/to/tagfs_boundary
    python migrate_rdf_to_split.py --rebuild /path/to/tagfs_boundary
"""

import os
import sys
import logging
import argparse

logging.basicConfig(level='INFO')
logobj = logging.getLogger(__name__)


def migrate_rdf_to_split(tagfs_boundary):
    """
    Migrate from single RDF file to split SQLite+RDF format.

    Reads the existing .tagfs.ttl, extracts:
      - Tag name↔id mappings → SQLite TAGS table
      - Resource url↔id mappings → SQLite RESOURCES table
      - Tag hierarchy (skos:broader) → RDF .tagfs.ttl
      - Resource-tag links (htfs:hasTag) → RDF .tagfs.ttl
    """
    ttl_path = os.path.join(tagfs_boundary, ".tagfs.ttl")
    db_path = os.path.join(tagfs_boundary, ".tagfs.db")

    if not os.path.exists(ttl_path):
        logobj.error("No .tagfs.ttl found at %s", tagfs_boundary)
        return False

    if os.path.exists(db_path):
        logobj.error("SQLite database already exists at %s", db_path)
        logobj.error("Use --rebuild to overwrite existing database")
        return False

    logobj.info("Reading RDF from %s", ttl_path)

    from rdflib import Graph, Namespace
    from rdflib.namespace import SKOS, RDF

    HTFS = Namespace("http://htfs.example.org/ontology#")

    # Load the existing RDF graph
    g = Graph()
    g.parse(ttl_path, format="turtle")

    logobj.info("RDF graph loaded: %d triples", len(g))

    # Create SQLite database
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Create schema
    conn.execute('''
        CREATE TABLE TAGS (
            ID INTEGER PRIMARY KEY NOT NULL,
            TAGNAME TEXT NOT NULL UNIQUE
        );
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS TAGNAME_INDEX ON TAGS(TAGNAME);')

    conn.execute('''
        CREATE TABLE RESOURCES (
            ID INTEGER PRIMARY KEY NOT NULL,
            URL TEXT NOT NULL UNIQUE
        );
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS URL_INDEX ON RESOURCES(URL);')

    conn.execute('''
        CREATE TABLE ID_SEQUENCES (
            NAME TEXT PRIMARY KEY,
            MAX_ID INTEGER NOT NULL DEFAULT 0
        );
    ''')
    conn.execute('INSERT OR IGNORE INTO ID_SEQUENCES (NAME, MAX_ID) VALUES ("TAG", 0);')
    conn.execute('INSERT OR IGNORE INTO ID_SEQUENCES (NAME, MAX_ID) VALUES ("RESOURCE", 0);')

    # Create RDF graph for relationships
    new_g = Graph()
    new_g.bind("htfs", HTFS)
    new_g.bind("skos", SKOS)

    # Track max IDs
    max_tag_id = 0
    max_res_id = 0

    # Extract tag data and build new RDF
    logobj.info("Processing tags...")
    tag_uri_map = {}
    for tag_uri in g.subjects(RDF.type, SKOS.Concept):
        tag_name = str(tag_uri)
        if tag_name.startswith("http://htfs.example.org/ontology#tag_"):
            name = tag_name.replace("http://htfs.example.org/ontology#tag_", "")

            # Get numeric ID
            tag_id = None
            for id_obj in g.objects(tag_uri, HTFS.id):
                tag_id = int(id_obj)
                break

            if tag_id is None:
                # Generate new ID
                max_tag_id += 1
                tag_id = max_tag_id
            else:
                max_tag_id = max(max_tag_id, tag_id)

            # Insert into SQLite
            conn.execute("INSERT INTO TAGS (ID, TAGNAME) VALUES (?, ?);", (tag_id, name))

            tag_uri_map[tag_uri] = HTFS[f"tag_{tag_id}"]

    logobj.info("Processed %d tags", max_tag_id)

    for old_child_uri, new_child_uri in tag_uri_map.items():
        for old_parent_uri in g.objects(old_child_uri, SKOS.broader):
            new_parent_uri = tag_uri_map.get(old_parent_uri)
            if new_parent_uri is not None:
                new_g.add((new_child_uri, SKOS.broader, new_parent_uri))

    # Extract resource data and build new RDF
    logobj.info("Processing resources...")
    resource_uri_map = {}
    for res_uri in g.subjects(RDF.type, HTFS.Resource):
        # Get URL
        url = None
        for url_obj in g.objects(res_uri, HTFS.url):
            url = str(url_obj)
            break

        if url is None:
            continue

        # Get numeric ID
        res_id = None
        for id_obj in g.objects(res_uri, HTFS.id):
            res_id = int(id_obj)
            break

        if res_id is None:
            max_res_id += 1
            res_id = max_res_id
        else:
            max_res_id = max(max_res_id, res_id)

        # Insert into SQLite
        conn.execute("INSERT INTO RESOURCES (ID, URL) VALUES (?, ?);", (res_id, url))

        resource_uri_map[res_uri] = HTFS[f"resource_{res_id}"]

    logobj.info("Processed %d resources", max_res_id)

    for old_res_uri, new_res_uri in resource_uri_map.items():
        for old_tag_uri in g.objects(old_res_uri, HTFS.hasTag):
            new_tag_uri = tag_uri_map.get(old_tag_uri)
            if new_tag_uri is not None:
                new_g.add((new_res_uri, HTFS.hasTag, new_tag_uri))

    # Update sequences
    conn.execute("UPDATE ID_SEQUENCES SET MAX_ID=? WHERE NAME='TAG';", (max_tag_id,))
    conn.execute("UPDATE ID_SEQUENCES SET MAX_ID=? WHERE NAME='RESOURCE';", (max_res_id,))

    # Save SQLite
    conn.commit()
    conn.close()

    # Save new RDF graph
    new_g.serialize(destination=ttl_path, format="turtle")
    logobj.info("Saved new RDF to %s", ttl_path)

    logobj.info("Migration complete!")
    logobj.info("  - SQLite DB: %s", db_path)
    logobj.info("  - RDF file: %s", ttl_path)
    logobj.info("  - Tags: %d, Resources: %d", max_tag_id, max_res_id)

    return True


def rebuild_from_rdf(tagfs_boundary):
    """
    Rebuild SQLite database from existing legacy RDF file.
    Minimal RDF generated by the split backend does not contain enough
    resource metadata to reconstruct the RESOURCES table.
    """
    ttl_path = os.path.join(tagfs_boundary, ".tagfs.ttl")
    db_path = os.path.join(tagfs_boundary, ".tagfs.db")

    if not os.path.exists(ttl_path):
        logobj.error("No .tagfs.ttl found at %s", tagfs_boundary)
        return False

    logobj.info("Rebuilding SQLite database from RDF...")

    from rdflib import Graph, Namespace
    from rdflib.namespace import SKOS, RDF

    HTFS = Namespace("http://htfs.example.org/ontology#")

    g = Graph()
    g.parse(ttl_path, format="turtle")

    has_resource_links = any(g.triples((None, HTFS.hasTag, None)))
    has_resource_urls = any(g.triples((None, HTFS.url, None)))
    if has_resource_links and not has_resource_urls:
        logobj.error("Minimal RDF format is not supported for --rebuild; resource URLs are only stored in SQLite")
        return False

    # Remove existing SQLite
    if os.path.exists(db_path):
        os.remove(db_path)
        logobj.info("Removed existing SQLite database")

    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Recreate schema
    conn.execute('''
        CREATE TABLE TAGS (
            ID INTEGER PRIMARY KEY NOT NULL,
            TAGNAME TEXT NOT NULL UNIQUE
        );
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS TAGNAME_INDEX ON TAGS(TAGNAME);')

    conn.execute('''
        CREATE TABLE RESOURCES (
            ID INTEGER PRIMARY KEY NOT NULL,
            URL TEXT NOT NULL UNIQUE
        );
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS URL_INDEX ON RESOURCES(URL);')

    conn.execute('''
        CREATE TABLE ID_SEQUENCES (
            NAME TEXT PRIMARY KEY,
            MAX_ID INTEGER NOT NULL DEFAULT 0
        );
    ''')
    conn.execute('INSERT OR IGNORE INTO ID_SEQUENCES (NAME, MAX_ID) VALUES ("TAG", 0);')
    conn.execute('INSERT OR IGNORE INTO ID_SEQUENCES (NAME, MAX_ID) VALUES ("RESOURCE", 0);')

    max_tag_id = 0
    max_res_id = 0

    # Process tags
    for tag_uri in g.subjects(RDF.type, SKOS.Concept):
        tag_name = str(tag_uri)
        if tag_name.startswith("http://htfs.example.org/ontology#tag_"):
            name = tag_name.replace("http://htfs.example.org/ontology#tag_", "")
            tag_id = None
            for id_obj in g.objects(tag_uri, HTFS.id):
                tag_id = int(id_obj)
                break
            if tag_id is None:
                continue
            conn.execute("INSERT INTO TAGS (ID, TAGNAME) VALUES (?, ?);", (tag_id, name))
            max_tag_id = max(max_tag_id, tag_id)

    # Process resources
    for res_uri in g.subjects(RDF.type, HTFS.Resource):
        url = None
        for url_obj in g.objects(res_uri, HTFS.url):
            url = str(url_obj)
            break
        if url is None:
            continue
        res_id = None
        for id_obj in g.objects(res_uri, HTFS.id):
            res_id = int(id_obj)
            break
        if res_id is None:
            continue
        conn.execute("INSERT INTO RESOURCES (ID, URL) VALUES (?, ?);", (res_id, url))
        max_res_id = max(max_res_id, res_id)

    conn.execute("UPDATE ID_SEQUENCES SET MAX_ID=? WHERE NAME='TAG';", (max_tag_id,))
    conn.execute("UPDATE ID_SEQUENCES SET MAX_ID=? WHERE NAME='RESOURCE';", (max_res_id,))

    conn.commit()
    conn.close()

    logobj.info("Rebuild complete!")
    logobj.info("  - Tags: %d, Resources: %d", max_tag_id, max_res_id)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Migrate from RDF-only to split SQLite+RDF format"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Tagfs boundary directory (default: current directory)"
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild SQLite from existing RDF (if SQLite is corrupted)"
    )

    args = parser.parse_args()
    path = os.path.realpath(args.path)

    if not os.path.isdir(path):
        logobj.error("Path is not a directory: %s", path)
        sys.exit(1)

    if args.rebuild:
        success = rebuild_from_rdf(path)
    else:
        success = migrate_rdf_to_split(path)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
