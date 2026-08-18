FROM apache/superset:6.1.0

USER root

RUN . /app/.venv/bin/activate && \
    uv pip install psycopg2-binary

COPY superset_config.py /app/pythonpath/superset_config.py
COPY extensions/ /app/extensions/

USER superset