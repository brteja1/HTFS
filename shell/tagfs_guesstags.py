#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

#get path separator
htfs_path = os.path.realpath('/home/raghub/github-archive/HTFS')
sys.path.append(htfs_path)

import TagfsUtilities

def get_tagfs_utils() :
    tagfs_boundary = TagfsUtilities.get_tag_fs_boundary()
    if tagfs_boundary == None :
        exit(1)
    th_utils = TagfsUtilities.TagfsTagHandlerUtilities(tagfs_boundary)
    return th_utils

def get_file_text(file_path):
    file_path = os.path.realpath(file_path)
    
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist.")
        return []
    
    print(f"File path: {file_path}")
    
    file = open(file_path)
    return file.read()

from transformers import pipeline

def get_tags_list():
    # Get the tagfs utilities
    th_utils = get_tagfs_utils()
    candidate_tags = th_utils.get_tags_list([])  
    return candidate_tags

def classify_text(text):    
    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")    
    candidate_tags = get_tags_list()  
    
    if len(text) != 0:
        result = classifier(text, candidate_tags)
    else:
        result = {'labels': [], 'scores': []}

    return result

#function takes probabilty distribution as input and returns set that is 70% probabile
def get_top_tags_from_prob_dist(prob_dist):
    tags = []
    prob = 0
    alltags = prob_dist['labels']
    allprobs = prob_dist['scores']
    for i in range(len(allprobs)):        
        prob = prob + allprobs[i]
        if prob > 0.7:
            tags.append(alltags[i])
    return tags

def guess_tags(file_path):
    text = get_file_text(file_path)
    prob_dist = classify_text(text)
    tags = get_top_tags_from_prob_dist(prob_dist)
    print(f"Tags: {tags}")
    return tags

if __name__ == "__main__":
    guess_tags(sys.argv[1])