package com.example.uade.tpo.practica2back.entity;

import java.time.LocalDate;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import lombok.Data;

@Entity
@Data
public class Usuario {

    public Usuario() {
    }

    public Usuario(String name, String email, String password, int tipoUsuario, boolean isBlack, LocalDate dateStart, LocalDate dateEnd) {
        this.name = name;
        this.email = email;
        this.password = password;
        this.tipoUsuario = tipoUsuario;
        this.isBlack = isBlack;
        this.dateStart = dateStart;
        this.dateEnd = dateEnd;
    }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column
    private String name;

    @Column
    private String email;

    @Column
    private String password;

    @Column
    private int tipoUsuario; // 1: Cliente, 2: Secretaria, 3: Abogado

    @Column
    private boolean isBlack;

    @Column
    private LocalDate dateStart;

    @Column
    private LocalDate dateEnd;

    public void setBlack(boolean b) {
        throw new UnsupportedOperationException("Not supported yet.");
    }


}
