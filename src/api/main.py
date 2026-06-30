"""Task 4 - FastAPI analytical API over the dbt star schema.

Run:  uvicorn src.api.main:app --reload
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.schemas import (
    ChannelActivity,
    ChannelActivityPoint,
    MessageHit,
    MessageSearchResponse,
    TopProduct,
    VisualContentStat,
)

MARTS = "public_marts"

# Common English/Amharic-transliteration stopwords to exclude from term counts.
STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "are", "this", "that", "from",
    "have", "has", "will", "not", "all", "can", "our", "out", "new", "now",
    "per", "use", "used", "more", "any", "get", "via", "etc", "also", "made",
    "made", "into", "only", "than", "then", "them", "they", "his", "her",
    "price", "birr", "call", "available", "contact", "address", "tel", "phone",
    "telegram", "option", "order", "item", "items", "shop", "store", "link",
    "here", "just", "please", "https", "http", "www", "com", "bole", "addis",
    "delivery", "around", "near", "branch", "open", "time", "info",
}
# Constant array literal (not user input) for the SQL filter.
_STOP_SQL = "array[" + ",".join(f"'{w}'" for w in sorted(STOPWORDS)) + "]"

app = FastAPI(
    title="Medical Telegram Warehouse API",
    description=(
        "Analytical API over the dbt star schema built from Ethiopian medical "
        "Telegram channels. Endpoints answer the project's core business questions."
    ),
    version="1.0.0",
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}


@app.get("/api/reports/top-products", response_model=list[TopProduct], tags=["reports"])
def top_products(
    limit: int = Query(10, ge=1, le=100, description="How many top terms to return."),
    db: Session = Depends(get_db),
):
    """Most frequently mentioned terms/products across all channels.

    Tokenizes message text, drops short words, numbers, and common stopwords,
    and counts the number of distinct messages mentioning each term.
    """
    sql = text(f"""
        with words as (
            select distinct f.message_id,
                   regexp_split_to_table(lower(coalesce(f.message_text, '')), '[^a-z]+') as term
            from {MARTS}.fct_messages f
        )
        select term, count(*) as mentions
        from words
        where length(term) >= 4
          and term <> all({_STOP_SQL})
        group by term
        order by mentions desc
        limit :limit
    """)
    rows = db.execute(sql, {"limit": limit}).fetchall()
    return [TopProduct(term=r.term, mentions=r.mentions) for r in rows]


@app.get("/api/channels/{channel_name}/activity", response_model=ChannelActivity, tags=["channels"])
def channel_activity(channel_name: str, db: Session = Depends(get_db)):
    """Posting activity and daily trends for a specific channel."""
    name = channel_name.strip().lower()
    chan = db.execute(text(f"""
        select channel_name, channel_type, total_posts, avg_views,
               first_post_date, last_post_date
        from {MARTS}.dim_channels
        where channel_name = :name
    """), {"name": name}).fetchone()
    if chan is None:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_name}' not found.")

    daily = db.execute(text(f"""
        select d.full_date as day,
               count(*) as posts,
               coalesce(sum(f.views), 0) as total_views,
               coalesce(sum(f.forwards), 0) as total_forwards
        from {MARTS}.fct_messages f
        join {MARTS}.dim_channels c using (channel_key)
        join {MARTS}.dim_dates d using (date_key)
        where c.channel_name = :name
        group by d.full_date
        order by d.full_date
    """), {"name": name}).fetchall()

    return ChannelActivity(
        channel_name=chan.channel_name,
        channel_type=chan.channel_type,
        total_posts=chan.total_posts,
        avg_views=float(chan.avg_views or 0),
        first_post_date=chan.first_post_date,
        last_post_date=chan.last_post_date,
        daily_activity=[
            ChannelActivityPoint(day=r.day, posts=r.posts,
                                 total_views=r.total_views, total_forwards=r.total_forwards)
            for r in daily
        ],
    )


@app.get("/api/search/messages", response_model=MessageSearchResponse, tags=["search"])
def search_messages(
    query: str = Query(..., min_length=2, description="Keyword to search message text for."),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Search messages containing a keyword, most-viewed first."""
    rows = db.execute(text(f"""
        select f.message_id, c.channel_name, d.full_date as message_date,
               f.views, f.forwards, f.has_image, f.message_text
        from {MARTS}.fct_messages f
        join {MARTS}.dim_channels c using (channel_key)
        join {MARTS}.dim_dates d using (date_key)
        where f.message_text ilike :q
        order by f.views desc
        limit :limit
    """), {"q": f"%{query}%", "limit": limit}).fetchall()

    def snippet(textval: str) -> str:
        textval = textval or ""
        idx = textval.lower().find(query.lower())
        if idx == -1:
            return textval[:160]
        start = max(0, idx - 40)
        return ("..." if start > 0 else "") + textval[start:idx + 120].strip()

    hits = [
        MessageHit(
            message_id=r.message_id, channel_name=r.channel_name,
            message_date=r.message_date, views=r.views, forwards=r.forwards,
            has_image=r.has_image, snippet=snippet(r.message_text),
        )
        for r in rows
    ]
    return MessageSearchResponse(query=query, count=len(hits), results=hits)


@app.get("/api/reports/visual-content", response_model=list[VisualContentStat], tags=["reports"])
def visual_content(db: Session = Depends(get_db)):
    """Image-usage statistics across channels, including YOLO category breakdown."""
    base = db.execute(text(f"""
        select c.channel_name, c.channel_type, c.total_posts,
               count(*) filter (where f.has_image) as posts_with_image
        from {MARTS}.fct_messages f
        join {MARTS}.dim_channels c using (channel_key)
        group by c.channel_name, c.channel_type, c.total_posts
        order by posts_with_image desc
    """)).fetchall()

    # Distinct image per category, per channel.
    cats = db.execute(text(f"""
        with imgs as (
            select distinct message_id, channel_key, image_category
            from {MARTS}.fct_image_detections
        )
        select c.channel_name, i.image_category, count(*) as n
        from imgs i
        join {MARTS}.dim_channels c using (channel_key)
        group by c.channel_name, i.image_category
    """)).fetchall()

    cat_map: dict[str, dict[str, int]] = {}
    for r in cats:
        cat_map.setdefault(r.channel_name, {})[r.image_category] = r.n

    out = []
    for r in base:
        c = cat_map.get(r.channel_name, {})
        share = (100.0 * r.posts_with_image / r.total_posts) if r.total_posts else 0.0
        out.append(VisualContentStat(
            channel_name=r.channel_name,
            channel_type=r.channel_type,
            total_posts=r.total_posts,
            posts_with_image=r.posts_with_image,
            image_share_pct=round(share, 1),
            promotional=c.get("promotional", 0),
            product_display=c.get("product_display", 0),
            lifestyle=c.get("lifestyle", 0),
            other=c.get("other", 0),
        ))
    return out
