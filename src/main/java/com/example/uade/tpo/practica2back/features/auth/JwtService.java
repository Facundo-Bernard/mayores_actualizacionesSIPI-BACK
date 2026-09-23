package com.example.uade.tpo.practica2back.features.auth;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;

import javax.crypto.SecretKey;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

@Service
public class JwtService {

    private final SecretKey signingKey;
    private final long expirationDays;

    public JwtService(
            @Value("${app.jwt.secret}") String secret,
            @Value("${app.jwt.expiration-days:180}") long expirationDays) {
        this.signingKey = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.expirationDays = expirationDays;
    }

    public String generarToken(Long userId, String name, String email, Boolean isBlack) {
        return generarToken(userId, name, email, isBlack, 1);
    }

    public String generarToken(Long userId, String name, String email, Boolean isBlack, Integer tipoUsuario) {
        Instant now = Instant.now();
        Instant expiry = now.plus(expirationDays, ChronoUnit.DAYS);

        Map<String, Object> claims = new HashMap<>();
        claims.put("name", name != null ? name : "");
        claims.put("email", email != null ? email : "");
        claims.put("black", isBlack != null ? isBlack : false);
        claims.put("rol", tipoUsuario != null ? tipoUsuario : 1);
        claims.put("tipoUsuario", tipoUsuario != null ? tipoUsuario : 1);

        return Jwts.builder()
                .subject(String.valueOf(userId))
                .claims(claims)
                .issuedAt(Date.from(now))
                .expiration(Date.from(expiry))
                .signWith(signingKey)
                .compact();
    }

    public Claims validarYObtenerClaims(String token) {
        return Jwts.parser()
                .verifyWith(signingKey)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    public boolean esTokenValido(String token) {
        try {
            Claims claims = validarYObtenerClaims(token);
            return claims.getExpiration().after(new Date());
        } catch (Exception e) {
            return false;
        }
    }

    public Long obtenerUserId(String token) {
        Claims claims = validarYObtenerClaims(token);
        return Long.parseLong(claims.getSubject());
    }
}
