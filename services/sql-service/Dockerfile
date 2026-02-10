FROM python:3.11-slim

WORKDIR /app

COPY services/sql-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared/ /app/shared/
COPY services/sql-service/ /app/

EXPOSE 8004
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
