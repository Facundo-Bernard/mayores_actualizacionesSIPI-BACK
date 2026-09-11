package com.example.uade.tpo.practica2back.features.progreso;

import java.util.List;

public interface ProgresoUsuarioService {
    ProgresoUsuario crearProgreso(ProgresoUsuario progreso);
    ProgresoUsuario actualizarProgreso(Long usuarioId, Long cursoId, ProgresoUsuario.UpdateRequest updateRequest);
    List<ProgresoUsuario> obtenerProgresoPorUsuario(Long usuarioId);
}
