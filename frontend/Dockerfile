# Build bundle React rồi phục vụ bằng Nginx (kèm reverse proxy /api). Build từ thư mục gốc repo:
#   docker build -f frontend/Dockerfile -t docso-web .
FROM node:24-alpine AS build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
COPY docs/openapi.json /src/docs/openapi.json
RUN npm run gen:api && npm run build

FROM nginx:1.29-alpine
COPY infra/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/frontend/dist /usr/share/nginx/html
EXPOSE 80
# 127.0.0.1 chứ không phải localhost: trong Alpine localhost ra ::1 (IPv6) mà Nginx chỉ nghe IPv4
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
