FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# ★これ重要
RUN playwright install chromium

COPY . /app

CMD ["python", "threads-auto/threads-auto/worker.py"]
