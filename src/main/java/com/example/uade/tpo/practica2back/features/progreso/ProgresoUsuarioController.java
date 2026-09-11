package com.example.uade.tpo.practica2back.features.progreso;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.uade.tpo.practica2back.features.usuario.Usuario;
import com.example.uade.tpo.practica2back.features.usuario.UsuarioService;

@RestController
@RequestMapping("/progreso")
@CrossOrigin(origins = "*")
public class ProgresoUsuarioController {

    private final ProgresoUsuarioService progresoUsuarioService;
    private final UsuarioService usuarioService;

    public ProgresoUsuarioController(ProgresoUsuarioService progresoUsuarioService, UsuarioService usuarioService) {
        this.progresoUsuarioService = progresoUsuarioService;
        this.usuarioService = usuarioService;
    }

    // Crear progreso
    @PostMapping("/crear")
    public ResponseEntity<ProgresoUsuario.Response> crearProgreso(@RequestBody ProgresoUsuario.CreateRequest req) {
        Usuario usuario = usuarioService.findById(req.usuarioId()).orElse(null);
        ProgresoUsuario nuevo = ProgresoUsuario.builder()
                .progreso(req.progreso())
                .completado(req.completado())
                .examenPuntos(req.examenPuntos())
                .cursoId(req.cursoId())
                .usuario(usuario)
                .build();

        ProgresoUsuario guardado = progresoUsuarioService.crearProgreso(nuevo);
        return ResponseEntity.status(HttpStatus.CREATED).body(ProgresoUsuario.Response.fromEntity(guardado));
    }

    // Actualizar progreso
    @PutMapping("/actualizar/{usuarioId}/{cursoId}")
    public ResponseEntity<ProgresoUsuario.Response> actualizarProgreso(
            @PathVariable Long usuarioId,
            @PathVariable Long cursoId,
            @RequestBody ProgresoUsuario.UpdateRequest req) {
        ProgresoUsuario actualizado = progresoUsuarioService.actualizarProgreso(usuarioId, cursoId, req);
        return ResponseEntity.ok(ProgresoUsuario.Response.fromEntity(actualizado));
    }

    // Obtener progreso por usuario
    @GetMapping("/obtenerUsuario/{usuarioId}")
    public List<ProgresoUsuario.Response> obtenerProgresoPorUsuario(@PathVariable Long usuarioId) {
        return progresoUsuarioService.obtenerProgresoPorUsuario(usuarioId).stream()
                .map(ProgresoUsuario.Response::fromEntity)
                .toList();
    }
}
