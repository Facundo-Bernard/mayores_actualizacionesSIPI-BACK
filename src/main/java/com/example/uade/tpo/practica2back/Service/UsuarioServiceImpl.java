package com.example.uade.tpo.practica2back.Service;

import java.util.List;
import java.util.Optional;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import com.example.uade.tpo.practica2back.entity.Usuario;
import com.example.uade.tpo.practica2back.repository.UsuarioRepository;

@Service
public class UsuarioServiceImpl implements UsuarioService {

    @Autowired
    private UsuarioRepository usuarioRepository;

    @Override
    public List<Usuario> getUsuarios() {
        return usuarioRepository.findAll();
    }

    @Override
    public Usuario registerUsuario(Usuario usuario) {
        // Normaliza null
        if (usuario.getBlack() == null) {
            usuario.setBlack(false);
        }
        return usuarioRepository.save(usuario);
    }

    @Override
    public boolean actualizarSuscripcion(Long usuarioId) {
        Optional<Usuario> usuarioBuscado = usuarioRepository.findById(usuarioId);

        if (usuarioBuscado.isPresent()) {
            Usuario usuario = usuarioBuscado.get();

            Boolean actual = usuario.getBlack();
            boolean nuevoValor = !(actual != null && actual);

            usuario.setBlack(nuevoValor);
            usuarioRepository.save(usuario);
            return true;
        }

        return false;
    }

    @Override
    public void deleteAllUsuarios() {
        usuarioRepository.deleteAll();
    }
}
