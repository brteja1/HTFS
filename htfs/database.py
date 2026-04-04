"""
DatabaseManager - Unified handler coordinating SQLite (ID lookups) and RDF (relationships).

Architecture:
  SQLite (.tagfs.db):  tag name↔id, resource url↔id  (O(1) lookups, fast)
  RDF    (.tagfs.ttl): tag hierarchy (skos:broader), resource-tag links (htfs:hasTag)

Key behaviors:
  - RDF is loaded lazily (only when needed)
  - RDF is serialized only on close() or flush()
  - SQLite commits immediately (for data integrity)
  - Tag/Resource operations use SQLite; links use RDF
"""

import os
import logging
from htfs.sqlite_handler import SQLiteManager, TagRepository as SQLTagRepo, ResourceRepository as SQLResRepo
from htfs.rdf_handler import RDFHandler

logobj = logging.getLogger(__name__)


class DatabaseManager:
    """
    Coordinates SQLite (ID lookups) and RDF (relationships) backends.

    Usage:
        db = DatabaseManager("/path/to/tagfs_boundary")
        db.initialize()  # Create tables if needed

        # Fast lookups via SQLite
        tag_id = db.get_tag_id("Project")
        res_id = db.get_resource_id("/path/to/file.pdf")

        # Relationship operations via RDF
        db.add_tag_link(tag_id, parent_id)
        db.add_resource_tag_link(res_id, tag_id)

        # On session end
        db.close()  # RDF is serialized here
    """

    def __init__(self, tagfs_boundary):
        self.tagfs_boundary = tagfs_boundary
        self.db_path = os.path.join(tagfs_boundary, ".tagfs.db")
        self.ttl_path = os.path.join(tagfs_boundary, ".tagfs.ttl")

        self.sqlite = SQLiteManager(self.db_path)
        self.tag_repo = SQLTagRepo(self.sqlite)
        self.res_repo = SQLResRepo(self.sqlite)
        self.rdf = RDFHandler(self.ttl_path)

        self._dirty = False

    def initialize(self):
        """Initialize SQLite schema. RDF is created on first close if needed."""
        self.sqlite.initialize_schema()
        logobj.info("SQLite schema initialized at %s", self.db_path)

    def connect(self):
        """Connect to SQLite. RDF is lazy-loaded."""
        self.sqlite.connect()
        self.rdf.connect()  # Ensure RDF is connected too
        return self

    def close(self):
        """Close SQLite and serialize RDF if dirty."""
        self.sqlite.close()
        self.rdf.close()
        # logobj.info("Database closed. RDF saved if modified.")

    def flush(self):
        """Force-save RDF to disk."""
        self.rdf.flush()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # -------------------------------------------------------------------------
    # Tag Operations (SQLite)
    # -------------------------------------------------------------------------

    def add_tag(self, tag_name):
        """Add a new tag. Returns tag ID if new, -1 if already exists."""
        tag_id = self.tag_repo.get_tag_id(tag_name)
        if tag_id > 0:
            return -1
        new_id = self.tag_repo.add_tag(tag_name)
        return new_id

    def get_tag_id(self, tag_name):
        """Get tag ID by name. O(1) lookup via SQLite."""
        return self.tag_repo.get_tag_id(tag_name)

    def get_tag_name(self, tag_id):
        """Get tag name by ID. O(1) lookup via SQLite."""
        return self.tag_repo.get_tag_name(tag_id)

    def get_tag_list(self):
        """Get all tag names."""
        return self.tag_repo.get_tag_list()

    def rename_tag(self, tag_name, new_tag_name):
        """Rename a tag."""
        return self.tag_repo.rename_tag(tag_name, new_tag_name)

    def delete_tag(self, tag_name):
        """Delete a tag and remove all hierarchy/resource links."""
        tag_id = self.get_tag_id(tag_name)
        if tag_id < 0:
            return False

        self.rdf.remove_all_links_for_tag(tag_id)
        self._dirty = True
        return self.tag_repo.delete_tag(tag_id)

    # -------------------------------------------------------------------------
    # Tag Hierarchy Operations (RDF)
    # -------------------------------------------------------------------------

    def add_tag_link(self, tag_id, parent_tag_id):
        """Create a parent-child link between tags."""
        self.rdf.add_tag_link(tag_id, parent_tag_id)
        self._dirty = True

    def remove_tag_link(self, tag_id, parent_tag_id):
        """Remove a parent-child link between tags."""
        self.rdf.remove_tag_link(tag_id, parent_tag_id)
        self._dirty = True

    def get_parent_tag_ids(self, tag_id):
        """Get immediate parent tag IDs."""
        return self.rdf.get_parent_tag_ids(tag_id)

    def get_child_tag_ids(self, tag_id):
        """Get immediate child tag IDs."""
        return self.rdf.get_child_tag_ids(tag_id)

    def get_tag_closure_ids(self, tag_ids):
        """Get transitive closure: given tag IDs, return all descendant IDs."""
        return self.rdf.get_tag_closure_ids(tag_ids)

    # -------------------------------------------------------------------------
    # Resource Operations (SQLite)
    # -------------------------------------------------------------------------

    def add_resource(self, resource_url):
        """Add a resource. Returns resource ID if new, -1 if already exists."""
        res_id = self.res_repo.get_resource_id(resource_url)
        if res_id > 0:
            return -1
        return self.res_repo.add_resource(resource_url)

    def get_resource_id(self, resource_url):
        """Get resource ID by URL. O(1) lookup via SQLite."""
        return self.res_repo.get_resource_id(resource_url)

    def get_resource_url(self, resource_id):
        """Get resource URL by ID."""
        return self.res_repo.get_resource_url(resource_id)

    def get_resource_ids(self):
        """Get all resource IDs."""
        return self.res_repo.get_resource_ids()

    def delete_resource(self, resource_url):
        """Delete a resource and all its tag links."""
        res_id = self.res_repo.get_resource_id(resource_url)
        if res_id < 0:
            return False
        # Remove tag links from RDF
        self.rdf.remove_all_tags_for_resource(res_id)
        self._dirty = True
        # Remove from SQLite
        self.res_repo.delete_resource(resource_url)
        return True

    def update_resource_url(self, old_url, new_url):
        """Update a resource's URL."""
        return self.res_repo.update_resource_url(old_url, new_url)

    # -------------------------------------------------------------------------
    # Resource-Tag Link Operations (RDF)
    # -------------------------------------------------------------------------

    def add_resource_tag_link(self, resource_id, tag_id):
        """Link a resource to a tag."""
        self.rdf.add_resource_tag_link(resource_id, tag_id)
        self._dirty = True

    def remove_resource_tag_link(self, resource_id, tag_id):
        """Remove a resource-tag link."""
        self.rdf.remove_resource_tag_link(resource_id, tag_id)
        self._dirty = True

    def get_resource_tag_ids(self, resource_id):
        """Get all tag IDs linked to a resource."""
        return self.rdf.get_resource_tag_ids(resource_id)

    def get_resources_by_tag_ids(self, tag_ids):
        """Get all resource IDs that have any of the given tags."""
        return self.rdf.get_resources_by_tag_ids(tag_ids)

    def get_all_resource_tag_links(self):
        """Get all resource-tag links."""
        return self.rdf.get_all_resource_tag_links()

    # -------------------------------------------------------------------------
    # Bulk Operations (for sync/migration)
    # -------------------------------------------------------------------------

    def get_max_tag_id(self):
        """Get the current max tag ID."""
        return self.tag_repo.get_max_tag_id()

    def get_max_resource_id(self):
        """Get the current max resource ID."""
        return self.res_repo.get_max_resource_id()

    # -------------------------------------------------------------------------
    # High-level combined operations
    # -------------------------------------------------------------------------

    def add_resource_tags(self, resource_url, tag_names):
        """
        Add tags to a resource by name.
        Creates tags if they don't exist.
        Returns list of unsuccessful tag names.
        """
        unsuccessful = []
        res_id = self.get_resource_id(resource_url)
        if res_id < 0:
            logobj.error("resource not tracked: %s", resource_url)
            return tag_names  # All unsuccessful

        for tag_name in tag_names:
            if "/" in tag_name:
                logobj.error("hierarchical tag paths are not allowed when tagging resources: %s", tag_name)
                unsuccessful.append(tag_name)
                continue

            tag_id = self.get_tag_id(tag_name)
            if tag_id < 0:
                # Auto-create the tag
                tag_id = self.add_tag(tag_name)
                if tag_id < 0:
                    unsuccessful.append(tag_name)
                    continue
            # Add link via RDF
            self.add_resource_tag_link(res_id, tag_id)

        return unsuccessful

    def get_resource_tags(self, resource_url):
        """Get all tag names for a resource."""
        res_id = self.get_resource_id(resource_url)
        if res_id < 0:
            return []
        tag_ids = self.get_resource_tag_ids(res_id)
        return [self.get_tag_name(tid) for tid in tag_ids if self.get_tag_name(tid)]

    def get_resources_by_tags(self, tag_names):
        """
        Get all resources that match ANY of the given tags (OR semantics).
        Uses transitive closure so searching for "Project" also finds Alpha, Reports, etc.
        Returns list of resource URLs.
        """
        if not tag_names:
            return []

        # Get tag IDs
        tag_ids = []
        for name in tag_names:
            tid = self.get_tag_id(name)
            if tid > 0:
                tag_ids.append(tid)

        if not tag_ids:
            return []

        # Get closure (include child tags) - this is the transitive closure
        all_tag_ids = self.get_tag_closure_ids(tag_ids)

        # Get resources that have ANY of these tags (OR semantics, with transitive closure)
        resource_ids = set(self.get_resources_by_tag_ids(list(all_tag_ids)))

        return [self.get_resource_url(rid) for rid in resource_ids if self.get_resource_url(rid)]

    def link_tag_to_parent(self, tag_name, parent_tag_name):
        """
        Convenience method: ensure both tags exist, then link them.
        """
        tag_id = self.get_tag_id(tag_name)
        if tag_id < 0:
            tag_id = self.add_tag(tag_name)
            if tag_id < 0:
                logobj.error("failed to create tag: %s", tag_name)
                return False

        parent_id = self.get_tag_id(parent_tag_name)
        if parent_id < 0:
            parent_id = self.add_tag(parent_tag_name)
            if parent_id < 0:
                logobj.error("failed to create parent tag: %s", parent_tag_name)
                return False

        self.add_tag_link(tag_id, parent_id)
        return True
