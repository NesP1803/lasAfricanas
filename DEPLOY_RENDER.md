# Despliegue en Render (Django + Vite)

Este proyecto queda preparado para desplegar en Render con:

- **Backend Django** como **Web Service (Docker)**.
- **Frontend Vite** como **Static Site**.
- **PostgreSQL** administrado por Render usando `DATABASE_URL`.

---

## 1) Variables de entorno (Backend)

Configura estas variables en el servicio backend de Render:

- `DJANGO_SETTINGS_MODULE=config.settings`
- `DEBUG=False`
- `SECRET_KEY=<valor-seguro>`
- `ALLOWED_HOSTS=<host-backend-render>,<otros-hosts-si-aplica>`
- `CSRF_TRUSTED_ORIGINS=https://<frontend-render>,https://<backend-render>`
- `CORS_ALLOWED_ORIGINS=https://<frontend-render>`
- `CORS_ALLOW_ALL_ORIGINS=False`
- `DATABASE_URL=<se inyecta desde PostgreSQL de Render>`

> Nota: en local se mantiene soporte con `.env` usando `python-decouple`.

---

## 2) Variable de entorno (Frontend)

Configura en el Static Site:

- `VITE_API_URL=https://<backend-render>`

El frontend consume el API usando esa URL en producción.

---

## 3) Orden recomendado de creación en Render

1. **PostgreSQL** (Render Database).
2. **Backend Web Service** (Docker, `rootDir=backend`).
3. **Frontend Static Site** (`rootDir=frontend`).

Si usas blueprint, puedes aplicar directamente `render.yaml` en la raíz del repo.

---

## 4) Pasos de despliegue manual en Render

1. Conecta el repo en Render.
2. Crea la base de datos PostgreSQL.
3. Crea el Web Service backend:
   - Runtime: **Docker**
   - Root Directory: `backend`
   - Vincula `DATABASE_URL` desde la DB de Render
   - Carga variables de entorno del backend
4. Crea el Static Site frontend:
   - Root Directory: `frontend`
   - Build Command: `npm ci && npm run build`
   - Publish Directory: `dist`
   - Variable: `VITE_API_URL=https://<backend-render>`
5. Revisa logs de build/deploy y prueba login + endpoints principales.

---

## 5) Probar Docker backend local antes de subir

Desde la raíz del repo:

```bash
docker build -t lasafricanas-backend ./backend
```

Ejemplo de ejecución local del contenedor:

```bash
docker run --rm -p 8000:8000 \
  -e DJANGO_SETTINGS_MODULE=config.settings \
  -e DEBUG=True \
  -e SECRET_KEY=dev-secret \
  -e DATABASE_NAME=lasAfricanas_db \
  -e DATABASE_USER=postgres \
  -e DATABASE_PASSWORD=postgres \
  -e DATABASE_HOST=host.docker.internal \
  -e DATABASE_PORT=5432 \
  lasafricanas-backend
```

Si quieres simular producción con Render DB:

```bash
docker run --rm -p 8000:8000 \
  -e DJANGO_SETTINGS_MODULE=config.settings \
  -e DEBUG=False \
  -e SECRET_KEY=dev-secret \
  -e ALLOWED_HOSTS=127.0.0.1,localhost \
  -e CSRF_TRUSTED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173 \
  -e CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173 \
  -e CORS_ALLOW_ALL_ORIGINS=False \
  -e DATABASE_URL=<postgres-url> \
  lasafricanas-backend
```

---

## 6) Nota importante sobre archivos media/XML/PDF

El despliegue actual mantiene `MEDIA_ROOT` en disco local del contenedor. En Render ese filesystem es **efímero** (no persistente entre reinicios/deploys).

Para producción estable, conviene mover media/XML/PDF a almacenamiento persistente (por ejemplo S3/R2/B2).
