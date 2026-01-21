# Las Africanas

Guía de instalación y configuración para el **backend** (Django) y el **frontend** (React + Vite).

## Requisitos

- **Python 3.11+** (recomendado) y `pip`
- **Node.js 20+** (recomendado) y `npm`
- **PostgreSQL 14+**

## Backend (Django)

### 1) Crear y activar entorno virtual

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
```

> En Windows usa: `\.venv\Scripts\activate`

**Si ya existe la carpeta del entorno virtual (por ejemplo `venv` o `.venv`):**

```bash
# Linux/macOS
source venv/bin/activate
# o, si el entorno se llama .venv
source .venv/bin/activate
```

```powershell
# Windows (PowerShell)
venv\Scripts\Activate.ps1
# o, si el entorno se llama .venv
.venv\Scripts\Activate.ps1
```

```cmd
:: Windows (CMD)
venv\Scripts\activate.bat
:: o, si el entorno se llama .venv
.venv\Scripts\activate.bat
```

### 2) Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3) Configurar variables de entorno

Crea un archivo `backend/.env` con los siguientes valores (ajusta según tu entorno):

```env
SECRET_KEY=django-insecure-local-key
DEBUG=True
DATABASE_NAME=lasAfricanas_db
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DATABASE_HOST=localhost
DATABASE_PORT=5432
```

### 4) Crear la base de datos

Asegúrate de tener PostgreSQL corriendo y crea la base de datos:

```bash
createdb lasAfricanas_db
```

> Si usas usuario distinto de `postgres`, crea el usuario o ajusta las variables del `.env`.

### 5) Ejecutar migraciones

```bash
python manage.py migrate
```

### 6) Crear superusuario (opcional)

```bash
python manage.py createsuperuser
```

### 7) Levantar el servidor

```bash
python manage.py runserver
```

El backend quedará disponible en `http://localhost:8000/`.

## Frontend (React + Vite)

### 1) Instalar dependencias

```bash
cd frontend
npm install
```

### 2) Configurar el endpoint del backend

Si el frontend usa variables de entorno para la API, crea un archivo `frontend/.env` (si aplica) con:

```env
VITE_API_URL=http://localhost:8000
```

> Si el proyecto no usa esta variable, puedes omitir este paso.

### 3) Levantar el servidor

```bash
npm run dev
```

El frontend quedará disponible en `http://localhost:5173/`.

## Flujo recomendado de desarrollo

1. Inicia PostgreSQL.
2. Levanta el backend (`python manage.py runserver`).
3. Levanta el frontend (`npm run dev`).

## Compartir datos de la base de datos con el equipo

Si los datos están solo en tu PC, hay dos formas comunes de compartirlos con tu compañero:

### Opción A: Exportar e importar la base de datos (PostgreSQL)

1) **Generar un dump** en tu máquina:

```bash
pg_dump -h localhost -U postgres -d lasAfricanas_db -F c -f lasAfricanas_db.dump
```

2) **Compartir el archivo** `lasAfricanas_db.dump` (por ejemplo, por Drive).

3) En la máquina de tu compañero, **crear la base** y **restaurar**:

```bash
createdb lasAfricanas_db
pg_restore -h localhost -U postgres -d lasAfricanas_db lasAfricanas_db.dump
```

> Ajusta usuario/host/puerto según tus variables de entorno.

### Opción B: Fixtures de Django (solo datos)

1) **Exportar datos** desde tu entorno:

```bash
python manage.py dumpdata --natural-foreign --natural-primary --indent 2 > data/seed.json
```

2) **Compartir** el archivo `data/seed.json`.

3) En la máquina de tu compañero, **cargar datos**:

```bash
python manage.py migrate
python manage.py loaddata data/seed.json
```

> Esta opción es útil si solo necesitas datos y no toda la estructura de PostgreSQL.

## Comandos útiles

### Backend

- `python manage.py makemigrations`
- `python manage.py migrate`
- `python manage.py createsuperuser`

### Frontend

- `npm run build`
- `npm run lint`
- `npm run preview`
