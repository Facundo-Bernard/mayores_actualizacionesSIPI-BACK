package com.example.uade.tpo.practica2back.Service;

import java.util.List;
import java.util.Optional;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import com.example.uade.tpo.practica2back.entity.ProgresoUsuario;
import com.example.uade.tpo.practica2back.repository.ProgresoUsuarioRepository;

@Service
public class ProgresoUsuarioServiceImpl implements ProgresoUsuarioService {

    @Autowired
    private ProgresoUsuarioRepository progresoUsuarioRepository;

    @Override
    public ProgresoUsuario crearProgreso(ProgresoUsuario progreso) {
        return progresoUsuarioRepository.save(progreso);
    }

    @Override
    public ProgresoUsuario actualizarProgreso(Long usuarioId, Long cursoId, ProgresoUsuario progresoActualizado) {
        Optional<ProgresoUsuario> progresoExiste = progresoUsuarioRepository.findByUsuario_IdAndCursoId(usuarioId,
                cursoId);

        if (progresoExiste.isPresent()) {
            ProgresoUsuario progreso = progresoExiste.get();
            progreso.setProgreso(progresoActualizado.getProgreso());
            progreso.setCompletado(progresoActualizado.isCompletado());
            progreso.setExamenPuntos(progresoActualizado.getExamenPuntos());
            return progresoUsuarioRepository.save(progreso);
        } else {
            throw new RuntimeException("No se encontró ningún progreso para el usuario y curso especificados");
        }
    }

    @Override
    public List<ProgresoUsuario> obtenerProgresoPorUsuario(Long usuarioId) {
        return progresoUsuarioRepository.findByUsuario_Id(usuarioId);
    }

    /*
     * @Override
     * public List<ProgresoUsuario> obtenerProgresoPorCurso(Long cursosId) {
     * return progresoUsuarioRepository.findByCursoId(cursosId);
     * }
     */
}
