FROM node:22-alpine AS web
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/reclaim ./backend/reclaim
COPY --from=web /app/dist ./dist
EXPOSE 8000
CMD ["sh", "-c", "uvicorn reclaim.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
