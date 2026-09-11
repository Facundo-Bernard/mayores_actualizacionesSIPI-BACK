package com.example.uade.tpo.practica2back.features.progreso;

import com.example.uade.tpo.practica2back.features.usuario.Usuario;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "progreso_usuario")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ProgresoUsuario {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column
    @Builder.Default
    private int progreso = 0;

    @Column
    @Builder.Default
    private boolean completado = false;

    @Column(name = "examen_puntos")
    @Builder.Default
    private int examenPuntos = 0;

    @Column(name = "curso_id")
    private Long cursoId;

    @ManyToOne
    @JoinColumn(name = "usuario_id")
    private Usuario usuario;

    public ProgresoUsuario(int progreso, boolean completado, int examenPuntos, Long cursoId, Usuario usuario) {
        this.progreso = progreso;
        this.completado = completado;
        this.examenPuntos = examenPuntos;
        this.cursoId = cursoId;
        this.usuario = usuario;
    }

    // ==========================================
    // SCHEMAS (DTOs) Integrados en la Entidad
    // ==========================================

    public static record CreateRequest(
        int progreso,
        boolean completado,
        int examenPuntos,
        Long cursoId,
        Long usuarioId
    ) {}

    public static record UpdateRequest(
        int progreso,
        boolean completado,
        int examenPuntos
    ) {}

    public static record Response(
        Long id,
        int progreso,
        boolean completado,
        int examenPuntos,
        Long cursoId,
        Long usuarioId
    ) {
        public static Response fromEntity(ProgresoUsuario p) {
            return new Response(
                p.getId(),
                p.getProgreso(),
                p.isCompletado(),
                p.getExamenPuntos(),
                p.getCursoId(),
                p.getUsuario() != null ? p.getUsuario().getId() : null
            );
        }
    }
}
