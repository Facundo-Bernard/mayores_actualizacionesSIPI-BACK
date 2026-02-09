package com.example.uade.tpo.practica2back.controllers;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
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
import org.springframework.web.bind.annotation.RestController;

import com.example.uade.tpo.practica2back.Service.UsuarioServiceImpl;
import com.example.uade.tpo.practica2back.entity.Usuario;

@RestController
@RequestMapping("/usuario")
@CrossOrigin(origins = "*")

public class UsuarioController {

    @Autowired
    private UsuarioServiceImpl usuarioService;

    // Método para obtener todos los usuarios
    @GetMapping
    public List<Usuario> getAllUsuarios() {
        return usuarioService.getUsuarios();
    }

    // Método para registrar un usuario
    @PostMapping("/register")
    public Usuario registerUsuario(@RequestBody Usuario usuario) {
        return usuarioService.registerUsuario(usuario);
    }

    //Permite actualizar el atributo black de false a true
    @PutMapping("/{usuarioId}/suscribirse")
    public ResponseEntity<String> actualizarSuscripcion(@PathVariable Long usuarioId){
        boolean success = usuarioService.actualizarSuscripcion(usuarioId);
        if(success){
            return ResponseEntity.ok("Suscripcion realizada con exito");
        } else {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body("Usuario no encontrado.");
        }
    }


    // Método para borrar todos los usuarios
    @DeleteMapping("/deleteAll")
    public void deleteAllUsuarios() {
        usuarioService.deleteAllUsuarios();
    }
}
