.mode tabs
.header off
SELECT
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
