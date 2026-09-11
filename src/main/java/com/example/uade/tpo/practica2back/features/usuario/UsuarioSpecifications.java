package com.example.uade.tpo.practica2back.features.usuario;

import java.util.ArrayList;
import java.util.List;

import org.springframework.data.jpa.domain.Specification;

import jakarta.persistence.criteria.Predicate;

/**
 * Especificaciones dinámicas de JPA Criteria API para el diccionario de filtros de usuarios.
 */
public class UsuarioSpecifications {

    private UsuarioSpecifications() {}

    public static Specification<Usuario> conFiltros(Usuario.FiltroUsuarios filtros) {
        return (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();

            if (filtros == null) {
                return cb.conjunction();
            }

            // Filtro por nombre o email (búsqueda parcial insensible a mayúsculas/minúsculas)
            if (filtros.nombre() != null && !filtros.nombre().isBlank()) {
                String search = "%" + filtros.nombre().trim().toLowerCase() + "%";
                Predicate nombreMatch = cb.like(cb.lower(root.get("name")), search);
                Predicate emailMatch = cb.like(cb.lower(root.get("email")), search);
                predicates.add(cb.or(nombreMatch, emailMatch));
            }

            // Filtro por fecha inicial (dateStart >= fechaDesde a las 00:00:00)
            if (filtros.fechaDesde() != null) {
                predicates.add(cb.greaterThanOrEqualTo(root.get("dateStart"), filtros.fechaDesde().atStartOfDay()));
            }

            // Filtro por fecha final (dateStart <= fechaHasta a las 23:59:59)
            if (filtros.fechaHasta() != null) {
                predicates.add(cb.lessThanOrEqualTo(root.get("dateStart"), filtros.fechaHasta().atTime(23, 59, 59)));
            }

            // Filtro por rol / tipo de usuario (1: Alumno, 2: Operador/Admin)
            if (filtros.tipoUsuario() != null) {
                predicates.add(cb.equal(root.get("tipoUsuario"), filtros.tipoUsuario()));
            }

            // Filtro por suscripción o membresía black
            if (filtros.black() != null) {
                predicates.add(cb.equal(root.get("black"), filtros.black()));
            }

            // Filtro por estado activo
            if (filtros.activo() != null) {
                predicates.add(cb.equal(root.get("activo"), filtros.activo()));
            }

            return cb.and(predicates.toArray(new Predicate[0]));
        };
    }
}
