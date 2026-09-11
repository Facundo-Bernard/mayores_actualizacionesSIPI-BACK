package com.example.uade.tpo.practica2back.features.usuario;

import java.io.Serializable;

import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;

/**
 * Implementación de Pageable que soporta paginación basada en desplazamiento (skip/offset) y límite (limit/count).
 * Permite paginar exactamente como en FastAPI o SQL con LIMIT y OFFSET.
 */
public class OffsetBasedPageRequest implements Pageable, Serializable {

    private final int limit;
    private final long offset;
    private final Sort sort;

    public OffsetBasedPageRequest(long offset, int limit, Sort sort) {
        if (offset < 0) {
            throw new IllegalArgumentException("El desplazamiento (skip/offset) no puede ser menor a 0.");
        }
        if (limit < 1) {
            throw new IllegalArgumentException("El límite de elementos por página debe ser al menos 1.");
        }
        this.offset = offset;
        this.limit = limit;
        this.sort = (sort != null) ? sort : Sort.by(Sort.Direction.DESC, "id");
    }

    public OffsetBasedPageRequest(long offset, int limit) {
        this(offset, limit, Sort.by(Sort.Direction.DESC, "id"));
    }

    @Override
    public int getPageNumber() {
        return (int) (offset / limit);
    }

    @Override
    public int getPageSize() {
        return limit;
    }

    @Override
    public long getOffset() {
        return offset;
    }

    @Override
    public Sort getSort() {
        return sort;
    }

    @Override
    public Pageable next() {
        return new OffsetBasedPageRequest(getOffset() + getPageSize(), getPageSize(), getSort());
    }

    public OffsetBasedPageRequest previous() {
        return hasPrevious() ? new OffsetBasedPageRequest(getOffset() - getPageSize(), getPageSize(), getSort()) : this;
    }

    @Override
    public Pageable previousOrFirst() {
        return hasPrevious() ? previous() : first();
    }

    @Override
    public Pageable first() {
        return new OffsetBasedPageRequest(0, getPageSize(), getSort());
    }

    @Override
    public Pageable withPage(int pageNumber) {
        return new OffsetBasedPageRequest((long) pageNumber * getPageSize(), getPageSize(), getSort());
    }

    @Override
    public boolean hasPrevious() {
        return offset > 0;
    }
}
