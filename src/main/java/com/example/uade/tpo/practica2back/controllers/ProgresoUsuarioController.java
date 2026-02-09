package com.example.uade.tpo.practica2back.controllers;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.uade.tpo.practica2back.Service.ProgresoUsuarioServiceImpl;
import com.example.uade.tpo.practica2back.entity.ProgresoUsuario;

@RestController
@RequestMapping({ "/progreso" })
@CrossOrigin(origins = { "http://localhost:5173" })
public class ProgresoUsuarioController {

   @Autowired
   private ProgresoUsuarioServiceImpl progresoUsuarioServiceImpl;

   // Constructor
   public ProgresoUsuarioController() {
   }

   // Crear progreso
   @PostMapping({ "/crear" })
   public ProgresoUsuario crearProgreso(@RequestBody ProgresoUsuario progreso) {
      return this.progresoUsuarioServiceImpl.crearProgreso(progreso);
   }

   // Actualizar progreso
   @PutMapping({ "/actualizar/{usuarioId}/{cursoId}" })
   public ProgresoUsuario actualizarProgreso(@PathVariable Long usuarioId, @PathVariable Long cursoId,
         @RequestBody ProgresoUsuario progresoActualizado) {
      return this.progresoUsuarioServiceImpl.actualizarProgreso(usuarioId, cursoId, progresoActualizado);
   }

   // Obtener progreso por usuario
   @GetMapping({ "/obtenerUsuario/{usuarioId}" })
   public List<ProgresoUsuario> obtenerProgresoPorUsuario(@PathVariable Long usuarioId) {
      return this.progresoUsuarioServiceImpl.obtenerProgresoPorUsuario(usuarioId);
   }
}
