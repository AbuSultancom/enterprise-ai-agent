FROM python:3.12-slim

# Microsoft ODBC Driver 18 for SQL Server (for Onyx Pro / accounting DB)
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list -o /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc-dev \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent_core ./agent_core
COPY llm_gateway ./llm_gateway
COPY tools ./tools
COPY memory ./memory
COPY connectors ./connectors
COPY api ./api
COPY dashboard ./dashboard

ENV MEMORY_DB_PATH=/data/knowledge.json
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
