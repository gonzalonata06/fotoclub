from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

class TipoPersona(Base):
    __tablename__ = "tipos_persona"
    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False)
    activo = Column(Boolean, default=True)

    # Relaciones
    usuarios = relationship("Usuario", back_populates="tipo_persona_rel")

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=False)
    telefono = Column(String, unique=True, index=True, nullable=False)
    correo = Column(String, nullable=True)
    pin_hash = Column(String, nullable=False)
    tipo_persona_id = Column(Integer, ForeignKey("tipos_persona.id"))
    
    tipo_tramite = Column(String) # 'Inscripcion' o 'Reinscripcion'
    fecha_vencimiento = Column(DateTime, nullable=True)
    intentos_fallidos = Column(Integer, default=0)
    bloqueado_hasta = Column(DateTime, nullable=True)
    requiere_cambio_pin = Column(Boolean, default=True)
    activo = Column(Boolean, default=True)
    es_admin = Column(Boolean, default=False)
    creado_en = Column(DateTime, server_default=func.now())

    # Relaciones
    tipo_persona_rel = relationship("TipoPersona", back_populates="usuarios")
    inscripciones = relationship("Inscripcion", back_populates="usuario")
    accesos = relationship("Acceso", back_populates="usuario")

class CostoInscripcion(Base):
    __tablename__ = "costos_inscripcion"
    id = Column(Integer, primary_key=True)
    tipo_persona_id = Column(Integer, ForeignKey("tipos_persona.id"))
    monto = Column(Float, nullable=False)
    activo = Column(Boolean, default=True)

# --- ESTA ES LA CLASE QUE FALTABA ---
class CostoReinscripcion(Base):
    __tablename__ = "costos_reinscripcion"
    id = Column(Integer, primary_key=True)
    tipo_persona_id = Column(Integer, ForeignKey("tipos_persona.id"))
    monto = Column(Float, nullable=False)
    activo = Column(Boolean, default=True)

class Inscripcion(Base):
    __tablename__ = "inscripciones"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    costo_aplicado = Column(Float, nullable=False)
    fecha_inscripcion = Column(DateTime, server_default=func.now())
    usuario = relationship("Usuario", back_populates="inscripciones")

class Acceso(Base):
    __tablename__ = "accesos"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    tipo_evento = Column(String, nullable=False) # 'entrada' o 'salida'
    actividad = Column(String, nullable=False)
    timestamp = Column(DateTime, server_default=func.now(), index=True)
    usuario = relationship("Usuario", back_populates="accesos")
