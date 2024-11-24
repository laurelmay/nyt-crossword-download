#!/usr/bin/env bash

if [ -t 1 ]; then
  >&2 echo "!!! This probably should be redirected to a file"
  >&2 echo
fi

if [ -z "$1" ]; then
  >&2 echo "!!! A cookies.sqlite file must be provided"
  >&2 echo "Usage: $0 FILE"
  exit
fi

# This roughly matches the header for these files that is
# used by the Python standard library
echo "# HTTP Cookie File"
echo "# http://curl.haxx.se/rfc/cookie_spec.html"
echo "# This is a generated file!  Do not edit."
echo ""

sqlite3 "$1" < ./query.sql
