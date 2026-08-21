# 🚀 Guía de Despliegue en Northflank — El Kiosquito de Lemon

Esta guía te explica paso a paso cómo crear tu bot en Discord, subir tu código a GitHub y ponerlo a funcionar **24/7 en Northflank** con base de datos persistente.

---

## 📋 Paso 1: Crear y Configurar el Bot en Discord Developer Portal

1. Entrá a [Discord Developer Portal](https://discord.com/developers/applications) e iniciá sesión.
2. Hacé clic en el botón azul **"New Application"**, poné de nombre `El Kiosquito de Lemon` y aceptá.
3. Andá a la pestaña **Bot** en el menú izquierdo:
   - Hacé clic en **"Reset Token"** (o "Add Bot") y copiá el **Token** (guardalo en un bloc de notas, lo vas a necesitar).
   - En la sección **Privileged Gateway Intents**:
     - *No es necesario* activar Message Content Intent (el bot no lee mensajes).
     - Podés activar **Server Members Intent** si querés que el bot autocomplete miembros con mayor fluidez.
4. Andá a la pestaña **OAuth2 > URL Generator**:
   - En **SCOPES**, marcá:
     - `bot`
     - `applications.commands`
   - En **BOT PERMISSIONS**, marcá:
     - `Manage Messages` (para limpiar anuncios de compras/consumos al cerrar)
     - `Send Messages`
     - `Embed Links`
     - `Read Message History`
     - `View Channels`
     - `Use Slash Commands`
5. Copiá la URL generada al final de la página, pegala en tu navegador e invitá al bot a tu servidor de Discord.

---

## 🐙 Paso 2: Subir tu Código a GitHub

1. Creá una cuenta o iniciá sesión en [GitHub](https://github.com/).
2. Creá un nuevo repositorio (puede ser público o privado), por ejemplo `kiosquito-lemon`.
3. En tu computadora (dentro de la carpeta `Kiosquitolemon`):
   ```bash
   git init
   git add .
   git commit -m "Kiosquito v3.2 para Northflank"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/kiosquito-lemon.git
   git push -u origin main
   ```

---

## ☁️ Paso 3: Crear el Proyecto y Despliegue en Northflank

1. Entrá a [Northflank](https://northflank.com/) e iniciá sesión (podés entrar con tu cuenta de GitHub).
2. Hacé clic en **"Create Project"**:
   - **Project Name:** `kiosquito-lemon`
   - **Region:** Elegí la más cercana (ej: `US Central` o `Europe`).
   - Hacé clic en **"Create Project"**.

3. Dentro de tu proyecto, hacé clic en **"Create Service"**:
   - Elegí **"Deployment"** (o *Combined Service* / *Background Worker*).
   - **Service Name:** `kiosquito-bot`

4. En **Source / Deployment Source**:
   - Seleccioná **"Build from VCS / Git repository"**.
   - Conectá tu cuenta de GitHub y seleccioná el repositorio `kiosquito-lemon` y la rama `main`.
   - En **Build Type**, seleccioná **Dockerfile** (Northflank detectará automáticamente el archivo `Dockerfile` que creamos).

5. En **Environment Variables** (Variables de entorno):
   - Agregá:
     - `DISCORD_TOKEN` = `(Pegá tu token de Discord)`
     - `TEST_GUILD_ID` = `(Opcional: ID de tu servidor de Discord para que los comandos se sincronicen al instante)`
     - `TZ` = `America/Argentina/Buenos_Aires`

6. En **Volumes / Persistent Storage** *(Muy Importante para que no se borre la base de datos)*:
   - Hacé clic en **"Add Volume"** o vinculá un volumen persistente.
   - **Mount Path:** `/app/data`
   - **Size:** `1 GB` (suficiente para años de registros).
   - *De esta forma, el archivo `kiosquito.db` quedará guardado de forma permanente aunque el bot se reinicie o actualices el código.*

7. En **Resources / Plan**:
   - Podés usar el plan gratuito (*Micro* o *Small* con 0.2 vCPU y 256MB/512MB RAM, el bot consume menos de 80MB).

8. Hacé clic en **"Create Service"**.

---

## ⚡ Paso 4: Configuración Inicial en tu Servidor de Discord

1. Una vez que Northflank termine de compilar y desplegar, andá a la pestaña **Logs** en Northflank y vas a ver:
   ```text
   ====================================================
   🏪 Bot conectado como: El Kiosquito de Lemon#1234 • v3.2
   🕗 Hora Argentina: 21:50
   Estado por horario: ABIERTO
   ====================================================
   ```
2. En tu servidor de Discord, andá al canal de texto donde querés que funcione el kiosquito (ej: `#kiosquito`).
3. Ejecutá como administrador:
   ```text
   /setup
   ```
4. ¡Listo! El bot fijará el mostrador interactivo con botones y empezará a gestionar la jornada, compras, changuitas, ofertas y cierres automáticamente.
