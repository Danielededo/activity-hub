# --- build ---------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

# Copied first so a source-only change reuses the installed layer.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# --- serve ---------------------------------------------------------------
FROM nginx:1.27-alpine

# API_URL is substituted at container start, so one image serves any backend.
ENV API_URL=http://backend:8000/api/
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

# nginx:alpine runs /etc/nginx/templates through envsubst on startup.
