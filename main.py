from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os

from database import engine, SessionLocal
import models
from auth import hash_pin, verify_pin, create_access_token, SECRET_KEY, ALGORITHM
import pytz # <-- Agregar esta importación

# Definimos tu zona horaria local
ZONA_HORARIA = pytz.timezone('America/Mexico_City') 

def get_now():
    # Esta función obtiene la hora actual de tu ciudad
    return datetime.now(ZONA_HORARIA)

app = FastAPI()

models.Base.metadata.create_all(bind=engine)

PIN_TEMPORAL = "0000"
DIAS_VIGENCIA = 135 

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Sesión inválida")
    usuario = db.query(models.Usuario).filter_by(id=user_id).first()
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=401, detail="Usuario inactivo")
    return usuario

# --- ENDPOINT DE LOGIN CORREGIDO ---
@app.post("/login")
def login(telefono: str, pin: str, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter_by(telefono=telefono).first()
    if not usuario: raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not usuario.activo: raise HTTPException(status_code=403, detail="Cuenta desactivada")

    ahora = get_now() 

    # Validación de Membresía (Correcto)
    if not usuario.es_admin and usuario.fecha_vencimiento:
        if ahora.replace(tzinfo=None) > usuario.fecha_vencimiento:
            usuario.activo = False
            db.commit()
            raise HTTPException(status_code=403, detail="Membresía vencida")

    if not verify_pin(pin, usuario.pin_hash):
        raise HTTPException(status_code=401, detail="PIN incorrecto")

    # Validación de Sesión Activa (Corregido)
    ultimo = db.query(models.Acceso).filter_by(usuario_id=usuario.id).order_by(models.Acceso.timestamp.desc()).first()
    esta_dentro = False
    if ultimo and ultimo.tipo_evento == "entrada":
        # Usamos ahora sin zona horaria para comparar con la base de datos
        if ahora.replace(tzinfo=None) < (ultimo.timestamp + timedelta(hours=2)):
            esta_dentro = True

    access_token = create_access_token({"sub": str(usuario.id), "es_admin": usuario.es_admin})
    return {
        "access_token": access_token,
        "cambiar_pin": True if pin == PIN_TEMPORAL else usuario.requiere_cambio_pin,
        "es_admin": usuario.es_admin,
        "nombre": usuario.nombre,
        "esta_dentro": esta_dentro
    }

# --- MODIFICACIÓN EN EL ENDPOINT DE ACCESO ---
@app.post("/acceso")
def registrar_acceso(actividad: str, current_user: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    ahora = get_now() # <--- Cambio para usar CDMX

    # SQLite guardará la hora tal cual (sin el objeto de zona horaria)
    db.add(models.Acceso(usuario_id=current_user.id, tipo_evento="entrada", actividad=actividad, timestamp=ahora))
    db.add(models.Acceso(usuario_id=current_user.id, tipo_evento="salida", actividad=actividad, timestamp=ahora + timedelta(hours=2)))
    db.commit()

    return {
        "mensaje": "Acceso registrado",
        "hora_confirmada": ahora.strftime("%H:%M:%S"),
        "fecha_confirmada": ahora.strftime("%d/%m/%Y")
    }

@app.post("/cambiar-pin")
def cambiar_pin(pin_actual: str, pin_nuevo: str, current_user: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_pin(pin_actual, current_user.pin_hash):
        raise HTTPException(status_code=401, detail="PIN actual incorrecto")
    current_user.pin_hash = hash_pin(pin_nuevo)
    current_user.requiere_cambio_pin = False
    db.commit()
    return {"mensaje": "PIN actualizado"}

@app.post("/admin/crear-usuario")
def crear_usuario(nombre: str, apellido: str, telefono: str, correo: str, tipo_persona_id: int, current_user: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.es_admin: raise HTTPException(status_code=403, detail="No autorizado")
    vencimiento = get_now().replace(tzinfo=None) + timedelta(days=DIAS_VIGENCIA)
    costo_ref = db.query(models.CostoInscripcion).filter_by(tipo_persona_id=int(tipo_persona_id), activo=True).first()
    nuevo = models.Usuario(nombre=nombre, apellido=apellido, telefono=telefono, correo=correo, 
                           pin_hash=hash_pin(PIN_TEMPORAL), tipo_persona_id=tipo_persona_id,
                           tipo_tramite="Inscripcion", fecha_vencimiento=vencimiento)
    db.add(nuevo); db.flush()
    db.add(models.Inscripcion(usuario_id=nuevo.id, costo_aplicado=costo_ref.monto if costo_ref else 0))
    db.commit()
    return {"mensaje": "Socio registrado"}

@app.post("/admin/migrar-socio")
def migrar_socio(nombre: str, apellido: str, telefono: str, correo: str, tipo_persona_id: int, current_user: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.es_admin: raise HTTPException(status_code=403, detail="No autorizado")
    vencimiento = get_now().replace(tzinfo=None) + timedelta(days=DIAS_VIGENCIA)
    # Buscamos el costo en la tabla de Reinscripción
    costo_ref = db.query(models.CostoReinscripcion).filter_by(tipo_persona_id=int(tipo_persona_id), activo=True).first()

    nuevo = models.Usuario(
        nombre=nombre,
        apellido=apellido,
        telefono=telefono,
        correo=correo,
        pin_hash=hash_pin(PIN_TEMPORAL),
        tipo_persona_id=tipo_persona_id,
        tipo_tramite="Reinscripcion", # <-- Cambiado de 'Migracion' a 'Reinscripcion'
        fecha_vencimiento=vencimiento
    )
    db.add(nuevo); db.flush()
    db.add(models.Inscripcion(usuario_id=nuevo.id, costo_aplicado=costo_ref.monto if costo_ref else 0))
    db.commit()
    return {"mensaje": "Socio registrado como Reinscripción"}

@app.post("/admin/reinscribir-socio")
def reinscribir_socio(telefono: str, tipo_persona_id: int, current_user: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.es_admin: raise HTTPException(status_code=403, detail="No autorizado")
    u = db.query(models.Usuario).filter_by(telefono=telefono).first()
    if not u: raise HTTPException(status_code=404, detail="No encontrado")
    u.fecha_vencimiento = get_now().replace(tzinfo=None) + timedelta(days=DIAS_VIGENCIA) 
    u.activo = True
    u.tipo_persona_id = tipo_persona_id
    u.tipo_tramite = "Reinscripcion"
    
    # AQUÍ ESTABA EL ERROR: Consultamos la tabla CostoReinscripcion que sí existe en tu models.py
    costo_ref = db.query(models.CostoReinscripcion).filter_by(tipo_persona_id=int(tipo_persona_id), activo=True).first()
    
    # Usamos .monto de la tabla de reinscripciones
    db.add(models.Inscripcion(usuario_id=u.id, costo_aplicado=costo_ref.monto if costo_ref else 0))
    db.commit()
    return {"mensaje": "Socio renovado"}

@app.post("/admin/reset-pin")
def reset_pin(telefono_usuario: str, current_user: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.es_admin: raise HTTPException(status_code=403, detail="No autorizado")
    u = db.query(models.Usuario).filter_by(telefono=telefono_usuario).first()
    if not u: raise HTTPException(status_code=404, detail="No encontrado")
    u.pin_hash, u.requiere_cambio_pin = hash_pin(PIN_TEMPORAL), True
    db.commit()
    return {"mensaje": "Reset exitoso"}

# --- CONFIGURACIÓN DE SEGURIDAD EXTRA ---
SUPER_ADMINS = ["5520217178"] # <-- Pon aquí los números autorizados

@app.get("/admin/asistencias-rango")
def asistencias_rango(inicio: str, fin: str, current_user: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.es_admin: raise HTTPException(status_code=403)

    # Buscamos en el rango de fechas
    # Al usar get_now() anteriormente, el timestamp ya está en tu hora local
    logs = db.query(models.Acceso).filter(
        models.func.strftime('%Y-%m-%d', models.Acceso.timestamp) >= inicio,
        models.func.strftime('%Y-%m-%d', models.Acceso.timestamp) <= fin
    ).order_by(models.Acceso.timestamp.asc()).all()

    total_visitas = len([l for l in logs if l.tipo_evento == "entrada"])

    return {
        "datos": [
            {
                "fecha": l.timestamp.strftime("%d/%m/%Y"),
                "hora": l.timestamp.strftime("%H:%M:%S"), # <-- Mostramos hora local formateada
                "socio": f"{l.usuario.nombre} {l.usuario.apellido}",
                "actividad": l.actividad,
                "evento": l.tipo_evento.capitalize()
            } for l in logs
        ],
        "resumen": {"total": total_visitas, "periodo": f"{inicio} al {fin}"}
    }

@app.get("/admin/lista-detallada-socios")
def lista_detallada_socios(current_user: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.es_admin: raise HTTPException(status_code=403)
    usuarios = db.query(models.Usuario).filter(models.Usuario.es_admin == False).order_by(models.Usuario.apellido.asc()).all()
    ahora = get_now().replace(tzinfo=None)
    return [
        {
            "nombre": u.nombre,
            "apellido": u.apellido,
            "tramite": u.tipo_tramite,
            "estado": "✅ Activo" if (u.activo and u.fecha_vencimiento and u.fecha_vencimiento > ahora) else "❌ Inactivo"
        } for u in usuarios
    ]

@app.post("/admin/cierre-semestre")
def cierre_semestre(current_user: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    # VALIDACIÓN DOBLE: Debe ser admin Y estar en la lista blanca
    if not current_user.es_admin or current_user.telefono not in SUPER_ADMINS:
        raise HTTPException(status_code=403, detail="No tienes permisos de Super Administrador para esta acción.")
    
    db.query(models.Usuario).filter(models.Usuario.es_admin == False).update({"activo": False})
    db.commit()
    return {"mensaje": "Cierre de semestre completado"}

app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/")
def root(): return FileResponse(os.path.join("static", "index.html"))
