1) Arquitectura (resumen rápido)

Broker / Server (en la nube o en tu LAN): crea sesiones y tokens (AES-256 GCM). Mantiene la lista de tokens válidos y estados (lectura/esperando-control/concedido). También retransmite datos si cliente y host no pueden hacer P2P (recomendado empezar con este modelo).

Host (la máquina que compartes): captura pantalla periódicamente, las comprime (JPEG), y envía al servidor. Aplica eventos de entrada (mouse/teclado) solo si la sesión tiene control concedido.

Viewer / Cliente: recibe imágenes, muestra en ventana; envía petición de control; si el servidor le concede control, envía eventos de entrada.

Canal: websocket(s) sobre TLS (wss). Además del TLS (transporte), el servidor usa un token AES-GCM para autenticar/autorizar la sesión (lo pediste explícito).

Por qué usar websockets: simple para enviar binarios y mensajes JSON en tiempo real.

2) Consideraciones de seguridad (no las saltees)

Usar TLS (SSL) para websockets (wss://). Nunca desplegar sin TLS en Internet.

AES-GCM para tokens (autenticidad + confidencialidad). No uses AES-ECB.

Rotación y expiración de tokens (ej: 5–60 min según necesidad).

Autorización explícita para control: el host (o el servidor si confías en él) debe aprobar cada cesión de control.

Registro / audit log para saber quién se conectó.

Evita ejecutar al host con privilegios innecesarios. En Windows, el envío de eventos de entrada puede requerir privilegios.

Para producción considerar: autenticación por usuario + 2FA, límites de conexión, protección contra fuerza bruta, y revisión legal (soporte remoto puede tener implicaciones de privacidad).
