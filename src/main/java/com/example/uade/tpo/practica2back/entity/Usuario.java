package com.example.uade.tpo.practica2back.entity;

import java.time.LocalDate;

import com.fasterxml.jackson.annotation.JsonProperty;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import lombok.Data;

@Entity
@Data
public class Usuario {

    public Usuario() {}

    public Usuario(String name, String email, String password, int tipoUsuario, Boolean black, LocalDate dateStart, LocalDate dateEnd) {
        this.name = name;
        this.email = email;
        this.password = password;
        this.tipoUsuario = tipoUsuario;
        this.black = black;
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
    private int tipoUsuario;

    // ✅ IMPORTANTE: wrapper Boolean para tolerar NULL y evitar el crash
    // ✅ Mapea a tu columna real (según logs: is_black)
    @Column(name = "is_black")
    @JsonProperty("black") // permite que el front mande/reciba "black"
    private Boolean black = false;

    @Column
    private LocalDate dateStart;

    @Column
    private LocalDate dateEnd;

    public void setBlack(boolean value) {
    this.black = value;
}

}
