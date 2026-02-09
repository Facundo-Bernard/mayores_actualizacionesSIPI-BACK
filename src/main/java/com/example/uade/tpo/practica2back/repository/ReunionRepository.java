package com.example.uade.tpo.practica2back.repository;

import java.time.LocalDateTime; // Cambiar LocalDate por LocalDateTime
import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import com.example.uade.tpo.practica2back.entity.Reunion;

@Repository
public interface ReunionRepository extends JpaRepository<Reunion, Long> {

    List<Reunion> findByAbogadoAndFecha(String abogado, LocalDateTime fecha); // Cambiar LocalDate por LocalDateTime
}
