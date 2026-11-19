# Manual de usuario

Este manual explica cómo usar el PoC Valkiria InvGate según tu papel:

- **Solicitante:** pide ayuda en el chat web.
- **Manager:** aprueba o rechaza solicitudes desde Microsoft Teams.
- **Agente o administrador:** sigue la operación en el dashboard y gestiona aprobaciones por API.

La instalación y la configuración están en el [Manual técnico](MANUAL_TECNICO.md).

---

## 1. Solicitante: el chat web

### 1.1 Abrir el chat

Abre la dirección que te haya dado el equipo de TI, por ejemplo `http://localhost:8000/`.

Si la instalación usa claves de acceso, escribe la tuya en el campo **Clave para la API**. El navegador la recuerda. Sin una clave válida, el chat responde que no tienes permiso.

### 1.2 Pedir ayuda

Describe tu problema en una frase en el cuadro **Describe tu problema…** y pulsa **Enviar**. Ejemplos:

| Escribe | Qué hace el PoC |
|---|---|
| «Olvidé mi contraseña de red» | Ticket de **acceso** con prioridad **alta** y el artículo de cómo restablecerla |
| «Necesito instalar Figma» | Ticket de **software** que **requiere aprobación** de tu manager |
| «Mi portátil no enciende» | Ticket de **hardware** con prioridad **alta** |
| «La aplicación de nómina está caída para todos los usuarios» | Incidente de **infraestructura** con prioridad **crítica** y escalado a Nivel 3 |
| Cualquier otra consulta | Ticket **general** con prioridad media |

### 1.3 Qué ves en pantalla

- **Agentes (semáforo):** los 8 agentes del PoC trabajan en orden. Cada uno se pone en verde (ha terminado bien), amarillo (aviso, por ejemplo «esperando aprobación») o rojo (no ha podido hacer su parte). Se actualizan en vivo.
- **Ticket:** el número del ticket creado en InvGate, su categoría y su prioridad.
- **Respuesta:** un resumen de lo que se ha hecho y, si existe, un artículo de la base de conocimiento que puede resolverlo sin esperar.

### 1.4 Solicitudes que necesitan aprobación

Si tu solicitud requiere aprobación, por ejemplo instalar software:

1. El chat te dice que el ticket **está esperando la aprobación de tu manager**.
2. Tu manager recibe la solicitud en Teams.
3. Cuando decide, el panel **Ticket** muestra **Aprobada** o **Rechazada**, quién decidió y sus **observaciones**.
4. La decisión y las observaciones también quedan registradas en el ticket de InvGate.

No tienes que recargar la página: el chat consulta el estado solo. La aprobación vence a las 72 horas si nadie decide.

---

## 2. Manager: aprobar desde Microsoft Teams

### 2.1 Primera vez

1. En Teams, busca la aplicación **Help Desk IA** y abre un chat con ella.
2. Escribe **«hola»**. El bot responde con un mensaje de bienvenida.

Este paso es necesario una sola vez. Así el bot sabe dónde escribirte cuando llegue una solicitud.

### 2.2 Decidir una solicitud

Cuando alguien pide algo que requiere tu aprobación, recibes una tarjeta **Aprobación requerida** con:

- El número de ticket y lo que se pide.
- Quién debe aprobar y en cuántas horas vence.
- Un campo **Observaciones (opcional)**.

Para decidir:

1. Escribe una observación si quieres, por ejemplo «Solo la licencia anual». El solicitante la verá.
2. Pulsa **Aprobar** o **Rechazar**.

Qué pasa después:

- La tarjeta cambia a **Solicitud aprobada** o **Solicitud rechazada**, con tu observación y **sin botones**.
- El bot confirma con «Aprobación APR-… aprobada» o «… rechazada».
- En InvGate, la aprobación del ticket queda registrada con tu voto y la observación se añade como comentario.

### 2.3 Mensajes que puedes ver

| Mensaje | Significado |
|---|---|
| «Esta aprobación ya fue resuelta (approved)» | Ya se decidió antes. El segundo clic no cambia nada. |
| «Solo el manager asignado puede decidir esta aprobación.» | Tu cuenta no es la del manager configurado para el PoC. |
| «La aprobación expiró.» | Pasó el plazo, 72 horas por defecto. El solicitante tendrá que volver a pedirlo. |
| «No se pudo registrar la decisión en el ticket. Inténtalo de nuevo.» | InvGate no respondió. La solicitud sigue pendiente y puedes volver a pulsar. |
| «Tarjeta no vigente» | La tarjeta es de una versión anterior del bot. Ignórala. |

---

## 3. Agente y administrador

### 3.1 Dashboard de operación

Abre `/dashboard.html`, por ejemplo `http://localhost:8000/dashboard.html`. Si la instalación usa claves, necesitas una con rol **agent** o **admin**. El dashboard usa la misma clave que escribiste en el chat, así que escríbela primero allí.

El dashboard muestra la telemetría de las últimas horas en cuatro bloques:

| Bloque | Qué muestra |
|---|---|
| **Negocio / ITSM** | Conversaciones, tickets creados, categorías, prioridades, escalaciones por nivel y aprobaciones |
| **Rendimiento** | Latencia del chat (p50, p95 y máxima), latencia por agente y peticiones limitadas |
| **Costos** | Llamadas al modelo de lenguaje, tokens y costo estimado por modelo |
| **Orquestación** | Estados verde, amarillo y rojo por agente, y veces que el modelo no respondió |

### 3.2 Gestionar aprobaciones por API

Sirve cuando no se usa el bot de Teams, por ejemplo con `NOTIFY_CHANNEL=webhook`.

```bash
# Listar aprobaciones (rol agent o admin)
curl -H "Authorization: Bearer <clave>" http://localhost:8000/api/approvals

# Decidir una aprobación (rol admin)
curl -X POST http://localhost:8000/api/approvals/APR-xxxx/decision \
  -H "Authorization: Bearer <clave>" -H "Content-Type: application/json" \
  -d '{"decision": "approved", "note": "Usa la licencia del equipo", "user_email": "manager@empresa.com"}'
```

### 3.3 Escalar una conversación a mano

```bash
curl -X POST http://localhost:8000/api/escalate \
  -H "Authorization: Bearer <clave>" -H "Content-Type: application/json" \
  -d '{"conversation_id": "<id>", "reason": "El usuario pide hablar con una persona"}'
```

### 3.4 Comprobar la auditoría

Con rol **admin**, `GET /api/audit/verify` comprueba que nadie ha editado ni borrado el registro de auditoría.

---

## 4. Preguntas frecuentes

**¿Dónde veo mis tickets?**
En InvGate, con el número que te da el chat. El PoC crea los tickets allí y no guarda una copia propia.

**¿Por qué mi ticket sigue «esperando aprobación» en InvGate si el manager ya aprobó?**
La aprobación sí queda aceptada. El estado del ticket lo mueve el flujo de trabajo de InvGate o un agente, no el PoC. En la sección **Aprobaciones** del ticket verás el voto del manager.

**¿El PoC guarda lo que escribo?**
En la telemetría y la auditoría, los correos y teléfonos se ocultan. Tu texto solo se envía a Langfuse, con datos personales ocultos, si el administrador lo activa (`LOG_USER_CONTENT=true`).

**El semáforo de un agente está en amarillo con «LLM no disponible». ¿Es un problema?**
No. El modelo de lenguaje no respondió y el PoC usó su clasificador de respaldo. La solicitud se procesa igual.
