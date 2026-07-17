FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent_core ./agent_core
COPY llm_gateway ./llm_gateway
COPY tools ./tools
COPY memory ./memory
COPY api ./api
COPY dashboard ./dashboard

ENV MEMORY_DB_PATH=/data/knowledge.json
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
