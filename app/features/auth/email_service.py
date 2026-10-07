import aiosmtplib
from email.message import EmailMessage
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def enviar_magic_link(to_email: str, user_name: str, access_url: str, codigo_acceso: str = None) -> bool:
    """
    Despacha el correo de acceso por SMTP (Brevo o similar) con la plantilla HTML para adultos mayores.
    Si la clave SMTP no está configurada, simula el envío e imprime el enlace en la consola.
    """
    subject = "Tu acceso directo a Mayores Actualizaciones"
    html_content = construir_plantilla_html(user_name, access_url, codigo_acceso)

    if not settings.SMTP_PASSWORD:
        logger.warning("=================================================================")
        logger.warning(f"ENVÍO SIMULADO (Sin clave SMTP configurada):")
        logger.warning(f"Destinatario: {to_email} ({user_name})")
        logger.warning(f"Código numérico: {codigo_acceso}")
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
        logger.info(f"Correo de acceso enviado con éxito a {to_email}")
        return True
    except Exception as e:
        logger.error(f"No se pudo enviar el correo a {to_email}: {e}. Enlace: {access_url}, Código: {codigo_acceso}")
        logger.info(f"ENLACE DE ACCESO (Fallback): {access_url}")
        return False

def construir_plantilla_html(user_name: str, access_url: str, codigo_acceso: str = None) -> str:
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
