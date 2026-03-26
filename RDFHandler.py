import os
import logging
from rdflib import Graph, Namespace, Literal, URIRef, RDF
from rdflib.namespace import SKOS, XSD

logobj = logging.getLogger(__name__)

HTFS = Namespace("http://htfs.example.org/ontology#")


class RDFHandler:
    """
    RDF handler for tag hierarchy and resource-tag relationships.

    SQLite stores: tag name↔id, resource url↔id (fast lookups)
    RDF stores: tag hierarchy (skos:broader), resource-tag links (htfs:hasTag)

    Only loads/parses RDF when needed, serializes only on close().
    """

    def __init__(self, ttl_path):
        self.ttl_path = ttl_path
        self.graph = None
        self._dirty = False

    def connect(self):
        """Load RDF graph from disk (lazy loading)."""
        if self.graph is None:
            self.graph = Graph()
            self.graph.bind("htfs", HTFS)
            self.graph.bind("skos", SKOS)
            if os.path.exists(self.ttl_path):
                self.graph.parse(self.ttl_path, format="turtle")
        return self.graph

    def close(self):
        """Serialize RDF to disk only if dirty, then clear memory."""
        if self.graph is not None and self._dirty:
            self._save()
        self.graph = None
        self._dirty = False

    def _mark_dirty(self):
        """Mark the graph as modified."""
        self._dirty = True

    def _save(self):
        """Serialize graph to Turtle file."""
        if self.graph is not None:
            self.graph.serialize(destination=self.ttl_path, format="turtle")

    def flush(self):
        """Explicitly save RDF to disk."""
        if self.graph is not None and self._dirty:
            self._save()
            self._dirty = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # -------------------------------------------------------------------------
    # Tag Hierarchy Operations (skos:broader)
    # -------------------------------------------------------------------------

    def _tag_uri(self, tag_id):
        """Convert tag ID to RDF URI."""
        return HTFS[f"tag_{tag_id}"]

    def _res_uri(self, resource_id):
        """Convert resource ID to RDF URI."""
        return HTFS[f"resource_{resource_id}"]

    def add_tag_link(self, tag_id, parent_tag_id):
        """Add a broader (parent) relationship between tags."""
        self.connect()
        child_uri = self._tag_uri(tag_id)
        parent_uri = self._tag_uri(parent_tag_id)
        self.graph.add((child_uri, SKOS.broader, parent_uri))
        self._mark_dirty()

    def remove_tag_link(self, tag_id, parent_tag_id):
        """Remove a broader relationship between tags."""
        self.connect()
        child_uri = self._tag_uri(tag_id)
        parent_uri = self._tag_uri(parent_tag_id)
        self.graph.remove((child_uri, SKOS.broader, parent_uri))
        self._mark_dirty()

    def get_parent_tag_ids(self, tag_id) -> list:
        """Get immediate parent tag IDs for a tag."""
        self.connect()
        tag_uri = self._tag_uri(tag_id)
        parent_ids = []
        for parent_uri in self.graph.objects(tag_uri, SKOS.broader):
            # Extract tag ID from URI (htfs:tag_N → N)
            try:
                parent_id = int(str(parent_uri).split("_")[-1])
                parent_ids.append(parent_id)
            except (ValueError, IndexError):
                continue
        return parent_ids

    def get_child_tag_ids(self, tag_id) -> list:
        """Get immediate child tag IDs for a tag."""
        self.connect()
        tag_uri = self._tag_uri(tag_id)
        child_ids = []
        for child_uri in self.graph.subjects(SKOS.broader, tag_uri):
            try:
                child_id = int(str(child_uri).split("_")[-1])
                child_ids.append(child_id)
            except (ValueError, IndexError):
                continue
        return child_ids

    def get_tag_closure_ids(self, tag_ids) -> set:
        """Get transitive closure of tag IDs (all descendants)."""
        self.connect()
        closure = set(tag_ids)
        queue = list(tag_ids)
        while queue:
            tag_id = queue.pop(0)
            children = self.get_child_tag_ids(tag_id)
            for child_id in children:
                if child_id not in closure:
                    closure.add(child_id)
                    queue.append(child_id)
        return closure

    def get_all_tag_links(self) -> list:
        """Get all tag hierarchy links as [(tagid, parentid), ...]."""
        self.connect()
        links = []
        for child_uri, _, parent_uri in self.graph.triples((None, SKOS.broader, None)):
            try:
                child_id = int(str(child_uri).split("_")[-1])
                parent_id = int(str(parent_uri).split("_")[-1])
                links.append((child_id, parent_id))
            except (ValueError, IndexError):
                continue
        return links

    # -------------------------------------------------------------------------
    # Resource-Tag Link Operations (htfs:hasTag)
    # -------------------------------------------------------------------------

    def add_resource_tag_link(self, resource_id, tag_id):
        """Link a resource to a tag."""
        self.connect()
        res_uri = self._res_uri(resource_id)
        tag_uri = self._tag_uri(tag_id)
        self.graph.add((res_uri, HTFS.hasTag, tag_uri))
        self._mark_dirty()

    def remove_resource_tag_link(self, resource_id, tag_id):
        """Remove a resource-tag link."""
        self.connect()
        res_uri = self._res_uri(resource_id)
        tag_uri = self._tag_uri(tag_id)
        self.graph.remove((res_uri, HTFS.hasTag, tag_uri))
        self._mark_dirty()

    def get_resource_tag_ids(self, resource_id) -> list:
        """Get all tag IDs linked to a resource."""
        self.connect()
        res_uri = self._res_uri(resource_id)
        tag_ids = []
        for tag_uri in self.graph.objects(res_uri, HTFS.hasTag):
            try:
                tag_id = int(str(tag_uri).split("_")[-1])
                tag_ids.append(tag_id)
            except (ValueError, IndexError):
                continue
        return tag_ids

    def get_resources_by_tag_ids(self, tag_ids) -> list:
        """Get all resource IDs that have any of the given tags (including tag closure)."""
        if not tag_ids:
            return []
        self.connect()
        resource_ids = set()

        # Use SPARQL with transitive closure to get resources linked to
        # any of the given tags OR any of their descendant tags
        for tag_id in tag_ids:
            tag_uri = self._tag_uri(tag_id)
            query = f"""
            SELECT ?res WHERE {{
                ?res htfs:hasTag ?tag .
                ?tag skos:broader* {tag_uri.n3()} .
            }}
            """
            results = self.graph.query(
                query,
                initNs={"htfs": HTFS, "skos": SKOS}
            )
            for row in results:
                try:
                    resid = int(str(row.res).split("_")[-1])
                    resource_ids.add(resid)
                except (ValueError, IndexError):
                    continue
        return list(resource_ids)

    def get_all_resource_tag_links(self) -> list:
        """Get all resource-tag links as [(resid, tagid), ...]."""
        self.connect()
        links = []
        for res_uri, _, tag_uri in self.graph.triples((None, HTFS.hasTag, None)):
            try:
                resid = int(str(res_uri).split("_")[-1])
                tagid = int(str(tag_uri).split("_")[-1])
                links.append((resid, tagid))
            except (ValueError, IndexError):
                continue
        return links

    def remove_all_tags_for_resource(self, resource_id):
        """Remove all tag links for a resource."""
        self.connect()
        res_uri = self._res_uri(resource_id)
        self.graph.remove((res_uri, HTFS.hasTag, None))
        self._mark_dirty()

    # -------------------------------------------------------------------------
    # Migration/Sync Helpers
    # -------------------------------------------------------------------------

    def export_to_turtle(self):
        """Export the graph as Turtle string."""
        self.connect()
        return self.graph.serialize(format="turtle")

    @staticmethod
    def create_from_sqlite(sqlite_path, ttl_path):
        """
        Create a new RDF file from existing SQLite data.
        Used for migration or rebuilding RDF from SQLite.
        """
        import sqlite3
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row

        handler = RDFHandler(ttl_path)
        graph = Graph()
        graph.bind("htfs", HTFS)
        graph.bind("skos", SKOS)

        # Export tag hierarchy from TAGLINKS
        cursor = conn.execute("SELECT TAGID, TAGPARENTID FROM TAGLINKS;")
        for row in cursor:
            child_uri = HTFS[f"tag_{row['TAGID']}"]
            parent_uri = HTFS[f"tag_{row['TAGPARENTID']}"]
            graph.add((child_uri, SKOS.broader, parent_uri))

        # Export resource-tag links from RESOURCELINKS
        cursor = conn.execute("SELECT RESID, TAGID FROM RESOURCELINKS;")
        for row in cursor:
            res_uri = HTFS[f"resource_{row['RESID']}"]
            tag_uri = HTFS[f"tag_{row['TAGID']}"]
            graph.add((res_uri, HTFS.hasTag, tag_uri))

        # Export metadata
        cursor = conn.execute("SELECT MAX_ID FROM ID_SEQUENCES WHERE NAME='TAG';")
        row = cursor.fetchone()
        max_tag_id = row[0] if row else 0
        cursor = conn.execute("SELECT MAX_ID FROM ID_SEQUENCES WHERE NAME='RESOURCE';")
        row = cursor.fetchone()
        max_res_id = row[0] if row else 0

        graph.add((HTFS.meta, HTFS.maxTagId, Literal(max_tag_id, datatype=XSD.integer)))
        graph.add((HTFS.meta, HTFS.maxResourceId, Literal(max_res_id, datatype=XSD.integer)))

        graph.serialize(destination=ttl_path, format="turtle")
        conn.close()
        return handler


class RDFManager:
    """
    Context manager for RDFHandler that also handles the TTL path resolution.

    Usage:
        with RDFManager(tagfs_boundary) as rdf:
            rdf.add_tag_link(tag_id, parent_id)
        # RDF is auto-saved on exit
    """

    def __init__(self, tagfs_boundary, ttl_filename=".tagfs.ttl"):
        self.ttl_path = os.path.join(tagfs_boundary, ttl_filename)
        self.handler = RDFHandler(self.ttl_path)

    def __enter__(self):
        return self.handler

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.handler.close()
