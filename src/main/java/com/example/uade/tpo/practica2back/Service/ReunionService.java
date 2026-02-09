package com.example.uade.tpo.practica2back.Service;

import java.time.LocalDateTime; // Asegúrate de importar LocalDateTime
import java.util.List;

import org.springframework.stereotype.Service;

import com.example.uade.tpo.practica2back.entity.Reunion;
import com.example.uade.tpo.practica2back.repository.ReunionRepository;

@Service
public class ReunionService {

    private final ReunionRepository reunionRepository;

    public ReunionService(ReunionRepository reunionRepository) {
        this.reunionRepository = reunionRepository;
    }

    public List<Reunion> getAllReuniones() {
        return reunionRepository.findAll();
    }

    public Reunion createReunion(Reunion reunion) {
        if (isConflictingReunion(reunion)) {
            throw new IllegalStateException("El abogado ya tiene una reunión en este horario.");
        }
        return reunionRepository.save(reunion);
    }

    public Reunion updateReunion(Long id, Reunion updatedReunion) {
        Reunion reunion = reunionRepository.findById(id).orElseThrow();
        if (isConflictingReunion(updatedReunion)) {
            throw new IllegalStateException("El abogado ya tiene una reunión en este horario.");
        }
        reunion.setTitulo(updatedReunion.getTitulo());
        reunion.setDescripcion(updatedReunion.getDescripcion());
        reunion.setFecha(updatedReunion.getFecha());
        reunion.setAbogado(updatedReunion.getAbogado());
        reunion.setEstado(updatedReunion.getEstado());
        return reunionRepository.save(reunion);
    }

    public void deleteReunion(Long id) {
        reunionRepository.deleteById(id);
    }

    // Validación de conflictos de horarios
    private boolean isConflictingReunion(Reunion reunion) {
        List<Reunion> reuniones = reunionRepository.findByAbogadoAndFecha(reunion.getAbogado(), reunion.getFecha()); // Cambiar toLocalDate por fecha directamente
        return reuniones.stream().anyMatch(r -> !r.getId().equals(reunion.getId()) &&
                r.getFecha().isEqual(reunion.getFecha()));
    }
}

