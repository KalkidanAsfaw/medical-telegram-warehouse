-- Fact table: YOLO image detections joined to the message fact, carrying the
-- channel and date foreign keys so detections sit inside the star schema.
-- Grain: one row per detected object (an image with no detections contributes a
-- single 'other' row with a null detected_class).

with detections as (
    select * from {{ ref('stg_image_detections') }}
),

messages as (
    select message_id, channel_key, date_key
    from {{ ref('fct_messages') }}
)

select
    d.message_id,
    m.channel_key,                       -- FK -> dim_channels
    m.date_key,                          -- FK -> dim_dates
    d.detected_class,
    d.confidence_score,
    d.image_category,
    d.image_path
from detections d
inner join messages m
    on d.message_id = m.message_id
