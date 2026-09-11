package com.example.uade.tpo.practica2back.features.usuario;

import java.util.List;
import java.util.Optional;

public interface UsuarioService {
    List<Usuario> getUsuarios();
    Usuario.PaginatedResponse<Usuario.Response> getUsuariosPaginados(int skip, int limit, Usuario.FiltroUsuarios filtros);
    Usuario registerUsuario(Usuario usuario);
    Optional<Usuario> findById(Long id);
    Optional<Usuario> findByEmail(String email);
    Optional<Usuario> findByCodigoAcceso(String codigoAcceso);
    String generarCodigoAccesoUnico();
    boolean actualizarSuscripcion(Long usuarioId);
    boolean toggleActivo(Long usuarioId);
    void deleteAllUsuarios();
}
