FROM python:3.11-slim

WORKDIR /app

COPY services/ats-agent-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared/ /app/shared/
COPY services/ats-agent-service/ /app/

EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
