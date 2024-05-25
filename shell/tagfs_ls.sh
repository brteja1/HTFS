#!/bin/bash

files=$(ls)

tagfs getboundary >> /dev/null 2>> /dev/null
retval=$?

for f in $files
do
    if [ $retval -ne 1 ]; then
        filetags=$(tagfs getresourcetags "$f" 2>>/dev/null)
    fi
    # shellcheck disable=SC2048
    # shellcheck disable=SC2116
    echo "$f" "$(printf '\t')" "::" $(echo "$filetags")
done