FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY static ./static
RUN useradd -r -u 10001 appuser && mkdir -p /srv/data && chown appuser /srv/data
USER appuser
ENV DATABASE_PATH=/srv/data/tigray.sqlite3
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
