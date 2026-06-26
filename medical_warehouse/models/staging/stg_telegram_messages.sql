-- Staging: clean & standardize raw Telegram messages.
-- Casts types, normalizes columns, filters invalid rows, and adds calculated
-- fields (message_length, has_image).

with source as (
    select * from {{ source('raw', 'telegram_messages') }}
),

cleaned as (
    select
        message_id::bigint                              as message_id,
        lower(trim(channel_name))                       as channel_name,
        message_date::timestamptz                       as message_date,
        nullif(trim(message_text), '')                  as message_text,
        coalesce(has_media, false)                      as has_media,
        image_path,
        (image_path is not null)                        as has_image,
        coalesce(views, 0)                              as views,
        coalesce(forwards, 0)                           as forwards,
        coalesce(char_length(trim(message_text)), 0)    as message_length,
        scraped_at::timestamptz                         as scraped_at
    from source
    where message_id is not null
      and channel_name is not null
      and message_date is not null
)

select *
from cleaned
-- Drop truly empty records: no text AND no media.
where message_text is not null
   or has_media
