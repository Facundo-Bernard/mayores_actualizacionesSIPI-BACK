package com.example.uade.tpo.practica2back.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import lombok.Data;

@Entity
@Data
public class ProgresoUsuario {

    public ProgresoUsuario() {
    }

    public ProgresoUsuario(int progreso, boolean completado, int examenPuntos, Long cursoId, Usuario usuario) {
        this.progreso = progreso;
        this.completado = completado;
        this.examenPuntos = examenPuntos;
        this.cursoId = cursoId;
        this.usuario = usuario;
    }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column
    private int progreso;
    
    @Column
    private boolean completado;

    @Column
    private int examenPuntos;

    @Column
    private Long cursoId;

    @ManyToOne
    @JoinColumn(name = "usuario_id")
    private Usuario usuario;

}
