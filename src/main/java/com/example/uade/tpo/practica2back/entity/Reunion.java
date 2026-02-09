package com.example.uade.tpo.practica2back.entity;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import lombok.Data;


@Entity
@Data
public class Reunion {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column
    private String titulo;

    @Column
    private String descripcion;

    @Column
    private LocalDateTime fecha;

    @Column
    private String abogado; // Nombre del abogado

    @Column
    private String estado; // PENDIENTE, CONFIRMADA, FINALIZADA
}
