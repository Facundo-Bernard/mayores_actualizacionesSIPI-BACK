package com.example.uade.tpo.practica2back.features.auth;

import java.time.LocalDateTime;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import com.example.uade.tpo.practica2back.features.usuario.Usuario;
import com.example.uade.tpo.practica2back.features.usuario.UsuarioRepository;

/**
 * Inicializador que garantiza la existencia de un usuario operador/administrador
 * para que el personal de sistemas pueda acceder inmediatamente a la Torre de Control.
 */
@Component
public class AdminUserInitializer implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(AdminUserInitializer.class);

    private final UsuarioRepository usuarioRepository;
    private final PasswordEncoder passwordEncoder;

    @Value("${app.sistemas.default-email:admin@sistemas.com}")
    private String adminEmail;

    @Value("${app.sistemas.default-password:admin123}")
    private String adminPassword;

    @Value("${app.sistemas.default-name:Operador Sistemas}")
    private String adminName;

    public AdminUserInitializer(UsuarioRepository usuarioRepository, PasswordEncoder passwordEncoder) {
        this.usuarioRepository = usuarioRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    public void run(String... args) {
        // Verificar si ya existe el admin por email o algún admin en el sistema
        if (usuarioRepository.findByEmail(adminEmail).isEmpty()) {
            Usuario admin = Usuario.builder()
                    .name(adminName)
                    .email(adminEmail)
                    .password(passwordEncoder.encode(adminPassword))
                    .tipoUsuario(Usuario.ROL_ADMIN)
                    .black(true)
                    .activo(true)
                    .dateStart(LocalDateTime.now())
                    .codigoAcceso("999999")
                    .build();

            usuarioRepository.save(admin);
            log.info("=================================================================");
            log.info("[SISTEMAS] Usuario administrador inicial creado:");
            log.info("Email:    {}", adminEmail);
            log.info("Password: {}", adminPassword);
            log.info("Rol:      ROL_ADMIN (2)");
            log.info("=================================================================");
        } else {
            log.info("[SISTEMAS] Usuario administrador ya existente ({})", adminEmail);
        }
    }
}
