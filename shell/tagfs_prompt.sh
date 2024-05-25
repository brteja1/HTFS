#!/bin/bash

get_abs_path() {
  # Use readlink to resolve the absolute path
  echo "$(cd "$(dirname "$1")" && pwd -P)/$(basename "$1")"
}

bdry=$(tagfs getboundary 2>>/dev/null)
retval=$?
output='';
if [ $retval -ne 1 ]; then
    cdir=$(pwd)
    bdrdir=$(get_abs_path "$bdry")

    while true; do
        curdir=$(get_abs_path "$cdir")

        cdirtags=$(tagfs getresourcetags "$curdir" 2>>/dev/null);
        retval=$?
        if [ $retval -ne 1 ]; then
            # shellcheck disable=SC2116
            # shellcheck disable=SC2086
            output="{$(echo $cdirtags | sed 's/[[:space:]]\+/,/g' | sed -e 's/,/, /g')}"
        else
            output='{}'
        fi

        # we already found a subfolder that has tags
        if [ "$output" != "{}" ]; then
            break
        fi
        
        # we only want to iterate till the folder where we initialized tagfs tracking
        if [ "$bdrdir" == "$curdir" ]; then
            break
        fi

        cdir=$(dirname "$cdir")
    done
fi
echo "$output"

