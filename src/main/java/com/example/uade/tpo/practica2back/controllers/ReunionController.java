package com.example.uade.tpo.practica2back.controllers;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.uade.tpo.practica2back.Service.ReunionService;
import com.example.uade.tpo.practica2back.entity.Reunion;

@RestController
@RequestMapping("/reuniones")
@CrossOrigin(origins = "*")


public class ReunionController {

    private final ReunionService reunionService;

    public ReunionController(ReunionService reunionService) {
        this.reunionService = reunionService;
    }

    @GetMapping
    public List<Reunion> getReuniones() {
        return reunionService.getAllReuniones();
    }

    @PostMapping
    public ResponseEntity<Reunion> createReunion(@RequestBody Reunion reunion) {
        try {
            Reunion nuevaReunion = reunionService.createReunion(reunion);
            return new ResponseEntity<>(nuevaReunion, HttpStatus.CREATED);
        } catch (IllegalStateException e) {
            return new ResponseEntity<>(HttpStatus.CONFLICT);
        }
    }

    @PutMapping("/{id}")
    public ResponseEntity<Reunion> updateReunion(@PathVariable Long id, @RequestBody Reunion updatedReunion) {
        try {
            Reunion reunionActualizada = reunionService.updateReunion(id, updatedReunion);
            return new ResponseEntity<>(reunionActualizada, HttpStatus.OK);
        } catch (IllegalStateException e) {
            return new ResponseEntity<>(HttpStatus.CONFLICT);
        }
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteReunion(@PathVariable Long id) {
        reunionService.deleteReunion(id);
        return new ResponseEntity<>(HttpStatus.NO_CONTENT);
    }
}
