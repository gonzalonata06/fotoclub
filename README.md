# 📸 Fotoclub Access Control

Sistema ligero de gestión de socios y control de asistencia diseñado para **FastAPI** y **SQLite**, optimizado para ejecutarse de forma permanente en una **Orange Pi 3B**.

---

## 🛡️ Niveles de Acceso

El sistema detecta automáticamente el rol del usuario tras el inicio de sesión y adapta la interfaz:

### 👤 Menú Socio (Usuario Regular)
- **Flujo de Asistencia Inteligente:** La interfaz detecta si el socio está "Dentro" o "Fuera". Solo permite registrar la **Salida** si existe una **Entrada** previa, bloqueando errores de selección.
- **Vigencia Automática:** El acceso es válido por **4.5 meses (135 días)**. Al cumplirse el plazo, el sistema bloquea el ingreso y solicita reinscripción.
- **Seguridad Obligatoria:** Si el socio ingresa con el PIN temporal `0000`, el sistema le obliga a actualizarlo antes de permitir cualquier otra acción.

### 🛠️ Menú Administrador
- **Gestión de Socios:** Registro de nuevos miembros con asignación automática de fecha de vencimiento.
- **Reinscripción Rápida:** Permite renovar la membresía de un socio existente por otros 4.5 meses con solo ingresar su número de teléfono.
- **Recuperación:** Función para resetear el PIN de cualquier socio a `0000`.
- **Integridad:** Los administradores tienen prohibido registrar asistencia para no alterar las estadísticas del club.

---

## ⚙️ Configuración e Instalación

### 1. Preparación del Entorno
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r paquetes_pip.txt

2. Inicialización de Datos Maestros
Ejecute estos comandos para configurar los costos y tipos de socio:

# Insertar Tipos de Persona
sqlite3 club.db "INSERT INTO tipos_persona (id, nombre, activo) VALUES (1, 'Facultad', 1), (2, 'Universidad', 1), (3, 'Externo', 1);"

# Insertar Costos de Inscripción (Nuevos)
sqlite3 club.db "INSERT INTO costos_inscripcion (tipo_persona_id, monto, activo) VALUES (1, 300.0, 1), (2, 650.0, 1), (3, 1150.0, 1);"

# Insertar Costos de Reinscripción (Socios actuales)
sqlite3 club.db "INSERT INTO costos_reinscripcion (tipo_persona_id, monto, activo) VALUES (1, 250.0, 1), (2, 550.0, 1), (3, 950.0, 1);"

📊 Reportes y Consultas SQL (Uso Administrativo)
Use estos comandos en la terminal de la Orange Pi para obtener información en tiempo real:

📅 Asistencia del Día
Muestra quiénes han entrado o salido hoy y en qué actividad están.
sqlite3 club.db -header -column "SELECT u.nombre, a.tipo_evento, a.actividad, time(a.timestamp, 'localtime') as hora FROM accesos a JOIN usuarios u ON a.usuario_id = u.id WHERE date(a.timestamp) = date('now', 'localtime') ORDER BY a.timestamp DESC;"

Cambiar el número de telefono de un socio dado de alta
Primero se busca el ID del usuario:
sqlite3 club.db -header -column "SELECT id, nombre, apellido, es_admin, activo FROM usuarios WHERE telefono = '5511223344';"
Luego se usa ID para el cambio:
sqlite3 club.db "UPDATE usuarios SET telefono = '5599887766' WHERE id = 15;"

💰 Reporte de Caja e Inscripciones
Lista todos los pagos recibidos, montos y fechas.
sqlite3 club.db -header -column "SELECT u.nombre, i.costo_aplicado as monto, i.fecha_inscripcion FROM inscripciones i JOIN usuarios u ON i.usuario_id = u.id ORDER BY i.fecha_inscripcion DESC;"
⚠️ Socios Vencidos o Inactivos
Lista de personas que requieren contactarse para reinscripción.
sqlite3 club.db -header -column "SELECT nombre, apellido, telefono, fecha_vencimiento FROM usuarios WHERE activo = 0 AND es_admin = 0;"
🔍 Buscar Socio por Nombre
sqlite3 club.db -header -column "SELECT id, nombre, telefono, activo FROM usuarios WHERE nombre LIKE '%NombreAquí%';"
🚀 Mantenimiento del Sistema
Iniciar servidor en segundo plano
Utilice nohup para asegurar que el sistema siga vivo tras cerrar la sesión SSH:
nohup venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > output.log 2>&1 &

Respaldos de Seguridad
Se recomienda copiar el archivo de base de datos semanalmente a una ubicación externa:
cp club.db ./respaldos/club_backup_$(date +%F).db

🚀 Automatización con Systemd (Servicio Profesional)
Para que el servidor inicie automáticamente con la Orange Pi y se recupere de fallos, se utiliza un servicio de sistema.

1. Crear el archivo del servicio

sudo nano /etc/systemd/system/fotoclub.service

2. Configuración del archivo
Pegue el siguiente contenido (ajustando las rutas si es necesario):
[Unit]
Description=Servicio de Control de Acceso Fotoclub
After=network.target

[Service]
User=orangepi
Group=orangepi
WorkingDirectory=/home/orangepi/fotoclub
ExecStart=/home/orangepi/fotoclub/venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=append:/home/orangepi/fotoclub/output.log
StandardError=append:/home/orangepi/fotoclub/output.log

[Install]
WantedBy=multi-user.target

3. Comandos de Gestión del Servicio
Acción,Comando
Iniciar,sudo systemctl start fotoclub
Detener,sudo systemctl stop fotoclub
Reiniciar,sudo systemctl restart fotoclub
Ver Estado,sudo systemctl status fotoclub
Habilitar Arranque,sudo systemctl enable fotoclub


