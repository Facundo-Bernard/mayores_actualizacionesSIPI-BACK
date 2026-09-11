package com.example.uade.tpo.practica2back.features.usuario;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.stereotype.Repository;

@Repository
public interface UsuarioRepository extends JpaRepository<Usuario, Long>, JpaSpecificationExecutor<Usuario> {
    Optional<Usuario> findByEmail(String email);
    boolean existsByEmail(String email);
    Optional<Usuario> findByCodigoAcceso(String codigoAcceso);
    boolean existsByCodigoAcceso(String codigoAcceso);
    boolean existsByTipoUsuario(int tipoUsuario);
}

