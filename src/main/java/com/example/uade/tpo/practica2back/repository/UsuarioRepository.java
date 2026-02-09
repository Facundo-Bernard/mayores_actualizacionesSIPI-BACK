package com.example.uade.tpo.practica2back.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import com.example.uade.tpo.practica2back.entity.Usuario;

public interface UsuarioRepository extends JpaRepository<Usuario, Long> {
    Usuario findByEmail(String email); // Método para encontrar usuario por email
}
