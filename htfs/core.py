"""
core - Main library entry point for HTFS.

Provides the HTFS class which is the public API for the library.
"""

import os
import re
import logging

from htfs.query_evaluator import QueryEvaluator
from htfs.tag_service import TagService

_tagfsdb = ".tagfs.db"
_tagfsttl = ".tagfs.ttl"

logging.basicConfig(level='INFO')
logobj = logging.getLogger(__name__)


def find_tagfs_boundary(start_dir=''):
    """
    Find the tagfs boundary by searching for .tagfs.db upward.
    Returns the directory path containing the tagfs database.
    """
    if not start_dir:
        start_dir = os.path.realpath(os.curdir)
    tag_fs_db_file = os.path.join(start_dir, _tagfsdb)
    tag_fs_db_file_path = start_dir
    while True:
        if os.path.exists(tag_fs_db_file):
            return os.path.realpath(tag_fs_db_file_path)
        else:
            realpath = os.path.realpath(tag_fs_db_file_path)
            if realpath == "/":
                return None
            elif re.fullmatch("[A-Z]:\\\\", realpath):
                return None
        tag_fs_db_file_path = os.path.pardir + os.path.sep + tag_fs_db_file_path
        tag_fs_db_file = tag_fs_db_file_path + _tagfsdb


def is_hierarchical_tag(tag):
    """Check if tag contains hierarchical separator."""
    return '/' not in tag


def get_hierarchical_tag_split(tag):
    """Split a hierarchical tag into atomic parts."""
    return tag.split('/')


class HTFS:
    """
    High-level HTFS main library class for tag and resource management.

    Uses TagService which coordinates SQLite (ID lookups) and RDF (relationships).
    RDF is flushed to disk only when close() is called or at session end.
    """

    def __init__(self, tagfs_boundary):
        """
        Initialize the HTFS tagging library at the specified boundary.
        """
        self.tagfs_boundary = tagfs_boundary
        tagsdb_file_path = os.path.join(tagfs_boundary, _tagfsdb)
        self.th = TagService(tagsdb_file_path)

    def close(self):
        """Close the database, flushing RDF to disk."""
        self.th.close()

    def initialize(self):
        """Initialize the database schema."""
        self.th.initialize()

    def normalize_url(self, resource_url):
        """Normalize a resource URL to be relative to the tagfs boundary."""
        normalized_url = os.path.relpath(os.path.realpath(resource_url), self.tagfs_boundary)
        normalized_url = normalized_url.replace("\\", "/")
        return normalized_url

    def full_url(self, normalized_resource_url):
        """Convert a normalized URL back to a full path."""
        url = os.path.join(self.tagfs_boundary, normalized_resource_url)
        return url

    def get_tags_list(self, tags=None):
        """Get list of tags, optionally filtered by closure."""
        if not tags:
            return self.th.get_tag_list()
        else:
            return self.th.get_tag_closure(tags)

    def add_tags(self, tags):
        """
        Add tags, supporting hierarchical syntax (e.g., "Project/Alpha/Reports").
        Returns list of newly added tag names.
        """
        added_tags = []
        for tag in tags:
            htags = get_hierarchical_tag_split(tag)
            prev_tag = htags[0]
            assert len(prev_tag) != 0

            # Create the root tag if it doesn't exist
            if self.th.get_tag_id(prev_tag) < 0:
                new_id = self.th.add_tag(prev_tag)
                if new_id > 0:
                    added_tags.append(prev_tag)

            # Create child tags and link to parent
            for i in range(1, len(htags)):
                cur_tag = htags[i]
                if self.th.get_tag_id(cur_tag) < 0:
                    new_id = self.th.add_tag(cur_tag)
                    if new_id > 0:
                        added_tags.append(cur_tag)
                # Link to parent (creates relationship in RDF)
                self.th.link_tag(cur_tag, prev_tag)
                prev_tag = cur_tag

        return added_tags

    def rename_tag(self, tag_name, new_tag_name):
        """Rename a tag."""
        return self.th.rename_tag(tag_name, new_tag_name)

    def del_tag(self, tag_name):
        """Delete a tag and remove all references to it."""
        return self.th.del_tag(tag_name)

    def add_resource(self, resource_url):
        """Add a resource for tracking. Returns resource ID."""
        resource_url = self.normalize_url(resource_url)
        rid = self.th.get_resource_id(resource_url)
        if rid < 0:
            rid = self.th.add_resource(resource_url)
        return rid

    def is_resource_tracked(self, resource_url):
        """Check if a resource is tracked."""
        resource_url = self.normalize_url(resource_url)
        rid = self.th.get_resource_id(resource_url)
        return rid >= 0

    def del_resource(self, resource_url):
        """Untrack a resource."""
        resource_url = self.normalize_url(resource_url)
        self.th.del_resource(resource_url)

    def tag_resource(self, resource_url, tags):
        """Assign tags to a resource. Returns list of unsuccessful tags."""
        resource_url = self.normalize_url(resource_url)
        return self.th.add_resource_tags(resource_url, tags)

    def untag_resource(self, resource_url, tags):
        """Remove tags from a resource."""
        resource_url = self.normalize_url(resource_url)
        self.th.del_resource_tags(resource_url, tags)

    def move_resource(self, resource_url, target_url):
        """Move a resource to a new path."""
        resource_url = self.normalize_url(resource_url)
        target_url = self.normalize_url(target_url)
        self.th.update_resource_url(resource_url, target_url)

    def get_resources_by_tag(self, tags):
        """Get resources matching given tags (AND semantics)."""
        tags_closure = self.th.get_tag_closure(tags)
        resource_urls = self.th.get_resources_by_tag(tags_closure)
        return [self.full_url(url) for url in resource_urls]

    def get_resources_by_tag_expr(self, tagsexpr):
        """Get resources matching a tag expression (e.g., '(proj1|proj2)&research')."""
        qe = QueryEvaluator(self.th)
        resource_urls = qe.evaluate(tagsexpr)
        return [self.full_url(url) for url in resource_urls]

    def link_tags(self, tag, parent_tag):
        """Create a parent-child link between tags."""
        return self.th.link_tag(tag, parent_tag)

    def get_resource_tags(self, resource_url):
        """Get all tags assigned to a resource."""
        resource_url = self.normalize_url(resource_url)
        return self.th.get_resource_tags(resource_url)
