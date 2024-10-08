#!/usr/bin/env bash

if [ -t 1 ]; then
  >&2 echo "!!! This probably should be redirected to a file"
  >&2 echo
fi

if [ -z "$1" ]; then
  >&2 echo "!!! A cookies.sqlite file must be provided"
  >&2 echo "Usage: $0 FILE"
fi

# This roughly matches the header for these files that is
# used by the Python standard library
echo "# HTTP Cookie File"
echo "# http://curl.haxx.se/rfc/cookie_spec.html"
echo "# This is a generated file!  Do not edit."
echo ""

sqlite3 "$1" <<- EOF
.mode tabs
.header off
SELECT
    -- In the Netscape Cookie format, HttpOnly cookies are prefixed
    -- with "#HttpOnly_".
    CASE
        WHEN isHttpOnly
        THEN '#HttpOnly_' || host
        ELSE host
    END,
    CASE
        WHEN host LIKE '.%'
        THEN 'TRUE'
        ELSE 'FALSE'
    END,
    path,
    CASE
        WHEN isSecure
        THEN 'TRUE'
        ELSE 'FALSE'
    END,
    expiry,
    name,
    value
FROM moz_cookies
WHERE
    host LIKE '%nytimes.com'
    -- Technically, either of these cookies works but we'll grab them
    -- both just to help ensure that we have at least one
    AND name IN ('NYT-S', 'SIDNY')
;
EOF
