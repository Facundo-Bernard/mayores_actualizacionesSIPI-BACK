"# mayores_actualizacionesSIPI-BACK" 

.\mvnw.cmd spring-boot:run

paso a paso 

generar el .jar
.\mvnw.cmd clean package -DskipTests

crear scrip que lea .env
iniciar.ps1

# ========================================================
# Script para cargar variables de .env y levantar Spring Boot
# ========================================================
$envFile = Join-Path $PSScriptRoot ".env"

if (-not (Test-Path $envFile)) {
    Write-Error "No se encontro el archivo .env en la carpeta."
    exit 1
}

Write-Host "Cargando variables de entorno desde .env..." -ForegroundColor Cyan

# Lee el archivo .env linea por linea ignorando comentarios y lineas vacias
Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not ($line.StartsWith("#"))) {
        $parts = $line -split '=', 2
        if ($parts.Count -eq 2) {
            $name = $parts[0].Trim()
            $value = $parts[1].Trim()
            [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

# Configuracion de perfil produccion
$env:SPRING_PROFILES_ACTIVE = "production"
$env:SERVER_FORWARD_HEADERS_STRATEGY = "framework"

Write-Host "Iniciando aplicacion Spring Boot..." -ForegroundColor Green
java -jar (Join-Path $PSScriptRoot "app.jar")


