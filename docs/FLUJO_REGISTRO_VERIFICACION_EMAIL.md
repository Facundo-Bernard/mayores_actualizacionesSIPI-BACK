# Especificación del Flujo de Registro con Verificación de Email y Despacho SMTP

> **Propósito del Documento:**  
> Este documento preserva el diseño técnico, esquemas Pydantic, lógica de servicio y plantillas HTML accesibles para adultos mayores del **flujo de registro en dos pasos con verificación de correo**, para su futura incorporación directa en el **Microservicio Central de Autenticación (`Autenticador`)**.

---

## 1. Arquitectura del Flujo

```
[ Alumno en Frontend ]
       │
       │ 1. Ingresa Nombre y Email
       ├──────────────────────────────────────────────► [ Autenticador Central ]
       │                                                       │
       │                                                       │ Genera PIN único (6 dígitos)
       │                                                       │ Estado: PENDIENTE_VERIFICACION (id: 1)
       │                                                       │ Despacha email SMTP con el PIN
       │                                                       ▼
       │ 2. Recibe PIN en su correo                [ Servidor SMTP / Brevo ]
       │                                                       │
       │ 3. Ingresa PIN de 6 dígitos en pantalla              ▼
       ├──────────────────────────────────────────────► [ Autenticador Central ]
       │                                                       │
       │                                                       │ Valida PIN
       │                                                       │ Estado pasa a ACTIVO (id: 2)
       │                                                       │ Emite Token JWT de sesión
       │                                                       ▼
       │ 4. Sesión iniciada y cuenta activada ◄────────────────┘
```

---

## 2. Esquemas Pydantic (`schemas.py`)

```python
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: Optional[str] = None
    codigoAcceso: Optional[str] = None
    tipoUsuario: Optional[int] = 1
    black: Optional[bool] = False
    activo: Optional[bool] = True
    servicios: Optional[Dict[str, bool]] = None
    servicioOrigen: Optional[str] = None

class VerificarCodigoRegistroRequest(BaseModel):
    email: EmailStr
    codigo: str = Field(..., min_length=6, max_length=6)

class ReenviarCodigoRequest(BaseModel):
    email: EmailStr

class ModificarEmailRegistroRequest(BaseModel):
    email_actual: EmailStr
    email_nuevo: EmailStr

class EnviarAccesoCorreoRequest(BaseModel):
    email: EmailStr
    redirectPath: Optional[str] = "mis-cursos"
```

---

## 3. Lógica de Servicio (`service.py`)

```python
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, status
from app.core.database import get_database
from app.core.security import create_access_token

logger = logging.getLogger(__name__)

async def verificar_codigo_registro(req: VerificarCodigoRegistroRequest):
    """
    Confirma el código numérico PIN de 6 dígitos recibido por correo y activa la cuenta.
    """
    db = get_database()
    email_clean = req.email.lower().strip()
    code_clean = req.codigo.strip()

    user = await db["usuarios"].find_one({"email": email_clean})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontramos ninguna cuenta con ese correo electrónico."
        )

    if user.get("estado_id") == 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta se encuentra inactiva. Contacta al administrador."
        )

    if user.get("codigo_acceso") != code_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El código ingresado no coincide con el enviado a tu correo. Revisalo e intentalo nuevamente."
        )

    now = datetime.now(timezone.utc)
    await db["usuarios"].update_one(
        {"id": user["id"]},
        {"$set": {
            "estado_id": 2,
            "estado_codigo": "ACTIVO",
            "activo": True,
            "fecha_activacion": now
        }}
    )

    user["estado_id"] = 2
    user["estado_codigo"] = "ACTIVO"
    user["activo"] = True

    token = create_access_token(user)
    return {
        "success": True,
        "message": "¡Cuenta activada con éxito!",
        "token": token,
        "user": user
    }


async def reenviar_codigo_registro(req: ReenviarCodigoRequest):
    """
    Vuelve a despachar el código PIN al correo del usuario si aún está pendiente de activación.
    """
    db = get_database()
    email_clean = req.email.lower().strip()

    user = await db["usuarios"].find_one({"email": email_clean})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontramos ninguna cuenta con ese correo electrónico."
        )

    if user.get("estado_id") == 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tu cuenta ya está activada. Podés ingresar directamente con tu código."
        )

    codigo = user.get("codigo_acceso")
    await enviar_codigo_activacion(email_clean, user.get("name", "Estimado alumno"), codigo)

    return {
        "success": True,
        "message": f"Código reenviado con éxito a {email_clean}."
    }


async def modificar_email_registro(req: ModificarEmailRegistroRequest):
    """
    Permite al usuario corregir su correo electrónico si escribió mal la dirección durante el registro.
    """
    db = get_database()
    actual_clean = req.email_actual.lower().strip()
    nuevo_clean = req.email_nuevo.lower().strip()

    if actual_clean == nuevo_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nuevo correo electrónico debe ser diferente al anterior."
        )

    user = await db["usuarios"].find_one({"email": actual_clean})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontramos el registro anterior."
        )

    if user.get("estado_id") == 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede modificar el correo porque la cuenta ya fue activada."
        )

    existente_nuevo = await db["usuarios"].find_one({"email": nuevo_clean})
    if existente_nuevo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe otra cuenta registrada con ese nuevo correo electrónico."
        )

    await db["usuarios"].update_one(
        {"id": user["id"]},
        {"$set": {"email": nuevo_clean}}
    )

    codigo = user.get("codigo_acceso")
    await enviar_codigo_activacion(nuevo_clean, user.get("name", "Estimado alumno"), codigo)

    return {
        "success": True,
        "message": f"Correo actualizado. Enviamos tu código de acceso a {nuevo_clean}."
    }
```

---

## 4. Servicio de Envío de Correo SMTP (`email_service.py`)

```python
import aiosmtplib
from email.message import EmailMessage
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def enviar_codigo_activacion(to_email: str, user_name: str, codigo_acceso: str) -> bool:
    """
    Envía por correo el código PIN de 6 dígitos para la activación de la cuenta.
    Si la clave SMTP no está configurada, simula el envío e imprime el código en consola.
    """
    subject = f"Tu código de acceso: {codigo_acceso} - Mayores Actualizaciones"
    html_content = construir_plantilla_codigo_activacion(user_name, codigo_acceso)

    if not getattr(settings, "SMTP_PASSWORD", None) or settings.SMTP_PASSWORD in ("tu_clave_smtp_aqui", ""):
        logger.warning("=================================================================")
        logger.warning("ENVÍO SIMULADO DE CÓDIGO (Sin clave SMTP configurada):")
        logger.warning(f"Destinatario: {to_email} ({user_name})")
        logger.warning(f"CÓDIGO DE ACCESO / ACTIVACIÓN: {codigo_acceso}")
        logger.warning("=================================================================")
        return True

    try:
        message = EmailMessage()
        message["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(html_content, subtype="html")

        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True
        )
        logger.info(f"Código de activación enviado con éxito a {to_email}")
        return True
    except Exception as e:
        logger.error(f"No se pudo enviar el correo de activación a {to_email}: {e}. Código: {codigo_acceso}")
        return False

def construir_plantilla_codigo_activacion(user_name: str, codigo_acceso: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b; }}
        .card {{ max-width: 580px; margin: 0 auto; background-color: #ffffff; border-radius: 18px; padding: 36px; border: 2px solid #cbd5e1; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }}
        h1 {{ color: #294c6b; font-size: 26px; margin-bottom: 16px; font-weight: 900; }}
        p {{ color: #334155; font-size: 18px; line-height: 1.55; margin-bottom: 20px; }}
        .codigo-box {{ background-color: #f1f5f9; border: 2px dashed #53bfc9; border-radius: 14px; padding: 24px; text-align: center; margin: 28px 0; }}
        .codigo-label {{ font-size: 15px; color: #64748b; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }}
        .codigo-numero {{ font-size: 42px; font-weight: 900; letter-spacing: 10px; color: #294c6b; font-family: Consolas, monospace; }}
        .nota-importante {{ background-color: #eff6ff; border-left: 4px solid #2563eb; padding: 14px 18px; border-radius: 8px; font-size: 16px; color: #1e40af; margin-top: 24px; line-height: 1.5; }}
        .nota-spam {{ background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 14px 18px; border-radius: 8px; font-size: 15px; color: #92400e; margin-top: 16px; line-height: 1.5; }}
        .footer {{ font-size: 14px; color: #64748b; text-align: center; margin-top: 32px; border-top: 1px solid #e2e8f0; padding-top: 18px; }}
      </style>
    </head>
    <body>
      <div class="card">
        <h1>¡Hola, {user_name}! 👋</h1>
        <p>Te damos la bienvenida a <strong>Mayores Actualizaciones</strong>. Para activar tu cuenta y comenzar a jugar, ingresá este código en tu pantalla:</p>
        
        <div class="codigo-box">
          <div class="codigo-label">Tu código de confirmación y acceso</div>
          <div class="codigo-numero">{codigo_acceso}</div>
        </div>

        <div class="nota-importante">
          <strong>📝 Importante:</strong> Guardá este código en un lugar seguro (por ejemplo, en un cuaderno). Con este mismo número de 6 dígitos vas a poder ingresar siempre desde cualquier celular o computadora.
        </div>

        <div class="nota-spam">
          <strong>💡 Consejo:</strong> Si en el futuro no encontrás nuestros correos en tu bandeja de entrada, revisá también tu carpeta de <strong>Correo no deseado o Spam</strong>.
        </div>

        <div class="footer">
          Equipo de Mayores Actualizaciones · Estimulación cognitiva y aprendizaje continuo
        </div>
      </div>
    </body>
    </html>
    """

async def enviar_magic_link(to_email: str, user_name: str, access_url: str, codigo_acceso: str = None) -> bool:
    """
    Despacha el correo con botón de acceso directo (Magic Link) para login con 1 solo clic.
    """
    subject = "Tu acceso directo a Mayores Actualizaciones"
    html_content = construir_plantilla_magic_link(user_name, access_url, codigo_acceso)

    if not getattr(settings, "SMTP_PASSWORD", None) or settings.SMTP_PASSWORD in ("tu_clave_smtp_aqui", ""):
        logger.warning("=================================================================")
        logger.warning(f"ENVÍO SIMULADO (Sin clave SMTP):")
        logger.warning(f"Destinatario: {to_email} ({user_name})")
        logger.warning(f"Magic Link: {access_url}")
        logger.warning("=================================================================")
        return True

    try:
        message = EmailMessage()
        message["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(html_content, subtype="html")

        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True
        )
        return True
    except Exception as e:
        logger.error(f"Error al enviar magic link a {to_email}: {e}")
        return False

def construir_plantilla_magic_link(user_name: str, access_url: str, codigo_acceso: str = None) -> str:
    bloque_codigo = ""
    if codigo_acceso:
        bloque_codigo = f"""
        <div style="background-color: #f1f5f9; border: 2px dashed #94a3b8; border-radius: 12px; padding: 20px; text-align: center; margin: 25px 0;">
          <p style="margin: 0 0 8px 0; font-size: 18px; color: #475569;">O si lo preferís, ingresá en la web con este <strong>código numérico</strong>:</p>
          <div style="font-size: 34px; font-weight: 800; letter-spacing: 6px; color: #1e3a8a; font-family: monospace;">{codigo_acceso}</div>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b; }}
        .card {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; padding: 40px; border: 2px solid #cbd5e1; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
        h1 {{ color: #0f172a; font-size: 28px; margin-bottom: 20px; font-weight: 800; }}
        p {{ color: #334155; font-size: 19px; line-height: 1.6; margin-bottom: 24px; }}
        .btn-container {{ text-align: center; margin: 35px 0; }}
        .btn {{ background-color: #2563eb; color: #ffffff !important; padding: 20px 40px; font-size: 24px; font-weight: 800; text-decoration: none; border-radius: 12px; display: inline-block; border: 2px solid #1d4ed8; }}
        .nota {{ background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 15px; border-radius: 6px; font-size: 17px; color: #1e40af; margin-top: 20px; }}
        .footer {{ font-size: 15px; color: #64748b; text-align: center; margin-top: 35px; border-top: 1px solid #e2e8f0; padding-top: 20px; }}
      </style>
    </head>
    <body>
      <div class="card">
        <h1>¡Hola, {user_name}!</h1>
        <p>Te damos la bienvenida a <strong>Mayores Actualizaciones</strong>. Tu plataforma de cursos ya está lista para vos.</p>
        <p>Para ingresar directamente a tus cursos desde esta computadora, solo hacé un clic en el siguiente botón grande:</p>
        <div class="btn-container">
          <a href="{access_url}" class="btn" target="_blank">👉 INGRESAR A MIS CURSOS</a>
        </div>
        {bloque_codigo}
        <div class="nota">
          <strong>ℹ️ Nota importante:</strong> No necesitás recordar ninguna contraseña compleja. Tu computadora recordará tu acceso para siempre.
        </div>
        <div class="footer">
          Si tenés alguna duda o necesitás asistencia, comunicate con nuestro equipo de atención telefónica o respondiendo a este correo.
        </div>
      </div>
    </body>
    </html>
    """
```

---

## 5. Pasos para Implementarlo en el Autenticador Central

Cuando se decida incorporar el envío de emails en el `Autenticador` (`backend/Autenticador`):

1. **Instalar dependencias:**  
   Agregar `aiosmtplib` en `requirements.txt` del backend de Autenticador.
2. **Configurar variables SMTP en `.env` del Autenticador:**  
   `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `MAIL_FROM_NAME`.
3. **Mudar el archivo `email_service.py`:**  
   Colocarlo en `backend/Autenticador/backend/app/core/email_service.py`.
4. **Registrar los endpoints en el router de Autenticador:**  
   Montar `/auth/verificar-codigo-registro`, `/auth/reenviar-codigo-registro` y `/auth/modificar-email-registro`.
5. **Ajustar el estado inicial en MongoDB:**  
   Crear al usuario inicialmente con `estado_id: 1` (`PENDIENTE_VERIFICACION`), despachar el correo y recién pasar a `estado_id: 2` (`ACTIVO`) cuando envíe el código en `/auth/verificar-codigo-registro`.
