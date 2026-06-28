-- Business rule: view and forward counts must be non-negative.
-- Returns offending rows; the test passes only when 0 rows come back.

select
    message_id,
    views,
    forwards
from {{ ref('fct_messages') }}
where views < 0
   or forwards < 0
