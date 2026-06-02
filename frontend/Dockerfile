# ── Etapa 1: builder ──────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

# NEXT_PUBLIC_* se incrusta en el bundle en tiempo de compilación.
# Debe llegar como ARG para que npm run build lo recoja.
ARG NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_BACKEND_URL=$NEXT_PUBLIC_BACKEND_URL

WORKDIR /app

# Instalar dependencias primero (capa cacheada si package*.json no cambia)
COPY package.json package-lock.json ./
RUN npm ci

# Copiar el resto del código y compilar
COPY . .
RUN npm run build

# ── Etapa 2: runner (imagen final ligera) ─────────────────────────────────────
FROM node:20-alpine AS runner

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

# Usuario no-root para reducir la superficie de ataque
RUN addgroup --system --gid 1001 nodejs \
 && adduser  --system --uid 1001 nextjs

# Copiar únicamente los artefactos necesarios para ejecutar la app
COPY --from=builder --chown=nextjs:nodejs /app/.next        ./.next
COPY --from=builder --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nextjs:nodejs /app/public       ./public
COPY --from=builder --chown=nextjs:nodejs /app/package.json ./package.json

USER nextjs

EXPOSE 3000

CMD ["npm", "run", "start"]
