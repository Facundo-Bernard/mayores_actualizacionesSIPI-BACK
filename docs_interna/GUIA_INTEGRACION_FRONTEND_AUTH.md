# Guía de Integración Backend ⇄ Frontend para Agente de IA y Desarrolladores
## Proyecto: Mayores Actualizaciones - Plataforma de Cursos para Adultos Mayores

- **Fecha:** Septiembre de 2026
- **Audiencia:** Agente de IA del Frontend / Desarrolladores Frontend React
- **Backend Base URL:** `http://localhost:8080` (en local) o variable de entorno `VITE_API_URL`
- **CORS:** Habilitado para `http://localhost:5173` y cualquier origen en desarrollo.

---

## 1. Visión General de la Experiencia de Acceso

La plataforma está diseñada específicamente para **adultos mayores**, por lo que se eliminaron las contraseñas complejas y los flujos difíciles. El frontend debe soportar **dos formas principales de acceso inmediato**:

1. **Acceso por Código (PIN numérico de 6 dígitos):**
   - El alumno entra a la página principal `/`.
   - Si no tiene sesión activa, ve una caja de texto grande y clara: *"Ingresá tu código de alumno (6 números)"*.
   - Escribe su código (ej. `748291`), presiona el botón grande y entra directamente a sus cursos.
2. **Acceso por Magic Link (Enlace de WhatsApp o Correo):**
   - El alumno hace clic en el enlace que le mandaron por WhatsApp o email:  
     `http://localhost:5173/acceso?token=eyJhbGciOi...`
   - La pantalla `/acceso` lee el token, lo valida con el backend y le guarda la sesión permanente.
3. **Registro directo desde la web:**
   - Para nuevos registros desde formulario o checkout, se crea el usuario y se auto-inicia sesión con el token devuelto.

---

## 2. Contratos de API (Endpoints en `AuthController`)

### 2.1. Ingreso con Código Numérico (PIN)
- **Método:** `POST`
- **Ruta:** `/api/auth/ingresar-codigo`
- **Cabeceras:** `Content-Type: application/json`

#### Request Body:
```json
{
  "codigo": "748291"
}
```

#### Respuesta Exitosa (`200 OK`):
```json
{
  "success": true,
  "message": "Acceso concedido exitosamente.",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwibmFtZSI6Ik1hcnRhIEfDs21leiIsImJsYWNrIjp0cnVlfQ...",
  "user": {
    "id": 1,
    "name": "Marta Gómez",
    "email": "marta.gomez@gmail.com",
    "codigoAcceso": "748291",
    "tipoUsuario": 1,
    "black": true,
    "dateStart": null,
    "dateEnd": null
  }
}
```

#### Respuestas de Error:
- **`404 Not Found`**:
  ```json
  {
    "success": false,
    "message": "Código de acceso inválido. Verifique el código e intente nuevamente.",
    "token": null,
    "user": null
  }
  ```
- **`403 Forbidden` (Cuenta inactiva / pausada)**:
  ```json
  {
    "success": false,
    "message": "Tu cuenta se encuentra pausada o inactiva. Por favor comunicate con administración.",
    "token": null,
    "user": null
  }
  ```

---

### 2.2. Validación de Magic Link (Token en URL)
- **Método:** `POST`
- **Ruta:** `/api/auth/verificar-token`
- **Cabeceras:** `Content-Type: application/json`

#### Request Body:
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Respuesta Exitosa (`200 OK`):
```json
{
  "success": true,
  "valid": true,
  "user": {
    "id": 1,
    "name": "Marta Gómez",
    "email": "marta.gomez@gmail.com",
    "codigoAcceso": "748291",
    "tipoUsuario": 1,
    "black": true,
    "activo": true,
    "dateStart": "2026-09-11T16:22:47",
    "dateEnd": null
  },
  "message": "Token validado exitosamente."
}
```

#### Respuestas de Error:
- **`401 Unauthorized`**:
  ```json
  {
    "success": false,
    "valid": false,
    "user": null,
    "message": "El token es inválido o ha expirado."
  }
  ```
- **`403 Forbidden` (Cuenta inactiva)**:
  ```json
  {
    "success": false,
    "valid": false,
    "user": null,
    "message": "Acceso deshabilitado. Tu cuenta se encuentra inactiva."
  }
  ```

---

### 2.3. Registro de Nuevo Alumno desde la Web
- **Método:** `POST`
- **Ruta:** `/api/auth/register`
- **Cabeceras:** `Content-Type: application/json`

#### Request Body:
```json
{
  "name": "Carlos Rodríguez",
  "email": "carlos.rodriguez@gmail.com",
  "password": "",
  "telefono": "+5491133445566",
  "codigoAcceso": "opcional (si no se envía, el backend genera uno único de 6 dígitos)",
  "black": false
}
```

#### Respuesta Exitosa (`201 Created`):
```json
{
  "success": true,
  "message": "Usuario registrado con éxito.",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 2,
    "name": "Carlos Rodríguez",
    "email": "carlos.rodriguez@gmail.com",
    "codigoAcceso": "519302",
    "tipoUsuario": 1,
    "black": false,
    "dateStart": null,
    "dateEnd": null
  }
}
```

---

### 2.4. Despachar Acceso por Correo y WhatsApp (Operador/Admin)
- **Método:** `POST`
- **Ruta:** `/api/admin/enviar-acceso-correo`
- **Cabeceras:** `Content-Type: application/json`

#### Request Body:
```json
{
  "name": "Marta Gómez",
  "email": "marta.gomez@gmail.com",
  "telefono": "+5491122334455",
  "black": true
}
```

#### Respuesta Exitosa (`200 OK`):
```json
{
  "success": true,
  "message": "Correo de acceso enviado exitosamente a marta.gomez@gmail.com",
  "data": {
    "userId": 1,
    "email": "marta.gomez@gmail.com",
    "codigoAcceso": "748291",
    "accessUrl": "http://localhost:5173/acceso?token=eyJhbGciOi..."
  }
}
```
> **Nota para WhatsApp:** El operador toma `data.accessUrl` y `data.codigoAcceso` y se los puede enviar por chat al alumno en un solo mensaje.

#### Error si la cuenta está inactiva (`400 Bad Request`):
```json
{
  "success": false,
  "message": "No se puede generar o enviar enlace de acceso para una cuenta inactiva. Active la cuenta primero en el panel.",
  "data": null
}
```

---

## 3. Otros Endpoints del Backend

### Progreso del Alumno (`ProgresoUsuarioController`)
* **Obtener progreso del alumno:** `GET /progreso/obtenerUsuario/{usuarioId}`
* **Actualizar progreso de un curso:** `PUT /progreso/actualizar/{usuarioId}/{cursoId}`
  ```json
  {
    "progreso": 80,
    "completado": false,
    "examenPuntos": 0
  }
  ```
* **Crear progreso inicial:** `POST /progreso/crear`
  ```json
  {
    "progreso": 0,
    "completado": false,
    "examenPuntos": 0,
    "cursoId": 1,
    "usuarioId": 1
  }
  ```

### Suscripción Black (`UsuarioController`)
* **Activar/Alternar suscripción Black:** `PUT /usuario/{usuarioId}/suscribirse`

---

## 4. Guía de Implementación en el Frontend React

### 4.1. Persistencia de Sesión (Redux + LocalStorage)
Al recibir un `token` y `user` (ya sea por código, enlace o registro):
```javascript
// Guardar permanentemente en la computadora del alumno
localStorage.setItem('token', token);
localStorage.setItem('user', JSON.stringify(user));

// Actualizar store de Redux
dispatch({
  type: 'LOGIN',
  payload: {
    id: user.id,
    name: user.name,
    black: user.black,
    codigoAcceso: user.codigoAcceso
  }
});
```

Al cargar la aplicación (ej. en `App.jsx` o en la inicialización de Redux), leer `localStorage.getItem('token')` y `localStorage.getItem('user')` para que el alumno **nunca tenga que volver a iniciar sesión**.

### 4.2. Pantalla `/acceso` (Receptor del Magic Link)
```jsx
// src/PAGINAS/AccesoToken.jsx
import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useDispatch } from 'react-redux';

export default function AccesoToken() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!token) {
      setError("Enlace de acceso incompleto.");
      return;
    }

    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8080';

    fetch(`${apiUrl}/api/auth/verificar-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token })
    })
      .then(res => res.json())
      .then(data => {
        if (data.valid && data.user) {
          localStorage.setItem('token', token);
          localStorage.setItem('user', JSON.stringify(data.user));
          dispatch({ type: 'LOGIN', payload: data.user });
          navigate('/cursos'); // O a la pantalla principal
        } else {
          setError(data.message || "El enlace de acceso es inválido o ha expirado.");
        }
      })
      .catch(() => setError("No se pudo conectar con el servidor."));
  }, [token]);

  if (error) {
    return (
      <div className="p-8 text-center">
        <h2 className="text-2xl font-bold text-red-600">Aviso</h2>
        <p className="text-lg mt-2 text-gray-700">{error}</p>
        <button onClick={() => navigate('/')} className="mt-4 px-6 py-3 bg-blue-600 text-white rounded-lg text-lg">
          Ir al Inicio
        </button>
      </div>
    );
  }

  return (
    <div className="p-12 text-center text-xl font-bold text-blue-800">
      Entrando a tus cursos, aguarda un momento...
    </div>
  );
}
```

### 4.3. Formulario de Código de Acceso (En la Home `/`)
Para alumnos que entran sin hacer clic en el email:
```jsx
const handleIngresarCodigo = async (codigoInput) => {
  try {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8080';
    const res = await fetch(`${apiUrl}/api/auth/ingresar-codigo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo: codigoInput.trim() })
    });

    const data = await res.json();
    if (data.success && data.token) {
      localStorage.setItem('token', data.token);
      localStorage.setItem('user', JSON.stringify(data.user));
      dispatch({ type: 'LOGIN', payload: data.user });
      navigate('/cursos');
    } else {
      alert(data.message || "Código no encontrado. Por favor verifique los 6 números.");
    }
  } catch (err) {
    alert("Error de conexión. Intente nuevamente.");
  }
};
```

---

## 4.4. Autenticación de Sistemas / Operadores (Torre de Control)

Para que el personal de sistemas pueda acceder al panel de gestión de usuarios (`PanelAltasSistemas.jsx`), se cuenta con un inicio de sesión restringido a administradores.

- **Método:** `POST`
- **Ruta:** `/api/auth/login-sistemas` (o `/api/auth/login-admin`)
- **Cabeceras:** `Content-Type: application/json`

#### Credenciales por defecto (creadas automáticamente si no existen):
- **Email:** `admin@sistemas.com`
- **Contraseña:** `admin123`
- **Rol:** `2` (ROL_ADMIN)

#### Request Body:
```json
{
  "email": "admin@sistemas.com",
  "password": "admin123"
}
```

#### Respuesta Exitosa (`200 OK`):
```json
{
  "success": true,
  "message": "Inicio de sesión de sistemas exitoso.",
  "token": "eyJhbGciOiJIUzUxMiJ9...",
  "user": {
    "id": 3,
    "name": "Operador Sistemas",
    "email": "admin@sistemas.com",
    "codigoAcceso": "999999",
    "tipoUsuario": 2,
    "black": true,
    "dateStart": "2026-09-11",
    "dateEnd": null
  }
}
```

#### Respuestas de Error:
- **`401 Unauthorized`**: Contraseña errónea o usuario no encontrado.
- **`403 Forbidden`**: El usuario existe pero no tiene rol de administrador (`tipoUsuario !== 2`).

---

## 4.5. Consulta de Usuarios Paginada y Diccionario de Filtros

- **Método:** `GET`
- **Ruta:** `/usuario`
- **Parámetros de consulta (Query Params):**
  - `limit` (número, default: `20`): Cantidad de usuarios por página.
  - `skip` (número, default: `0`): Cantidad de registros a omitir (desplazamiento / offset).
  - `nombre` (string, opcional): Búsqueda insensible a mayúsculas/minúsculas en `name` o `email`.
  - `fechaDesde` (formato `YYYY-MM-DD`, opcional): Filtra usuarios cuya fecha de alta (`dateStart`) sea mayor o igual.
  - `fechaHasta` (formato `YYYY-MM-DD`, opcional): Filtra usuarios cuya fecha de alta sea menor o igual.
  - `tipoUsuario` (número, opcional): `1` para sólo alumnos, `2` para administradores.
  - `black` (booleano, opcional): `true` para miembros Club Black, `false` para estándar.
  - `orden` (string, opcional): `"desc"` (predeterminado, más recientes primero) o `"asc"`.

#### Ejemplo de URL:
`GET http://localhost:8080/usuario?limit=10&skip=0&nombre=juan&fechaDesde=2026-09-01`

#### Respuesta (`200 OK`):
```json
{
  "total": 45,
  "skip": 0,
  "limit": 10,
  "items": [
    {
      "id": 2,
      "name": "Juan Pepe",
      "email": "montinahuel2@gmail.com",
      "codigoAcceso": "143672",
      "tipoUsuario": 1,
      "black": false,
      "dateStart": "2026-09-11",
      "dateEnd": null
    }
  ]
}
```

#### Ejemplo de integración en `PanelAltasSistemas.jsx`:
```javascript
const fetchUsuarios = async ({ skip = 0, limit = 20, nombre = '', fechaDesde = '', fechaHasta = '' }) => {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString()
  });

  if (nombre.trim()) params.append('nombre', nombre.trim());
  if (fechaDesde) params.append('fechaDesde', fechaDesde);
  if (fechaHasta) params.append('fechaHasta', fechaHasta);

  const res = await fetch(`http://localhost:8080/usuario?${params.toString()}`);
  const data = await res.json();
  
  // data contiene: { total: 45, skip: 0, limit: 20, items: [...] }
  return data;
};
```

---

## 4.6. Alternar Estado Activo / Inactivo de un Usuario

Permite pausar o reactivar el acceso de un alumno con un solo clic desde la Torre de Control.

- **Método:** `PUT`
- **Ruta:** `/usuario/{id}/toggle-activo`
- **Respuesta Exitosa (`200 OK`):**
```json
{
  "success": true,
  "message": "Estado de actividad actualizado con éxito",
  "activo": false
}
```
> **Efecto Inmediato:** Al pasar a `activo: false`, el usuario no podrá iniciar sesión por código (PIN), los enlaces previos de Magic Link serán rechazados con `403 Forbidden`, y no se podrán generar nuevos enlaces hasta que vuelva a activarse.

---

## 5. Recomendaciones de Accesibilidad (Adultos Mayores)

1. **Tipografía grande:** Tamaños mínimos de `18px` a `22px` para textos y `24px` a `32px` para números de código.
2. **Alto contraste:** Fondos claros con textos oscuros (`#0f172a` o `#1e293b`).
3. **Botones gigantes y táctiles:** Con padding amplio (`py-4 px-8`), esquinas redondeadas y colores bien identificables (azul `#2563eb` o verde `#16a34a`).
4. **Mensajes comprensibles:** Evitar términos técnicos como *"Token expired"* o *"Error 401"*. En su lugar: *"El enlace ha vencido. Solicitá uno nuevo a tu asesor telefónico"*.
