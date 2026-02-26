FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy
WORKDIR /app 
COPY . /app 
RUN pip install --no-cache-dir -r threads-auto/threads-auto/requirements.txt 
CMD ["python", "threads-auto/worker.py"]
