FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Tokyo

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$PORT"]
