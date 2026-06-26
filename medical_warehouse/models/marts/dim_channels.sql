-- Channel dimension: one row per channel with descriptive + summary attributes.

with messages as (
    select * from {{ ref('stg_telegram_messages') }}
),

agg as (
    select
        channel_name,
        min(message_date)::date as first_post_date,
        max(message_date)::date as last_post_date,
        count(*)                as total_posts,
        avg(views)              as avg_views
    from messages
    group by channel_name
)

select
    md5(channel_name) as channel_key,
    channel_name,
    case
        when channel_name = 'tikvahpharma'      then 'Pharmaceutical'
        when channel_name = 'lobelia4cosmetics' then 'Cosmetics'
        when channel_name = 'chemed123'         then 'Medical'
        else 'Other'
    end                                  as channel_type,
    first_post_date,
    last_post_date,
    total_posts,
    round(avg_views, 1)                  as avg_views
from agg
