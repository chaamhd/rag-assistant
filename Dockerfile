FROM python:3.12-slim

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Les modèles sont téléchargés une seule fois, à la construction de l'image
ARG EMBEDDING_MODEL
ARG RERANK_MODEL
ENV FASTEMBED_CACHE_PATH=/opt/models
RUN python -c "import os; from fastembed import TextEmbedding; from fastembed.rerank.cross_encoder import TextCrossEncoder; TextEmbedding(os.environ['EMBEDDING_MODEL']); TextCrossEncoder(model_name=os.environ['RERANK_MODEL'])"

COPY app ./app

RUN useradd --create-home appuser && chown -R appuser /opt/models
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
