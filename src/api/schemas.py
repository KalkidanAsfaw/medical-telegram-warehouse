"""Task 4 - Pydantic request/response models for the analytical API."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class TopProduct(BaseModel):
    """A frequently mentioned term/product across all channels."""
    term: str = Field(..., description="Normalized word/term mentioned in messages.")
    mentions: int = Field(..., description="Number of messages mentioning the term.")


class ChannelActivityPoint(BaseModel):
    """Posting activity for a single day."""
    day: date
    posts: int
    total_views: int
    total_forwards: int


class ChannelActivity(BaseModel):
    """Posting activity and trends for a specific channel."""
    channel_name: str
    channel_type: str
    total_posts: int
    avg_views: float
    first_post_date: date | None
    last_post_date: date | None
    daily_activity: list[ChannelActivityPoint]


class MessageHit(BaseModel):
    """A single message matching a search query."""
    message_id: int
    channel_name: str
    message_date: date | None
    views: int
    forwards: int
    has_image: bool
    snippet: str = Field(..., description="Excerpt of the matching message text.")


class MessageSearchResponse(BaseModel):
    query: str
    count: int
    results: list[MessageHit]


class VisualContentStat(BaseModel):
    """Image-usage statistics for one channel."""
    channel_name: str
    channel_type: str
    total_posts: int
    posts_with_image: int
    image_share_pct: float = Field(..., description="Percent of posts that include an image.")
    promotional: int = 0
    product_display: int = 0
    lifestyle: int = 0
    other: int = 0
