#!/bin/bash

get_abs_path() {
  # Use readlink to resolve the absolute path
  echo "$(cd "$(dirname "$1")" && pwd -P)/$(basename "$1")"
}

subst_comma_for_space() {
    args=("$@")
    output=$(echo $args | sed 's/[[:space:]]\+/,/g' | sed -e 's/,/, /g')
    echo "$output"
}

get_dir_tags() {
    cdirtags=$(tagfs getresourcetags "$1" 2>>/dev/null);
    retval=$?
    if [ $retval -ne 1 ]; then
        # shellcheck disable=SC2116
        # shellcheck disable=SC2086
        output="{$(subst_comma_for_space "$cdirtags")}"
    else
        output='{}'
    fi
    echo "$output"
}

bdry=$(tagfs getboundary 2>>/dev/null)
retval=$?
output='';
# try moving up to see if we get any folder with tags
if [ $retval -ne 1 ]; then
    cdir=$(pwd)
    bdrdir=$(get_abs_path "$bdry")

    while true; do
        curdir=$(get_abs_path "$cdir")
        output=$(get_dir_tags "$curdir")

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

# try looking at all files and see if any of them has tags
# need to make this logic more smarter by merging some flags based on tag graph
if [ "$output" == "{}" ]; then
    output=''
    files=$(ls)
    if [ $retval -ne 1 ]; then
        for f in $files
        do
            filetags=$(tagfs getresourcetags "$f" 2>>/dev/null)            
            # shellcheck disable=SC2086
            # shellcheck disable=SC2116
            output=$(echo $output $filetags)
        done
    fi
    # shellcheck disable=SC2178
    output=( $output )
    output=$(for a in "${output[@]}"; do echo "$a"; done | sort | uniq)
    output="{$(subst_comma_for_space "$output")}"
fi
echo "$output"

