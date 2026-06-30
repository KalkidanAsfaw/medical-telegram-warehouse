-- Staging: clean YOLO detection results. One row per detected object.

with source as (
    select * from {{ source('raw', 'image_detections') }}
)

select
    message_id::bigint                       as message_id,
    lower(trim(channel_name))                as channel_name,
    image_path,
    nullif(detected_class, '')               as detected_class,
    confidence_score::numeric                as confidence_score,
    image_category
from source
where message_id is not null
