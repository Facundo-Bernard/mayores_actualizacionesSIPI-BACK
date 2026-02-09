package com.example.uade.tpo.practica2back.entity;

import java.time.LocalDate;

import com.fasterxml.jackson.annotation.JsonProperty;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

@Entity
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

    @Column(name = "is_black")
    @JsonProperty("black")
    private Boolean black = false;

    @Column
    private LocalDate dateStart;

    @Column
    private LocalDate dateEnd;

    // ===== GETTERS / SETTERS MANUALES =====

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }

    public int getTipoUsuario() {
        return tipoUsuario;
    }

    public void setTipoUsuario(int tipoUsuario) {
        this.tipoUsuario = tipoUsuario;
    }

    // LOS QUE TE FALTAN
    public Boolean getBlack() {
        return black;
    }

    public void setBlack(Boolean black) {
        this.black = black;
    }

    public LocalDate getDateStart() {
        return dateStart;
    }

    public void setDateStart(LocalDate dateStart) {
        this.dateStart = dateStart;
    }

    public LocalDate getDateEnd() {
        return dateEnd;
    }

    public void setDateEnd(LocalDate dateEnd) {
        this.dateEnd = dateEnd;
    }
}
