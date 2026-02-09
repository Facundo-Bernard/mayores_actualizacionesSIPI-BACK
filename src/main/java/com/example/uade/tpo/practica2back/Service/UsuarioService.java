package com.example.uade.tpo.practica2back.Service;

import java.util.List;

import com.example.uade.tpo.practica2back.entity.Usuario;

public interface UsuarioService {
    List<Usuario> getUsuarios();
    Usuario registerUsuario(Usuario usuario);
    boolean actualizarSuscripcion(Long usuarioId);
    void deleteAllUsuarios(); // Método para borrar todos los usuarios
}
