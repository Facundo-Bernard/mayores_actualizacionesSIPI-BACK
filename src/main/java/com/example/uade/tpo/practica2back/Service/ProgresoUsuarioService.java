package com.example.uade.tpo.practica2back.Service;

import java.util.List;

import com.example.uade.tpo.practica2back.entity.ProgresoUsuario;

public interface ProgresoUsuarioService {
    ProgresoUsuario crearProgreso(ProgresoUsuario progreso);

    ProgresoUsuario actualizarProgreso(Long usuarioId, Long cursoId, ProgresoUsuario progreso);

    List<ProgresoUsuario> obtenerProgresoPorUsuario(Long usuarioId);

    /* List<ProgresoUsuario> obtenerProgresoPorCurso(Long cursosId); */
}
