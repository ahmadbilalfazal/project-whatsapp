FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV FLASK_ENV=production
ENV DATABASE_URL=sqlite:///app.db
EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "run:app"]
