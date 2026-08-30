# 🍋 Guía de Comandos — El Kiosquito de Lemon (v3.2)

## 🏪 Mostrador y Kiosquito
- `/setup [canal]` — *(Admin)* Configura el canal oficial del kiosquito y publica el mensaje fijo persistente e interactivo.
- `/kiosquito` — Abre el mostrador interactivo con el catálogo de productos (solo visible para vos).
- `/productos` — Catálogo completo con precios, ofertas activas, XP y stock en tiempo real.
- `/comprar <producto> [cantidad]` — Comprar golosinas de contado en el kiosquito sujeto al stock disponible.
- `/mochila [usuario]` — Ver tu inventario y consumir golosinas directamente desde el menú.
- `/consumir <producto> [cantidad]` — Consumir productos disponibles de tu mochila para ganar XP. Envía un anuncio público en el chat.
- `/regalar <usuario> <producto> [cantidad]` — Regalarle golosinas de tu mochila a otro miembro del servidor.

## 🔥 Sistema de Stock Limitado y Ofertas
- **Stock Corto por Jornada**: Cada vez que el kiosco abre, cada producto inicia con un stock limitado (ej. 3 a 7 unidades).
- **Reposición Gradual**: Cada 30 minutos el kiosquero repone stock de productos escasos. También se repone cuando los usuarios completan changuitas de orden/reposición.
- **Probabilidad de Ofertas**: Al abrir la jornada, hay un **20% de probabilidad** de que el kiosquero lance **Promos de la Jornada** (con 25% a 40% de descuento en productos seleccionados), anunciadas en el mensaje fijo del canal.

## 🧹 Changuitas y Minijuegos Interactivos
- `/changuitas` o `/changuita` — Abre la bolsa de trabajo del kiosquito. Cada trabajo incluye minijuegos interactivos arcade en vivo con botones y tableros. Cooldown: 30 minutos.
  - **Fácil ($150 – $300 | 10–20 XP):**
    - 🧹 **Barrer el piso (Grilla 3×3):** Limpiar las casillas de basura (`🍂`, `🧻`) sin tocar la cucaracha `🪳`.
    - Sacar la basura, Limpiar la entrada/vereda, Sacar telarañas, Desinfectar mostradores.
  - **Normal ($300 – $600 | 20–35 XP):**
    - 🧮 **Cobrar en la caja (Cálculo mental de vuelto):** El cliente paga con un billete y vos debés armar el vuelto exacto con botones de plata sin que el bot te diga el resultado.
    - 🍫 **Ordenar productos (Simón Dice de Góndola):** Memorizar la secuencia de 4 golosinas y acomodarlas en orden.
    - 🪟 **Limpiar vidrios (Secador en cadena):** Pasar la espátula secavidrios en el orden exacto (1 ➔ 2 ➔ 3 ➔ 4).
    - 🥤 **Atajar las Manaos (Arcade de reflejos):** Mover la canasta con `⬅️` y `➡️` para atajar las botellas que caen del camión.
    - 📦 **Buscaminas del Depósito (Riesgo):** Abrir cajas de mercadería acumulando plata con la opción de retirarte seguro o arriesgarte a que salte la rata.
    - Trapear, Limpiar estantes, Limpiar derrames, Reponer artículos de limpieza.
  - **Pesada ($600 – $1.000 | 35–60 XP):**
    - 🏋️ **Mover cajas pesadas (Barra de Fuerza QTE):** Presionar rápido `¡HACER FUERZA!` para llenar la barra al 100% esquivando el botón trampa.
    - ❄️ **Reparar la Heladera (Minijuego Técnico - Evento Raro):** Conectar los cables correctos y calibrar el termostato a frío (0°C a 4°C).
    - Ordenar el depósito, Acomodar cajones de bebidas, Limpiar la heladera, Limpieza profunda del depósito.
  - ⚠️ *¡Si te equivocás en un paso o juego, te rajan del laburo sin un mango y con 30 min de sanción!*

## 🎰 Lotería y Azar
- `/raspadita` — Jugar a la Raspadita del Kiosquito en una grilla interactiva 3×3. Costo: **$1.000** ($750 para Suscriptores y Boosters).
  - 🍋 **`🍋 🍋 🍋` (2%):** ¡POZO ACUMULADO DEL SERVIDOR! (Arranca en $10.000 y acumula +$400 de cada tirada).
  - 💎 **`💎 💎 💎` (8%):** Ganás **$3.500** en efectivo.
  - 🍫 **`🍫 🍫 🍫` (12%):** Ganás **$1.500** + 1 Alfajor Jorgito a tu mochila.
  - ❌ **Sin Premio (78%):** Se suman **+$400** al Pozo Acumulado.
- `/quiniela [numero] [apuesta]` — Apostar a un número de la suerte (del 1 al 50) para el sorteo diario de las 22:00 hs (Máximo 3 apuestas por usuario por sorteo).
  - 🎯 **Acierto a la cabeza (Número exacto):** Paga **x35 veces** la apuesta.
  - 🤏 **Pegó en el palo (Número anterior o siguiente):** Paga **x2 veces** la apuesta.
  - 🔔 Asigna el rol `@Quinielero` automáticamente para notificar en el sorteo en vivo.

## 💵 Economía y Progresión
- `/perfil [usuario]` — Saldo en billetera, XP acumulada, deuda y barra de progreso del fiado.
- `/saldo` — Resumen rápido de dinero y deuda.
- `/diario` — Recompensa diaria en plata y XP cada 24 horas.
- `/fiado <producto> [cantidad]` — Comprar fiado anotando en la libretita (disponible a partir de 2.000 XP).
- `/pagar_deuda [monto]` — Pagar total o parcialmente la deuda pendiente con el kiosquito.

## 🏆 Comunidad y Horarios
- `/ranking` — Top 10 de clientes con más experiencia en el kiosquito.
- `/horario` — Horarios habituales de apertura y cierre (Hora Argentina).
- `/ayuda` — Guía completa de comandos.

## 🛠️ Administración
- `/setup [canal]` — Configura el canal exclusivo y fija el panel interactivo del bot.
- `/admin_abrir [minutos]` — Abre el kiosquito manualmente (con minutos o hasta cierre manual).
- `/admin_cerrar` — Cierra la apertura manual o la jornada, generando el resumen con deudores y productos vendidos, y limpiando anuncios de consumo de esa jornada.
- `/admin_reponer [cantidad]` — Repone stock a todos los productos del kiosquito inmediatamente.
- `/admin_dar_dinero <usuario> <cantidad>` — Modifica el dinero de un usuario.
- `/admin_dar_xp <usuario> <cantidad>` — Modifica la XP de un usuario.
- `/admin_resetear <usuario>` — Resetea los datos e inventario de un usuario.
- `/autolimpieza <activado:True/False>` — Activa o desactiva el borrado automático de mensajes comunes en el canal del kiosco.
- `/admin_sortear_quiniela` — Forzar o probar el sorteo de la Quiniela en vivo con animación de bolillero.
- `/admin_quiniela_automatica <activado:True/False>` — Activa o desactiva los sorteos y avisos automáticos de las 22:00 hs.

## 💬 Experiencia Automática
- Los usuarios reciben entre 3 y 7 XP al participar activamente en el chat (con un cooldown de 1 minuto).

## 🛡️ Limpieza del Chat
- Todas las interacciones de botones, compras y consultas de perfil/saldo responden de forma efímera (`ephemeral=True`) y se autodestruyen tras 3 minutos de inactividad, manteniendo el canal oficial siempre impecable con su mensaje fijo.
- Los anuncios públicos de consumo generados durante la jornada se eliminan automáticamente cuando el kiosquito cierra.


