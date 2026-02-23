from database import SessionLocal
import models
from auth import hash_pin

db = SessionLocal()

# Borramos por si acaso quedó algún rastro fallido
#db.query(models.Usuario).filter_by(telefono="5520217187").delete()

admin_maestro = models.Usuario(
    nombre="Mariel",
    apellido="N",
    telefono="5561963597",
    correo="mariel@example.com",
    pin_hash=hash_pin("0000"),
    es_admin=True,
    requiere_cambio_pin=True,
    tipo_persona_id=None, # El admin no necesita obligatoriamente procedencia
    activo=True
)

db.add(admin_maestro)
db.commit()
print("✅ Administrador creado correctamente")
