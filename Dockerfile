# ==========================================
# ETAPA 1: Compilación (Build)
# ==========================================
FROM maven:3.9.6-eclipse-temurin-21-alpine AS build
WORKDIR /app

# Copiamos el descriptor de dependencias e instalamos en caché
COPY pom.xml .
RUN mvn dependency:go-offline -B

# Copiamos el código fuente e invocamos el empaquetado omitiendo tests
COPY src ./src
RUN mvn clean package -DskipTests

# ==========================================
# ETAPA 2: Ejecución (Runtime ligero)
# ==========================================
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

# Copiamos el archivo .jar generado en la etapa anterior
COPY --from=build /app/target/*.jar app.jar

# Exponemos el puerto de la aplicación (3000 para IIS Proxy)
EXPOSE 3000

# Arrancamos el JAR
ENTRYPOINT ["java", "-jar", "app.jar"]