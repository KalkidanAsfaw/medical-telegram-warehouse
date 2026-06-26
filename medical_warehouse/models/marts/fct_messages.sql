-- Fact table: one row per message, with FKs to the channel and date dimensions.

with messages as (
    select * from {{ ref('stg_telegram_messages') }}
)

select
    m.message_id,
    md5(m.channel_name)                  as channel_key,   -- FK -> dim_channels
    to_char(m.message_date, 'YYYYMMDD')::int as date_key,   -- FK -> dim_dates
    m.message_text,
    m.message_length,
    m.views,
    m.forwards,
    m.has_image
from messages m
