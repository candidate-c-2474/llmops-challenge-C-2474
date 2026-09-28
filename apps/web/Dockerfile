FROM node:18-alpine

WORKDIR /app
COPY apps/web/package*.json ./
RUN npm install 2>/dev/null || true

COPY apps/web/ ./
EXPOSE 3000
CMD ["npm", "run", "dev"]
