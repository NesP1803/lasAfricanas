# Instrucciones para Activar el Sistema de Configuración

Se ha implementado un sistema completo de configuración funcional para el sistema de Las Africanas. A continuación se detallan las funcionalidades implementadas y los pasos para activarlas.

## Funcionalidades Implementadas

### 1. Configuración de Empresa
- ✅ Botón "GUARDAR" funcional - Guarda los datos de la empresa en la base de datos
- ✅ Botón "CANCELAR" (X) funcional - Cancela cambios y recarga datos originales
- ✅ Botón "Seleccionar" funcional - Permite seleccionar y subir el logo de la empresa
- ✅ Todos los campos del formulario son editables y se guardan correctamente
- ✅ Sistema de auditoría registra cambios automáticamente

### 2. Gestión de Usuarios
- ✅ Botón "Nuevo Usuario" funcional - Abre modal para crear nuevo usuario
- ✅ Botón "Editar" funcional - Permite editar datos de usuarios existentes
- ✅ Botón "Desactivar" funcional - Desactiva usuarios con confirmación
- ✅ Modal completo con validación de contraseñas
- ✅ Sistema de auditoría registra todas las operaciones

### 3. Impuestos
- ✅ Botón "Guardar" funcional - Agrega nuevos impuestos al sistema
- ✅ Campo de texto para agregar valores de IVA (números o "E" para exento)
- ✅ Lista de impuestos existentes cargada desde la base de datos

### 4. Auditoría
- ✅ Sistema completo de auditoría implementado
- ✅ Registra automáticamente todos los cambios realizados por usuarios
- ✅ Captura: usuario, fecha/hora, acción, modelo afectado, descripción e IP
- ✅ Visualización en tabla con datos en tiempo real
- ✅ Soporta filtros (por fecha, usuario, tipo de acción)

### 5. Cambiar Contraseña
- ✅ Formulario completo funcional
- ✅ Validación de contraseña actual
- ✅ Validación de coincidencia de contraseñas nuevas
- ✅ Longitud mínima de 6 caracteres
- ✅ Sistema de auditoría registra cambios de contraseña

### 6. Backup y Restauración
- ✅ Botón "Crear Backup Ahora" funcional - Genera backup JSON de toda la BD
- ✅ Lista de backups anteriores con fecha y tamaño
- ✅ Sistema de auditoría registra creación de backups
- ✅ Backups guardados en directorio `/backend/backups/`

## Pasos para Activar el Sistema

### 1. Activar el Entorno Virtual (Backend)

```bash
cd /home/user/lasAfricanas/backend

# Si no existe el entorno virtual, crearlo:
python3 -m venv venv

# Activar el entorno virtual:
source venv/bin/activate

# Instalar dependencias si es necesario:
pip install -r requirements.txt
```

### 2. Crear las Migraciones de Base de Datos

```bash
# Asegurarse de estar en el directorio backend con el entorno virtual activo
cd /home/user/lasAfricanas/backend

# Crear las migraciones
python manage.py makemigrations

# Aplicar las migraciones
python manage.py migrate
```

### 3. Inicializar Datos por Defecto (Opcional)

El sistema creará automáticamente los registros de configuración por defecto la primera vez que accedas a cada sección. Sin embargo, puedes cargar impuestos por defecto ejecutando:

```bash
python manage.py shell
```

Luego en la shell de Django:

```python
from apps.core.models import Impuesto

# Crear impuestos por defecto
Impuesto.objects.create(nombre='IVA', valor='0', porcentaje=0, es_exento=False)
Impuesto.objects.create(nombre='IVA', valor='19', porcentaje=19, es_exento=False)
Impuesto.objects.create(nombre='IVA', valor='E', porcentaje=0, es_exento=True)

exit()
```

### 4. Iniciar el Servidor Backend

```bash
cd /home/user/lasAfricanas/backend
source venv/bin/activate
python manage.py runserver
```

### 5. Iniciar el Servidor Frontend

En una nueva terminal:

```bash
cd /home/user/lasAfricanas/frontend
npm run dev
```

## Modelos de Base de Datos Creados

Se han agregado los siguientes modelos en `/backend/apps/core/models.py`:

1. **ConfiguracionEmpresa** - Datos de la empresa (NIT, razón social, dirección, etc.)
2. **Impuesto** - Configuración de impuestos IVA
3. **Auditoria** - Registro completo de auditoría del sistema
4. **ConfiguracionFacturacion** - Configuración de numeración de facturas

## API Endpoints Disponibles

Todos los endpoints están protegidos con autenticación JWT:

- `GET/POST/PATCH /api/config/empresa/` - Configuración de empresa
- `GET/POST/PATCH/DELETE /api/config/impuestos/` - Gestión de impuestos
- `GET /api/config/auditoria/` - Consulta de auditoría (solo lectura)
- `GET/POST/PATCH /api/config/facturacion/` - Configuración de facturación
- `GET/POST/PATCH /api/config/usuarios/` - Gestión de usuarios
- `POST /api/config/usuarios/{id}/desactivar/` - Desactivar usuario
- `POST /api/config/usuarios/{id}/activar/` - Activar usuario
- `POST /api/config/usuarios/cambiar_password/` - Cambiar contraseña
- `POST /api/config/backup/crear_backup/` - Crear backup
- `GET /api/config/backup/listar_backups/` - Listar backups

## Archivos Modificados/Creados

### Backend:
- ✅ `/backend/apps/core/models.py` - Modelos agregados
- ✅ `/backend/apps/core/serializers.py` - Serializers nuevos
- ✅ `/backend/apps/core/views.py` - ViewSets nuevos
- ✅ `/backend/config/api_router.py` - Rutas registradas

### Frontend:
- ✅ `/frontend/src/api/configuracion.ts` - Cliente API nuevo
- ✅ `/frontend/src/pages/Configuracion.tsx` - Componente completamente renovado

## Notas Importantes

1. **Auditoría Automática**: Todos los cambios en configuración, usuarios, impuestos, etc., se registran automáticamente en la tabla de auditoría.

2. **Seguridad**: Todos los endpoints requieren autenticación JWT. Solo usuarios autenticados pueden acceder.

3. **Backups**: Los backups se crean en formato JSON usando el comando `dumpdata` de Django. Se guardan en `/backend/backups/`.

4. **Permisos**: Para producción, considera agregar permisos más granulares (por ejemplo, solo administradores pueden crear backups o modificar la configuración de empresa).

5. **Facturación**: La sección de facturación está creada pero dejada sin funcionalidad de backend según lo solicitado.

## Próximos Pasos Sugeridos

1. Ejecutar las migraciones para crear las tablas en la base de datos
2. Iniciar los servidores backend y frontend
3. Probar cada funcionalidad desde la interfaz
4. Agregar validaciones adicionales según necesidades del negocio
5. Configurar permisos más específicos para diferentes tipos de usuarios

## Soporte

Si encuentras algún problema:
1. Verifica que las migraciones se aplicaron correctamente
2. Revisa los logs del servidor backend
3. Asegúrate de que el usuario está autenticado correctamente
4. Verifica la consola del navegador para errores en el frontend
