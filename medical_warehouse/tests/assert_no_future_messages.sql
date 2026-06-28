-- Business rule: no message may be dated in the future.
-- Returns offending rows; the test passes only when 0 rows come back.

select
    message_id,
    channel_key,
    date_key
from {{ ref('fct_messages') }} f
join {{ ref('dim_dates') }} d using (date_key)
where d.full_date > current_date
