# Vielma - MotoRepuestos

Sistema web de gestión de órdenes de trabajo para el taller **Vielma - MotoRepuestos**
(motos, autos y motocarros). Permite registrar y seguir órdenes, controlar tiempos de
trabajo, gestionar empleados y generar reportes diarios y mensuales.

Pensado para usarse cómodamente desde el celular de los mecánicos (diseño responsivo,
botones grandes, PWA instalable) y desde la laptop del jefe.

---

## 1. Tecnologías

- **Backend:** Python + Flask
- **Base de datos:** SQLite (local, persistente, en `instance/vielma.db`)
- **ORM:** Flask-SQLAlchemy
- **Frontend:** HTML5 + CSS3 + JavaScript (Jinja2)
- **Autenticación:** sesiones de Flask + contraseñas con hash seguro (Werkzeug)
- **Seguridad:** protección CSRF (Flask-WTF), cookies HttpOnly/SameSite, roles en backend
- **Gráficos:** Chart.js (incluido localmente, sin CDN)
- **Zona horaria:** `America/Asuncion` (las marcas se guardan en UTC y se muestran en hora local)

---

## 2. Estructura del proyecto

```
.
├── app.py                 # App factory, filtros, manejo de errores
├── config.py              # Configuración por entorno (lee .env)
├── constants.py           # Roles, estados, tipos de trabajo/vehículo, transiciones
├── extensions.py          # Instancias de SQLAlchemy y CSRF
├── models.py              # Modelo de datos (users, work_orders, sesiones, etc.)
├── forms.py               # Formularios con validación de servidor
├── auth.py                # Login/sesión y decoradores de permisos
├── seed.py                # Creación de BD y usuarios iniciales (idempotente)
├── requirements.txt       # Dependencias de ejecución
├── requirements-dev.txt   # Dependencias de desarrollo (pytest)
├── .env.example           # Plantilla de variables de entorno
├── blueprints/            # Rutas
│   ├── auth_routes.py     #   login, logout, cambio de contraseña
│   ├── main_routes.py     #   panel del empleado
│   ├── order_routes.py    #   órdenes: crear, ver, editar, transiciones
│   ├── jefe_routes.py     #   dashboard, bandeja, gestión de empleados
│   └── report_routes.py   #   reportes diarios/mensuales + CSV
├── services/              # Lógica de negocio
│   ├── orders.py          #   máquina de estados y reglas de transición
│   ├── timing.py          #   cálculo de tiempos (historial + sesiones)
│   ├── reports.py         #   indicadores de reportes
│   └── audit.py           #   registro de auditoría
├── utils/
│   └── timezone.py        # Conversión UTC <-> America/Asuncion y formatos
├── templates/             # Plantillas Jinja2
├── static/                # CSS, JS, logo, Chart.js, manifest, service worker
├── tests/                 # Pruebas automatizadas (pytest)
└── instance/              # BD SQLite (se crea sola; NO se versiona)
```

---

## 3. Instalación

Requiere **Python 3.11 o superior**.

```powershell
# 1. Posicionarse en la carpeta del proyecto
cd "sistema de control y asignacion de tareas"

# 2. Crear el entorno virtual
python -m venv venv

# 3. Activar el entorno
#    Windows (PowerShell):
.\venv\Scripts\Activate.ps1
#    Linux / macOS:
#    source venv/bin/activate

# 4. Instalar dependencias
pip install -r requirements.txt
```

---

## 4. Configuración inicial (credenciales y secretos)

1. Copia la plantilla de entorno:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Edita `.env` y configura al menos:

   - `SECRET_KEY`: clave larga y aleatoria. Genérala con:
     ```powershell
     python -c "import secrets; print(secrets.token_hex(32))"
     ```
   - `SEED_PASSWORD_CHRISTIAN`, `SEED_PASSWORD_HUMBERTO`, `SEED_PASSWORD_ARTURO`:
     contraseñas iniciales de los tres usuarios.

   Si dejas las contraseñas de semilla vacías, el sistema usa la contraseña
   temporal `cambiar123` y **obliga a cambiarla** en el primer inicio de sesión.

3. En producción, además:
   - `FLASK_ENV=production`
   - `SESSION_COOKIE_SECURE=true` (solo si usas HTTPS)

Los usuarios iniciales se crean automáticamente la primera vez que arranca la app
y **no se duplican** si reinicias:

| Usuario     | Rol      |
|-------------|----------|
| `christian` | Jefe     |
| `humberto`  | Empleado |
| `arturo`    | Empleado |

El usuario se escribe en minúsculas al iniciar sesión.

---

## 5. Ejecutar la aplicación

```powershell
python app.py
```

Luego abre `http://127.0.0.1:5000` en el navegador.

La base de datos SQLite se crea automáticamente en `instance/vielma.db` la primera vez.

Para acceder desde el celular en la misma red Wi-Fi, usa la IP de la laptop que
muestra Flask al arrancar (por ejemplo `http://192.168.100.12:5000`).

---

## 6. Flujo de trabajo de una orden

```
Solicitado
  → En espera de aprobación      (empleado envía presupuesto)
     → Aprobado por cliente      (se registra la decisión externa del cliente)
        → Confirmado             (el jefe confirma, fija monto y asigna)
           → En trabajo          (empleado inicia; arranca el cronómetro)
              ⇄ Pausado          (pausa con motivo; no suma tiempo efectivo)
              → Finalizado        (empleado cierra el trabajo)
                 → Entregado      (el jefe cierra al retirar el vehículo)
```

Estados alternativos: **Rechazado por cliente** y **Cancelado** (conservan historial).

Reglas aplicadas en el backend:
- No se puede confirmar sin aprobación del cliente registrada.
- El empleado no puede modificar el monto aprobado ni el monto cobrado.
- Una orden finalizada/cerrada no sigue acumulando tiempo efectivo.
- Las reaperturas quedan auditadas.
- Las transiciones inválidas se bloquean.

---

## 7. Medición de tiempos

Los tiempos se calculan desde el **historial de estados** y las **sesiones de trabajo**,
no desde el estado actual:

- **Tiempo efectivo:** suma de todas las sesiones de trabajo (excluye pausas).
- **Tiempo de espera / pendiente:** suma de todos los periodos en cada estado.
- **Tiempo calendario:** desde la creación hasta el cierre.

Si una orden pasa varias veces por un estado, se acumulan todos los periodos.
Cada empleado tiene sus propias sesiones; no se permiten sesiones duplicadas
simultáneas para el mismo empleado en la misma orden.

---

## 8. Reportes

En **Reportes** (solo jefe) puedes generar informes **diarios** o **mensuales**:

- Conteos (creadas, aprobadas, confirmadas, iniciadas, finalizadas, entregadas, rechazadas/canceladas).
- Tiempos promedio (con el tamaño `n` de cada cálculo).
- Indicadores económicos (promedios que excluyen nulos; montos aprobados y cobrados separados).
- Gráficos de tipos de trabajo, marcas, vehículos y evolución diaria.
- Botón de **imprimir** y exportación a **CSV**.

---

## 9. Pruebas

```powershell
pip install -r requirements-dev.txt
pytest -v
```

Las pruebas cubren autenticación, permisos por rol, el flujo completo de órdenes
(crear → aprobar → confirmar → iniciar → pausar → finalizar), las reglas de
transición y el cálculo de tiempos.

**Resultado verificado:** 12 pruebas, todas en verde.

---

## 10. Respaldo (backup) de SQLite

La base de datos es un único archivo: `instance/vielma.db`.

**Copia simple (con la app detenida):**

```powershell
Copy-Item instance\vielma.db "backups\vielma_$(Get-Date -Format yyyyMMdd_HHmmss).db"
```

**Copia en caliente (con la app corriendo, recomendado):**

```powershell
.\venv\Scripts\python.exe -c "import sqlite3; src=sqlite3.connect('instance/vielma.db'); dst=sqlite3.connect('backups/vielma_backup.db'); src.backup(dst); dst.close(); src.close()"
```

El método `backup()` de SQLite genera una copia consistente aunque haya escrituras
en curso. Guarda los respaldos fuera del equipo (nube/USB) periódicamente.

**Restaurar:** detén la app y reemplaza `instance/vielma.db` por la copia.

---

## 11. Despliegue en un servidor

Para producción no uses el servidor de desarrollo de Flask. Usa un WSGI como
**gunicorn** (incluido en `requirements.txt`).

### Opción recomendada — Render.com (con PostgreSQL gratis)

El proyecto ya trae `render.yaml`, `Procfile` y `runtime.txt` listos. Los datos
se guardan en una base **PostgreSQL** que persiste entre despliegues (el disco
del servicio web en el plan Free es efímero, por eso NO se usa SQLite en Render).

Pasos:

1. Subí el proyecto a un repositorio de GitHub.
2. En [Render](https://render.com) → **New** → **Blueprint**, conectá el repo.
   Render leerá `render.yaml` y creará dos recursos:
   - la base de datos PostgreSQL `vielma-db`,
   - el servicio web `sistema-vielma`, con `DATABASE_URL` ya conectada.
3. En el servicio web → **Environment**, definí las contraseñas iniciales:
   `SEED_PASSWORD_CHRISTIAN`, `SEED_PASSWORD_HUMBERTO`, `SEED_PASSWORD_ARTURO`.
   (`SECRET_KEY` la genera Render automáticamente.)
4. **Deploy**. Al primer arranque se crean las tablas y los usuarios iniciales.
5. Abrí la URL pública que te da Render e iniciá sesión.

Notas del plan Free de Render:
- El servicio se "duerme" tras inactividad; la primera visita tras dormir tarda
  unos segundos en despertar. No se pierden datos (viven en PostgreSQL).
- La base PostgreSQL Free tiene vencimiento (Render avisa por correo); extenderla
  o migrarla es sencillo desde el panel.

El código detecta `DATABASE_URL` automáticamente (ver `config.py`): si existe,
usa PostgreSQL; si no, cae a SQLite local para desarrollo.

### Opción A — Windows con waitress (uso local en el taller)

```powershell
pip install waitress
$env:FLASK_ENV="production"
.\venv\Scripts\python.exe -m waitress --listen=0.0.0.0:8000 app:app
```

### Opción B — Linux con gunicorn + Nginx

```bash
pip install gunicorn
export FLASK_ENV=production
gunicorn --workers 2 --bind 127.0.0.1:8000 app:app
```

Luego pon **Nginx** delante como proxy inverso con HTTPS (Let's Encrypt) y, con
HTTPS activo, establece `SESSION_COOKIE_SECURE=true` en `.env`.

Checklist de producción:
- `SECRET_KEY` fuerte y único.
- `FLASK_ENV=production` (desactiva el modo debug).
- HTTPS + `SESSION_COOKIE_SECURE=true`.
- Respaldos automáticos de `instance/vielma.db`.
- La carpeta `instance/` fuera del control de versiones.

---

## 12. Seguridad implementada

- Contraseñas con hash (nunca en texto plano ni en logs).
- Control de acceso por rol **validado en el backend** (no solo ocultando botones).
- Protección CSRF en todos los formularios.
- Consultas vía ORM (parametrizadas).
- Validación de datos en servidor.
- Cookies HttpOnly y SameSite; Secure en HTTPS.
- Auditoría de acciones relevantes (login, cambios de estado, montos, asignaciones, reaperturas).
- Verificación de acceso por orden (un empleado no abre órdenes ajenas manipulando el ID).

---

## 13. PWA (instalable en el celular)

La app incluye `manifest.webmanifest` y un service worker que cachea los archivos
estáticos. Desde Chrome en Android puedes usar **"Agregar a pantalla de inicio"**
para instalarla como app. Los datos de las órdenes **no** se cachean (siempre se
piden al servidor para evitar mostrar información desactualizada).

---

## 14. Limitaciones conocidas

- La aprobación del cliente es **externa**: el sistema solo registra manualmente si
  el cliente aprobó o rechazó (no envía mensajes ni contacta al cliente).
- El servidor de desarrollo (`python app.py`) es solo para pruebas locales; en
  producción se debe usar waitress/gunicorn.
- La exportación a **PDF** no está incluida para no añadir dependencias pesadas;
  se ofrece **imprimir** (que permite "Guardar como PDF" desde el navegador) y **CSV**.
- SQLite es ideal para un taller (un solo nodo, bajo volumen). Si en el futuro
  hay muchos usuarios concurrentes, convendría migrar a PostgreSQL.
- La zona horaria usa la base de datos de zonas del sistema; si falta, se aplica
  un desfase fijo UTC-3 (vigente para Asunción).
