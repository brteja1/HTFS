#!/usr/bin/env python3
"""
Tagfs Inotify Daemon - Automatically tracks file moves within the tagfs boundary.

Monitors filesystem events and updates resource URLs when files are moved/renamed.
Requires inotify (Linux only): pip install inotify
"""

import os
import sys
import logging
from pathlib import Path

try:
    if sys.platform.startswith("linux"):
        import inotify.adapters
    else:
        inotify = None
except ImportError:
    inotify = None

from htfs import HTFS, find_tagfs_boundary

logging.basicConfig(level='INFO')
logobj = logging.getLogger(__name__)


class TagfsInotifyDaemon:
    """Daemon that monitors filesystem moves and updates resource URLs in the database."""

    MOVED_FROM = 'MF'
    MOVED_DIR = 'MD'

    def __init__(self, tag_boundary_path):
        self.tag_boundary_path = Path(tag_boundary_path).expanduser().resolve()
        self.eventlist = []
        self.th_utils = HTFS(self.tag_boundary_path)

    def close(self):
        """Clean up resources, flushing RDF to disk."""
        self.th_utils.close()

    def run(self):
        if inotify is None:
            raise RuntimeError("tagfs inotify daemon is only available on Linux")
        logobj.info("Initializing inotify on path: %s", self.tag_boundary_path)
        try:
            i = inotify.adapters.InotifyTree(str(self.tag_boundary_path))
        except (PermissionError, OSError) as e:
            logobj.error("Failed to initialize inotify: %s", e)
            sys.exit(1)

        logobj.info("inode tracking active on: %s", self.tag_boundary_path)

        try:
            for event in i.event_gen(yield_nones=False):
                self.handle_event(event)
        except KeyboardInterrupt:
            logobj.info("Shutting down daemon gracefully.")
        finally:
            inotify.adapters.InotifyTree.close(i)
            self.close()

    def handle_event(self, event):
        """Route events to appropriate handlers."""
        ievent, type_names, path, filename = event
        full_path = Path(path) / filename if filename else Path(path)

        if 'IN_MOVED_FROM' in type_names:
            self.handle_moved_from(ievent, type_names, full_path)
        elif 'IN_MOVED_TO' in type_names:
            self.handle_moved_to(ievent, type_names, full_path)

    def handle_moved_from(self, ievent, type_names, originalpath):
        """Record a file/directory move start."""
        if 'IN_ISDIR' not in type_names:
            if not self.th_utils.is_resource_tracked(originalpath):
                return
            self.eventlist.append((ievent.cookie, self.MOVED_FROM, originalpath))
        else:
            self.eventlist.append((ievent.cookie, self.MOVED_DIR, originalpath))

    def handle_moved_to(self, ievent, type_names, movedpath):
        """Match MOVED_FROM with MOVED_TO and update the database."""
        for e in self.eventlist[:]:
            event_cookie, dir_or_file, originalpath = e
            try:
                movedpath.relative_to(self.tag_boundary_path)
            except ValueError:
                self.eventlist.remove(e)
                continue
            if event_cookie == ievent.cookie:
                try:
                    if dir_or_file == self.MOVED_FROM:
                        self.th_utils.move_resource(originalpath, movedpath)
                    else:
                        self.th_utils.move_resource(originalpath, movedpath)
                    logobj.info("%s -> %s", originalpath, movedpath)
                except Exception as ex:
                    logobj.error("Failed to update resource: %s", ex)
                self.eventlist.remove(e)


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else find_tagfs_boundary()
    if path is None:
        logobj.error("tagfs not initialized in path")
        sys.exit(1)

    daemon = TagfsInotifyDaemon(path)
    daemon.run()
    sys.exit(0)
