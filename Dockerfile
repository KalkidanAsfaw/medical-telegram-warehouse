FROM python:3.11-slim

# System deps for psycopg2 and opencv (used by ultralytics)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash"]
