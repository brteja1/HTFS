#!/usr/bin/env bash

_tagfs_completions()
{
  if [ "${#COMP_WORDS[@]}" == "2" ]; then
    # shellcheck disable=SC2207
    COMPREPLY=($(compgen -W "init getboundary lstags addtags renametag linktags addresource tagresource untagresource lsresources rmresource mvresource getresourcetags rmresourcetags help" "${COMP_WORDS[1]}"))
  fi

  if [ "${#COMP_WORDS[@]}" == "3" ]; then

    if [ "${COMP_WORDS[1]}" == "addresource" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -f -- "${COMP_WORDS[2]}"))
    fi

    if [ "${COMP_WORDS[1]}" == "tagresource" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -f -- "${COMP_WORDS[2]}"))
    fi

    if [ "${COMP_WORDS[1]}" == "untagresource" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -f -- "${COMP_WORDS[2]}"))
    fi

    if [ "${COMP_WORDS[1]}" == "mvresource" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -f -- "${COMP_WORDS[2]}"))
    fi
    
    if [ "${COMP_WORDS[1]}" == "rmresource" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -f -- "${COMP_WORDS[2]}"))
    fi

    if [ "${COMP_WORDS[1]}" == "getresourcetags" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -f -- "${COMP_WORDS[2]}"))
    fi

    if [ "${COMP_WORDS[1]}" == "rmresourcetags" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -f -- "${COMP_WORDS[2]}"))
    fi

    if [ "${COMP_WORDS[1]}" == "lstags" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -W "$(tagfs lstags)" "${COMP_WORDS[2]}"))
    fi

    if [ "${COMP_WORDS[1]}" == "lsresources" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -W "$(tagfs lstags)" "${COMP_WORDS[2]}"))
    fi

    if [ "${COMP_WORDS[1]}" == "renametag" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -W "$(tagfs lstags)" "${COMP_WORDS[2]}"))
    fi
    
    if [ "${COMP_WORDS[1]}" == "linktags" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -W "$(tagfs lstags)" "${COMP_WORDS[2]}"))
    fi
    
  fi

  if [ "${#COMP_WORDS[@]}" == "4" ]; then
    if [ "${COMP_WORDS[1]}" == "tagresource" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -W "$(tagfs lstags)" "${COMP_WORDS[3]}"))
    fi

    if [ "${COMP_WORDS[1]}" == "untagresource" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -W "$(tagfs lstags)" "${COMP_WORDS[3]}"))
    fi

    if [ "${COMP_WORDS[1]}" == "linktags" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -W "$(tagfs lstags)" "${COMP_WORDS[3]}"))
    fi
  fi

  if [ ${#COMP_WORDS[@]} -gt 4 ]; then
    if [ "${COMP_WORDS[1]}" == "tagresource" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -W "$(tagfs lstags)" "${COMP_WORDS[${#COMP_WORDS[@]} - 1]}"))
    fi

    if [ "${COMP_WORDS[1]}" == "untagresource" ]; then
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -W "$(tagfs lstags)" "${COMP_WORDS[${#COMP_WORDS[@]} - 1]}"))
    fi
  fi
}

complete -F _tagfs_completions tagfs
complete -F _tagfs_completions tagfs.py

