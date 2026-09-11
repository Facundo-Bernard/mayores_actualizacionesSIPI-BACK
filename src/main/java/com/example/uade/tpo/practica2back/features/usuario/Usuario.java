package com.example.uade.tpo.practica2back.features.usuario;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonProperty;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "usuario")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Usuario {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column
    private String name;

    @Column(unique = true)
    private String email;

    @Column
    private String password;

    // Roles de usuario de la plataforma (1: Alumno, 2: Administrador)
    public static final int ROL_ALUMNO = 1;
    public static final int ROL_ADMIN = 2;

    @Column(name = "tipo_usuario")
    @Builder.Default
    private int tipoUsuario = ROL_ALUMNO;

    @Column(name = "is_black")
    @JsonProperty("black")
    @Builder.Default
    private Boolean black = false;

    @Column(name = "date_start")
    @JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss")
    private LocalDateTime dateStart;

    @Column(name = "date_end")
    private LocalDate dateEnd;

    @Column(name = "activo")
    @Builder.Default
    private Boolean activo = true;

    @Column(name = "codigo_acceso", unique = true)
    private String codigoAcceso;

    @PrePersist
    public void prePersist() {
        if (this.dateStart == null) {
            this.dateStart = LocalDateTime.now();
        }
        if (this.activo == null) {
            this.activo = true;
        }
    }

    public Usuario(String name, String email, String password, int tipoUsuario, Boolean black, LocalDateTime dateStart, LocalDate dateEnd) {
        this.name = name;
        this.email = email;
        this.password = password;
        this.tipoUsuario = tipoUsuario;
        this.black = (black != null) ? black : false;
        this.dateStart = (dateStart != null) ? dateStart : LocalDateTime.now();
        this.dateEnd = dateEnd;
        this.activo = true;
    }

    // ==========================================
    // SCHEMAS (DTOs) Integrados en la Entidad
    // ==========================================

    /** Schema de entrada para registrar un usuario */
    public static record RegisterRequest(
        @NotBlank(message = "El nombre es obligatorio") String name,
        @Email(message = "Debe ser un email válido") @NotBlank(message = "El email es obligatorio") String email,
        String password,
        String codigoAcceso,
        Integer tipoUsuario,
        Boolean black,
        Boolean activo
    ) {}

    /** Schema de salida con la información del usuario */
    public static record Response(
        Long id,
        String name,
        String email,
        String codigoAcceso,
        int tipoUsuario,
        Boolean black,
        Boolean activo,
        @JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss")
        LocalDateTime dateStart,
        LocalDate dateEnd
    ) {
        public static Response fromEntity(Usuario u) {
            return new Response(
                u.getId(),
                u.getName(),
                u.getEmail(),
                u.getCodigoAcceso(),
                u.getTipoUsuario(),
                u.getBlack(),
                u.getActivo() != null ? u.getActivo() : true,
                u.getDateStart(),
                u.getDateEnd()
            );
        }
    }

    /** Schema de respuesta al actualizar la suscripción */
    public static record SuscripcionResponse(
        boolean success,
        String message,
        Boolean black
    ) {}

    /** Schema de respuesta al activar/desactivar un usuario */
    public static record EstadoActivoResponse(
        boolean success,
        String message,
        Boolean activo
    ) {}

    /** Schema de salida para respuestas paginadas con skip y limit */
    public static record PaginatedResponse<T>(
        long total,
        int skip,
        int limit,
        List<T> items
    ) {}

    /** Schema / Diccionario para filtros dinámicos de búsqueda de usuarios */
    public static record FiltroUsuarios(
        String nombre,
        LocalDate fechaDesde,
        LocalDate fechaHasta,
        Integer tipoUsuario,
        Boolean black,
        Boolean activo,
        String orden
    ) {}
}
