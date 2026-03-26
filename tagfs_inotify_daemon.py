#!/usr/bin/env python3

import os
import sys
import logging
# requires: pip install inotify
import inotify.adapters
import TagfsUtilities

logging.basicConfig(level='INFO')
logobj = logging.getLogger(__name__)

class TagfsInotifyDaemon:
    MOVED_FROM = 'MF'
    MOVED_DIR = 'MD'

    def __init__(self, tag_boundary_path):
        self.tag_boundary_path = tag_boundary_path
        self.eventlist = []
        self.th_utils = TagfsUtilities.TagfsTagHandlerUtilities(tag_boundary_path)

    def run(self):
        logobj.info("Initializing inotify..")
        try:
            i = inotify.adapters.InotifyTree(self.tag_boundary_path)
        except (PermissionError, OSError) as e:
            logobj.error(f"Failed to initialize inotify: {e}")
            sys.exit(1)
        logobj.info("inode tracking on path: %s", self.tag_boundary_path)

        try:
            for event in i.event_gen(yield_nones=False):
                self.handle_event(event)
        except KeyboardInterrupt:
            #remote inotify request
            inotify.adapters.InotifyTree.close(i)
            logobj.info("Shutting down daemon gracefully.")
    

    def handle_event(self, event):
        ievent, type_names, path, filename = event
        full_path = os.path.join(path, filename)
        if 'IN_MOVED_FROM' in type_names:
            self.handle_moved_from(ievent, type_names, full_path)
        elif 'IN_MOVED_TO' in type_names:
            self.handle_moved_to(ievent, type_names, full_path)

    def handle_moved_from(self, ievent, type_names, originalpath):
        if 'IN_ISDIR' not in type_names:
            if not self.th_utils.is_resource_tracked(originalpath):
                return
            self.eventlist.append((ievent.cookie, self.MOVED_FROM, originalpath))
        else:
            self.eventlist.append((ievent.cookie, self.MOVED_DIR, originalpath))

    def handle_moved_to(self, ievent, type_names, movedpath):
        # Copy to avoid modifying while iterating
        for e in self.eventlist[:]:
            event_cookie, dir_or_file, originalpath = e
            if not movedpath.startswith(self.tag_boundary_path):
                self.eventlist.remove(e)
                continue
            if event_cookie == ievent.cookie:
                try:
                    if dir_or_file == self.MOVED_FROM:
                        self.th_utils.move_resource(originalpath, movedpath)
                    else:
                        self.th_utils.update_resource_sub_url(originalpath, movedpath)
                    logobj.info("%s -> %s", originalpath, movedpath)
                except Exception as ex:
                    logobj.error("Failed to update resource: %s", ex)
                self.eventlist.remove(e)

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else TagfsUtilities.get_tag_fs_boundary()
    daemon = TagfsInotifyDaemon(path)
    daemon.run()
    sys.exit(0)
