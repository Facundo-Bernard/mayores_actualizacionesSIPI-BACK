package com.example.uade.tpo.practica2back.features.auth;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.uade.tpo.practica2back.features.usuario.Usuario;
import com.example.uade.tpo.practica2back.features.usuario.UsuarioService;

import org.springframework.security.crypto.password.PasswordEncoder;

import io.jsonwebtoken.Claims;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

@RestController
@RequestMapping
@CrossOrigin(origins = "*")
public class AuthController {

    private final JwtService jwtService;
    private final UsuarioService usuarioService;
    private final EmailService emailService;
    private final PasswordEncoder passwordEncoder;
    private final String frontendUrl;

    public AuthController(
            JwtService jwtService,
            UsuarioService usuarioService,
            EmailService emailService,
            PasswordEncoder passwordEncoder,
            @Value("${app.frontend.url:http://localhost:5173}") String frontendUrl) {
        this.jwtService = jwtService;
        this.usuarioService = usuarioService;
        this.emailService = emailService;
        this.passwordEncoder = passwordEncoder;
        this.frontendUrl = frontendUrl;
    }

    // ==========================================
    // SCHEMAS (DTOs)
    // ==========================================

    public static record RegistroRequest(
        @NotBlank(message = "El nombre es obligatorio") String name,
        @Email(message = "Email inválido") @NotBlank(message = "El email es obligatorio") String email,
        String password,
        String telefono,
        String codigoAcceso,
        Boolean black
    ) {}

    public static record RegistroResponse(
        boolean success,
        String message,
        String token,
        Usuario.Response user
    ) {}

    public static record IngresarCodigoRequest(
        @NotBlank(message = "El código es obligatorio") String codigo
    ) {}

    public static record TokenVerifyRequest(
        @NotBlank(message = "El token es obligatorio") String token
    ) {}

    public static record TokenVerifyResponse(
        boolean success,
        boolean valid,
        Usuario.Response user,
        String message
    ) {}

    public static record EnviarAccesoRequest(
        @NotBlank(message = "El nombre es obligatorio") String name,
        @Email(message = "Email inválido") @NotBlank(message = "El email es obligatorio") String email,
        String telefono,
        String codigoAcceso,
        Boolean black
    ) {}

    public static record AccesoData(
        Long userId,
        String email,
        String codigoAcceso,
        String accessUrl
    ) {}

    public static record EnviarAccesoResponse(
        boolean success,
        String message,
        AccesoData data
    ) {}

    public static record LoginSistemasRequest(
        @Email(message = "Email inválido") @NotBlank(message = "El email es obligatorio") String email,
        @NotBlank(message = "La contraseña es obligatoria") String password
    ) {}

    public static record LoginSistemasResponse(
        boolean success,
        String message,
        String token,
        Usuario.Response user
    ) {}

    // ==========================================
    // ENDPOINTS
    // ==========================================

    /**
     * Endpoint para que el personal de sistemas / operadores inicie sesión con usuario y contraseña.
     * Valida credenciales, comprueba que posea rol de administrador (ROL_ADMIN = 2) y genera un JWT de acceso.
     */
    @PostMapping({"/api/auth/login-sistemas", "/api/auth/login-admin"})
    public ResponseEntity<LoginSistemasResponse> loginSistemas(@Valid @RequestBody LoginSistemasRequest req) {
        try {
            Usuario usuario = usuarioService.findByEmail(req.email().trim().toLowerCase()).orElse(null);
            if (usuario == null) {
                return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                        .body(new LoginSistemasResponse(false, "Credenciales inválidas. Usuario no encontrado.", null, null));
            }

            if (usuario.getPassword() == null || usuario.getPassword().isBlank()) {
                return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                        .body(new LoginSistemasResponse(false, "El usuario no cuenta con contraseña configurada para acceso de sistemas.", null, null));
            }

            if (!passwordEncoder.matches(req.password(), usuario.getPassword())) {
                return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                        .body(new LoginSistemasResponse(false, "Contraseña incorrecta.", null, null));
            }

            if (usuario.getTipoUsuario() != Usuario.ROL_ADMIN) {
                return ResponseEntity.status(HttpStatus.FORBIDDEN)
                        .body(new LoginSistemasResponse(false, "Acceso denegado: El usuario no tiene permisos de operador de sistemas.", null, null));
            }

            if (usuario.getActivo() != null && !usuario.getActivo()) {
                return ResponseEntity.status(HttpStatus.FORBIDDEN)
                        .body(new LoginSistemasResponse(false, "Acceso denegado: La cuenta de operador se encuentra inactiva.", null, null));
            }

            String token = jwtService.generarToken(
                    usuario.getId(),
                    usuario.getName(),
                    usuario.getEmail(),
                    usuario.getBlack(),
                    usuario.getTipoUsuario()
            );

            return ResponseEntity.ok(new LoginSistemasResponse(
                    true,
                    "Inicio de sesión de sistemas exitoso.",
                    token,
                    Usuario.Response.fromEntity(usuario)
            ));
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(new LoginSistemasResponse(false, "Error interno en login de sistemas: " + e.getMessage(), null, null));
        }
    }

    /**
     * Endpoint para registrar un nuevo usuario desde la interfaz web.
     * Retorna el usuario creado junto con su token JWT de 180 días para auto-login inmediato.
     */
    @PostMapping("/api/auth/register")
    public ResponseEntity<RegistroResponse> registrarUsuario(@Valid @RequestBody RegistroRequest req) {
        try {
            if (usuarioService.findByEmail(req.email()).isPresent()) {
                return ResponseEntity.status(HttpStatus.CONFLICT)
                        .body(new RegistroResponse(false, "El correo electrónico ya se encuentra registrado.", null, null));
            }

            String encodedPassword = (req.password() != null && !req.password().isBlank())
                    ? passwordEncoder.encode(req.password())
                    : null;

            Usuario usuario = Usuario.builder()
                    .name(req.name())
                    .email(req.email())
                    .password(encodedPassword)
                    .codigoAcceso(req.codigoAcceso())
                    .tipoUsuario(Usuario.ROL_ALUMNO)
                    .black(req.black() != null ? req.black() : false)
                    .build();

            Usuario guardado = usuarioService.registerUsuario(usuario);
            String token = jwtService.generarToken(guardado.getId(), guardado.getName(), guardado.getEmail(), guardado.getBlack());

            return ResponseEntity.status(HttpStatus.CREATED)
                    .body(new RegistroResponse(
                            true,
                            "Usuario registrado con éxito.",
                            token,
                            Usuario.Response.fromEntity(guardado)
                    ));
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(new RegistroResponse(false, "Error al registrar usuario: " + e.getMessage(), null, null));
        }
    }

    /**
     * Endpoint para que el alumno ingrese con su código de acceso (PIN)
     * en la pantalla y se le active la sesión automáticamente sin correo.
     */
    @PostMapping("/api/auth/ingresar-codigo")
    public ResponseEntity<RegistroResponse> ingresarConCodigo(@Valid @RequestBody IngresarCodigoRequest req) {
        try {
            Usuario usuario = usuarioService.findByCodigoAcceso(req.codigo()).orElse(null);
            if (usuario == null) {
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(new RegistroResponse(false, "Código de acceso inválido. Verifique el código e intente nuevamente.", null, null));
            }

            if (usuario.getActivo() != null && !usuario.getActivo()) {
                return ResponseEntity.status(HttpStatus.FORBIDDEN)
                        .body(new RegistroResponse(false, "Tu cuenta se encuentra pausada o inactiva. Por favor comunicate con administración.", null, null));
            }

            String token = jwtService.generarToken(usuario.getId(), usuario.getName(), usuario.getEmail(), usuario.getBlack());
            return ResponseEntity.ok(new RegistroResponse(
                    true,
                    "Acceso concedido exitosamente.",
                    token,
                    Usuario.Response.fromEntity(usuario)
            ));
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(new RegistroResponse(false, "Error al validar código: " + e.getMessage(), null, null));
        }
    }

    @PostMapping("/api/auth/verificar-token")
    public ResponseEntity<TokenVerifyResponse> verificarToken(@Valid @RequestBody TokenVerifyRequest request) {
        try {
            if (!jwtService.esTokenValido(request.token())) {
                return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                        .body(new TokenVerifyResponse(false, false, null, "El token es inválido o ha expirado."));
            }

            Claims claims = jwtService.validarYObtenerClaims(request.token());
            Long userId = Long.parseLong(claims.getSubject());

            Usuario usuario = usuarioService.findById(userId).orElse(null);
            if (usuario == null) {
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(new TokenVerifyResponse(false, false, null, "Usuario no encontrado en la base de datos."));
            }

            if (usuario.getActivo() != null && !usuario.getActivo()) {
                return ResponseEntity.status(HttpStatus.FORBIDDEN)
                        .body(new TokenVerifyResponse(false, false, null, "Acceso deshabilitado. Tu cuenta se encuentra inactiva."));
            }

            return ResponseEntity.ok(new TokenVerifyResponse(
                    true,
                    true,
                    Usuario.Response.fromEntity(usuario),
                    "Token validado exitosamente."
            ));
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(new TokenVerifyResponse(false, false, null, "Error al validar token: " + e.getMessage()));
        }
    }

    @PostMapping("/api/admin/enviar-acceso-correo")
    public ResponseEntity<EnviarAccesoResponse> enviarAccesoCorreo(@Valid @RequestBody EnviarAccesoRequest req) {
        try {
            Usuario usuario = usuarioService.findByEmail(req.email()).orElse(null);

            if (usuario != null && usuario.getActivo() != null && !usuario.getActivo()) {
                return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                        .body(new EnviarAccesoResponse(false, "No se puede generar o enviar enlace de acceso para una cuenta inactiva. Active la cuenta primero en el panel.", null));
            }

            if (usuario == null) {
                usuario = Usuario.builder()
                        .name(req.name())
                        .email(req.email())
                        .codigoAcceso(req.codigoAcceso())
                        .tipoUsuario(Usuario.ROL_ALUMNO)
                        .black(req.black() != null ? req.black() : false)
                        .build();
                usuario = usuarioService.registerUsuario(usuario);
            } else {
                usuario.setName(req.name());
                if (req.black() != null) {
                    usuario.setBlack(req.black());
                }
                if (req.codigoAcceso() != null && !req.codigoAcceso().isBlank()) {
                    usuario.setCodigoAcceso(req.codigoAcceso());
                }
                usuario = usuarioService.registerUsuario(usuario);
            }

            String token = jwtService.generarToken(usuario.getId(), usuario.getName(), usuario.getEmail(), usuario.getBlack());
            String accessUrl = frontendUrl + "/acceso?token=" + token;

            emailService.enviarMagicLink(usuario.getEmail(), usuario.getName(), accessUrl, usuario.getCodigoAcceso());

            return ResponseEntity.ok(new EnviarAccesoResponse(
                    true,
                    "Correo de acceso enviado exitosamente a " + usuario.getEmail(),
                    new AccesoData(usuario.getId(), usuario.getEmail(), usuario.getCodigoAcceso(), accessUrl)
            ));
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(new EnviarAccesoResponse(false, "Error al enviar correo de acceso: " + e.getMessage(), null));
        }
    }
}
