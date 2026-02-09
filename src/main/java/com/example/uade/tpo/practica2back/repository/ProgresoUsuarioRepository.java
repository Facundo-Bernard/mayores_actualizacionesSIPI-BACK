package com.example.uade.tpo.practica2back.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import com.example.uade.tpo.practica2back.entity.ProgresoUsuario;

public interface ProgresoUsuarioRepository extends JpaRepository<ProgresoUsuario, Long> {
    List<ProgresoUsuario> findByUsuario_Id(Long usuarioId);

    Optional<ProgresoUsuario> findByUsuario_IdAndCursoId(Long usuarioId, Long cursoId);
}
