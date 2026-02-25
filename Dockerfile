FROM python:3.11-slim

WORKDIR /app

# 必要最低限
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 依存関係
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# ソース全部
COPY . /app

# RailwayはPORTを環境変数で渡すことが多い（使わんでもOK）
ENV PORT=8000

# ★ここが超重要：実際の場所に合わせる
CMD ["python", "threads-auto/threads-auto/worker.py"]
