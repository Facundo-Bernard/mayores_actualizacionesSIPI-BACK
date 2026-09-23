package com.example.uade.tpo.practica2back;

import java.io.File;
import java.nio.file.Files;
import java.util.List;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class Practica2backApplication {

	public static void main(String[] args) {
		cargarDotEnv();
		SpringApplication.run(Practica2backApplication.class, args);
	}

	private static void cargarDotEnv() {
		try {
			File envFile = new File(".env");
			if (envFile.exists() && envFile.isFile()) {
				List<String> lines = Files.readAllLines(envFile.toPath());
				for (String line : lines) {
					line = line.trim();
					if (line.isEmpty() || line.startsWith("#")) continue;
					int idx = line.indexOf('=');
					if (idx > 0) {
						String key = line.substring(0, idx).trim();
						String value = line.substring(idx + 1).trim();
						if (System.getProperty(key) == null && System.getenv(key) == null) {
							System.setProperty(key, value);
						}
					}
				}
			}
		} catch (Exception ignored) {
		}
	}

}
