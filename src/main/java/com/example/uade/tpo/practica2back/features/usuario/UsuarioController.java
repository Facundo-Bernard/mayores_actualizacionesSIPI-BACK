package com.example.uade.tpo.practica2back.features.usuario;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;

@RestController
@RequestMapping("/usuario")
@CrossOrigin(origins = "*")
public class UsuarioController {

    private final UsuarioService usuarioService;

    public UsuarioController(UsuarioService usuarioService) {
        this.usuarioService = usuarioService;
    }

    // Obtener usuarios con paginación (skip y limit) y diccionario de filtros
    @GetMapping
    public ResponseEntity<Usuario.PaginatedResponse<Usuario.Response>> getUsuarios(
            @RequestParam(defaultValue = "20") int limit,
            @RequestParam(defaultValue = "0") int skip,
            @RequestParam(required = false) String nombre,
            @RequestParam(required = false) @org.springframework.format.annotation.DateTimeFormat(iso = org.springframework.format.annotation.DateTimeFormat.ISO.DATE) java.time.LocalDate fechaDesde,
            @RequestParam(required = false) @org.springframework.format.annotation.DateTimeFormat(iso = org.springframework.format.annotation.DateTimeFormat.ISO.DATE) java.time.LocalDate fechaHasta,
            @RequestParam(required = false) Integer tipoUsuario,
            @RequestParam(required = false) Boolean black,
            @RequestParam(required = false) Boolean activo,
            @RequestParam(required = false) String orden
    ) {
        Usuario.FiltroUsuarios filtros = new Usuario.FiltroUsuarios(nombre, fechaDesde, fechaHasta, tipoUsuario, black, activo, orden);
        return ResponseEntity.ok(usuarioService.getUsuariosPaginados(skip, limit, filtros));
    }

    // Endpoint opcional para obtener todos sin paginar
    @GetMapping("/todos")
    public List<Usuario.Response> getAllUsuarios() {
        return usuarioService.getUsuarios().stream()
                .map(Usuario.Response::fromEntity)
                .toList();
    }

    // Registrar un usuario utilizando el schema RegisterRequest
    @PostMapping("/register")
    public ResponseEntity<Usuario.Response> registerUsuario(@Valid @RequestBody Usuario.RegisterRequest request) {
        Usuario usuario = Usuario.builder()
                .name(request.name())
                .email(request.email())
                .password(request.password())
                .tipoUsuario(request.tipoUsuario() != null ? request.tipoUsuario() : 1)
                .black(request.black() != null ? request.black() : false)
                .activo(request.activo() != null ? request.activo() : true)
                .build();

        Usuario guardado = usuarioService.registerUsuario(usuario);
        return ResponseEntity.status(HttpStatus.CREATED).body(Usuario.Response.fromEntity(guardado));
    }

    // Actualizar suscripcion black
    @PutMapping("/{usuarioId}/suscribirse")
    public ResponseEntity<Usuario.SuscripcionResponse> actualizarSuscripcion(@PathVariable Long usuarioId) {
        boolean success = usuarioService.actualizarSuscripcion(usuarioId);
        if (success) {
            Usuario actualizado = usuarioService.findById(usuarioId).orElse(null);
            Boolean isBlack = actualizado != null ? actualizado.getBlack() : null;
            return ResponseEntity.ok(new Usuario.SuscripcionResponse(true, "Suscripción actualizada con éxito", isBlack));
        } else {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(new Usuario.SuscripcionResponse(false, "Usuario no encontrado", null));
        }
    }

    // Alternar estado activo / inactivo
    @PutMapping("/{usuarioId}/toggle-activo")
    public ResponseEntity<Usuario.EstadoActivoResponse> toggleActivo(@PathVariable Long usuarioId) {
        boolean success = usuarioService.toggleActivo(usuarioId);
        if (success) {
            Usuario actualizado = usuarioService.findById(usuarioId).orElse(null);
            Boolean isActivo = actualizado != null ? actualizado.getActivo() : null;
            return ResponseEntity.ok(new Usuario.EstadoActivoResponse(true, "Estado de actividad actualizado con éxito", isActivo));
        } else {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(new Usuario.EstadoActivoResponse(false, "Usuario no encontrado", null));
        }
    }

    // Borrar todos los usuarios
    @DeleteMapping("/deleteAll")
    public ResponseEntity<Void> deleteAllUsuarios() {
        usuarioService.deleteAllUsuarios();
        return ResponseEntity.noContent().build();
    }
}
