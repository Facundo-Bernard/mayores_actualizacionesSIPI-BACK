package com.example.uade.tpo.practica2back.features.usuario;

import java.util.List;
import java.util.Optional;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class UsuarioServiceImpl implements UsuarioService {

    private final UsuarioRepository usuarioRepository;

    public UsuarioServiceImpl(UsuarioRepository usuarioRepository) {
        this.usuarioRepository = usuarioRepository;
    }

    @Override
    public List<Usuario> getUsuarios() {
        return usuarioRepository.findAll();
    }

    @Override
    public Usuario.PaginatedResponse<Usuario.Response> getUsuariosPaginados(int skip, int limit, Usuario.FiltroUsuarios filtros) {
        int safeLimit = (limit > 0) ? Math.min(limit, 100) : 20;
        int safeSkip = Math.max(skip, 0);

        org.springframework.data.domain.Sort sort = org.springframework.data.domain.Sort.by(
                "asc".equalsIgnoreCase(filtros != null ? filtros.orden() : null)
                        ? org.springframework.data.domain.Sort.Direction.ASC
                        : org.springframework.data.domain.Sort.Direction.DESC,
                "id"
        );

        org.springframework.data.jpa.domain.Specification<Usuario> spec = UsuarioSpecifications.conFiltros(filtros);
        org.springframework.data.domain.Pageable pageable = new OffsetBasedPageRequest(safeSkip, safeLimit, sort);

        org.springframework.data.domain.Page<Usuario> page = usuarioRepository.findAll(spec, pageable);

        List<Usuario.Response> items = page.getContent().stream()
                .map(Usuario.Response::fromEntity)
                .toList();

        return new Usuario.PaginatedResponse<>(
                page.getTotalElements(),
                safeSkip,
                safeLimit,
                items
        );
    }

    @Override
    @Transactional
    public Usuario registerUsuario(Usuario usuario) {
        if (usuario.getBlack() == null) {
            usuario.setBlack(false);
        }
        if (usuario.getActivo() == null) {
            usuario.setActivo(true);
        }
        if (usuario.getDateStart() == null) {
            usuario.setDateStart(java.time.LocalDateTime.now());
        }
        // Si no tiene código de acceso asignado, genera uno único de 6 dígitos
        if (usuario.getCodigoAcceso() == null || usuario.getCodigoAcceso().isBlank()) {
            usuario.setCodigoAcceso(generarCodigoAccesoUnico());
        }
        return usuarioRepository.save(usuario);
    }

    @Override
    public Optional<Usuario> findById(Long id) {
        return usuarioRepository.findById(id);
    }

    @Override
    public Optional<Usuario> findByEmail(String email) {
        return usuarioRepository.findByEmail(email);
    }

    @Override
    public Optional<Usuario> findByCodigoAcceso(String codigoAcceso) {
        return usuarioRepository.findByCodigoAcceso(codigoAcceso.trim());
    }

    @Override
    public String generarCodigoAccesoUnico() {
        java.util.concurrent.ThreadLocalRandom random = java.util.concurrent.ThreadLocalRandom.current();
        String codigo;
        do {
            // Código de 6 dígitos numéricos, ideal y fácil para dictar a adultos mayores
            codigo = String.valueOf(random.nextInt(100000, 999999));
        } while (usuarioRepository.existsByCodigoAcceso(codigo));
        return codigo;
    }

    @Override
    @Transactional
    public boolean actualizarSuscripcion(Long usuarioId) {
        Optional<Usuario> usuarioBuscado = usuarioRepository.findById(usuarioId);

        if (usuarioBuscado.isPresent()) {
            Usuario usuario = usuarioBuscado.get();
            Boolean actual = usuario.getBlack();
            boolean nuevoValor = !(actual != null && actual);

            usuario.setBlack(nuevoValor);
            usuarioRepository.save(usuario);
            return true;
        }

        return false;
    }

    @Override
    @Transactional
    public boolean toggleActivo(Long usuarioId) {
        Optional<Usuario> usuarioBuscado = usuarioRepository.findById(usuarioId);

        if (usuarioBuscado.isPresent()) {
            Usuario usuario = usuarioBuscado.get();
            Boolean actual = usuario.getActivo();
            boolean nuevoValor = !(actual != null && actual);

            usuario.setActivo(nuevoValor);
            usuarioRepository.save(usuario);
            return true;
        }

        return false;
    }

    @Override
    @Transactional
    public void deleteAllUsuarios() {
        usuarioRepository.deleteAll();
    }
}
