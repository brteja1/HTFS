#!/usr/bin/env python3

import os
import sys
import shutil
import logging
import argparse

import TagfsUtilities

logging.basicConfig(level='INFO')
logobj = logging.getLogger(__name__)

def get_tagfs_utils() :
    tagfs_boundary = TagfsUtilities.get_tag_fs_boundary()
    
    if tagfs_boundary == None :
        logobj.error('db not initialized')
        print_usage([])
        return None
    th_utils = TagfsUtilities.TagfsTagHandlerUtilities(tagfs_boundary)
    return th_utils

def _get_tag_fs_boundary(args) :
    tagfs_boundary = TagfsUtilities.get_tag_fs_boundary()
    if tagfs_boundary == None :
        logobj.error('db not initialized')
        print_usage(args)
        return 1
    print(tagfs_boundary)
    return 0
    
def _init_tag_fs(args) :
    ts = TagfsUtilities.TagfsTagHandlerUtilities(os.path.realpath(os.curdir))
    ts.th.initialize()
    ts = None
    if not os.path.exists(TagfsUtilities._tagfsdb) :
        return 1    
    logobj.info("initialized in " + os.path.realpath(os.curdir))
    return 0

def _get_tags_list(args) :
    tags = args.tags
    th_utils = get_tagfs_utils()
    if th_utils is None:
        return 1
    tags_list = th_utils.get_tags_list(tags)
    for tag in tags_list :
        print(tag)
    return 0

def _add_tags(args) :
    tags = args.tags
    th_utils = get_tagfs_utils()
    if th_utils is None:
        return 1
    new_tags = th_utils.add_tags(tags)
    if len(new_tags) > 0 :
        logobj.info("new tags added: " + str(new_tags))
    return 0

def _rename_tag(args) :
    old_tag_name = args.tag
    new_tag_name = args.newtag
    th_utils = get_tagfs_utils()
    if th_utils is None:
        return 1
    res = th_utils.rename_tag(old_tag_name, new_tag_name)
    if not res :
        logobj.error("could not rename tags, check if tags are present in db")
        return 1
    return 0
            
def _add_resource(args) :
    resource_url = args.path
    th_utils = get_tagfs_utils()
    if th_utils is None:
        return 1
    th_utils.add_resource(resource_url)
    return 0

def _del_resource(args) :
    resource_url = args.path
    make_fs_change = args.makefschange.lower() == 'true'
    th_utils = get_tagfs_utils()
    if th_utils is None:
        return 1
    th_utils.del_resource(resource_url)
    if make_fs_change :
        if os.path.isfile(resource_url) :
            os.remove(resource_url)
        elif os.path.isdir(resource_url) :
            shutil.rmtree(resource_url)
    return 0

def _tag_resource(args) :
    resource_url = args.path
    tags = args.tags
    th_utils = get_tagfs_utils()
    if th_utils is None:
        return 1
    unsuccessful_tags = th_utils.tag_resource(resource_url, tags)
    if len(unsuccessful_tags) > 0 :
        logobj.warning("following tags not in db " + str(unsuccessful_tags))
    return 0

def _untag_resource(args) :
    resource_url = args.path
    tags = args.tags
    th_utils = get_tagfs_utils()
    if th_utils is None:
        return 1
    th_utils.untag_resource(resource_url, tags)
    return 0

def _move_resource(args) :
    resource_url = args.path
    target_url = args.newpath
    make_fs_change = args.makefschange.lower() == 'true'
    # validate if target_url falls under the same tagfs hierarchy
    src_is_file = os.path.isfile(resource_url)
    target_is_dir = os.path.isdir(target_url)
    if target_is_dir & src_is_file :
        target_url = target_url + os.sep + os.path.basename(resource_url)
    if make_fs_change :
        shutil.move(resource_url, target_url)
    th_utils = get_tagfs_utils()
    if th_utils is None:
        return 1
    th_utils.move_resource(resource_url, target_url)
    return 0
    
def _get_resources_by_tag_expr(args) :
    tagsexpr = args.tagexpr
    th_utils = get_tagfs_utils()
    if th_utils is None:
        return 1
    resource_urls = th_utils.get_resources_by_tag_expr(tagsexpr)
    for res_url in resource_urls :
        print(res_url)
    return 0

def _link_tags(args) :
    tag = args.tag
    parent_tag = args.parenttag
    th_utils = get_tagfs_utils()
    if th_utils is None:
        return 1
    res = th_utils.link_tags(tag, parent_tag)
    if not res :
        logobj.error("invalid tags used.")
        return 1
    return 0

def _get_resource_tags(args) :
    resource_url = args.path
    th_utils = get_tagfs_utils()
    if th_utils is None:
        return 1
    is_resource_tracked = th_utils.is_resource_tracked(resource_url)
    if not is_resource_tracked :
        logobj.error("resource not tracked")
        return 1
    tags = th_utils.get_resource_tags(resource_url)
    for tag in tags :
        print(tag)
    return 0

def _rm_resource_tags(args) :
    resource_url = args.path
    th_utils = get_tagfs_utils()
    if th_utils is None:
        return 1
    is_resource_tracked = th_utils.is_resource_tracked(resource_url)
    if not is_resource_tracked :
        logobj.error("resource not tracked")
        return 1
    tags = th_utils.get_resource_tags(resource_url)
    th_utils.untag_resource(resource_url, tags)
    logobj.info("removed tags" + str(tags) +  " on the resource")
    return 0


def print_usage(args):
    print("HTFS: Hierarchially Tagged File System")
    cmd = "\t" + os.path.basename(sys.argv[0])
    print(cmd + " init \t\t initialize the tags db")
    print(cmd + " getboundary \t fs boundary starting which tags are tracked")
    print(cmd + " lstags [tag] \t\t list tags")
    print(cmd + " addtags [tag]* \t\t add new tags")
    print(cmd + " renametag tag newtag \t rename an existing tag")
    print(cmd + " linktags tag parenttag \t link existing tags")
    print(cmd + " addresource path \t\t track a new resource")
    print(cmd + " tagresource path [tag]* \t add tags to tracked resources")
    print(cmd + " untagresource path [tag] \t remove tags on tracked resources")
    print(cmd + " lsresources tagexpr \t list resources with given tags")
    print(cmd + " getresourcetags path \t list all the tags of the resource")
    print(cmd + " rmresourcetags path \t remove all tags on the resource")
    print(cmd + " rmresource path \t untrack the resource in the db")
    print(cmd + " mvresource path newpath\t move resource to a new path")
    return 0

def unimplemented_feature_error(args) :
    logobj.error("unimplemented feature")
    return 1

def improper_usage(args) :
    logobj.error("improper usage")
    print_usage(args)
    return 1

COMMANDS = {
    'init': _init_tag_fs,
    'getboundary': _get_tag_fs_boundary,
    'lstags': _get_tags_list,
    'addtags': _add_tags,
    'renametag': _rename_tag,
    'linktags': _link_tags,
    'unlinktags': unimplemented_feature_error,
    'addresource': _add_resource,
    'tagresource': _tag_resource,
    'untagresource': _untag_resource,
    'lsresources': _get_resources_by_tag_expr,
    'getresourcetags': _get_resource_tags,
    'rmresourcetags': _rm_resource_tags,
    'rmresource': _del_resource,
    'mvresource': _move_resource,
    'sanitize': unimplemented_feature_error,
    'help': print_usage
}


def create_parser():
    parser = argparse.ArgumentParser(description='HTFS: Hierarchically Tagged File System')
    subparsers = parser.add_subparsers(dest='command')
    
    init_parser = subparsers.add_parser('init')
    tags_parser = subparsers.add_parser('lstags')
    tags_parser.add_argument('tags', nargs='*')
    
    getboundary_parser = subparsers.add_parser('getboundary')
    
    addtags_parser = subparsers.add_parser('addtags')
    addtags_parser.add_argument('tags', nargs='+')
    
    renametag_parser = subparsers.add_parser('renametag')
    renametag_parser.add_argument('tag')
    renametag_parser.add_argument('newtag')
    
    linktags_parser = subparsers.add_parser('linktags')
    linktags_parser.add_argument('tag')
    linktags_parser.add_argument('parenttag')
    
    unlinktags_parser = subparsers.add_parser('unlinktags')
    unlinktags_parser.add_argument('tag')
    unlinktags_parser.add_argument('parenttag')
    
    addresource_parser = subparsers.add_parser('addresource')
    addresource_parser.add_argument('path')
    
    tagresource_parser = subparsers.add_parser('tagresource')
    tagresource_parser.add_argument('path')
    tagresource_parser.add_argument('tags', nargs='+')
    
    untagresource_parser = subparsers.add_parser('untagresource')
    untagresource_parser.add_argument('path')
    untagresource_parser.add_argument('tags', nargs='+')
    
    lsresources_parser = subparsers.add_parser('lsresources')
    lsresources_parser.add_argument('tagexpr')
    
    getresourcetags_parser = subparsers.add_parser('getresourcetags')
    getresourcetags_parser.add_argument('path')
    
    rmresourcetags_parser = subparsers.add_parser('rmresourcetags')
    rmresourcetags_parser.add_argument('path')
    
    rmresource_parser = subparsers.add_parser('rmresource')
    rmresource_parser.add_argument('path')
    rmresource_parser.add_argument('makefschange', nargs='?', default='true')
    
    mvresource_parser = subparsers.add_parser('mvresource')    
    mvresource_parser.add_argument('path')
    mvresource_parser.add_argument('newpath')
    mvresource_parser.add_argument('makefschange', nargs='?', default='true')
    
    sanitize_parser = subparsers.add_parser('sanitize')
    help_parser = subparsers.add_parser('help')
    
    return parser

def tagfs(arg):
    parser = create_parser()
    args = parser.parse_args(arg)    
    
    if not args.command or not args.command in COMMANDS :
        code = improper_usage(args)        
    else:
        code = COMMANDS[args.command](args)
    sys.exit(code)

if __name__ == "__main__":
    tagfs(sys.argv[1:])
