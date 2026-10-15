FROM python:3.12-slim
WORKDIR /app
RUN useradd --uid 10001 --create-home portal && mkdir /data && chown portal:portal /data
COPY --chown=portal:portal server.py ./
COPY --chown=portal:portal public ./public
ENV HOST=0.0.0.0 PORT=8000 DATABASE_PATH=/data/portal.db
USER portal
EXPOSE 8000
VOLUME ["/data"]
CMD ["python", "server.py"]
