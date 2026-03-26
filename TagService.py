"""
TagService - High-level service for tag and resource operations.

Delegates to DatabaseManager which coordinates SQLite (ID lookups) and RDF (relationships).
"""

import logging
import DatabaseManager

logobj = logging.getLogger(__name__)


class TagService:
    """
    High-level service to manage tags and resources.

    Uses DatabaseManager which splits:
      - SQLite: fast tag name↔id, resource url↔id lookups
      - RDF: tag hierarchy (skos:broader), resource-tag links (htfs:hasTag)

    The RDF graph is loaded lazily and serialized only on close().
    """

    def __init__(self, db_path_or_boundary):
        """
        Initialize TagService.

        Args:
            db_path_or_boundary: Either a path to .tagfs.db or a directory boundary.
                                 If it ends with .db, it's treated as the db path.
                                 Otherwise, it's treated as the tagfs boundary.
        """
        if db_path_or_boundary.endswith(".db"):
            # Direct path to SQLite db - derive boundary from it
            import os
            self.tagfs_boundary = os.path.dirname(db_path_or_boundary)
        else:
            self.tagfs_boundary = db_path_or_boundary

        self.db = DatabaseManager.DatabaseManager(self.tagfs_boundary)
        self.db.connect()

    def __del__(self):
        try:
            self.db.close()
        except Exception:
            pass

    def initialize(self):
        """Initialize the database schema."""
        self.db.initialize()

    def close(self):
        """Close the database, serializing RDF if dirty."""
        self.db.close()

    def flush(self):
        """Force-save RDF to disk."""
        self.db.flush()

    # -------------------------------------------------------------------------
    # Tag Operations
    # -------------------------------------------------------------------------

    def add_tag(self, tag_name):
        """Add a new tag. Returns tag ID if created, -1 if exists."""
        return self.db.add_tag(tag_name)

    def get_tag_id(self, tag_name):
        """Get tag ID by name."""
        return self.db.get_tag_id(tag_name)

    def get_tag_name(self, tag_id):
        """Get tag name by ID."""
        return self.db.get_tag_name(tag_id)

    def get_tag_list(self):
        """Get all tag names."""
        return self.db.get_tag_list()

    def rename_tag(self, tag_name, new_tag_name):
        """Rename a tag."""
        return self.db.rename_tag(tag_name, new_tag_name)

    def link_tag(self, tag_name, tag_parent_name):
        """
        Create a parent-child link between tags.
        Creates the tags if they don't exist.
        """
        return self.db.link_tag_to_parent(tag_name, tag_parent_name)

    def unlink_tag(self, tag_name, tag_parent_name):
        """Remove a parent-child link between tags."""
        child_id = self.db.get_tag_id(tag_name)
        parent_id = self.db.get_tag_id(tag_parent_name)
        if child_id < 0 or parent_id < 0:
            logobj.error("tags not in db")
            return False
        self.db.remove_tag_link(child_id, parent_id)
        return True

    def get_tag_closure(self, tags):
        """
        Get transitive closure of tags: the given tags plus all their descendants.
        Returns list of tag names.
        """
        tag_ids = []
        for tag in tags:
            tid = self.db.get_tag_id(tag)
            if tid > 0:
                tag_ids.append(tid)
            else:
                logobj.warning("tag %s not present in the db", tag)

        if not tag_ids:
            return []

        closure_ids = self.db.get_tag_closure_ids(tag_ids)
        return [self.db.get_tag_name(tid) for tid in closure_ids if self.db.get_tag_name(tid)]

    def get_parent_tags(self, tag_name):
        """Get immediate parent tag names."""
        tag_id = self.db.get_tag_id(tag_name)
        if tag_id < 0:
            return []
        parent_ids = self.db.get_parent_tag_ids(tag_id)
        return [self.db.get_tag_name(tid) for tid in parent_ids if self.db.get_tag_name(tid)]

    def get_child_tags(self, tag_name):
        """Get immediate child tag names."""
        tag_id = self.db.get_tag_id(tag_name)
        if tag_id < 0:
            return []
        child_ids = self.db.get_child_tag_ids(tag_id)
        return [self.db.get_tag_name(tid) for tid in child_ids if self.db.get_tag_name(tid)]

    # -------------------------------------------------------------------------
    # Resource Operations
    # -------------------------------------------------------------------------

    def add_resource(self, resource_url):
        """Add a resource. Returns resource ID if new, -1 if exists."""
        return self.db.add_resource(resource_url)

    def get_resource_id(self, resource_url):
        """Get resource ID by URL."""
        return self.db.get_resource_id(resource_url)

    def get_resource_url(self, res_id):
        """Get resource URL by ID."""
        return self.db.get_resource_url(res_id)

    def get_resource_ids(self):
        """Get all resource IDs."""
        return self.db.get_resource_ids()

    def del_resource(self, resource_url):
        """Delete a resource and all its tag links."""
        return self.db.delete_resource(resource_url)

    def update_resource_url(self, resource_url, new_resource_url):
        """Update a resource's URL."""
        return self.db.update_resource_url(resource_url, new_resource_url)

    # -------------------------------------------------------------------------
    # Resource-Tag Operations
    # -------------------------------------------------------------------------

    def add_resource_tags(self, resource_url, tags):
        """
        Add tags to a resource by name.
        Returns list of unsuccessful tag names.
        """
        return self.db.add_resource_tags(resource_url, tags)

    def del_resource_tags(self, resource_url, tags):
        """Remove tags from a resource."""
        res_id = self.db.get_resource_id(resource_url)
        if res_id < 0:
            logobj.error("resource not tracked: %s", resource_url)
            return

        for tag in tags:
            tag_id = self.db.get_tag_id(tag)
            if tag_id > 0:
                self.db.remove_resource_tag_link(res_id, tag_id)

    def get_resource_tags(self, resource_url):
        """Get all tag names for a resource."""
        return self.db.get_resource_tags(resource_url)

    def get_resources_by_tag(self, tags):
        """
        Get resources that have ALL the given tags (AND semantics).
        Returns list of resource URLs.
        """
        return self.db.get_resources_by_tags(tags)
