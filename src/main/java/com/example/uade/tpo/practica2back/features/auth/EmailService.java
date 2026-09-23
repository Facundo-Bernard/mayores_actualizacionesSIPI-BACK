package com.example.uade.tpo.practica2back.features.auth;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.stereotype.Service;

import jakarta.mail.internet.MimeMessage;

@Service
public class EmailService {

    private static final Logger log = LoggerFactory.getLogger(EmailService.class);

    @Autowired(required = false)
    private JavaMailSender mailSender;

    @org.springframework.beans.factory.annotation.Value("${app.mail.from:no-reply@mayoresactualizaciones.com}")
    private String mailFrom;

    public boolean enviarMagicLink(String toEmail, String userName, String accessUrl) {
        return enviarMagicLink(toEmail, userName, accessUrl, null);
    }

    public boolean enviarMagicLink(String toEmail, String userName, String accessUrl, String codigoAcceso) {
        String subject = "¡Bienvenido/a " + userName + "! Acceso directo a tus cursos";
        String htmlContent = construirPlantillaHtml(userName, accessUrl, codigoAcceso);

        if (mailSender == null) {
            log.warn("=================================================================");
            log.warn("[EMAIL MOCK - JavaMailSender no configurado]");
            log.warn("Destinatario: {}", toEmail);
            log.warn("Asunto: {}", subject);
            log.warn("Magic Link de Acceso: {}", accessUrl);
            if (codigoAcceso != null) {
                log.warn("Código de Acceso: {}", codigoAcceso);
            }
            log.warn("=================================================================");
            return true;
        }

        try {
            MimeMessage message = mailSender.createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(message, true, "UTF-8");

            helper.setTo(toEmail);
            helper.setSubject(subject);
            helper.setText(htmlContent, true);
            helper.setFrom(mailFrom, "Mayores Actualizaciones");

            mailSender.send(message);
            log.info("Correo de acceso enviado con éxito a {}", toEmail);
            return true;
        } catch (Exception e) {
            log.error("No se pudo enviar el correo a {}: {}. Enlace: {}, Código: {}", toEmail, e.getMessage(), accessUrl, codigoAcceso);
            log.info("ENLACE DE ACCESO (Fallback): {}", accessUrl);
            return false;
        }
    }

    private String construirPlantillaHtml(String userName, String accessUrl, String codigoAcceso) {
        String bloqueCodigo = (codigoAcceso != null && !codigoAcceso.isBlank())
            ? """
              <div style="background-color: #f1f5f9; border: 2px dashed #94a3b8; border-radius: 12px; padding: 20px; text-align: center; margin: 25px 0;">
                <p style="margin: 0 0 8px 0; font-size: 18px; color: #475569;">O si lo preferís, ingresá en la web con este <strong>código numérico</strong>:</p>
                <div style="font-size: 34px; font-weight: 800; letter-spacing: 6px; color: #1e3a8a; font-family: monospace;">%s</div>
              </div>
              """.formatted(codigoAcceso)
            : "";

        return """
            <!DOCTYPE html>
            <html lang="es">
            <head>
              <meta charset="utf-8">
              <style>
                body { font-family: 'Segoe UI', Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b; }
                .card { max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; padding: 40px; border: 2px solid #cbd5e1; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
                h1 { color: #0f172a; font-size: 28px; margin-bottom: 20px; font-weight: 800; }
                p { color: #334155; font-size: 19px; line-height: 1.6; margin-bottom: 24px; }
                .btn-container { text-align: center; margin: 35px 0; }
                .btn { background-color: #2563eb; color: #ffffff !important; padding: 20px 40px; font-size: 24px; font-weight: 800; text-decoration: none; border-radius: 12px; display: inline-block; border: 2px solid #1d4ed8; }
                .nota { background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 15px; border-radius: 6px; font-size: 17px; color: #1e40af; margin-top: 20px; }
                .footer { font-size: 15px; color: #64748b; text-align: center; margin-top: 35px; border-top: 1px solid #e2e8f0; padding-top: 20px; }
              </style>
            </head>
            <body>
              <div class="card">
                <h1>¡Hola, %s!</h1>
                <p>Te damos la bienvenida a <strong>Mayores Actualizaciones</strong>. Tu plataforma de cursos ya está lista para vos.</p>
                <p>Para ingresar directamente a tus cursos desde esta computadora, solo hacé un clic en el siguiente botón grande:</p>
                <div class="btn-container">
                  <a href="%s" class="btn" target="_blank">👉 INGRESAR A MIS CURSOS</a>
                </div>
                %s
                <div class="nota">
                  <strong>ℹ️ Nota importante:</strong> No necesitás recordar ninguna contraseña compleja. Tu computadora recordará tu acceso para siempre.
                </div>
                <div class="footer">
                  Si tenés alguna duda o necesitás asistencia, comunicate con nuestro equipo de atención telefónica o respondiendo a este correo.
                </div>
              </div>
            </body>
            </html>
            """.formatted(userName, accessUrl, bloqueCodigo);
    }
}
