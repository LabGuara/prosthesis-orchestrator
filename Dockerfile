FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY db ./db

CMD ["sh", "-c", "python -m app.migrate && python -m app.main"]
