FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH="${PYTHONPATH}:/app"

RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copia il progetto
COPY pyproject.toml README.md Home.py ./
COPY src pages schemas data .streamlit ./

# Installa il package principale
RUN pip install --no-cache-dir .

# Assicura permessi per Streamlit
RUN mkdir -p /app/.streamlit && chmod -R 777 /app/.streamlit

EXPOSE 8501

CMD ["streamlit", "run", "Home.py", "--server.port=8501", "--server.address=0.0.0.0"]