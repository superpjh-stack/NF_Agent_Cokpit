FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py cockpit_runtime.py ./
COPY needs_agent/ ./needs_agent/
COPY sample_docs/ ./sample_docs/
COPY scripts/migrate_sqlite_to_postgres.py ./scripts/migrate_sqlite_to_postgres.py
COPY .streamlit/ ./.streamlit/
COPY data/needs_food_demo.db ./data/needs_food_demo.db
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
