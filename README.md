# 🍋 El Kiosquito de Lemon — Bot de Discord

Versión local con economía, XP, inventario y sistema de fiado.

## Lo importante

El kiosquito abre:

- 08:00 a 13:00
- 17:00 a 00:00

Usa la zona horaria `America/Argentina/Buenos_Aires`.

El **fiado se desbloquea al llegar a 2.000 XP**.

## Instalación rápida

### 1. Instalar Python

Usá Python 3.11 o superior.

### 2. Instalar las dependencias

Hacé doble clic en:

`1_INSTALAR.bat`

### 3. Configurar el token

Copiá `.env.example` y renombrá la copia a `.env`.

Abrilo y poné:

`DISCORD_TOKEN=TU_TOKEN`

Opcionalmente agregá el ID de tu servidor para que los slash commands aparezcan instantáneamente:

`TEST_GUILD_ID=123456789012345678`

Para copiar el ID del servidor:
Discord > Ajustes > Avanzado > Modo desarrollador.
Después click derecho al servidor > Copiar ID del servidor.

### 4. Invitar al bot

En Discord Developer Portal, al generar el enlace del bot, usá:

- `bot`
- `applications.commands`

Permisos mínimos recomendados:

- View Channels
- Send Messages
- Manage Messages (para limpiar consumos y renovar el panel)
- Manage Channels (para crear automáticamente el canal #el-kiosquito-de-lemon)
- Embed Links
- Read Message History

**No hace falta activar Message Content Intent.**
El sistema de XP por actividad no lee el contenido de los mensajes.

### 5. Iniciar

Doble clic:

`2_INICIAR.bat`

## Primeras pruebas

Como administrador podés probar el sistema sin esperar:

`/admin_dar_xp @TuUsuario 2000`

Después probá `/fiado`.

También podés darte dinero:

`/admin_dar_dinero @TuUsuario 10000`

## Archivos fáciles de editar

- `config.json`: horarios, XP requerida, límite de deuda y recompensas.
- `products.json`: productos, precios y XP.
- `data/kiosquito.db`: base de datos creada automáticamente.

No edites el archivo `.db` a mano.

## Abrir antes de horario

Un administrador puede usar:

`/admin_abrir`

Eso lo deja abierto manualmente hasta usar:

`/admin_cerrar`

También se puede abrir por un tiempo concreto:

`/admin_abrir minutos:30`

La apertura manual queda guardada en la base de datos, así que no se pierde si reiniciás el bot.

## v3.0 — Panel Fijo, Changuitas y Resumen de Jornadas

- `/setup [canal]`: Selección y fijación de panel interactivo persistente en el canal exclusivo.
- **Mensaje Fijo Automático**: Muestra el mostrador abierto en horario comercial y cerrado al terminar, con resumen de ventas y lista de deudores de la jornada.
- **16 Changuitas con Botones**: Mini-juegos interactivos por pasos para realizar tareas del kiosco (Fácil $150-300, Normal $300-600, Pesada $600-1000).
- `/consumir` con Autocomplete Inteligente: Solo muestra productos comprados con stock disponible en tu mochila.
- **Anuncios Públicos y Limpieza**: Al consumir, se anuncia en el chat; al finalizar la jornada, el bot limpia automáticamente todos los anuncios de consumo para mantener el chat 100% ordenado.
- **Interacciones Efímeras**: Comandos y menús son visibles únicamente para el usuario que interactúa y se autodestruyen a los 3 minutos de inactividad.

