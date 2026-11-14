# Configuración de despliegue — Earth2Worlds

## Arquitectura operativa

El frontend y el backend están diseñados para ejecutarse como servicios independientes:

- **Frontend**: `https://earth2worlds-frontend.onrender.com`
- **Backend / API**: `https://earth2worlds.onrender.com`

## URLs de API y política CORS

- **Producción**: El frontend define `VITE_API_BASE_URL=https://earth2worlds.onrender.com` en `frontend/.env.production` para dirigir las peticiones `/api/v1/...` al servicio de backend.
- **Desarrollo local**: El frontend utiliza rutas relativas `/api/v1/...` y el proxy de Vite (`frontend/vite.config.ts`) las redirige a `http://127.0.0.1:3000`.
- **Allowlist CORS en Fastify**:
  - Con `NODE_ENV=production`: autoriza exclusivamente `https://earth2worlds-frontend.onrender.com`.
  - Fuera de producción: autoriza además `http://localhost:5173`.
  - Nunca utiliza comodín (`*`).

## Gestión de secretos y compilación

- `ROTATERRA_API_KEY` se configura exclusivamente en las variables de entorno privadas del servicio backend.
- Nunca debe incluirse en variables con prefijo `VITE_`, código fuente, repositorio Git, URLs ni logs.
- El comando de compilación del backend (`npm run build`) requiere las dependencias de desarrollo (`typescript` y `@types/node`), por lo que en entornos de CI/CD debe instalarse con `npm ci --include=dev` antes de compilar.
