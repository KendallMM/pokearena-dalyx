FROM node:22-alpine

WORKDIR /app

# Primero las dependencias, para aprovechar la caché de Docker.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# Servidor de desarrollo con recarga automática.
CMD ["npm", "run", "dev"]
