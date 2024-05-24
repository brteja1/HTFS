#!/bin/bash

files=$(ls)

tagbounday=$(tagfs getboundary >> /dev/null 2>> /dev/null)
retval=$?


for f in $files
do
    if [ $retval -ne 1 ]; then
        filetags=$(tagfs getresourcetags "$f" 2>>/dev/null)
    fi
    echo "$f" "::" "$filetags"
done