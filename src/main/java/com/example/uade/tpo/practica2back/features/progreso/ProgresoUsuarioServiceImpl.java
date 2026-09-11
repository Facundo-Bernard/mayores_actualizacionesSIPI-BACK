package com.example.uade.tpo.practica2back.features.progreso;

import java.util.List;
import java.util.Optional;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ProgresoUsuarioServiceImpl implements ProgresoUsuarioService {

    private final ProgresoUsuarioRepository progresoUsuarioRepository;

    public ProgresoUsuarioServiceImpl(ProgresoUsuarioRepository progresoUsuarioRepository) {
        this.progresoUsuarioRepository = progresoUsuarioRepository;
    }

    @Override
    @Transactional
    public ProgresoUsuario crearProgreso(ProgresoUsuario progreso) {
        return progresoUsuarioRepository.save(progreso);
    }

    @Override
    @Transactional
    public ProgresoUsuario actualizarProgreso(Long usuarioId, Long cursoId, ProgresoUsuario.UpdateRequest updateRequest) {
        Optional<ProgresoUsuario> progresoExiste = progresoUsuarioRepository.findByUsuario_IdAndCursoId(usuarioId, cursoId);

        if (progresoExiste.isPresent()) {
            ProgresoUsuario progreso = progresoExiste.get();
            progreso.setProgreso(updateRequest.progreso());
            progreso.setCompletado(updateRequest.completado());
            progreso.setExamenPuntos(updateRequest.examenPuntos());
            return progresoUsuarioRepository.save(progreso);
        } else {
            throw new RuntimeException("No se encontró ningún progreso para el usuario " + usuarioId + " y curso " + cursoId);
        }
    }

    @Override
    public List<ProgresoUsuario> obtenerProgresoPorUsuario(Long usuarioId) {
        return progresoUsuarioRepository.findByUsuario_Id(usuarioId);
    }
}
