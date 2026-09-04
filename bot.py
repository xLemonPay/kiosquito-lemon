import asyncio
import json
import os
import random
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
DB_PATH = DATA_DIR / "kiosquito.db"

with open(ROOT / "config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

with open(ROOT / "products.json", "r", encoding="utf-8") as f:
    PRODUCT_LIST = json.load(f)

PRODUCTS = {p["id"]: p for p in PRODUCT_LIST}

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN", "").strip().strip('"').strip("'")
TEST_GUILD_ID_RAW = os.getenv("TEST_GUILD_ID", "").strip().strip('"').strip("'")
TEST_GUILD_ID = int(TEST_GUILD_ID_RAW) if TEST_GUILD_ID_RAW.isdigit() else None

if not TOKEN:
    raise RuntimeError(
        "Falta DISCORD_TOKEN. Copiá .env.example como .env y pegá el token del bot."
    )

TZ = ZoneInfo(CONFIG["timezone"])
MESSAGE_XP_COOLDOWNS: dict[tuple[int, int], float] = {}
BOT_VERSION = "3.2"

# ---------- DEFINICIÓN DE LAS CHANGUITAS ----------
CHANGUITAS_LIST = [
    # --- FÁCILES ($150 - $300) ---
    {
        "id": "barrer_piso",
        "name": "Barrer el piso",
        "emoji": "🧹",
        "tier": "facil",
        "desc": "Barrer mugre del salón evitando la cucaracha.",
        "is_minigame": "barrer",
    },
    {
        "id": "sacar_basura",
        "name": "Sacar la basura",
        "emoji": "🗑️",
        "tier": "facil",
        "desc": "Atar las bolsas llenas y llevarlas al contenedor.",
        "steps": [
            {
                "text": "El tacho del kiosco está desbordando de envoltorios. ¿Qué hacés?",
                "correct_btn": ("Atar fuerte la bolsa negra", "🪢"),
                "wrong_btn": ("Empujar con el pie hasta que rompa", "🦶"),
                "fail_text": "¡Pisaste la bolsa con fuerza, se reventó y derramaste café podrido por todos lados!",
            },
            {
                "text": "La bolsa está pesada. ¿Hacia dónde la llevás?",
                "correct_btn": ("Llevar al contenedor de la esquina", "🏃"),
                "wrong_btn": ("Tirarla en la vereda del vecino", "🚪"),
                "fail_text": "¡Tiraste la basura en la puerta del vecino y te denunció con la policía!",
            },
            {
                "text": "Falta dejar el tacho listo para el turno siguiente.",
                "correct_btn": ("Colocar una bolsa nueva", "♻️"),
                "wrong_btn": ("Dejar el tacho pelado", "🙅"),
                "fail_text": "¡No le pusiste bolsa al tacho y tiraron un yogur abierto adentro!",
            },
        ],
    },
    {
        "id": "limpiar_entrada",
        "name": "Limpiar la entrada/vereda",
        "emoji": "🚪",
        "tier": "facil",
        "desc": "Dejar la vereda impecable y acomodar el cartel.",
        "steps": [
            {
                "text": "La vereda tiene hojas y tierra. ¿Cómo arrancás?",
                "correct_btn": ("Manguerear y tirar agua", "🚿"),
                "wrong_btn": ("Tirarle un baldazo a los peatones", "🌊"),
                "fail_text": "¡Le tiraste un baldazo de agua sucia a una abuelita que iba a misa!",
            },
            {
                "text": "Quedó el agua estancada en la entrada.",
                "correct_btn": ("Pasar el secador hacia el cordón", "🧹"),
                "wrong_btn": ("Dejar el charco resbaloso", "⛸️"),
                "fail_text": "¡Dejaste una laguna congelada y el cartero se pegó un palo tremendo!",
            },
            {
                "text": "Para terminar, acomodá la entrada del local.",
                "correct_btn": ("Acomodar cartel de ofertas", "🪧"),
                "wrong_btn": ("Patear el cartel a la calle", "💥"),
                "fail_text": "¡Pateaste el cartel publicitario a la avenida y lo pisó el colectivo 60!",
            },
        ],
    },
    {
        "id": "sacar_telaranas",
        "name": "Sacar telarañas",
        "emoji": "🕸️",
        "tier": "facil",
        "desc": "Bajar las telarañas de las esquinas del techo.",
        "steps": [
            {
                "text": "Hay telarañas en lo alto del techo del kiosco.",
                "correct_btn": ("Armar el palo largo con plumero", "🪄"),
                "wrong_btn": ("Subirse a un cajón de gaseosas tambaleante", "🧗"),
                "fail_text": "¡Te subiste al cajón, se partió la madera y tiraste una torre de alfajores!",
            },
            {
                "text": "Tenés el plumero en posición. ¿Dónde limpiás?",
                "correct_btn": ("Pasar por los rincones y molduras", "🕸️"),
                "wrong_btn": ("Salir corriendo por una arañita chiquita", "🕷️"),
                "fail_text": "¡Gritaste como loco por una arañita inofensiva y asustaste a todos los clientes!",
            },
            {
                "text": "Cayeron restos al estante superior.",
                "correct_btn": ("Pasar un trapito húmedo", "✨"),
                "wrong_btn": ("Soplar fuerte hacia los clientes", "💨"),
                "fail_text": "¡Soplaste la mugre y le llenaste de tierra los ojos a un cliente!",
            },
        ],
    },
    {
        "id": "desinfectar_mostradores",
        "name": "Desinfectar mostradores",
        "emoji": "🧴",
        "tier": "facil",
        "desc": "Limpiar el vidrio y la zona de la caja registradora.",
        "steps": [
            {
                "text": "El mostrador de vidrio tiene huellas y monedas pegajosas.",
                "correct_btn": ("Rociar con alcohol al 70%", "🧴"),
                "wrong_btn": ("Echarle Manaos para limpiar", "🥤"),
                "fail_text": "¡Le tiraste Manaos al mostrador de vidrio y se llenó de hormigas negras!",
            },
            {
                "text": "El líquido está en el mostrador.",
                "correct_btn": ("Pasar trapo rejilla limpio", "🧽"),
                "wrong_btn": ("Limpiar con la manga de la campera", "👕"),
                "fail_text": "¡Pasaste la campera grasienta y dejaste una franja negra en el vidrio!",
            },
            {
                "text": "Último toque para que quede brillante.",
                "correct_btn": ("Secar y lustrar con papel", "✨"),
                "wrong_btn": ("Dejarlo todo chorreado", "🌫️"),
                "fail_text": "¡Dejaste un charco de alcohol sobre los billetes de la caja!",
            },
        ],
    },
    # --- NORMALES ($300 - $600) ---
    {
        "id": "cobrar_caja",
        "name": "Cobrar en la caja",
        "emoji": "🧮",
        "tier": "normal",
        "desc": "Calcular y entregar el vuelto exacto a los clientes.",
        "is_minigame": "caja",
    },
    {
        "id": "limpiar_vidrios",
        "name": "Limpiar vidrios con secador",
        "emoji": "🪟",
        "tier": "normal",
        "desc": "Pasar la espátula secavidrios en orden por la vidriera.",
        "is_minigame": "vidrios",
    },
    {
        "id": "ordenar_productos",
        "name": "Ordenar productos en góndola",
        "emoji": "🍫",
        "tier": "normal",
        "desc": "Memorizar y acomodar los productos en la secuencia pedida.",
        "is_minigame": "ordenar",
    },
    {
        "id": "trapear",
        "name": "Trapear",
        "emoji": "🪣",
        "tier": "normal",
        "desc": "Pasar el trapo con lavandina por todo el piso.",
        "steps": [
            {
                "text": "Hay que preparar el balde para trapear a fondo.",
                "correct_btn": ("Cargar agua caliente y lavandina", "🧼"),
                "wrong_btn": ("Usar agua sucia del florero", "🥀"),
                "fail_text": "¡Tiraste agua de florero podrido y el kiosco huele a pantano!",
            },
            {
                "text": "El trapo está empapado en el balde.",
                "correct_btn": ("Escurrir bien en el prensador", "🪣"),
                "wrong_btn": ("Tirarlo empapado inundando el pasillo", "🌊"),
                "fail_text": "¡Inundaste el pasillo y flotaron las cajas de Don Satur!",
            },
            {
                "text": "Toca pasar el trapo con ganas.",
                "correct_btn": ("Pasar en zigzag cubriendo todo", "✨"),
                "wrong_btn": ("Pisar con las zapatillas con barro", "👟"),
                "fail_text": "¡Caminaste con barro por encima de lo recién trapeado frente al dueño!",
            },
        ],
    },
    {
        "id": "limpiar_estantes",
        "name": "Limpiar estantes",
        "emoji": "🪶",
        "tier": "normal",
        "desc": "Bajar las mercaderías, plumerear y volver a acomodar.",
        "steps": [
            {
                "text": "Los estantes de galletitas y chocolates juntaron polvo.",
                "correct_btn": ("Bajar los productos a una caja limpia", "📦"),
                "wrong_btn": ("Tirar todo al piso de golpe", "💥"),
                "fail_text": "¡Tiraste las galletitas al suelo y quedaron todas hechas migajas!",
            },
            {
                "text": "El estante está libre.",
                "correct_btn": ("Pasar plumero y lustramuebles", "🪶"),
                "wrong_btn": ("Soplar con los ojos cerrados", "💨"),
                "fail_text": "¡Soplaste la tierra hacia la cara del kiosquero!",
            },
            {
                "text": "Hay que volver a colocar la mercadería.",
                "correct_btn": ("Acomodar por fecha de vencimiento", "🏷️"),
                "wrong_btn": ("Tirar todo mezclado adentro", "🎲"),
                "fail_text": "¡Mezclaste alfajores con pilas alcalinas en el mismo estante!",
            },
        ],
    },
    {
        "id": "limpiar_derrames",
        "name": "Limpiar derrames",
        "emoji": "⚠️",
        "tier": "normal",
        "desc": "Atender una botella rota o líquido derramado.",
        "steps": [
            {
                "text": "¡Un cliente volteó una botella de gaseosa en el pasillo!",
                "correct_btn": ("Poner el cartel amarillo de peligro", "⚠️"),
                "wrong_btn": ("Hacerse el desentendido e irse a silbar", "🤫"),
                "fail_text": "¡Miraste para otro lado, un cliente se resbaló y se rompió los pantalones!",
            },
            {
                "text": "Hay que levantar el líquido antes que se pegue.",
                "correct_btn": ("Tirar aserrín o papel absorbente", "🧻"),
                "wrong_btn": ("Tratar de secar con las medias", "🧦"),
                "fail_text": "¡Metiste las medias en el charco de gaseosa y manchaste las paredes!",
            },
            {
                "text": "Retirado el grueso, falta desinfectar la zona.",
                "correct_btn": ("Trapear con desodorante de piso", "🪣"),
                "wrong_btn": ("Pisar fuerte para ver si patina", "👞"),
                "fail_text": "¡Te pusiste a patinar en el piso mojado y te estampaste contra la vitrina!",
            },
        ],
    },
    {
        "id": "reponer_limpieza",
        "name": "Reponer artículos de limpieza",
        "emoji": "🧼",
        "tier": "normal",
        "desc": "Traer jabones, papel y lavandinas a la góndola.",
        "steps": [
            {
                "text": "El estante de artículos de higiene quedó pelado.",
                "correct_btn": ("Buscar bultos de lavandina al fondo", "🧴"),
                "wrong_btn": ("Poner botellas vacías para disimular", "👻"),
                "fail_text": "¡Llenaste el mostrador de botellas vacías para fingir que trabajabas!",
            },
            {
                "text": "Llegaste con los productos a la góndola.",
                "correct_btn": ("Alinear jabones y rollos de cocina", "🧼"),
                "wrong_btn": ("Tirarlos como si fueran ladrillos", "🧱"),
                "fail_text": "¡Revoleaste las botellas de lavandina y se abrió una en el piso!",
            },
            {
                "text": "Falta el detalle comercial.",
                "correct_btn": ("Verificar y colocar cartelitos de precio", "🏷️"),
                "wrong_btn": ("Inventar precios disparatados", "📈"),
                "fail_text": "¡Le pusiste precio de $99.999 a un jabón y espantaste a todos los clientes!",
            },
        ],
    },
    {
        "id": "minijuego_atajar",
        "name": "Atajar las Manaos",
        "emoji": "🥤",
        "tier": "normal",
        "desc": "Atajá las botellas que caen del camión de reparto.",
        "is_minigame": "atajar",
    },
    {
        "id": "minijuego_deposito",
        "name": "Buscaminas del depósito",
        "emoji": "📦",
        "tier": "normal",
        "desc": "Buscá mercadería en las cajas del fondo esquivando la rata.",
        "is_minigame": "deposito",
    },
    # --- PESADAS ($600 - $1.000) ---
    {
        "id": "mover_cajas",
        "name": "Mover cajas pesadas",
        "emoji": "🏋️",
        "tier": "pesada",
        "desc": "Hacer fuerza rápida para subir la carga pesada al depósito.",
        "is_minigame": "cajas",
    },
    {
        "id": "minijuego_heladera",
        "name": "Reparar heladera y termostato",
        "emoji": "❄️",
        "tier": "pesada",
        "desc": "Conectar cables y calibrar el termostato a frío.",
        "is_minigame": "heladera",
    },
    {
        "id": "ordenar_deposito",
        "name": "Ordenar el depósito",
        "emoji": "📦",
        "tier": "pesada",
        "desc": "Reorganizar todas las cajas y bultos en la trastienda.",
        "steps": [
            {
                "text": "El depósito es un caos total de bultos cruzados.",
                "correct_btn": ("Apilar las cajas pesadas abajo", "🧱"),
                "wrong_btn": ("Poner los cajones de vidrio arriba de todo", "🪜"),
                "fail_text": "¡Pusiste 4 cajones de cerveza arriba de una caja de cartón y se derrumbó todo!",
            },
            {
                "text": "Hay bultos cerrados recién llegados.",
                "correct_btn": ("Etiquetar bultos con fecha de ingreso", "🏷️"),
                "wrong_btn": ("Mezclar galletitas con desodorantes", "❓"),
                "fail_text": "¡Apilaste lavandina con alfajores y contaminaste 50 cajas de mercadería!",
            },
            {
                "text": "Hay que despejar la circulación.",
                "correct_btn": ("Dejar el pasillo central libre", "🧹"),
                "wrong_btn": ("Tapar la puerta de salida con pallets", "🚪"),
                "fail_text": "¡Tapaste la puerta del baño y el kiosquero quedó encerrado 2 horas!",
            },
        ],
    },
    {
        "id": "acomodar_cajones",
        "name": "Acomodar cajones de bebidas",
        "emoji": "🍾",
        "tier": "pesada",
        "desc": "Descargar cajones de cerveza y retornables del camión.",
        "steps": [
            {
                "text": "Llegó el camión repartidor con 20 cajones de envases.",
                "correct_btn": ("Bajar los cajones de a dos con cuidado", "🚚"),
                "wrong_btn": ("Tirar los cajones de vidrio desde arriba", "💥"),
                "fail_text": "¡Tiraste los cajones de vidrio desde la caja del camión y rompiste 24 botellas!",
            },
            {
                "text": "Tenés los cajones en la vereda.",
                "correct_btn": ("Separar envases retornables por marca", "🍾"),
                "wrong_btn": ("Hacer malabares con 3 porrones", "🤹"),
                "fail_text": "¡Te pusiste a hacer malabares y le rompiste un porrón en la cabeza al chofer!",
            },
            {
                "text": "Hora de guardar el stock en la trastienda.",
                "correct_btn": ("Trabar los cajones en columnas seguras", "🏗️"),
                "wrong_btn": ("Dejar todo al rayo del sol en enero", "☀️"),
                "fail_text": "¡Dejaste 10 cajones de cerveza al sol a 40 grados y se pudrieron!",
            },
        ],
    },
    {
        "id": "limpiar_heladera",
        "name": "Limpiar la heladera",
        "emoji": "❄️",
        "tier": "pesada",
        "desc": "Descongelar, pasar desinfectante y reorganizar botellas.",
        "steps": [
            {
                "text": "La heladera exhibidora juntó hielo y tiene latas volcadas.",
                "correct_btn": ("Desenchufar y vaciar todas las bebidas", "🔌"),
                "wrong_btn": ("Picar el hielo con un cuchillo filoso", "🔪"),
                "fail_text": "¡Le clavaste un cuchillo al caño de gas de la heladera y la arruinaste!",
            },
            {
                "text": "La heladera está vacía y descongelada.",
                "correct_btn": ("Desinfectar estantes y desagüe", "🧼"),
                "wrong_btn": ("Secar con un secador de pelo adentro", "🔥"),
                "fail_text": "¡Derretiste todo el termostato de la exhibidora con el secador de pelo!",
            },
            {
                "text": "Toca reponer las bebidas para la venta.",
                "correct_btn": ("Acomodar latas y botellas con logo al frente", "🥤"),
                "wrong_btn": ("Tirar los jugos Baggio aplastados", "🧃"),
                "fail_text": "¡Reventaste los cartones de chocolatada Cindor dentro de la heladera!",
            },
        ],
    },
    {
        "id": "mover_cajas",
        "name": "Mover cajas",
        "emoji": "🏋️",
        "tier": "pesada",
        "desc": "Trasladar mercadería pesada hacia la estantería alta.",
        "steps": [
            {
                "text": "Hay bultos de 25 kg de azúcar y harina en el suelo.",
                "correct_btn": ("Flexionar rodillas y levantar con piernas", "🏋️"),
                "wrong_btn": ("Hacer fuerza pura doblando la columna", "🦴"),
                "fail_text": "¡Te doblaste la espalda, gritaste del dolor y tiraste una balanza digital!",
            },
            {
                "text": "Toca llevar la carga hasta el fondo.",
                "correct_btn": ("Cargar en la zorra de carga y empujar", "🛒"),
                "wrong_btn": ("Llevar 5 cajas apiladas tapándote los ojos", "🏃"),
                "fail_text": "¡Caminaste a ciegas con 5 cajas y te llevaste puesto el mostrador!",
            },
            {
                "text": "Último esfuerzo: acomodar en el estante superior.",
                "correct_btn": ("Usar escalera firme y asegurar la carga", "📦"),
                "wrong_btn": ("Revolear la caja desde abajo", "🎯"),
                "fail_text": "¡Revoleaste una caja de azúcar y llovió polvo blanco en todo el negocio!",
            },
        ],
    },
    {
        "id": "limpieza_profunda_deposito",
        "name": "Limpieza profunda del depósito",
        "emoji": "🏗️",
        "tier": "pesada",
        "desc": "Mover pallets, barrer a fondo y desinfectar todo.",
        "steps": [
            {
                "text": "Toca la limpieza general del mes en el depósito.",
                "correct_btn": ("Mover pallets de mercadería con la carretilla", "📦"),
                "wrong_btn": ("Dormir una siestita arriba de las cajas", "😴"),
                "fail_text": "¡Te tiraste a dormir una siesta y el kiosquero te enganchó roncando fuerte!",
            },
            {
                "text": "Apareció una capa de tierra de 5 años atrás.",
                "correct_btn": ("Barrer y tirar desinfectante industrial", "🪣"),
                "wrong_btn": ("Tirar nafta para desengrasar", "⛽"),
                "fail_text": "¡Tiraste combustible en un lugar cerrado y casi vuela el edificio!",
            },
            {
                "text": "Todo limpio y oliendo a lavandina.",
                "correct_btn": ("Reorganizar stock y cerrar candado", "🔐"),
                "wrong_btn": ("Dejar la puerta de la calle abierta de par en par", "🚪"),
                "fail_text": "¡Dejaste el portón abierto de par en par y le robaron 10 cajas de Oreos!",
            },
        ],
    },
]

CHANGUITAS_MAP = {c["id"]: c for c in CHANGUITAS_LIST}


# ---------- FUNCIONES DE FORMATEO Y UTILIDADES ----------

def money(value: int) -> str:
    return f"${value:,}".replace(",", ".")


def parse_hhmm(value: str) -> int:
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute


def minutes_now(now: datetime) -> int:
    return now.hour * 60 + now.minute


def seconds_text(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours} h {minutes} min"
    if minutes:
        return f"{minutes} min {secs} s"
    return f"{secs} s"


def opening_hours_text() -> str:
    return "\n".join(
        f"• **{p['start']} — {p['end']} hs**" for p in CONFIG["opening_hours"]
    )


def get_current_schedule_period(now: datetime | None = None) -> str | None:
    now = now or datetime.now(TZ)
    current = minutes_now(now)
    date_str = now.strftime("%Y-%m-%d")

    for period in CONFIG["opening_hours"]:
        start = parse_hhmm(period["start"])
        end = parse_hhmm(period["end"])
        if end == 0 and start > 0:
            end = 24 * 60
        if start <= current < end:
            return f"{date_str}_{period['start']}"

    return None


def is_open(now: datetime | None = None, guild_id: int | None = None) -> bool:
    now = now or datetime.now(TZ)

    if guild_id is not None:
        manual_open, _ = manual_open_status(guild_id)
        if manual_open:
            return True

        # Verificar si un admin forzó el cierre de este turno
        current_period = get_current_schedule_period(now)
        force_closed = get_setting(guild_id, "force_closed_period", "")
        if force_closed:
            if current_period and force_closed == current_period:
                return False
            elif not current_period:
                # Terminó el turno que estaba forzado a cerrar
                set_setting(guild_id, "force_closed_period", "")
            elif current_period and force_closed != current_period:
                # Llegó un nuevo turno de apertura programada
                set_setting(guild_id, "force_closed_period", "")

    current = minutes_now(now)
    for period in CONFIG["opening_hours"]:
        start = parse_hhmm(period["start"])
        end = parse_hhmm(period["end"])
        if end == 0 and start > 0:
            end = 24 * 60
        if start <= current < end:
            return True

    return False


def next_opening(now: datetime | None = None) -> str:
    now = now or datetime.now(TZ)
    current = minutes_now(now)
    starts = sorted(parse_hhmm(p["start"]) for p in CONFIG["opening_hours"])

    for start in starts:
        if current < start:
            return f"{start // 60:02d}:{start % 60:02d} hs"

    first = starts[0]
    return f"{first // 60:02d}:{first % 60:02d} hs (de mañana)"


async def auto_delete_interaction(interaction: discord.Interaction, delay: int = 180):
    """Borra la respuesta efímera luego de 3 minutos (180 segundos)."""
    await asyncio.sleep(delay)
    try:
        await interaction.delete_original_response()
    except (discord.NotFound, discord.HTTPException):
        pass


async def auto_delete_message(message: discord.Message, delay: int = 600):
    """Borra un mensaje luego del tiempo especificado (default 10 min = 600 seg)."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except (discord.NotFound, discord.HTTPException):
        pass


# ---------- BASE DE DATOS Y PERSISTENCIA ----------

def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=60.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=60000;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                money INTEGER NOT NULL DEFAULT 0,
                xp INTEGER NOT NULL DEFAULT 0,
                debt INTEGER NOT NULL DEFAULT 0,
                last_daily INTEGER NOT NULL DEFAULT 0,
                last_work INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                guild_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (guild_id, key)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, product_id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shift_sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                shift_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price_total INTEGER NOT NULL,
                is_fiado INTEGER NOT NULL DEFAULT 0,
                timestamp INTEGER NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS consumption_messages (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                shift_id INTEGER NOT NULL,
                timestamp INTEGER NOT NULL,
                PRIMARY KEY (guild_id, message_id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kiosk_stock (
                guild_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, product_id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quiniela_bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                number INTEGER NOT NULL,
                bet_amount INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS raspadita_daily (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                play_date TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, play_date)
            )
            """
        )

        try:
            conn.execute("ALTER TABLE users ADD COLUMN has_lemon_black INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("ALTER TABLE users ADD COLUMN custom_title TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass


def get_setting(guild_id: int, key: str, default: str = "0") -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE guild_id=? AND key=?",
            (guild_id, key),
        ).fetchone()
        return row["value"] if row else default


def set_setting(guild_id: int, key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings (guild_id, key, value)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, key)
            DO UPDATE SET value=excluded.value
            """,
            (guild_id, key, value),
        )


def get_current_shift_id(guild_id: int) -> int:
    raw = get_setting(guild_id, "current_shift_id", "0")
    try:
        shift_id = int(raw)
    except ValueError:
        shift_id = 0
    if shift_id <= 0:
        shift_id = int(time.time())
        set_setting(guild_id, "current_shift_id", str(shift_id))
    return shift_id


# ---------- SISTEMA DE OFERTAS Y STOCK DEL KIOSQUITO ----------

def get_shift_offers(guild_id: int) -> dict[str, int]:
    raw = get_setting(guild_id, "shift_offers", "{}")
    try:
        return json.loads(raw)
    except Exception:
        return {}


def get_product_price(guild_id: int, product_id: str) -> tuple[int, bool, int]:
    """Devuelve (precio_actual, esta_en_oferta, precio_original)."""
    p = PRODUCTS.get(product_id)
    if not p:
        return 0, False, 0
    orig = p["price"]
    offers = get_shift_offers(guild_id)
    if product_id in offers:
        return offers[product_id], True, orig
    return orig, False, orig


def get_kiosk_stock(guild_id: int, product_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT stock FROM kiosk_stock WHERE guild_id=? AND product_id=?",
            (guild_id, product_id),
        ).fetchone()
        if row is not None:
            return int(row["stock"])
        # Si no existe, inicializar con stock corto
        init_stock = random.randint(CONFIG.get("stock_min_initial", 3), CONFIG.get("stock_max_initial", 7))
        conn.execute(
            "INSERT OR REPLACE INTO kiosk_stock (guild_id, product_id, stock) VALUES (?, ?, ?)",
            (guild_id, product_id, init_stock),
        )
        return init_stock


def get_all_kiosk_stock(guild_id: int) -> dict[str, int]:
    stock_map = {}
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT product_id, stock FROM kiosk_stock WHERE guild_id=?",
            (guild_id,),
        ).fetchall()
        for r in rows:
            stock_map[r["product_id"]] = int(r["stock"])
        for pid in PRODUCTS:
            if pid not in stock_map:
                init_val = random.randint(CONFIG.get("stock_min_initial", 3), CONFIG.get("stock_max_initial", 7))
                conn.execute(
                    "INSERT OR REPLACE INTO kiosk_stock (guild_id, product_id, stock) VALUES (?, ?, ?)",
                    (guild_id, pid, init_val),
                )
                stock_map[pid] = init_val
    return stock_map


def init_shift_stock(guild_id: int) -> None:
    """Genera stock corto inicial para cada producto al abrir el kiosco."""
    with get_connection() as conn:
        for pid in PRODUCTS:
            initial = random.randint(CONFIG.get("stock_min_initial", 3), CONFIG.get("stock_max_initial", 7))
            conn.execute(
                "INSERT OR REPLACE INTO kiosk_stock (guild_id, product_id, stock) VALUES (?, ?, ?)",
                (guild_id, pid, initial),
            )


def restock_kiosk(guild_id: int, amount_min: int = 1, amount_max: int = 3) -> None:
    """Repone gradualmente unidades de productos con poco stock."""
    max_cap = CONFIG.get("stock_max_initial", 7) + 2
    with get_connection() as conn:
        for pid in PRODUCTS:
            row = conn.execute(
                "SELECT stock FROM kiosk_stock WHERE guild_id=? AND product_id=?",
                (guild_id, pid),
            ).fetchone()
            if row is not None:
                current = int(row["stock"])
            else:
                current = random.randint(CONFIG.get("stock_min_initial", 3), CONFIG.get("stock_max_initial", 7))
            if current < max_cap:
                add_qty = random.randint(amount_min, amount_max)
                new_stock = min(max_cap, current + add_qty)
                conn.execute(
                    "INSERT OR REPLACE INTO kiosk_stock (guild_id, product_id, stock) VALUES (?, ?, ?)",
                    (guild_id, pid, new_stock),
                )


def roll_shift_offers(guild_id: int) -> dict[str, int]:
    """Tira probabilidad baja para determinar si hoy hay ofertas y qué productos entran."""
    chance = CONFIG.get("offer_day_chance", 0.20)
    if random.random() < chance:
        # ¡Jornada con ofertas! Elegir 1 a 2 productos al azar
        chosen_prods = random.sample(PRODUCT_LIST, k=random.randint(1, 2))
        offers = {}
        for p in chosen_prods:
            discount_pct = random.randint(
                CONFIG.get("offer_discount_percent_min", 25),
                CONFIG.get("offer_discount_percent_max", 40),
            )
            discounted = max(50, round((p["price"] * (1 - discount_pct / 100)) / 50) * 50)
            offers[p["id"]] = discounted
        set_setting(guild_id, "shift_offers", json.dumps(offers))
        return offers
    else:
        set_setting(guild_id, "shift_offers", "{}")
        return {}


def record_sale(
    guild_id: int,
    user_id: int,
    product_id: str,
    quantity: int,
    price_total: int,
    is_fiado: bool = False,
) -> None:
    shift_id = get_current_shift_id(guild_id)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO shift_sales
            (guild_id, shift_id, user_id, product_id, quantity, price_total, is_fiado, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                shift_id,
                user_id,
                product_id,
                quantity,
                price_total,
                1 if is_fiado else 0,
                int(time.time()),
            ),
        )


def get_shift_sales_summary(guild_id: int, shift_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT product_id, SUM(quantity) as total_qty, SUM(price_total) as total_money
            FROM shift_sales
            WHERE guild_id=? AND shift_id=?
            GROUP BY product_id
            ORDER BY total_qty DESC
            """,
            (guild_id, shift_id),
        ).fetchall()
        total_revenue = conn.execute(
            """
            SELECT SUM(price_total) as total
            FROM shift_sales
            WHERE guild_id=? AND shift_id=?
            """,
            (guild_id, shift_id),
        ).fetchone()["total"] or 0
        return rows, total_revenue


def get_guild_debtors(guild_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT user_id, debt
            FROM users
            WHERE guild_id=? AND debt > 0
            ORDER BY debt DESC
            """,
            (guild_id,),
        ).fetchall()


def record_consumption_message(guild_id: int, channel_id: int, message_id: int) -> None:
    shift_id = get_current_shift_id(guild_id)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO consumption_messages
            (guild_id, channel_id, message_id, shift_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guild_id, channel_id, message_id, shift_id, int(time.time())),
        )


def get_shift_consumption_messages(guild_id: int, shift_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT channel_id, message_id
            FROM consumption_messages
            WHERE guild_id=? AND shift_id=?
            """,
            (guild_id, shift_id),
        ).fetchall()


def get_guild_consumption_messages(guild_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT channel_id, message_id
            FROM consumption_messages
            WHERE guild_id=?
            """,
            (guild_id,),
        ).fetchall()


async def notify_fired(interaction: discord.Interaction, fail_reason: str) -> None:
    """Envía un anuncio público en el chat cuando rajan a alguien del laburo."""
    if not interaction.channel:
        return
    try:
        clean_reason = fail_reason.strip()
        msg = await interaction.channel.send(
            f"📢 **¡A {interaction.user.mention} lo rajaron del laburo!** 💥\n"
            f"> 🤦‍♂️ *¿Qué hizo?* {clean_reason}"
        )
        record_consumption_message(interaction.guild_id, interaction.channel_id, msg.id)
    except Exception as e:
        print(f"Error al enviar aviso de despido en el chat: {e}")


def delete_shift_consumption_records(guild_id: int, shift_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM consumption_messages WHERE guild_id=? AND shift_id=?",
            (guild_id, shift_id),
        )


def delete_all_consumption_records(guild_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM consumption_messages WHERE guild_id=?",
            (guild_id,),
        )


def get_raspadita_jackpot(guild_id: int) -> int:
    raw = get_setting(guild_id, "raspadita_jackpot", "10000")
    try:
        val = int(raw)
        return max(10000, val)
    except ValueError:
        return 10000


def add_raspadita_jackpot(guild_id: int, amount: int = 400) -> int:
    current = get_raspadita_jackpot(guild_id)
    new_val = current + amount
    set_setting(guild_id, "raspadita_jackpot", str(new_val))
    return new_val


def reset_raspadita_jackpot(guild_id: int) -> int:
    set_setting(guild_id, "raspadita_jackpot", "10000")
    return 10000


def get_user_raspadita_daily_count(guild_id: int, user_id: int) -> int:
    today_str = datetime.now(TZ).strftime("%Y-%m-%d")
    with get_connection() as conn:
        row = conn.execute(
            "SELECT count FROM raspadita_daily WHERE guild_id=? AND user_id=? AND play_date=?",
            (guild_id, user_id, today_str),
        ).fetchone()
        return row["count"] if row else 0


def increment_user_raspadita_daily_count(conn: sqlite3.Connection, guild_id: int, user_id: int) -> int:
    today_str = datetime.now(TZ).strftime("%Y-%m-%d")
    conn.execute(
        """
        INSERT INTO raspadita_daily (guild_id, user_id, play_date, count)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(guild_id, user_id, play_date) DO UPDATE SET count=count+1
        """,
        (guild_id, user_id, today_str),
    )
    row = conn.execute(
        "SELECT count FROM raspadita_daily WHERE guild_id=? AND user_id=? AND play_date=?",
        (guild_id, user_id, today_str),
    ).fetchone()
    return row["count"] if row else 1


def reset_user_raspadita_daily_count(guild_id: int, user_id: int) -> None:
    today_str = datetime.now(TZ).strftime("%Y-%m-%d")
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM raspadita_daily WHERE guild_id=? AND user_id=? AND play_date=?",
            (guild_id, user_id, today_str),
        )


RASPADITA_DAILY_LIMIT = 20
QUINIELA_DRAWING: set[int] = set()


def is_subscriber(member: discord.Member | discord.User) -> bool:
    if not isinstance(member, discord.Member):
        return False
    if member.premium_since is not None:
        return True
    for role in member.roles:
        rname = role.name.lower()
        if "sub tier" in rname or "subscriber" in rname or "suscriptor" in rname or "booster" in rname or rname.startswith("sub"):
            return True
    return False


def add_inventory_item(guild_id: int, user_id: int, product_id: str, quantity: int = 1) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO inventory (guild_id, user_id, product_id, quantity)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id, product_id)
            DO UPDATE SET quantity=quantity+excluded.quantity
            """,
            (guild_id, user_id, product_id, quantity),
        )


QUINIELA_NUMBERS = {
    1: {"name": "El Agua", "emoji": "💧"},
    2: {"name": "El Niño", "emoji": "👦"},
    3: {"name": "El Trébol", "emoji": "☘️"},
    4: {"name": "La Cama", "emoji": "🛏️"},
    5: {"name": "El Gato", "emoji": "🐈"},
    6: {"name": "El Perro", "emoji": "🐕"},
    7: {"name": "El Revólver", "emoji": "🔫"},
    8: {"name": "El Incendio", "emoji": "🔥"},
    9: {"name": "El Arroyo", "emoji": "🌊"},
    10: {"name": "La Leche", "emoji": "🥛"},
    11: {"name": "El Minero", "emoji": "⛏️"},
    12: {"name": "El Soldado", "emoji": "💂"},
    13: {"name": "La Yeta", "emoji": "🍀"},
    14: {"name": "El Borracho", "emoji": "🥴"},
    15: {"name": "La Niña Bonita", "emoji": "👧"},
    16: {"name": "El Anillo", "emoji": "💍"},
    17: {"name": "La Desgracia", "emoji": "💔"},
    18: {"name": "La Sangre", "emoji": "🩸"},
    19: {"name": "El Pescado", "emoji": "🐟"},
    20: {"name": "La Fiesta", "emoji": "🥳"},
    21: {"name": "La Mujer", "emoji": "👩"},
    22: {"name": "El Loco", "emoji": "🤪"},
    23: {"name": "El Cocinero", "emoji": "👨‍🍳"},
    24: {"name": "El Caballo", "emoji": "🐎"},
    25: {"name": "La Gallina", "emoji": "🐓"},
    26: {"name": "La Misa", "emoji": "⛪"},
    27: {"name": "El Peine", "emoji": "🪮"},
    28: {"name": "El Cerro", "emoji": "⛰️"},
    29: {"name": "San Pedro", "emoji": "🔑"},
    30: {"name": "Santa Rosa", "emoji": "🌹"},
    31: {"name": "La Luz", "emoji": "💡"},
    32: {"name": "El Dinero", "emoji": "💵"},
    33: {"name": "Cristo", "emoji": "✝️"},
    34: {"name": "La Cabeza", "emoji": "🗣️"},
    35: {"name": "El Pajarito", "emoji": "🐦"},
    36: {"name": "La Manteca", "emoji": "🧈"},
    37: {"name": "El Dentista", "emoji": "🦷"},
    38: {"name": "El Aceite", "emoji": "🫒"},
    39: {"name": "La Lluvia", "emoji": "🌧️"},
    40: {"name": "El Cura", "emoji": "⛪"},
    41: {"name": "El Cuchillo", "emoji": "🔪"},
    42: {"name": "Las Zapatillas", "emoji": "👟"},
    43: {"name": "El Balcón", "emoji": "🏢"},
    44: {"name": "La Cárcel", "emoji": "⛓️"},
    45: {"name": "El Vino", "emoji": "🍷"},
    46: {"name": "El Tomate", "emoji": "🍅"},
    47: {"name": "El Muerto", "emoji": "💀"},
    48: {"name": "El Muerto que habla", "emoji": "🗣️"},
    49: {"name": "La Carne", "emoji": "🥩"},
    50: {"name": "El Pan", "emoji": "🥖"},
}


def record_quiniela_bet(guild_id: int, user_id: int, number: int, amount: int) -> None:
    now = int(time.time())
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO quiniela_bets (guild_id, user_id, number, bet_amount, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guild_id, user_id, number, amount, now),
        )


def get_active_quiniela_bets(guild_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM quiniela_bets WHERE guild_id=?",
            (guild_id,),
        ).fetchall()


def get_user_quiniela_bets(guild_id: int, user_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM quiniela_bets WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ).fetchall()


def clear_quiniela_bets(guild_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM quiniela_bets WHERE guild_id=?", (guild_id,))


def get_quiniela_history(guild_id: int) -> list[int]:
    raw = get_setting(guild_id, "quiniela_history", "[]")
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [int(x) for x in data if 1 <= int(x) <= 50][:3]
    except Exception:
        pass
    return []


def record_quiniela_history(guild_id: int, win_number: int) -> None:
    history = get_quiniela_history(guild_id)
    history = [win_number] + history[:2]
    set_setting(guild_id, "quiniela_history", json.dumps(history))


async def resolve_member_name(guild: discord.Guild, user_id: int) -> str:
    """Obtiene el nombre real o tag de un usuario evitando el problema de cache vacío."""
    m = guild.get_member(user_id)
    if m:
        return m.display_name or m.name
    try:
        m = await guild.fetch_member(user_id)
        if m:
            return m.display_name or m.name
    except Exception:
        pass
    try:
        u = await bot.fetch_user(user_id)
        if u:
            return u.display_name or u.name
    except Exception:
        pass
    return f"Vecino_{user_id % 1000:03d}"


async def get_or_create_quinielero_role(guild: discord.Guild) -> discord.Role | None:
    for r in guild.roles:
        if "quinielero" in r.name.lower():
            return r
    try:
        return await guild.create_role(
            name="Quinielero",
            color=discord.Color.gold(),
            mentionable=True,
            reason="Rol para participantes de la Quiniela del Kiosquito",
        )
    except Exception as e:
        print(f"Aviso al crear rol Quinielero: {e}")
        return None


async def schedule_quinielero_role_removal(guild: discord.Guild, role: discord.Role, user_ids: list[int], delay_seconds: int = 1200):
    await asyncio.sleep(delay_seconds)
    for uid in user_ids:
        try:
            member = guild.get_member(uid)
            if not member:
                member = await guild.fetch_member(uid)
            if member and role in member.roles:
                await member.remove_roles(role, reason="Fin del sorteo de Quiniela (20 min cumplidos)")
        except Exception:
            pass


async def get_or_create_lemon_black_role(guild: discord.Guild) -> discord.Role | None:
    for r in guild.roles:
        if "lemon black" in r.name.lower():
            return r
    try:
        return await guild.create_role(
            name="Lemon Black",
            color=discord.Color.from_rgb(40, 40, 40),
            hoist=True,
            mentionable=False,
            reason="Rol VIP Lemon Black del Kiosquito",
        )
    except Exception as e:
        print(f"Aviso al crear rol Lemon Black: {e}")
        return None


def manual_open_status(guild_id: int) -> tuple[bool, int | None]:
    raw = get_setting(guild_id, "manual_open_until", "0")
    try:
        until = int(raw)
    except ValueError:
        until = 0

    if until == -1:
        return True, None

    if until <= 0:
        return False, 0

    remaining = until - int(time.time())
    if remaining <= 0:
        set_setting(guild_id, "manual_open_until", "0")
        return False, 0

    return True, remaining


def ensure_user(conn: sqlite3.Connection, guild_id: int, user_id: int) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO users
        (guild_id, user_id, money, xp, debt, last_daily, last_work, created_at, has_lemon_black, custom_title)
        VALUES (?, ?, ?, 0, 0, 0, 0, ?, 0, '')
        """,
        (guild_id, user_id, CONFIG["starting_money"], int(time.time())),
    )


def get_user(guild_id: int, user_id: int) -> sqlite3.Row:
    with get_connection() as conn:
        ensure_user(conn, guild_id, user_id)
        return conn.execute(
            "SELECT * FROM users WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ).fetchone()


def get_inventory(guild_id: int, user_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        ensure_user(conn, guild_id, user_id)
        return conn.execute(
            """
            SELECT product_id, quantity
            FROM inventory
            WHERE guild_id=? AND user_id=? AND quantity > 0
            ORDER BY product_id
            """,
            (guild_id, user_id),
        ).fetchall()


def add_xp(guild_id: int, user_id: int, amount: int) -> int:
    with get_connection() as conn:
        ensure_user(conn, guild_id, user_id)
        conn.execute(
            "UPDATE users SET xp=xp+? WHERE guild_id=? AND user_id=?",
            (amount, guild_id, user_id),
        )
        row = conn.execute(
            "SELECT xp FROM users WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ).fetchone()
        return int(row["xp"])


def normal_purchase(guild_id: int, user_id: int, product_id: str, quantity: int):
    is_lb = product_id == "lemon_black"
    stock = 999 if is_lb else get_kiosk_stock(guild_id, product_id)
    if not is_lb and stock < quantity:
        with get_connection() as conn:
            ensure_user(conn, guild_id, user_id)
            user = conn.execute(
                "SELECT money FROM users WHERE guild_id=? AND user_id=?",
                (guild_id, user_id),
            ).fetchone()
            return False, int(user["money"]), 0, "out_of_stock", stock

    unit_price, _, _ = get_product_price(guild_id, product_id)

    with get_connection() as conn:
        ensure_user(conn, guild_id, user_id)
        user = conn.execute(
            "SELECT * FROM users WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ).fetchone()

        if is_lb:
            if user["has_lemon_black"] == 1:
                return False, int(user["money"]), 0, "already_lemon_black", stock
            total = 50000
        else:
            # 15% de descuento permanente si tiene Lemon Black
            if user["has_lemon_black"] == 1:
                unit_price = max(1, int(unit_price * 0.85))
            total = unit_price * quantity

        cursor = conn.execute(
            "UPDATE users SET money=money-? WHERE guild_id=? AND user_id=? AND money >= ?",
            (total, guild_id, user_id, total),
        )
        if cursor.rowcount == 0:
            return False, int(user["money"]), total, "no_money", stock

        if is_lb:
            conn.execute(
                "UPDATE users SET has_lemon_black=1 WHERE guild_id=? AND user_id=?",
                (guild_id, user_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO inventory (guild_id, user_id, product_id, quantity)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id, product_id)
                DO UPDATE SET quantity=quantity+excluded.quantity
                """,
                (guild_id, user_id, product_id, quantity),
            )
            conn.execute(
                "UPDATE kiosk_stock SET stock=stock-? WHERE guild_id=? AND product_id=?",
                (quantity, guild_id, product_id),
            )

    record_sale(guild_id, user_id, product_id, quantity, total, is_fiado=False)
    return True, int(user["money"]) - total, total, "ok", (stock - quantity) if not is_lb else 999


def fiado_purchase(guild_id: int, user_id: int, product_id: str, quantity: int):
    if product_id == "lemon_black":
        user = get_user(guild_id, user_id)
        return "no_fiado_lemon_black", dict(user), 0, 999

    stock = get_kiosk_stock(guild_id, product_id)
    if stock < quantity:
        with get_connection() as conn:
            ensure_user(conn, guild_id, user_id)
            user = conn.execute(
                "SELECT * FROM users WHERE guild_id=? AND user_id=?",
                (guild_id, user_id),
            ).fetchone()
            return "out_of_stock", dict(user), 0, stock

    unit_price, _, _ = get_product_price(guild_id, product_id)

    with get_connection() as conn:
        ensure_user(conn, guild_id, user_id)
        user = conn.execute(
            "SELECT * FROM users WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ).fetchone()

        if user["has_lemon_black"] == 1:
            unit_price = max(1, int(unit_price * 0.85))
        total = unit_price * quantity

        required = CONFIG["fiado_xp_required"]
        debt_limit = CONFIG["fiado_debt_limit"]

        if user["xp"] < required:
            return "locked", dict(user), total, 0

        missing = max(0, total - user["money"])
        if missing == 0:
            return "enough_money", dict(user), total, 0

        if user["debt"] + missing > debt_limit:
            return "debt_limit", dict(user), total, missing

        cash_paid = min(user["money"], total)
        new_money = user["money"] - cash_paid

        conn.execute(
            """
            UPDATE users
            SET money=?, debt=debt+?
            WHERE guild_id=? AND user_id=?
            """,
            (new_money, missing, guild_id, user_id),
        )

        conn.execute(
            """
            INSERT INTO inventory (guild_id, user_id, product_id, quantity)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id, product_id)
            DO UPDATE SET quantity=quantity+excluded.quantity
            """,
            (guild_id, user_id, product_id, quantity),
        )

        conn.execute(
            "UPDATE kiosk_stock SET stock=stock-? WHERE guild_id=? AND product_id=?",
            (quantity, guild_id, product_id),
        )

    record_sale(guild_id, user_id, product_id, quantity, total, is_fiado=True)
    return "ok", dict(user), total, missing


def consume_product(guild_id: int, user_id: int, product_id: str, quantity: int):
    product = PRODUCTS[product_id]

    with get_connection() as conn:
        ensure_user(conn, guild_id, user_id)
        row = conn.execute(
            """
            SELECT quantity FROM inventory
            WHERE guild_id=? AND user_id=? AND product_id=?
            """,
            (guild_id, user_id, product_id),
        ).fetchone()

        owned = int(row["quantity"]) if row else 0
        if owned < quantity:
            return False, owned, 0, 0

        gained_xp = product["xp"] * quantity

        conn.execute(
            """
            UPDATE inventory
            SET quantity=quantity-?
            WHERE guild_id=? AND user_id=? AND product_id=?
            """,
            (quantity, guild_id, user_id, product_id),
        )
        conn.execute(
            "UPDATE users SET xp=xp+? WHERE guild_id=? AND user_id=?",
            (gained_xp, guild_id, user_id),
        )
        xp = conn.execute(
            "SELECT xp FROM users WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ).fetchone()["xp"]

        return True, owned - quantity, gained_xp, int(xp)


def gift_product(
    guild_id: int,
    sender_id: int,
    receiver_id: int,
    product_id: str,
    quantity: int,
):
    with get_connection() as conn:
        ensure_user(conn, guild_id, sender_id)
        ensure_user(conn, guild_id, receiver_id)

        row = conn.execute(
            """
            SELECT quantity FROM inventory
            WHERE guild_id=? AND user_id=? AND product_id=?
            """,
            (guild_id, sender_id, product_id),
        ).fetchone()

        owned = int(row["quantity"]) if row else 0
        if owned < quantity:
            return False, owned

        conn.execute(
            """
            UPDATE inventory
            SET quantity=quantity-?
            WHERE guild_id=? AND user_id=? AND product_id=?
            """,
            (quantity, guild_id, sender_id, product_id),
        )
        conn.execute(
            """
            INSERT INTO inventory (guild_id, user_id, product_id, quantity)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id, product_id)
            DO UPDATE SET quantity=quantity+excluded.quantity
            """,
            (guild_id, receiver_id, product_id, quantity),
        )

        return True, owned - quantity


# ---------- EMBEDS DEL BOT ----------

def profile_embed(member: discord.Member, guild_id: int) -> discord.Embed:
    user = get_user(guild_id, member.id)
    required = CONFIG["fiado_xp_required"]
    unlocked = user["xp"] >= required

    user_keys = user.keys() if hasattr(user, "keys") else []
    title_text = user["custom_title"] if ("custom_title" in user_keys and user["custom_title"]) else ""
    has_lb = user["has_lemon_black"] if ("has_lemon_black" in user_keys and user["has_lemon_black"]) else 0

    desc_lines = []
    if title_text:
        desc_lines.append(f"🏷️ **Título:** `{title_text}`")
    if has_lb:
        desc_lines.append("💳 **Miembro Lemon Black VIP** *(15% OFF permanente)*")

    embed = discord.Embed(
        title=f"👤 Perfil de {member.display_name}",
        description="\n".join(desc_lines) if desc_lines else None,
        color=discord.Color.from_rgb(45, 45, 45) if has_lb else discord.Color.gold(),
    )
    embed.add_field(name="💵 Billetera", value=money(user["money"]), inline=True)
    embed.add_field(name="⭐ Experiencia", value=f"{user['xp']} XP", inline=True)
    embed.add_field(name="🧾 Deuda", value=money(user["debt"]), inline=True)

    if unlocked:
        credit = (
            f"✅ **Fiado habilitado**\n"
            f"Límite de deuda: {money(CONFIG['fiado_debt_limit'])}"
        )
    else:
        missing = required - user["xp"]
        percent = min(100, int((user["xp"] / required) * 100))
        bars = 10
        filled = round(percent / 10)
        progress = "█" * filled + "░" * (bars - filled)
        credit = (
            f"🔒 Se desbloquea a **{required} XP**\n"
            f"`{progress}` {percent}%\n"
            f"Te faltan **{missing} XP**."
        )

    embed.add_field(name="🤝 Fiado", value=credit, inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed


def inventory_embed(member: discord.Member, guild_id: int) -> discord.Embed:
    rows = get_inventory(guild_id, member.id)

    embed = discord.Embed(
        title=f"🎒 Mochila de {member.display_name}",
        color=discord.Color.gold(),
    )

    if not rows:
        embed.description = "Está más vacía que la heladera a fin de mes."
        return embed

    lines = []
    for row in rows:
        product = PRODUCTS.get(row["product_id"])
        if not product:
            continue
        lines.append(
            f"{product['emoji']} **{product['name']}** ×{row['quantity']}"
        )

    embed.description = "\n".join(lines) or "No hay productos."
    embed.set_footer(text="Usá el menú de abajo para consumir productos y ganar XP.")
    return embed


def kiosk_open_embed(guild_id: int | None = None) -> discord.Embed:
    now = datetime.now(TZ)
    jackpot = get_raspadita_jackpot(guild_id) if guild_id else 10000

    desc_lines = [
        "¡Buenas, maestro! El mostrador está atendiendo.\n",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "🎰 **POZO DE LA RASPADITA**",
        f"💰 Acumulado: **{money(jackpot)}**  •  🎟️ Ticket: **$1.000** *($750 Subs)*\n",
    ]

    if guild_id:
        offers = get_shift_offers(guild_id)
        if offers:
            desc_lines.append("🏷️ **OFERTAS DE LA JORNADA**")
            for pid, disc_price in offers.items():
                p = PRODUCTS.get(pid)
                if p:
                    stock = get_kiosk_stock(guild_id, pid)
                    desc_lines.append(f"🔥 {p['emoji']} **{p['name']}**: **{money(disc_price)}** *(Antes {money(p['price'])})* • Stock: `{stock} un.`")
            desc_lines.append("")

        manual_open, rem = manual_open_status(guild_id)
        if manual_open:
            if rem is None:
                extra = "🔓 *Apertura manual activa.*"
            else:
                extra = f"🔓 *Apertura manual activa por {seconds_text(rem)}.*"
            desc_lines.append(f"{extra}\n")

    desc_lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ **Horarios:** `08:00 – 13:00 hs` | `17:00 – 00:00 hs` *(Arg)*",
        "👉 *Tocá los botones de abajo para comprar, laburar o raspar.*",
    ])

    embed = discord.Embed(
        title="🏪 EL KIOSQUITO DE LEMON 🍋",
        description="\n".join(desc_lines),
        color=discord.Color.green(),
    )
    embed.set_footer(text=f"🟢 Abierto • Hora Argentina {now.strftime('%H:%M')}")
    return embed


def kiosk_closed_embed(guild_id: int) -> discord.Embed:
    now = datetime.now(TZ)
    shift_id = get_current_shift_id(guild_id)
    sales_rows, total_money = get_shift_sales_summary(guild_id, shift_id)
    debtors = get_guild_debtors(guild_id)
    jackpot = get_raspadita_jackpot(guild_id)

    desc_lines = [
        f"El mostrador está cerrado. Volvemos a abrir a las **{next_opening(now)}**.\n",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🎰 **POZO ACUMULADO:** **{money(jackpot)}** 🍋 *(Guardado para la próxima apertura)*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "📊 **RESUMEN DE LA JORNADA**\n",
    ]

    if sales_rows:
        sales_lines = []
        for r in sales_rows:
            prod = PRODUCTS.get(r["product_id"])
            pname = prod["name"] if prod else r["product_id"]
            pemoji = prod["emoji"] if prod else "📦"
            sales_lines.append(f"• {pemoji} **{pname}**: ×{r['total_qty']} ({money(r['total_money'])})")
        desc_lines.append("\n".join(sales_lines))
    else:
        desc_lines.append("• *No se registraron ventas en esta jornada.*")

    desc_lines.append(f"\n💰 **Facturación total:** **{money(total_money)}**\n")

    if debtors:
        desc_lines.append("🧾 **Deudores de la Libretita:**")
        debt_lines = []
        for d in debtors[:10]:
            debt_lines.append(f"• <@{d['user_id']}>: **{money(d['debt'])}**")
        if len(debtors) > 10:
            debt_lines.append(f"*...y {len(debtors) - 10} más.*")
        desc_lines.append("\n".join(debt_lines))
    else:
        desc_lines.append("✨ *¡Nadie debe nada! Milagro barrial.*")

    desc_lines.extend([
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ **Horarios habituales:** `08:00 – 13:00 hs` | `17:00 – 00:00 hs` *(Arg)*",
    ])

    embed = discord.Embed(
        title="🏪 EL KIOSQUITO DE LEMON — CERRADO 🔒",
        description="\n".join(desc_lines),
        color=discord.Color.red(),
    )
    embed.set_footer(text=f"🔒 Cerrado • Hora Argentina {now.strftime('%H:%M')}")
    return embed


# ---------- SISTEMA DE CHANGUITAS INTERACTIVAS ----------

class ChanguitaWorkView(discord.ui.View):
    def __init__(
        self,
        job_data: dict,
        user_id: int,
        guild_id: int,
        parent_interaction: discord.Interaction,
    ):
        super().__init__(timeout=180)
        self.job = job_data
        self.user_id = user_id
        self.guild_id = guild_id
        self.interaction = parent_interaction
        self.current_step = 0
        self.total_steps = len(job_data["steps"])
        self.build_step()

    def build_step(self):
        self.clear_items()
        step_data = self.job["steps"][self.current_step]

        correct_label, correct_emoji = step_data["correct_btn"]
        wrong_label, wrong_emoji = step_data["wrong_btn"]

        btns = [
            ("correct", correct_label, correct_emoji, discord.ButtonStyle.primary),
            ("wrong", wrong_label, wrong_emoji, discord.ButtonStyle.secondary),
        ]
        random.shuffle(btns)

        for btn_type, label, emoji, style in btns:
            button = discord.ui.Button(label=label, emoji=emoji, style=style)
            if btn_type == "correct":
                button.callback = self.on_correct
            else:
                button.callback = self.on_wrong
            self.add_item(button)

    async def on_timeout(self):
        try:
            await self.interaction.delete_original_response()
        except (discord.NotFound, discord.HTTPException):
            pass

    async def on_wrong(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Esta changuita no es tuya! 😅", ephemeral=True)
            return

        step_data = self.job["steps"][self.current_step]
        fail_msg = step_data.get("fail_text", "¡Hiciste cualquier cosa!")
        now = int(time.time())

        # Sanción: Aplica cooldown de 30 minutos sin pago
        with get_connection() as conn:
            ensure_user(conn, self.guild_id, self.user_id)
            conn.execute(
                "UPDATE users SET last_work=? WHERE guild_id=? AND user_id=?",
                (now, self.guild_id, self.user_id),
            )

        embed = discord.Embed(
            title=f"💥 ¡TE RAJARON DEL LABURO! {self.job['emoji']} {self.job['name']}",
            description=(
                f"❌ **Mandaste cualquiera:** {fail_msg}\n\n"
                f"🧔 **El Kiosquero:** *«¡Andate de acá antes de que me caliente más! ¡No te pago un mango!»*\n\n"
                f"💸 **Cobro:** $0 • ⭐ **XP:** 0\n"
                f"⏳ **Sanción:** Podés volver a pedir changuita en **{CONFIG['changuita_cooldown_minutes']} minutos**."
            ),
            color=discord.Color.red(),
        )
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
        await notify_fired(interaction, fail_msg)

    async def on_correct(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Esta changuita no es tuya! 😅", ephemeral=True)
            return

        self.current_step += 1

        if self.current_step < self.total_steps:
            self.build_step()
            embed = discord.Embed(
                title=f"{self.job['emoji']} {self.job['name']} (Paso {self.current_step + 1}/{self.total_steps})",
                description=self.job["steps"][self.current_step]["text"],
                color=discord.Color.gold(),
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            # ¡Changuita completada con éxito!
            tier_info = CONFIG["changuita_tiers"][self.job["tier"]]
            cash = random.randint(tier_info["money_min"], tier_info["money_max"])
            xp = random.randint(tier_info["xp_min"], tier_info["xp_max"])
            now = int(time.time())

            with get_connection() as conn:
                ensure_user(conn, self.guild_id, self.user_id)
                conn.execute(
                    """
                    UPDATE users
                    SET money=money+?, xp=xp+?, last_work=?
                    WHERE guild_id=? AND user_id=?
                    """,
                    (cash, xp, now, self.guild_id, self.user_id),
                )
                user = conn.execute(
                    "SELECT money, xp FROM users WHERE guild_id=? AND user_id=?",
                    (self.guild_id, self.user_id),
                ).fetchone()

            # Si era changuita de reposición/orden, reponer un toque de stock
            if self.job["id"] in ["reponer_limpieza", "ordenar_productos", "ordenar_deposito", "acomodar_cajones"]:
                restock_kiosk(self.guild_id, 1, 2)

            embed = discord.Embed(
                title=f"✨ ¡Changuita completada! {self.job['emoji']} {self.job['name']}",
                description=(
                    f"¡Excelente laburo, maestro! Dejaste todo impecable.\n\n"
                    f"💵 **Cobraste:** +{money(cash)}\n"
                    f"⭐ **Ganaste:** +{xp} XP\n\n"
                    f"💼 Billetera: **{money(user['money'])}** | ⭐ Total: **{user['xp']} XP**"
                ),
                color=discord.Color.green(),
            )
            embed.set_footer(text=f"Próxima changuita disponible en {CONFIG['changuita_cooldown_minutes']} minutos.")
            self.clear_items()
            await interaction.response.edit_message(embed=embed, view=self)


# ---------- MINIJUEGOS INTERACTIVOS EN VIVO ----------

class AtajarManaosMinigameView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: int, parent_interaction: discord.Interaction):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.guild_id = guild_id
        self.interaction = parent_interaction
        self.grid_w = 5
        self.grid_h = 4
        self.basket_x = 2
        self.bottle_x = random.randint(0, 4)
        self.bottle_y = 0
        self.score = 0
        self.target_score = 3
        self.lives = 2
        self.game_over = False
        self.last_action = "¡Mové la canasta 🧺 con los botones para atajar la Manaos 🥤 antes de que toque el suelo!"
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if not self.game_over:
            btn_left = discord.ui.Button(label="Mover Izquierda", emoji="⬅️", style=discord.ButtonStyle.primary)
            btn_down = discord.ui.Button(label="Esperar / Bajar", emoji="⬇️", style=discord.ButtonStyle.secondary)
            btn_right = discord.ui.Button(label="Mover Derecha", emoji="➡️", style=discord.ButtonStyle.primary)

            btn_left.callback = self.on_move_left
            btn_down.callback = self.on_move_down
            btn_right.callback = self.on_move_right

            self.add_item(btn_left)
            self.add_item(btn_down)
            self.add_item(btn_right)

    def render_board(self) -> str:
        lines = []
        for y in range(self.grid_h):
            row = []
            for x in range(self.grid_w):
                if y == self.bottle_y and x == self.bottle_x:
                    if y == self.grid_h - 1:
                        if x == self.basket_x:
                            row.append("🎯")
                        else:
                            row.append("💥")
                    else:
                        row.append("🥤")
                elif y == self.grid_h - 1 and x == self.basket_x:
                    row.append("🧺")
                else:
                    row.append("⬛")
            lines.append("".join(row))
        return "\n".join(lines)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🥤 Minijuego: Atajar las Manaos",
            description=(
                f"🎯 **Atajadas:** `{self.score}/{self.target_score}`  •  ❤️ **Vidas:** `{self.lives}`\n\n"
                f"{self.render_board()}\n\n"
                f"ℹ️ *{self.last_action}*"
            ),
            color=discord.Color.blue() if not self.game_over else (discord.Color.green() if self.score >= self.target_score else discord.Color.red()),
        )
        return embed

    async def advance_tick(self, interaction: discord.Interaction):
        self.bottle_y += 1
        if self.bottle_y == self.grid_h - 1:
            if self.basket_x == self.bottle_x:
                self.score += 1
                self.last_action = "🎯 ¡Excelente atajada! +1 botella salvada."
            else:
                self.lives -= 1
                self.last_action = "💥 ¡SE REVENTÓ UNA MANAOS EN EL PISO!"

            if self.score >= self.target_score:
                self.game_over = True
                await self.on_win(interaction)
                return
            elif self.lives <= 0:
                self.game_over = True
                await self.on_fail(interaction)
                return
            else:
                self.bottle_x = random.randint(0, self.grid_w - 1)
                self.bottle_y = 0

        self.update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_move_left(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Este juego no es tuyo! 😅", ephemeral=True)
            return
        if self.basket_x > 0:
            self.basket_x -= 1
        await self.advance_tick(interaction)

    async def on_move_right(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Este juego no es tuyo! 😅", ephemeral=True)
            return
        if self.basket_x < self.grid_w - 1:
            self.basket_x += 1
        await self.advance_tick(interaction)

    async def on_move_down(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Este juego no es tuyo! 😅", ephemeral=True)
            return
        await self.advance_tick(interaction)

    async def on_win(self, interaction: discord.Interaction):
        cash = random.randint(350, 600)
        xp = random.randint(25, 40)
        now = int(time.time())

        with get_connection() as conn:
            ensure_user(conn, self.guild_id, self.user_id)
            conn.execute(
                "UPDATE users SET money=money+?, xp=xp+?, last_work=? WHERE guild_id=? AND user_id=?",
                (cash, xp, now, self.guild_id, self.user_id),
            )
            user = conn.execute("SELECT money, xp FROM users WHERE guild_id=? AND user_id=?", (self.guild_id, self.user_id)).fetchone()

        restock_kiosk(self.guild_id, 1, 2)

        embed = discord.Embed(
            title="🎉 ¡VICTORIA! 🥤 Atajaste todas las Manaos",
            description=(
                f"{self.render_board()}\n\n"
                f"¡Sos un maestro de los reflejos! No se rompió ni una sola botella.\n\n"
                f"💵 **Cobraste:** +{money(cash)}\n"
                f"⭐ **Ganaste:** +{xp} XP\n\n"
                f"💼 Billetera: **{money(user['money'])}** | ⭐ Total: **{user['xp']} XP**"
            ),
            color=discord.Color.green(),
        )
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_fail(self, interaction: discord.Interaction):
        now = int(time.time())
        with get_connection() as conn:
            ensure_user(conn, self.guild_id, self.user_id)
            conn.execute(
                "UPDATE users SET last_work=? WHERE guild_id=? AND user_id=?",
                (now, self.guild_id, self.user_id),
            )

        embed = discord.Embed(
            title="💥 ¡TE RAJARON DEL KIOSCO!",
            description=(
                f"{self.render_board()}\n\n"
                f"❌ Rompiste las botellas y llenaste el pasillo de gas y líquido pegajoso.\n"
                f"🧔 **El Kiosquero:** *«¡Me hiciste perder mercadería! ¡Volá de acá!»*\n\n"
                f"💸 **Cobro:** $0 • ⭐ **XP:** 0\n"
                f"⏳ Podés volver a laburar en **{CONFIG['changuita_cooldown_minutes']} minutos**."
            ),
            color=discord.Color.red(),
        )
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
        await notify_fired(interaction, "¡No pudo atajar las botellas de Manaos que caían del camión y se reventaron contra el piso!")


class RepararHeladeraMinigameView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: int, parent_interaction: discord.Interaction):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.guild_id = guild_id
        self.interaction = parent_interaction
        self.phase = 1
        self.cables_step = 0
        self.temp = 24
        self.target_min = 0
        self.target_max = 4
        self.setup_phase_1()

    def setup_phase_1(self):
        self.clear_items()
        if self.cables_step == 0:
            options = [
                ("⚡ Termostato del Compresor", True),
                ("🌊 Caño de desagüe de agua", False),
                ("🚪 Burlete de goma", False),
            ]
        elif self.cables_step == 1:
            options = [
                ("💡 Luz decorativa rota", False),
                ("❄️ Ventilador del evaporador", True),
                ("🍫 Estante de golosinas", False),
            ]
        else:
            options = [
                ("🔩 Chasis metálico de masa", True),
                ("🔌 Puentear directo a 220V", False),
                ("🧊 Bloque de hielo", False),
            ]

        random.shuffle(options)
        for label, is_correct in options:
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary)
            if is_correct:
                btn.callback = self.on_correct_cable
            else:
                btn.callback = self.on_wrong_cable
            self.add_item(btn)

    def setup_phase_2(self):
        self.clear_items()
        btn_cool_big = discord.ui.Button(label="Gas Rápido (-10°C)", emoji="❄️", style=discord.ButtonStyle.primary)
        btn_cool_small = discord.ui.Button(label="Gas Fino (-4°C)", emoji="🧊", style=discord.ButtonStyle.primary)
        btn_heat = discord.ui.Button(label="Abrir Válvula (+6°C)", emoji="🔥", style=discord.ButtonStyle.secondary)
        btn_lock = discord.ui.Button(label="Bloquear Termostato", emoji="✅", style=discord.ButtonStyle.success)

        btn_cool_big.callback = lambda i: self.adjust_temp(i, -10)
        btn_cool_small.callback = lambda i: self.adjust_temp(i, -4)
        btn_heat.callback = lambda i: self.adjust_temp(i, +6)
        btn_lock.callback = self.lock_thermostat

        self.add_item(btn_cool_big)
        self.add_item(btn_cool_small)
        self.add_item(btn_heat)
        self.add_item(btn_lock)

    def build_embed(self) -> discord.Embed:
        if self.phase == 1:
            cables = ["🔴 Rojo (Fase Principal)", "🔵 Azul (Neutro)", "🟢 Verde (Descarga a Tierra)"]
            current_wire = cables[self.cables_step]
            embed = discord.Embed(
                title="❄️ Minijuego: Reparar la Heladera Exhibidora (Fase 1/2)",
                description=(
                    f"🔌 **Conectando Circuito Eléctrico** (Cable {self.cables_step + 1}/3)\n\n"
                    f"¿A qué terminal conectás el **{current_wire}**?\n\n"
                    f"⚠️ *¡Cuidado con no tocar el terminal equivocado o salta la térmica!*"
                ),
                color=discord.Color.gold(),
            )
        else:
            if self.temp < self.target_min:
                temp_status = "🧊 ¡CONGELADA! (Se van a reventar las botellas de vidrio)"
                bar_color = "🟦"
            elif self.target_min <= self.temp <= self.target_max:
                temp_status = "✨ ¡TEMPERATURA PERFECTA! (Bebidas al punto justo)"
                bar_color = "🟩"
            else:
                temp_status = "🔥 CALIENTE (La birra y la Manaos están tibias)"
                bar_color = "🟥"

            embed = discord.Embed(
                title="❄️ Minijuego: Reparar la Heladera Exhibidora (Fase 2/2)",
                description=(
                    f"🌡️ **Calibración del Termostato y Gas Refrigerante**\n\n"
                    f"**Temperatura actual:** `{self.temp}°C` {bar_color}\n"
                    f"**Rango ideal:** `{self.target_min}°C a {self.target_max}°C` 🎯\n\n"
                    f"Estado: **{temp_status}**\n\n"
                    f"Usá los botones para regular la temperatura y dale a **Bloquear Termostato** en el rango ideal."
                ),
                color=discord.Color.green() if self.target_min <= self.temp <= self.target_max else discord.Color.blue(),
            )
        return embed

    async def on_wrong_cable(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Este trabajo no es tuyo! 😅", ephemeral=True)
            return
        now = int(time.time())
        with get_connection() as conn:
            ensure_user(conn, self.guild_id, self.user_id)
            conn.execute(
                "UPDATE users SET last_work=? WHERE guild_id=? AND user_id=?",
                (now, self.guild_id, self.user_id),
            )
        embed = discord.Embed(
            title="⚡ ¡CORTO CIRCUITO Y FOGONAZO!",
            description=(
                f"💥 Conectaste el cable al lugar equivocado, saltó la térmica y salió humo negro del motor de la heladera.\n\n"
                f"🧔 **El Kiosquero:** *«¡Casi me prendés fuego el boliche, animal! ¡Tomátelas!»*\n\n"
                f"💸 **Cobro:** $0 • ⭐ **XP:** 0\n"
                f"⏳ Podés volver a laburar en **{CONFIG['changuita_cooldown_minutes']} minutos**."
            ),
            color=discord.Color.red(),
        )
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
        await notify_fired(interaction, "¡Conectó un cable al lugar equivocado, hizo saltar la térmica y casi prende fuego la heladera!")

    async def on_correct_cable(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Este trabajo no es tuyo! 😅", ephemeral=True)
            return
        self.cables_step += 1
        if self.cables_step < 3:
            self.setup_phase_1()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            self.phase = 2
            self.setup_phase_2()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def adjust_temp(self, interaction: discord.Interaction, delta: int):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Este trabajo no es tuyo! 😅", ephemeral=True)
            return
        self.temp += delta
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def lock_thermostat(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Este trabajo no es tuyo! 😅", ephemeral=True)
            return

        if self.target_min <= self.temp <= self.target_max:
            cash = random.randint(700, 1000)
            xp = random.randint(40, 60)
            now = int(time.time())
            with get_connection() as conn:
                ensure_user(conn, self.guild_id, self.user_id)
                conn.execute(
                    "UPDATE users SET money=money+?, xp=xp+?, last_work=? WHERE guild_id=? AND user_id=?",
                    (cash, xp, now, self.guild_id, self.user_id),
                )
                user = conn.execute("SELECT money, xp FROM users WHERE guild_id=? AND user_id=?", (self.guild_id, self.user_id)).fetchone()

            restock_kiosk(self.guild_id, 2, 3)

            embed = discord.Embed(
                title="❄️ ¡HELADERA REPARADA Y CONGELANDO! 🍾",
                description=(
                    f"¡Quedó calibrada a **{self.temp}°C**! El motor ronronea y las Manaos están bajo cero.\n\n"
                    f"💵 **Cobraste:** +{money(cash)} (Changuita Pesada)\n"
                    f"⭐ **Ganaste:** +{xp} XP\n\n"
                    f"💼 Billetera: **{money(user['money'])}** | ⭐ Total: **{user['xp']} XP**"
                ),
                color=discord.Color.green(),
            )
            self.clear_items()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            now = int(time.time())
            with get_connection() as conn:
                ensure_user(conn, self.guild_id, self.user_id)
                conn.execute(
                    "UPDATE users SET last_work=? WHERE guild_id=? AND user_id=?",
                    (now, self.guild_id, self.user_id),
                )
            error_reason = "quedó tibia y se pudrieron los yogures" if self.temp > self.target_max else "se congelaron y reventaron las botellas de vidrio"
            embed = discord.Embed(
                title="💥 ¡CALIBRACIÓN FALLIDA!",
                description=(
                    f"❌ Bloqueaste el termostato a **{self.temp}°C** (fuera de rango).\n"
                    f"Como resultado, {error_reason}.\n\n"
                    f"🧔 **El Kiosquero:** *«¡Sos un desastre técnico! ¡Afuera de acá!»*\n\n"
                    f"💸 **Cobro:** $0 • ⭐ **XP:** 0\n"
                    f"⏳ Podés volver a laburar en **{CONFIG['changuita_cooldown_minutes']} minutos**."
                ),
                color=discord.Color.red(),
            )
            self.clear_items()
            await interaction.response.edit_message(embed=embed, view=self)
            await notify_fired(interaction, f"¡Bloqueó el termostato a {self.temp}°C ({error_reason})!")


class BuscaminasDepositoView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: int, parent_interaction: discord.Interaction):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.guild_id = guild_id
        self.interaction = parent_interaction
        self.size = 9
        content_pool = ["🍫", "🥤", "🍪", "🍬", "🧃", "🍾", "🕸️", "🕸️", "🐀"]
        random.shuffle(content_pool)
        self.grid_content = content_pool
        self.revealed = [False] * 9
        self.opened_count = 0
        self.accumulated_cash = 0
        self.accumulated_xp = 0
        self.game_over = False
        self.build_grid()

    def build_grid(self):
        self.clear_items()
        for idx in range(self.size):
            if self.revealed[idx] or self.game_over:
                item = self.grid_content[idx]
                style = discord.ButtonStyle.danger if item == "🐀" else discord.ButtonStyle.secondary
                btn = discord.ui.Button(label=item, style=style, disabled=True, row=idx // 3)
            else:
                btn = discord.ui.Button(label=f"📦 {idx + 1}", style=discord.ButtonStyle.primary, row=idx // 3)
                btn.callback = self.make_box_callback(idx)
            self.add_item(btn)

        if not self.game_over and self.opened_count >= 2:
            cashout_btn = discord.ui.Button(
                label=f"🏃 Retirarse y Cobrar ({money(self.accumulated_cash)})",
                style=discord.ButtonStyle.success,
                row=3,
            )
            cashout_btn.callback = self.on_cashout
            self.add_item(cashout_btn)

    def make_box_callback(self, idx: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("¡Este juego no es tuyo! 😅", ephemeral=True)
                return

            if self.game_over:
                return

            self.revealed[idx] = True
            item = self.grid_content[idx]

            if item == "🐀":
                self.game_over = True
                now = int(time.time())
                with get_connection() as conn:
                    ensure_user(conn, self.guild_id, self.user_id)
                    conn.execute(
                        "UPDATE users SET last_work=? WHERE guild_id=? AND user_id=?",
                        (now, self.guild_id, self.user_id),
                    )

                self.build_grid()
                embed = discord.Embed(
                    title="🐀 ¡SALTÓ LA RATA DEL DEPÓSITO!",
                    description=(
                        "😱 Abriste la caja y te saltó una rata gigante a la cara. Saliste corriendo a los gritos y perdiste todo lo acumulado.\n\n"
                        f"💸 **Cobro:** $0 • ⭐ **XP:** 0\n"
                        f"⏳ Podés volver a laburar en **{CONFIG['changuita_cooldown_minutes']} minutos**."
                    ),
                    color=discord.Color.red(),
                )
                await interaction.response.edit_message(embed=embed, view=self)
                await notify_fired(interaction, "¡Abrió una caja en el depósito, le saltó una rata gigante a la cara y salió corriendo a los gritos!")
                return

            self.opened_count += 1
            if item != "🕸️":
                self.accumulated_cash += random.randint(120, 180)
                self.accumulated_xp += random.randint(8, 14)

            safe_boxes = sum(1 for x in self.grid_content if x != "🐀")
            opened_safe = sum(1 for i, r in enumerate(self.revealed) if r and self.grid_content[i] != "🐀")
            if opened_safe == safe_boxes:
                await self.on_win_all(interaction)
                return

            self.build_grid()
            embed = discord.Embed(
                title="📦 Buscaminas del Depósito",
                description=(
                    f"¡Encontraste: {item}!\n\n"
                    f"💵 **Acumulado:** `{money(self.accumulated_cash)}`\n"
                    f"⭐ **XP Acumulada:** `+{self.accumulated_xp} XP`\n\n"
                    f"📦 Cajas abiertas: `{self.opened_count}/{safe_boxes}`\n"
                    "*(Abrí más cajas para ganar más o retirate seguro si ya tenés 2 abiertas)*"
                ),
                color=discord.Color.gold(),
            )
            await interaction.response.edit_message(embed=embed, view=self)

        return callback

    async def on_cashout(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Este juego no es tuyo! 😅", ephemeral=True)
            return

        self.game_over = True
        now = int(time.time())
        with get_connection() as conn:
            ensure_user(conn, self.guild_id, self.user_id)
            conn.execute(
                "UPDATE users SET money=money+?, xp=xp+?, last_work=? WHERE guild_id=? AND user_id=?",
                (self.accumulated_cash, self.accumulated_xp, now, self.guild_id, self.user_id),
            )
            user = conn.execute("SELECT money, xp FROM users WHERE guild_id=? AND user_id=?", (self.guild_id, self.user_id)).fetchone()

        restock_kiosk(self.guild_id, 1, 2)
        self.build_grid()
        embed = discord.Embed(
            title="💼 ¡Te retiraste con la mercadería a salvo!",
            description=(
                f"💵 **Cobraste:** +{money(self.accumulated_cash)}\n"
                f"⭐ **Ganaste:** +{self.accumulated_xp} XP\n\n"
                f"💼 Billetera: **{money(user['money'])}** | ⭐ Total: **{user['xp']} XP**"
            ),
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_win_all(self, interaction: discord.Interaction):
        self.game_over = True
        bonus_cash = self.accumulated_cash + 250
        bonus_xp = self.accumulated_xp + 20
        now = int(time.time())
        with get_connection() as conn:
            ensure_user(conn, self.guild_id, self.user_id)
            conn.execute(
                "UPDATE users SET money=money+?, xp=xp+?, last_work=? WHERE guild_id=? AND user_id=?",
                (bonus_cash, bonus_xp, now, self.guild_id, self.user_id),
            )
            user = conn.execute("SELECT money, xp FROM users WHERE guild_id=? AND user_id=?", (self.guild_id, self.user_id)).fetchone()

        restock_kiosk(self.guild_id, 2, 3)
        self.build_grid()
        embed = discord.Embed(
            title="🏆 ¡DEPÓSITO 100% LIMPIO Y SIN RATAS!",
            description=(
                f"¡Abriste todas las cajas seguras sin tocar la rata! ¡Sos un crack total!\n\n"
                f"💵 **Cobraste con bonus:** +{money(bonus_cash)}\n"
                f"⭐ **Ganaste con bonus:** +{bonus_xp} XP\n\n"
                f"💼 Billetera: **{money(user['money'])}** | ⭐ Total: **{user['xp']} XP**"
            ),
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=self)


class BarrerPisoMinigameView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: int, parent_interaction: discord.Interaction):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.guild_id = guild_id
        self.interaction = parent_interaction
        self.size = 9
        pool = ["🍂", "🧻", "🍂", "🧻", "✨", "✨", "✨", "✨", "🪳"]
        random.shuffle(pool)
        self.tiles = pool
        self.cleaned = [False] * 9
        self.game_over = False
        self.build_grid()

    def build_grid(self):
        self.clear_items()
        for idx in range(self.size):
            item = self.tiles[idx]
            if self.cleaned[idx] or (item == "✨" and not self.game_over):
                btn = discord.ui.Button(label="✨ Limpio", style=discord.ButtonStyle.secondary, disabled=True, row=idx // 3)
            elif self.game_over:
                style = discord.ButtonStyle.danger if item == "🪳" else discord.ButtonStyle.secondary
                btn = discord.ui.Button(label=item, style=style, disabled=True, row=idx // 3)
            else:
                label = "🍂 Hojas" if item == "🍂" else ("🧻 Papel" if item == "🧻" else ("🪳 Cuca" if item == "🪳" else "✨"))
                btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary, row=idx // 3)
                btn.callback = self.make_callback(idx)
            self.add_item(btn)

    def make_callback(self, idx: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("¡Este laburo no es tuyo! 😅", ephemeral=True)
                return
            if self.game_over:
                return

            item = self.tiles[idx]
            if item == "🪳":
                self.game_over = True
                now = int(time.time())
                with get_connection() as conn:
                    ensure_user(conn, self.guild_id, self.user_id)
                    conn.execute("UPDATE users SET last_work=? WHERE guild_id=? AND user_id=?", (now, self.guild_id, self.user_id))
                self.build_grid()
                embed = discord.Embed(
                    title="🪳 ¡PISASTE LA CUCARACHA Y VOLÓ A TU CARA!",
                    description=(
                        "😱 Te pegaste el susto de tu vida, revoleaste la escoba y tiraste un estante.\n\n"
                        "🧔 **El Kiosquero:** *«¡Qué escándalo hacés por un bicho! ¡Volá de acá!»*\n\n"
                        f"💸 **Cobro:** $0 • ⭐ **XP:** 0\n"
                        f"⏳ Podés volver a laburar en **{CONFIG['changuita_cooldown_minutes']} minutos**."
                    ),
                    color=discord.Color.red(),
                )
                await interaction.response.edit_message(embed=embed, view=self)
                await notify_fired(interaction, "¡Pisó una cucaracha mientras barría el salón, se asustó, revoleó la escoba y tiró un estante de golosinas!")
                return

            self.cleaned[idx] = True
            dirty_indices = [i for i, t in enumerate(self.tiles) if t in ("🍂", "🧻")]
            if all(self.cleaned[i] for i in dirty_indices):
                self.game_over = True
                cash = random.randint(150, 300)
                xp = random.randint(10, 20)
                now = int(time.time())
                with get_connection() as conn:
                    ensure_user(conn, self.guild_id, self.user_id)
                    conn.execute("UPDATE users SET money=money+?, xp=xp+?, last_work=? WHERE guild_id=? AND user_id=?", (cash, xp, now, self.guild_id, self.user_id))
                    user = conn.execute("SELECT money, xp FROM users WHERE guild_id=? AND user_id=?", (self.guild_id, self.user_id)).fetchone()

                self.build_grid()
                embed = discord.Embed(
                    title="✨ ¡PISO IMPECABLE Y BARRIDO! 🧹",
                    description=(
                        "¡Dejaste el salón de ventas reluciente como un espejo!\n\n"
                        f"💵 **Cobraste:** +{money(cash)}\n"
                        f"⭐ **Ganaste:** +{xp} XP\n\n"
                        f"💼 Billetera: **{money(user['money'])}** | ⭐ Total: **{user['xp']} XP**"
                    ),
                    color=discord.Color.green(),
                )
                await interaction.response.edit_message(embed=embed, view=self)
                return

            self.build_grid()
            embed = discord.Embed(
                title="🧹 Barrer el piso del salón",
                description=(
                    "Hacé clic en todas las casillas con basura (`🍂`, `🧻`) para barrerlas.\n\n"
                    "⚠️ *¡Cuidado de no tocar la cucaracha `🪳` que anda suelta!*"
                ),
                color=discord.Color.gold(),
            )
            await interaction.response.edit_message(embed=embed, view=self)

        return callback


class OrdenarProductosMinigameView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: int, parent_interaction: discord.Interaction):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.guild_id = guild_id
        self.interaction = parent_interaction
        self.phase = 1
        self.sequence = random.sample(PRODUCT_LIST, 4)
        self.current_step = 0
        self.game_over = False
        self.setup_phase_1()

    def setup_phase_1(self):
        self.clear_items()
        btn_ready = discord.ui.Button(label="🧠 ¡Ya memoricé el orden, empezar!", style=discord.ButtonStyle.success)
        btn_ready.callback = self.start_ordering
        self.add_item(btn_ready)

    def setup_phase_2(self):
        self.clear_items()
        shuffled = self.sequence.copy()
        random.shuffle(shuffled)
        for p in shuffled:
            btn = discord.ui.Button(label=p["name"], emoji=p["emoji"], style=discord.ButtonStyle.primary)
            btn.callback = self.make_product_callback(p["id"])
            self.add_item(btn)

    def build_embed(self) -> discord.Embed:
        if self.phase == 1:
            seq_text = " ➔ ".join([f"{p['emoji']} **{p['name']}**" for p in self.sequence])
            embed = discord.Embed(
                title="🍫 Simón Dice de Góndola (Memorización)",
                description=(
                    "El kiosquero te pidió acomodar este pedido exacto en la estantería:\n\n"
                    f"📦 **Secuencia a memorizar:**\n{seq_text}\n\n"
                    "Cuando tengas clara la secuencia en la cabeza, tocá el botón verde para arrancar."
                ),
                color=discord.Color.gold(),
            )
        else:
            placed = " ➔ ".join([f"{self.sequence[i]['emoji']} {self.sequence[i]['name']}" for i in range(self.current_step)])
            if not placed:
                placed = "*(Góndola vacía)*"
            embed = discord.Embed(
                title="🍫 Simón Dice de Góndola (Acomodando)",
                description=(
                    f"Progreso: `{self.current_step}/4` productos colocados.\n\n"
                    f"🛒 **Colocados:** {placed}\n\n"
                    "👉 *Tocá el siguiente producto que corresponde en la secuencia.*"
                ),
                color=discord.Color.blue(),
            )
        return embed

    async def start_ordering(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Este laburo no es tuyo! 😅", ephemeral=True)
            return
        self.phase = 2
        self.setup_phase_2()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    def make_product_callback(self, prod_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("¡Este laburo no es tuyo! 😅", ephemeral=True)
                return
            if self.game_over:
                return

            expected = self.sequence[self.current_step]
            if prod_id != expected["id"]:
                self.game_over = True
                now = int(time.time())
                with get_connection() as conn:
                    ensure_user(conn, self.guild_id, self.user_id)
                    conn.execute("UPDATE users SET last_work=? WHERE guild_id=? AND user_id=?", (now, self.guild_id, self.user_id))
                self.clear_items()
                embed = discord.Embed(
                    title="💥 ¡MANDASTE CUALQUIERA EN LA GÓNDOLA!",
                    description=(
                        f"❌ Pusiste un producto equivocado y desarmaste toda la exhibición.\n\n"
                        f"🧔 **El Kiosquero:** *«¡Te pedí {expected['name']} y me encajás cualquier cosa! ¡Afuera!»*\n\n"
                        f"💸 **Cobro:** $0 • ⭐ **XP:** 0\n"
                        f"⏳ Podés volver a laburar en **{CONFIG['changuita_cooldown_minutes']} minutos**."
                    ),
                    color=discord.Color.red(),
                )
                await interaction.response.edit_message(embed=embed, view=self)
                await notify_fired(interaction, f"¡Puso mercadería equivocada en la góndola (se le pidió {expected['name']}) y desarmó toda la exhibición!")
                return

            self.current_step += 1
            if self.current_step == 4:
                self.game_over = True
                cash = random.randint(300, 600)
                xp = random.randint(20, 35)
                now = int(time.time())
                with get_connection() as conn:
                    ensure_user(conn, self.guild_id, self.user_id)
                    conn.execute("UPDATE users SET money=money+?, xp=xp+?, last_work=? WHERE guild_id=? AND user_id=?", (cash, xp, now, self.guild_id, self.user_id))
                    user = conn.execute("SELECT money, xp FROM users WHERE guild_id=? AND user_id=?", (self.guild_id, self.user_id)).fetchone()

                restock_kiosk(self.guild_id, 1, 2)
                self.clear_items()
                embed = discord.Embed(
                    title="✨ ¡GÓNDOLA PERFECTAMENTE ORDENADA! 🍫",
                    description=(
                        "¡Sos un fenómeno de la memoria! Acomodaste los 4 productos en orden exacto.\n\n"
                        f"💵 **Cobraste:** +{money(cash)}\n"
                        f"⭐ **Ganaste:** +{xp} XP\n\n"
                        f"💼 Billetera: **{money(user['money'])}** | ⭐ Total: **{user['xp']} XP**"
                    ),
                    color=discord.Color.green(),
                )
                await interaction.response.edit_message(embed=embed, view=self)
                return

            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        return callback


class MoverCajasMinigameView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: int, parent_interaction: discord.Interaction):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.guild_id = guild_id
        self.interaction = parent_interaction
        self.force = 0
        self.game_over = False
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if not self.game_over:
            btn_force = discord.ui.Button(label="¡HACER FUERZA! (+25%)", emoji="🏋️", style=discord.ButtonStyle.primary)
            btn_trap = discord.ui.Button(label="Trabar con el pie", emoji="🦶", style=discord.ButtonStyle.secondary)

            btn_force.callback = self.on_force
            btn_trap.callback = self.on_trap

            btns = [btn_force, btn_trap]
            random.shuffle(btns)
            for b in btns:
                self.add_item(b)

    def render_bar(self) -> str:
        total_blocks = 10
        filled = int((self.force / 100) * total_blocks)
        bar = "█" * filled + "░" * (total_blocks - filled)
        return f"[{bar}] {self.force}%"

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🏋️ Minijuego: Mover Cajas Pesadas (Fuerza QTE)",
            description=(
                f"📦 **Levantando cajones de bebidas al depósito alto...**\n\n"
                f"**Potencia de empuje:** `{self.render_bar()}`\n\n"
                "👉 *Presioná **¡HACER FUERZA!** para llegar al 100% sin aflojar. ¡Cuidado con pisar en falso!*"
            ),
            color=discord.Color.gold(),
        )
        return embed

    async def on_force(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Este laburo no es tuyo! 😅", ephemeral=True)
            return
        if self.game_over:
            return

        self.force += 25
        if self.force >= 100:
            self.game_over = True
            cash = random.randint(600, 1000)
            xp = random.randint(35, 60)
            now = int(time.time())
            with get_connection() as conn:
                ensure_user(conn, self.guild_id, self.user_id)
                conn.execute("UPDATE users SET money=money+?, xp=xp+?, last_work=? WHERE guild_id=? AND user_id=?", (cash, xp, now, self.guild_id, self.user_id))
                user = conn.execute("SELECT money, xp FROM users WHERE guild_id=? AND user_id=?", (self.guild_id, self.user_id)).fetchone()

            restock_kiosk(self.guild_id, 2, 3)
            self.clear_items()
            embed = discord.Embed(
                title="💪 ¡CAJONES ACOMODADOS EN LO ALTO! 📦",
                description=(
                    f"**Potencia alcanzada:** `[██████████] 100%`\n\n"
                    "¡Tremendo lomo tenés! Subiste la carga sin que se caiga ni una botella.\n\n"
                    f"💵 **Cobraste:** +{money(cash)} (Changuita Pesada)\n"
                    f"⭐ **Ganaste:** +{xp} XP\n\n"
                    f"💼 Billetera: **{money(user['money'])}** | ⭐ Total: **{user['xp']} XP**"
                ),
                color=discord.Color.green(),
            )
            await interaction.response.edit_message(embed=embed, view=self)
            return

        self.update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_trap(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Este laburo no es tuyo! 😅", ephemeral=True)
            return
        self.game_over = True
        now = int(time.time())
        with get_connection() as conn:
            ensure_user(conn, self.guild_id, self.user_id)
            conn.execute("UPDATE users SET last_work=? WHERE guild_id=? AND user_id=?", (now, self.guild_id, self.user_id))

        self.clear_items()
        embed = discord.Embed(
            title="💥 ¡TE PATINASTE Y SE TE CAYERON 5 CAJONES ENCIMA!",
            description=(
                "🦴 Quisiste trabar con el pie, resbalaste en el piso y llovieron botellas.\n\n"
                "🧔 **El Kiosquero:** *«¡Me rompiste 5 cajones enteros de cerveza! ¡Tomátelas!»*\n\n"
                f"💸 **Cobro:** $0 • ⭐ **XP:** 0\n"
                f"⏳ Podés volver a laburar en **{CONFIG['changuita_cooldown_minutes']} minutos**."
            ),
            color=discord.Color.red(),
        )
        await interaction.response.edit_message(embed=embed, view=self)
        await notify_fired(interaction, "¡Quiso trabar una columna de cajones de cerveza con el pie, resbaló en el piso y se le cayeron 5 cajones encima!")


class CobrarCajaMinigameView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: int, parent_interaction: discord.Interaction):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.guild_id = guild_id
        self.interaction = parent_interaction

        customers = [
            ("Doña Rosa 👵", "un alfajor Jorgito y una Manaos"),
            ("Don Carlos 👴", "un atado de puchos y un turrón"),
            ("El Pibe de la Moto 🛵", "tres Don Satur y un energizante"),
            ("La Vecina del 3B 👩", "dos chocolates y caramelos"),
            ("El Tano de la esquina 👨", "una Coca y un paquete de galletitas"),
        ]
        cust, items = random.choice(customers)
        self.customer = cust
        self.items_desc = items

        costs = [350, 450, 650, 750, 850, 1150, 1250, 1350, 1650, 1750, 2350, 2650, 3150, 3450]
        self.cost = random.choice(costs)
        if self.cost < 1000:
            self.paid = random.choice([1000, 2000])
        elif self.cost < 2000:
            self.paid = random.choice([2000, 5000])
        else:
            self.paid = 5000

        self.exact_change = self.paid - self.cost
        self.delivered = 0
        self.game_over = False
        self.build_buttons()

    def build_buttons(self):
        self.clear_items()
        if not self.game_over:
            btn_1000 = discord.ui.Button(label="+$1.000", emoji="💵", style=discord.ButtonStyle.primary, row=0)
            btn_500 = discord.ui.Button(label="+$500", emoji="💵", style=discord.ButtonStyle.primary, row=0)
            btn_200 = discord.ui.Button(label="+$200", emoji="💵", style=discord.ButtonStyle.primary, row=0)
            btn_100 = discord.ui.Button(label="+$100", emoji="💵", style=discord.ButtonStyle.primary, row=0)
            btn_50 = discord.ui.Button(label="+$50", emoji="🪙", style=discord.ButtonStyle.secondary, row=1)
            btn_reset = discord.ui.Button(label="Borrar ($0)", emoji="🔄", style=discord.ButtonStyle.danger, row=1)
            btn_confirm = discord.ui.Button(label="Entregar Vuelto", emoji="✅", style=discord.ButtonStyle.success, row=1)

            btn_1000.callback = lambda i: self.add_money(i, 1000)
            btn_500.callback = lambda i: self.add_money(i, 500)
            btn_200.callback = lambda i: self.add_money(i, 200)
            btn_100.callback = lambda i: self.add_money(i, 100)
            btn_50.callback = lambda i: self.add_money(i, 50)
            btn_reset.callback = self.reset_money
            btn_confirm.callback = self.confirm_change

            self.add_item(btn_1000)
            self.add_item(btn_500)
            self.add_item(btn_200)
            self.add_item(btn_100)
            self.add_item(btn_50)
            self.add_item(btn_reset)
            self.add_item(btn_confirm)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🧮 Minijuego: Cobrar en la Caja Registradora",
            description=(
                f"{self.customer} compró **{self.items_desc}**.\n\n"
                f"🧾 **Total de la compra:** **{money(self.cost)}**\n"
                f"💵 **Pagó con:** **{money(self.paid)}**\n\n"
                f"🪙 **Dinero colocado en el mostrador:** **{money(self.delivered)}**\n\n"
                "💡 *Hacé la cuenta mental del vuelto que le corresponde, armá el dinero con los botones y dale a **Entregar Vuelto**.*"
            ),
            color=discord.Color.gold(),
        )
        return embed

    async def add_money(self, interaction: discord.Interaction, amount: int):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Este laburo no es tuyo! 😅", ephemeral=True)
            return
        if self.game_over:
            return
        self.delivered += amount
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def reset_money(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Este laburo no es tuyo! 😅", ephemeral=True)
            return
        if self.game_over:
            return
        self.delivered = 0
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def confirm_change(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Este laburo no es tuyo! 😅", ephemeral=True)
            return
        if self.game_over:
            return

        self.game_over = True
        now = int(time.time())

        if self.delivered == self.exact_change:
            cash = random.randint(300, 600)
            xp = random.randint(20, 35)
            with get_connection() as conn:
                ensure_user(conn, self.guild_id, self.user_id)
                conn.execute("UPDATE users SET money=money+?, xp=xp+?, last_work=? WHERE guild_id=? AND user_id=?", (cash, xp, now, self.guild_id, self.user_id))
                user = conn.execute("SELECT money, xp FROM users WHERE guild_id=? AND user_id=?", (self.guild_id, self.user_id)).fetchone()

            self.clear_items()
            embed = discord.Embed(
                title="✨ ¡VUELTO EXACTO Y CLIENTE FELIZ! 💵",
                description=(
                    f"¡Calculaste perfecto! El vuelto exacto era **{money(self.exact_change)}**.\n"
                    f"{self.customer} te agradece sonriendo y se va contento.\n\n"
                    f"💵 **Cobraste:** +{money(cash)}\n"
                    f"⭐ **Ganaste:** +{xp} XP\n\n"
                    f"💼 Billetera: **{money(user['money'])}** | ⭐ Total: **{user['xp']} XP**"
                ),
                color=discord.Color.green(),
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            with get_connection() as conn:
                ensure_user(conn, self.guild_id, self.user_id)
                conn.execute("UPDATE users SET last_work=? WHERE guild_id=? AND user_id=?", (now, self.guild_id, self.user_id))

            self.clear_items()
            if self.delivered > self.exact_change:
                reason = f"Le diste **{money(self.delivered)}** cuando el vuelto era **{money(self.exact_change)}**. ¡Le regalaste plata del negocio!"
                fail_public = f"¡Le dio {money(self.delivered)} a {self.customer} cuando el vuelto era {money(self.exact_change)} (le regaló plata del negocio)!"
            else:
                reason = f"Le diste **{money(self.delivered)}** cuando el vuelto era **{money(self.exact_change)}**. ¡El cliente te gritó estafador y llamó al dueño!"
                fail_public = f"¡Le dio {money(self.delivered)} a {self.customer} cuando el vuelto era {money(self.exact_change)} y el cliente le gritó estafador!"

            embed = discord.Embed(
                title="💥 ¡ERROR GRAVE EN LA CAJA!",
                description=(
                    f"❌ **Mandaste cualquiera con la cuenta:**\n{reason}\n\n"
                    "🧔 **El Kiosquero:** *«¡No sabés ni restar, animal! ¡Dejá la caja y andate!»*\n\n"
                    f"💸 **Cobro:** $0 • ⭐ **XP:** 0\n"
                    f"⏳ Podés volver a laburar en **{CONFIG['changuita_cooldown_minutes']} minutos**."
                ),
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(embed=embed, view=self)
            await notify_fired(interaction, fail_public)


class LimpiarVidriosMinigameView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: int, parent_interaction: discord.Interaction):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.guild_id = guild_id
        self.interaction = parent_interaction
        self.step = 0
        self.cleaned = [False, False, False, False]
        self.game_over = False
        self.build_buttons()

    def build_buttons(self):
        self.clear_items()
        zones = [
            ("1. Superior Izquierda", 0, 0),
            ("2. Superior Derecha", 1, 0),
            ("3. Inferior Izquierda", 2, 1),
            ("4. Inferior Derecha", 3, 1),
        ]
        for name, idx, row in zones:
            if self.cleaned[idx]:
                btn = discord.ui.Button(label=f"✨ {name}", style=discord.ButtonStyle.secondary, disabled=True, row=row)
            elif self.game_over:
                btn = discord.ui.Button(label=f"❌ {name}", style=discord.ButtonStyle.danger, disabled=True, row=row)
            else:
                btn = discord.ui.Button(label=f"🧼 {name}", style=discord.ButtonStyle.primary, row=row)
                btn.callback = self.make_zone_callback(idx)
            self.add_item(btn)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🪟 Minijuego: Limpiar la Vidriera con Secador",
            description=(
                "El ventanal está enjabonado. Tenés que pasar la espátula secavidrios **en orden (1 ➔ 2 ➔ 3 ➔ 4)** de arriba hacia abajo.\n\n"
                f"Progreso: `{self.step}/4` zonas secadas.\n\n"
                "⚠️ *¡Si saltás de zona o pasás en seco, rayás todo el vidrio!*"
            ),
            color=discord.Color.gold(),
        )
        return embed

    def make_zone_callback(self, idx: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("¡Este laburo no es tuyo! 😅", ephemeral=True)
                return
            if self.game_over:
                return

            if idx != self.step:
                self.game_over = True
                now = int(time.time())
                with get_connection() as conn:
                    ensure_user(conn, self.guild_id, self.user_id)
                    conn.execute("UPDATE users SET last_work=? WHERE guild_id=? AND user_id=?", (now, self.guild_id, self.user_id))

                self.build_buttons()
                embed = discord.Embed(
                    title="💥 ¡RAYASTE TODO EL VENTANAL FRONTAL!",
                    description=(
                        f"❌ Pasaste la espátula en la zona {idx + 1} fuera de orden y se secó el jabón en el resto.\n\n"
                        "🧔 **El Kiosquero:** *«¡Dejaste el vidrio rayado y grasiento! ¡Tomátelas!»*\n\n"
                        f"💸 **Cobro:** $0 • ⭐ **XP:** 0\n"
                        f"⏳ Podés volver a laburar en **{CONFIG['changuita_cooldown_minutes']} minutos**."
                    ),
                    color=discord.Color.red(),
                )
                await interaction.response.edit_message(embed=embed, view=self)
                await notify_fired(interaction, f"¡Pasó la espátula en la zona {idx + 1} fuera de orden y rayó todo el ventanal frontal del kiosco!")
                return

            self.cleaned[idx] = True
            self.step += 1

            if self.step == 4:
                self.game_over = True
                cash = random.randint(300, 600)
                xp = random.randint(20, 35)
                now = int(time.time())
                with get_connection() as conn:
                    ensure_user(conn, self.guild_id, self.user_id)
                    conn.execute("UPDATE users SET money=money+?, xp=xp+?, last_work=? WHERE guild_id=? AND user_id=?", (cash, xp, now, self.guild_id, self.user_id))
                    user = conn.execute("SELECT money, xp FROM users WHERE guild_id=? AND user_id=?", (self.guild_id, self.user_id)).fetchone()

                self.build_buttons()
                embed = discord.Embed(
                    title="✨ ¡VIDRIERA IMPECABLE Y TRANSPARENTE! 🪟",
                    description=(
                        "¡Pasaste el secador con técnica perfecta! El vidrio parece invisible.\n\n"
                        f"💵 **Cobraste:** +{money(cash)}\n"
                        f"⭐ **Ganaste:** +{xp} XP\n\n"
                        f"💼 Billetera: **{money(user['money'])}** | ⭐ Total: **{user['xp']} XP**"
                    ),
                    color=discord.Color.green(),
                )
                await interaction.response.edit_message(embed=embed, view=self)
                return

            self.build_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

        return callback


class RaspaditaGameView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: int, is_sub: bool, cost: int, parent_interaction: discord.Interaction):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.guild_id = guild_id
        self.is_sub = is_sub
        self.cost = cost
        self.parent_interaction = parent_interaction
        self.revealed_indices = []
        self.game_over = False
        self.lock = asyncio.Lock()

        # Probabilidades balanceadas:
        # 0.05% -> Pozo Acumulado (🍋) (1 en 2000)
        # 7.95% -> Diamantes $3.500 (💎)
        # 12.0% -> Golosinas $1.500 + Alfajor (🍫)
        # 80.0% -> Sin premio (+$400 al pozo)
        roll = random.random()
        if roll < 0.0005:
            self.win_type = "🍋"
        elif roll < 0.0800:
            self.win_type = "💎"
        elif roll < 0.2000:
            self.win_type = "🍫"
        else:
            self.win_type = None

        if self.win_type is None:
            self.player_loss_symbols = random.choice([
                ["💎", "💎", "🍂"],
                ["🍋", "🍋", "💩"],
                ["🍫", "🍫", "🧻"],
                ["💎", "🍂", "💩"],
                ["🍋", "🪙", "🧻"],
                ["🍫", "🪙", "🍂"],
                ["🪙", "🪙", "💩"],
            ])
            self.missed_prize_symbol = random.choice(["💎", "🍫", "🍋"])

        self.board = [None] * 9
        self.build_grid()

    def build_grid(self):
        self.clear_items()
        for idx in range(9):
            row = idx // 3
            if idx in self.revealed_indices or self.game_over:
                sym = self.board[idx] or "❓"
                style = discord.ButtonStyle.success if sym in ("🍋", "💎", "🍫") else discord.ButtonStyle.secondary
                btn = discord.ui.Button(label=sym, style=style, disabled=True, row=row)
            else:
                btn = discord.ui.Button(label=f"❓ {idx + 1}", style=discord.ButtonStyle.primary, row=row)
                btn.callback = self.make_tile_callback(idx)
            self.add_item(btn)

    def build_embed(self) -> discord.Embed:
        jackpot = get_raspadita_jackpot(self.guild_id)
        scratched_count = len(self.revealed_indices)

        revealed_symbols = [self.board[i] for i in self.revealed_indices if self.board[i] is not None]
        slots = []
        for i in range(3):
            if i < len(revealed_symbols):
                slots.append(f"**[{revealed_symbols[i]}]**")
            else:
                slots.append("`[ ❓ ]`")
        slots_text = " ".join(slots)

        sub_badge = " *(🔥 Descuento Sub aplicado)*" if self.is_sub else ""

        embed = discord.Embed(
            title="🎫 Raspadita del Kiosquito 🍋",
            description=(
                f"💰 **Pozo Acumulado:** `{money(jackpot)}`\n"
                f"💵 **Ticket:** `{money(self.cost)}`{sub_badge}\n\n"
                f"Tus raspadas ({scratched_count}/3): {slots_text}\n\n"
                "👉 **Tocá 3 casillas de la grilla para rasparlas.**\n\n"
                "**Premios posibles (3 iguales):**\n"
                f"• `🍋 🍋 🍋` ➔ **¡POZO ACUMULADO!** ({money(jackpot)})\n"
                "• `💎 💎 💎` ➔ **$3.500** en efectivo\n"
                "• `🍫 🍫 🍫` ➔ **$1.500** + 1 Alfajor Jorgito"
            ),
            color=discord.Color.gold(),
        )
        return embed

    def make_tile_callback(self, idx: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("¡Este cartón no es tuyo! 😅", ephemeral=True)
                return

            async with self.lock:
                if self.game_over or idx in self.revealed_indices or len(self.revealed_indices) >= 3:
                    return

                self.revealed_indices.append(idx)
                scratched = len(self.revealed_indices)

                if self.win_type is not None:
                    self.board[idx] = self.win_type
                else:
                    self.board[idx] = self.player_loss_symbols[scratched - 1]

                if scratched < 3:
                    self.build_grid()
                    await interaction.response.edit_message(embed=self.build_embed(), view=self)
                    return

                self.game_over = True
                unpicked = [i for i in range(9) if i not in self.revealed_indices]
                random.shuffle(unpicked)

                if self.win_type is not None:
                    other_pool = [x for x in ["🍋", "💎", "🍫", "💩", "🍂", "🧻", "🪙"] if x != self.win_type]
                    extras = []
                    for s in other_pool:
                        extras.extend([s, s])
                    random.shuffle(extras)
                    for i, u_idx in enumerate(unpicked):
                        self.board[u_idx] = extras[i]
                else:
                    for u_idx in unpicked[:3]:
                        self.board[u_idx] = self.missed_prize_symbol
                    filler = [x for x in ["💩", "🍂", "🧻", "🪙", "🍫", "💎"] if x != self.missed_prize_symbol]
                    random.shuffle(filler)
                    for i, u_idx in enumerate(unpicked[3:]):
                        self.board[u_idx] = filler[i]

                c1 = self.board[self.revealed_indices[0]]
                c2 = self.board[self.revealed_indices[1]]
                c3 = self.board[self.revealed_indices[2]]

                jackpot = get_raspadita_jackpot(self.guild_id)

                if c1 == c2 == c3 == "🍋":
                    win_amount = jackpot
                    reset_raspadita_jackpot(self.guild_id)
                    with get_connection() as conn:
                        ensure_user(conn, self.guild_id, self.user_id)
                        conn.execute("UPDATE users SET money=money+? WHERE guild_id=? AND user_id=?", (win_amount, self.guild_id, self.user_id))
                        user = conn.execute("SELECT money FROM users WHERE guild_id=? AND user_id=?", (self.guild_id, self.user_id)).fetchone()

                    self.build_grid()
                    embed = discord.Embed(
                        title="🎆 ¡¡¡GANASTE EL POZO ACUMULADO DE LA RASPADITA!!! 🍋🍋🍋",
                        description=(
                            f"¡¡SACASTE 3 LIMONES DE ORO!! ¡Sos el ganador del Jackpot!\n\n"
                            f"💰 **Premio cobrado:** **+{money(win_amount)}**\n"
                            f"💼 Billetera: **{money(user['money'])}**\n\n"
                            "*(Se destapó todo el cartón para que veas el tablero completo)*"
                        ),
                        color=discord.Color.green(),
                    )
                    await interaction.response.edit_message(embed=embed, view=self)

                    if interaction.channel:
                        try:
                            msg = await interaction.channel.send(
                                f"🎆 **¡¡¡FELICITACIONES {interaction.user.mention}!!!** 🍾🍋\n"
                                f"> 🎰 ¡Acaba de raspar **3 LIMONES** `🍋 🍋 🍋` y se llevó el **POZO ACUMULADO DE {money(win_amount)}**! 💰🎉"
                            )
                            record_consumption_message(self.guild_id, interaction.channel_id, msg.id)
                        except Exception as e:
                            print(f"Aviso anuncio jackpot: {e}")
                    if interaction.guild:
                        asyncio.create_task(update_kiosk_fixed_message(interaction.guild, repost=False))
                    return

                elif c1 == c2 == c3 == "💎":
                    win_amount = 3500
                    add_raspadita_jackpot(self.guild_id, 400)
                    with get_connection() as conn:
                        ensure_user(conn, self.guild_id, self.user_id)
                        conn.execute("UPDATE users SET money=money+? WHERE guild_id=? AND user_id=?", (win_amount, self.guild_id, self.user_id))
                        user = conn.execute("SELECT money FROM users WHERE guild_id=? AND user_id=?", (self.guild_id, self.user_id)).fetchone()

                    self.build_grid()
                    embed = discord.Embed(
                        title="💎 ¡¡3 DIAMANTES! PREMIO MAYOR 💎",
                        description=(
                            f"¡Impresionante! Conseguiste 3 diamantes `💎 💎 💎`.\n\n"
                            f"💵 **Premio:** **+{money(win_amount)}** en efectivo\n"
                            f"💼 Billetera: **{money(user['money'])}**\n\n"
                            "*(Se destapó todo el cartón para que veas el tablero completo)*"
                        ),
                        color=discord.Color.green(),
                    )
                    await interaction.response.edit_message(embed=embed, view=self)
                    if interaction.guild:
                        asyncio.create_task(update_kiosk_fixed_message(interaction.guild, repost=False))
                    return

                elif c1 == c2 == c3 == "🍫":
                    win_amount = 1500
                    add_raspadita_jackpot(self.guild_id, 400)
                    with get_connection() as conn:
                        ensure_user(conn, self.guild_id, self.user_id)
                        conn.execute("UPDATE users SET money=money+? WHERE guild_id=? AND user_id=?", (win_amount, self.guild_id, self.user_id))
                        user = conn.execute("SELECT money FROM users WHERE guild_id=? AND user_id=?", (self.guild_id, self.user_id)).fetchone()

                    add_inventory_item(self.guild_id, self.user_id, "jorgito", 1)

                    self.build_grid()
                    embed = discord.Embed(
                        title="🍫 ¡¡3 GOLOSINAS! PREMIO DULCE 🍫",
                        description=(
                            f"¡Qué rico! Conseguiste 3 chocolates `🍫 🍫 🍫`.\n\n"
                            f"💵 **Premio:** **+{money(win_amount)}** en efectivo\n"
                            f"🎒 **Bonus:** **+1 Alfajor Jorgito** agregado a tu mochila!\n"
                            f"💼 Billetera: **{money(user['money'])}**\n\n"
                            "*(Se destapó todo el cartón para que veas el tablero completo)*"
                        ),
                        color=discord.Color.green(),
                    )
                    await interaction.response.edit_message(embed=embed, view=self)
                    if interaction.guild:
                        asyncio.create_task(update_kiosk_fixed_message(interaction.guild, repost=False))
                    return

                else:
                    new_jackpot = add_raspadita_jackpot(self.guild_id, 400)
                    user = get_user(self.guild_id, self.user_id)

                    self.build_grid()
                    embed = discord.Embed(
                        title="❌ ¡Siga participando! No hubo suerte",
                        description=(
                            f"Sacaste: **[{c1}] [{c2}] [{c3}]**.\n\n"
                            f"¡No te desanimes! Se sumaron **+$400** al Pozo Acumulado.\n"
                            f"💰 **Nuevo Pozo Acumulado:** `{money(new_jackpot)}`\n"
                            f"💼 Billetera: **{money(user['money'])}**\n\n"
                            "*(Se destapó todo el cartón para que veas dónde estaban los demás premios)*"
                        ),
                        color=discord.Color.dark_grey(),
                    )
                    await interaction.response.edit_message(embed=embed, view=self)
                    if interaction.guild:
                        asyncio.create_task(update_kiosk_fixed_message(interaction.guild, repost=False))
                    return

        return callback


class RaspaditaConfirmView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: int, is_sub: bool, cost: int):
        super().__init__(timeout=90)
        self.user_id = user_id
        self.guild_id = guild_id
        self.is_sub = is_sub
        self.cost = cost

    @discord.ui.button(
        label="Comprar y Raspar",
        emoji="🟢",
        style=discord.ButtonStyle.success,
        custom_id="raspadita:confirm",
    )
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Esta ventana no es tuya! 😅", ephemeral=True)
            return

        if not is_open(guild_id=self.guild_id):
            await interaction.response.edit_message(
                content=f"🔒 La lotería del kiosco cerró. Volvemos a abrir a las **{next_opening()}**.",
                embed=None,
                view=None,
            )
            return

        today_str = datetime.now(TZ).strftime("%Y-%m-%d")
        with get_connection() as conn:
            ensure_user(conn, self.guild_id, self.user_id)

            # Verificar límite diario atómicamente
            row = conn.execute(
                "SELECT count FROM raspadita_daily WHERE guild_id=? AND user_id=? AND play_date=?",
                (self.guild_id, self.user_id, today_str),
            ).fetchone()
            daily_count = row["count"] if row else 0
            if daily_count >= RASPADITA_DAILY_LIMIT:
                await interaction.response.edit_message(
                    content=f"🛑 **Límite diario alcanzado:** Ya compraste tus **{RASPADITA_DAILY_LIMIT} cartones** de Raspadita permitidos por hoy ({RASPADITA_DAILY_LIMIT}/{RASPADITA_DAILY_LIMIT}). ¡Volvé mañana a tentar a la suerte!",
                    embed=None,
                    view=None,
                )
                return

            # Deducción atómica con verificación en SQL para evitar saldo negativo
            cursor = conn.execute(
                "UPDATE users SET money=money-? WHERE guild_id=? AND user_id=? AND money >= ?",
                (self.cost, self.guild_id, self.user_id, self.cost),
            )
            if cursor.rowcount == 0:
                user = conn.execute("SELECT money FROM users WHERE guild_id=? AND user_id=?", (self.guild_id, self.user_id)).fetchone()
                user_money = user["money"] if user else 0
                await interaction.response.edit_message(
                    content=f"💸 No te alcanza la plata. Necesitás **{money(self.cost)}** y tenés **{money(user_money)}**.",
                    embed=None,
                    view=None,
                )
                return

            increment_user_raspadita_daily_count(conn, self.guild_id, self.user_id)

        view = RaspaditaGameView(
            user_id=self.user_id,
            guild_id=self.guild_id,
            is_sub=self.is_sub,
            cost=self.cost,
            parent_interaction=interaction,
        )
        await interaction.response.edit_message(content=None, embed=view.build_embed(), view=view)

    @discord.ui.button(
        label="Cancelar",
        emoji="❌",
        style=discord.ButtonStyle.secondary,
        custom_id="raspadita:cancel",
    )
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Esta ventana no es tuya! 😅", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎫 Raspadita cancelada",
            description="No se te cobró nada. ¡Volvé cuando quieras tentar a la suerte!",
            color=discord.Color.dark_grey(),
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)


async def start_raspadita_session(interaction: discord.Interaction):
    if not is_open(guild_id=interaction.guild_id):
        await interaction.response.send_message(
            f"🔒 La lotería del kiosco está cerrada. Volvemos a abrir a las **{next_opening()}**.",
            ephemeral=True,
        )
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    daily_count = get_user_raspadita_daily_count(interaction.guild_id, interaction.user.id)
    if daily_count >= RASPADITA_DAILY_LIMIT:
        embed = discord.Embed(
            title=f"🛑 Límite Diario de Raspaditas Alcanzado ({RASPADITA_DAILY_LIMIT}/{RASPADITA_DAILY_LIMIT})",
            description=(
                f"Ya compraste tus **{RASPADITA_DAILY_LIMIT} cartones** de Raspadita permitidos para el día de hoy.\n\n"
                "⏰ *El cupo se renueva a las 00:00 hs. ¡Mañana te esperamos para seguir tentando a la suerte!*"
            ),
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    sub = is_subscriber(interaction.user)
    cost = 750 if sub else 1000
    jackpot = get_raspadita_jackpot(interaction.guild_id)
    user = get_user(interaction.guild_id, interaction.user.id)

    if user["money"] < cost:
        sub_text = "*(Descuento de Suscriptor / Booster aplicado ⭐)*" if sub else "*(Suscriptores pagan $750)*"
        embed = discord.Embed(
            title="🎫 Raspadita del Kiosquito 🍋",
            description=(
                f"❌ **No tenés suficiente plata en tu billetera.**\n\n"
                f"💵 **Precio del cartón:** **{money(cost)}** {sub_text}\n"
                f"💼 Tu saldo actual: **{money(user['money'])}**\n\n"
                "💡 *Podés hacer una changuita con `/changuitas` o reclamar tu `/diario` para juntar plata.*"
            ),
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    sub_badge = " *(🔥 Descuento de Suscriptor / Booster aplicado)*" if sub else ""

    embed = discord.Embed(
        title="🎫 Lotería «El Lemoncito» — Confirmar Compra",
        description=(
            f"💰 **Pozo Acumulado actual:** `{money(jackpot)}` 🍋\n\n"
            f"💵 **Precio de tu cartón:** **{money(cost)}**{sub_badge}\n"
            f"💼 **Tu saldo en billetera:** **{money(user['money'])}**\n"
            f"🎟️ **Tus cartones de hoy:** `{daily_count}/{RASPADITA_DAILY_LIMIT}`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🏆 **Tabla de Premios (3 casillas iguales):**\n"
            f"• `🍋 🍋 🍋` ➔ **¡EL POZO ACUMULADO!** ({money(jackpot)})\n"
            "• `💎 💎 💎` ➔ **$3.500** en efectivo\n"
            "• `🍫 🍫 🍫` ➔ **$1.500** + 1 Alfajor Jorgito\n"
            "• ❌ *Siga participando* ➔ Suma **+$400** al Pozo Acumulado\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "¿Querés comprar este cartón y raspar ahora?"
        ),
        color=discord.Color.gold(),
    )
    view = RaspaditaConfirmView(
        user_id=interaction.user.id,
        guild_id=interaction.guild_id,
        is_sub=sub,
        cost=cost,
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class QuinielaBetModal(discord.ui.Modal, title="🎱 Apostar en la Quiniela"):
    def __init__(self, guild_id: int, parent_interaction: discord.Interaction | None = None):
        super().__init__()
        self.guild_id = guild_id
        self.parent_interaction = parent_interaction

    numero_input = discord.ui.TextInput(
        label="Número de la suerte (del 1 al 50)",
        placeholder="Ej: 22 (El Loco), 07 (El Revólver), etc.",
        min_length=1,
        max_length=2,
        required=True,
    )

    apuesta_input = discord.ui.TextInput(
        label="Monto a apostar ($100 a $1.000)",
        placeholder="Ej: 500",
        min_length=3,
        max_length=5,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if self.guild_id in QUINIELA_DRAWING:
            await interaction.response.send_message(
                "⏳ **El sorteo de la Quiniela está en vivo en este momento.** Las apuestas volverán a abrir en unos instantes.",
                ephemeral=True,
            )
            return

        try:
            num = int(self.numero_input.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ El número debe ser un valor numérico entre **1 y 50**.", ephemeral=True)
            return

        if num < 1 or num > 50:
            await interaction.response.send_message("❌ El número de la Quiniela debe estar entre **1 y 50**.", ephemeral=True)
            return

        try:
            apuesta = int(self.apuesta_input.value.strip().replace("$", "").replace(".", ""))
        except ValueError:
            await interaction.response.send_message("❌ El monto a apostar debe ser un número válido.", ephemeral=True)
            return

        if apuesta < 100 or apuesta > 1000:
            await interaction.response.send_message("❌ La apuesta mínima es de **$100** y la máxima de **$1.000**.", ephemeral=True)
            return

        # Descontar plata y registrar apuesta de forma atómica
        with get_connection() as conn:
            ensure_user(conn, self.guild_id, interaction.user.id)

            row = conn.execute(
                "SELECT COUNT(*) as c FROM quiniela_bets WHERE guild_id=? AND user_id=?",
                (self.guild_id, interaction.user.id),
            ).fetchone()
            current_bets_count = row["c"] if row else 0

            if current_bets_count >= 3:
                await interaction.response.send_message(
                    "❌ Ya alcanzaste el límite máximo de **3 apuestas activas** para el sorteo de hoy. ¡Esperá a las 22:00 hs para ver los resultados!",
                    ephemeral=True,
                )
                return

            cursor = conn.execute(
                "UPDATE users SET money=money-? WHERE guild_id=? AND user_id=? AND money >= ?",
                (apuesta, self.guild_id, interaction.user.id, apuesta),
            )
            if cursor.rowcount == 0:
                user = conn.execute("SELECT money FROM users WHERE guild_id=? AND user_id=?", (self.guild_id, interaction.user.id)).fetchone()
                user_money = user["money"] if user else 0
                await interaction.response.send_message(
                    f"💸 No te alcanza la plata. Tu saldo actual es de **{money(user_money)}** y querés apostar **{money(apuesta)}**.",
                    ephemeral=True,
                )
                return

            now_ts = int(time.time())
            conn.execute(
                "INSERT INTO quiniela_bets (guild_id, user_id, number, bet_amount, created_at) VALUES (?, ?, ?, ?, ?)",
                (self.guild_id, interaction.user.id, num, apuesta, now_ts),
            )
            total_bets_now = current_bets_count + 1

        # Borrar el mensaje de selección previo para que no se dupliquen
        if self.parent_interaction:
            try:
                await self.parent_interaction.delete_original_response()
            except Exception:
                pass

        # Asignar rol Quinielero
        quinielero_role = await get_or_create_quinielero_role(interaction.guild)
        if quinielero_role and isinstance(interaction.user, discord.Member):
            try:
                await interaction.user.add_roles(quinielero_role, reason="Participante de la Quiniela")
            except Exception:
                pass

        num_info = QUINIELA_NUMBERS.get(num, {"name": f"Número {num}", "emoji": "🎱"})
        premio_potencial = apuesta * 35
        premio_palo = apuesta * 2

        embed = discord.Embed(
            title="🎫 ¡Apuesta Registrada en la Quiniela! 🍀",
            description=(
                f"🧔 **El Kiosquero:** *«¡Anotado en la boleta, maestro! Mucha suerte hoy.»*\n\n"
                f"🎱 **Tu Número:** **`{num:02d}` — {num_info['name']} {num_info['emoji']}**\n"
                f"💵 **Tu Apuesta:** **{money(apuesta)}** *(Llevás {total_bets_now}/3 jugadas hoy)*\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏆 **Premios Potenciales:**\n"
                f"• 🎯 **Acierto a la cabeza (x35):** **+{money(premio_potencial)}**\n"
                f"• 🤏 **Pegó en el palo (x2):** **+{money(premio_palo)}** *(si sale {num-1 if num>1 else 50} o {num+1 if num<50 else 1})*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "🔔 *Se te asignó el rol `@Quinielero`. Te avisaremos a las **22:00 hs** cuando arranque el sorteo en vivo.*"
            ),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))


class QuinielaView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: int, parent_interaction: discord.Interaction, user_bets_count: int = 0):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.guild_id = guild_id
        self.parent_interaction = parent_interaction

        if user_bets_count >= 3:
            self.bet_button.disabled = True
            self.bet_button.label = "Límite de 3 alcanzado"

    @discord.ui.button(
        label="Elegir Número y Apostar",
        emoji="🎫",
        style=discord.ButtonStyle.success,
        custom_id="quiniela:bet",
    )
    async def bet_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Esta ventana no es tuya! 😅", ephemeral=True)
            return
        await interaction.response.send_modal(QuinielaBetModal(self.guild_id, parent_interaction=self.parent_interaction))

    @discord.ui.button(
        label="Cerrar",
        emoji="❌",
        style=discord.ButtonStyle.secondary,
        custom_id="quiniela:cancel",
    )
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("¡Esta ventana no es tuya! 😅", ephemeral=True)
            return
        try:
            await interaction.response.defer()
            await interaction.delete_original_response()
        except Exception:
            pass


async def start_quiniela_session(interaction: discord.Interaction):
    if interaction.guild_id in QUINIELA_DRAWING:
        await interaction.response.send_message(
            "⏳ **El sorteo de la Quiniela está en vivo en este momento.** Las apuestas volverán a abrir en unos instantes.",
            ephemeral=True,
        )
        return

    user = get_user(interaction.guild_id, interaction.user.id)
    if user["money"] < 100:
        embed = discord.Embed(
            title="🎱 Quiniela del Kiosquito 🍋",
            description=(
                "❌ **No tenés suficiente plata en tu billetera.**\n\n"
                f"💵 **Apuesta mínima:** **$100**\n"
                f"💼 Tu saldo actual: **{money(user['money'])}**\n\n"
                "💡 *Hacé una changuita con `/changuitas` o pedí tu `/diario` para juntar plata.*"
            ),
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    tabla_path = ROOT / "assets" / "quiniela" / "tabla_quiniela.jpg"
    if not tabla_path.exists():
        tabla_path = ROOT / "assets" / "quiniela" / "banner.png"

    user_bets = get_user_quiniela_bets(interaction.guild_id, interaction.user.id)
    bets_count = len(user_bets)

    if user_bets:
        bets_lines = []
        for b in user_bets:
            num = b["number"]
            info = QUINIELA_NUMBERS.get(num, {"name": f"Número {num}", "emoji": "🎱"})
            potencial = b["bet_amount"] * 35
            bets_lines.append(f"• **`{num:02d}` — {info['name']} {info['emoji']}** (`{money(b['bet_amount'])}`) ➔ Cobrás **{money(potencial)}**")
        bets_text = f"🎟️ **Tus apuestas para hoy ({bets_count}/3):**\n" + "\n".join(bets_lines) + "\n\n"
    else:
        bets_text = "🎟️ **Tus apuestas para hoy (0/3):** *Aún no jugaste ningún número hoy.*\n\n"

    limit_note = "*(⚠️ Ya completaste tus 3 jugadas permitidas para el sorteo de hoy)*\n\n" if bets_count >= 3 else ""

    recent_history = get_quiniela_history(interaction.guild_id)
    if recent_history:
        hist_parts = []
        for num in recent_history:
            inf = QUINIELA_NUMBERS.get(num, {"name": f"Número {num}", "emoji": "🎱"})
            hist_parts.append(f"**`{num:02d}`** *({inf['name']} {inf['emoji']})*")
        history_text = f"📜 **Últimos 3 números salidos:** " + " • ".join(hist_parts) + "\n\n"
    else:
        history_text = ""

    embed = discord.Embed(
        title="🎱 Quiniela del Kiosquito — ¡Apostá a tu Número! 🍀",
        description=(
            "¡Elegí tu número de la suerte del **1 al 50** para el sorteo diario de las **22:00 hs**!\n\n"
            f"{bets_text}"
            f"{limit_note}"
            f"{history_text}"
            "🏆 **Tabla de Pagos:**\n"
            "• 🎯 **Acierto a la cabeza (Número exacto):** Paga **x35 veces** tu apuesta.\n"
            "• 🤏 **Pegó en el palo (Número anterior o siguiente):** Paga **x2 veces** tu apuesta.\n\n"
            f"💼 **Tu saldo actual:** **{money(user['money'])}** • Apuestas: `$100 – $1.000` (Máx 3 jugadas)\n"
            "🔔 *Al apostar se te asignará el rol `@Quinielero` para recibir la notificación del sorteo.*"
        ),
        color=discord.Color.gold(),
    )

    view = QuinielaView(
        user_id=interaction.user.id,
        guild_id=interaction.guild_id,
        parent_interaction=interaction,
        user_bets_count=bets_count,
    )

    if tabla_path.exists():
        file = discord.File(str(tabla_path), filename="tabla_quiniela.jpg")
        embed.set_image(url="attachment://tabla_quiniela.jpg")
        await interaction.response.send_message(embed=embed, view=view, file=file, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    asyncio.create_task(auto_delete_interaction(interaction, 180))


async def run_quiniela_draw(guild: discord.Guild, target_channel: discord.TextChannel | None = None, is_private: bool = False):
    channel = target_channel or await get_or_create_kiosk_channel(guild)
    if not channel:
        return

    QUINIELA_DRAWING.add(guild.id)
    try:
        win_number = random.randint(1, 50)
        info = QUINIELA_NUMBERS.get(win_number, {"name": f"Número {win_number}", "emoji": "🎱"})

        # Guardar en el historial de últimos resultados
        record_quiniela_history(guild.id, win_number)

        bets = get_active_quiniela_bets(guild.id)
        quinielero_role = None
        for r in guild.roles:
            if "quinielero" in r.name.lower():
                quinielero_role = r
                break

        sorteando_path = ROOT / "assets" / "quiniela" / "sorteando.gif"
        role_ping = quinielero_role.mention if (quinielero_role and not is_private) else ""

        initial_embed = discord.Embed(
            title="🎱 ¡SORTEO OFICIAL DE LA QUINIELA DEL KIOSQUITO! 🎰",
            description=(
                f"{role_ping}\n\n" if role_ping else ""
                "🧔 **El Kiosquero:** *«¡Atención a todos los vecinos! Hacemos girar el bolillero de metal...»*\n\n"
                "⏳ *Las bolillas están dando vueltas en el aire a toda velocidad...*"
            ),
            color=discord.Color.gold(),
        )

        gif_file = discord.File(str(sorteando_path), filename="sorteando.gif") if sorteando_path.exists() else None
        if gif_file:
            initial_embed.set_image(url="attachment://sorteando.gif")

        content_msg = quinielero_role.mention if (quinielero_role and not is_private) else None
        draw_msg = None
        try:
            if gif_file:
                draw_msg = await channel.send(content=content_msg, embed=initial_embed, file=gif_file)
            else:
                draw_msg = await channel.send(content=content_msg, embed=initial_embed)
        except Exception as e:
            print(f"Error enviando mensaje inicial de la quiniela: {e}")

        # Pausa de 8 segundos para que se aprecie la animación del GIF del bolillero
        await asyncio.sleep(8.0)

        # Calcular ganadores
        exact_winners = []
        near_winners = []
        total_distributed = 0
        participant_user_ids = set()

        for b in bets:
            uid = b["user_id"]
            bet_num = b["number"]
            amount = b["bet_amount"]
            participant_user_ids.add(uid)

            if bet_num == win_number:
                prize = amount * 35
                exact_winners.append({"user_id": uid, "prize": prize, "bet": amount})
                total_distributed += prize
                with get_connection() as conn:
                    ensure_user(conn, guild.id, uid)
                    conn.execute("UPDATE users SET money=money+? WHERE guild_id=? AND user_id=?", (prize, guild.id, uid))
            elif abs(bet_num - win_number) == 1 or (bet_num == 1 and win_number == 50) or (bet_num == 50 and win_number == 1):
                prize = amount * 2
                near_winners.append({"user_id": uid, "prize": prize, "bet": amount, "number": bet_num})
                total_distributed += prize
                with get_connection() as conn:
                    ensure_user(conn, guild.id, uid)
                    conn.execute("UPDATE users SET money=money+? WHERE guild_id=? AND user_id=?", (prize, guild.id, uid))

        results_text = []
        if exact_winners:
            results_text.append("🏆 **¡ACIERTOS A LA CABEZA (x35)!** 🎯")
            for w in exact_winners:
                uname = await resolve_member_name(guild, w['user_id'])
                results_text.append(f"• 🥇 **@{uname}** jugó `{money(w['bet'])}` al **{win_number}** ➔ **¡COBRÓ {money(w['prize'])}!** 💸🍾")
            results_text.append("")

        if near_winners:
            results_text.append("🤏 **¡PEGÓ EN EL PALO (x2)!**")
            for w in near_winners:
                uname = await resolve_member_name(guild, w['user_id'])
                results_text.append(f"• 🥈 **@{uname}** jugó `{money(w['bet'])}` al **{w['number']}** ➔ Cobró `{money(w['prize'])}` 🪙")
            results_text.append("")

        if not exact_winners and not near_winners:
            results_text.append("❌ *¡La banca se quedó con todo! Ningún vecino acertó a este número hoy.*")

        results_text.append(f"\n💰 **Total entregado en premios:** `{money(total_distributed)}`")

        # Lista de todos los usuarios únicos que participaron hoy (mostrando su @tag sin arrobar con sonido)
        if participant_user_ids:
            p_names = []
            for p_uid in set(participant_user_ids):
                uname = await resolve_member_name(guild, p_uid)
                p_names.append(f"**@{uname}**")
            results_text.append(f"👥 **Participantes de hoy ({len(p_names)}):** " + ", ".join(p_names))

        # Mostrar historial de últimos números
        recent_history = get_quiniela_history(guild.id)
        if len(recent_history) > 1:
            hist_parts = []
            for num in recent_history:
                inf = QUINIELA_NUMBERS.get(num, {"name": f"Número {num}", "emoji": "🎱"})
                hist_parts.append(f"**`{num:02d}`** {inf['emoji']}")
            results_text.append(f"📜 **Últimos resultados:** " + " • ".join(hist_parts))

        result_img_path = ROOT / "assets" / "quiniela" / "resultados" / f"{win_number}.png"
        final_embed = discord.Embed(
            title=f"🎱 ¡SALIÓ EL {win_number:02d} — {info['name'].upper()} {info['emoji']}! 🏆",
            description="\n".join(results_text),
            color=discord.Color.green() if (exact_winners or near_winners) else discord.Color.gold(),
        )
        final_embed.set_footer(text=f"Sorteo Oficial de la Quiniela • Hora Argentina {datetime.now(TZ).strftime('%H:%M')} • Se borra en 10m")

        result_file = discord.File(str(result_img_path), filename=f"{win_number}.png") if result_img_path.exists() else None
        if result_file:
            final_embed.set_image(url=f"attachment://{win_number}.png")

        # Limpiar el mensaje de animación previo para dejar el canal impecable
        if draw_msg:
            try:
                await draw_msg.delete()
            except Exception:
                pass

        try:
            no_mentions = discord.AllowedMentions.none()
            if result_file:
                res_msg = await channel.send(embed=final_embed, file=result_file, allowed_mentions=no_mentions)
            else:
                res_msg = await channel.send(embed=final_embed, allowed_mentions=no_mentions)
            record_consumption_message(guild.id, channel.id, res_msg.id)
            # El resultado permanece 10 minutos (600 seg) y se borra automáticamente para mantener limpio el kiosco:
            asyncio.create_task(auto_delete_message(res_msg, 600))
        except Exception as e:
            print(f"Error publicando resultado final de la quiniela: {e}")

        # Limpiar apuestas del sorteo
        clear_quiniela_bets(guild.id)

        # Quitar rol Quinielero a los 20 minutos
        if participant_user_ids and quinielero_role:
            asyncio.create_task(schedule_quinielero_role_removal(guild, quinielero_role, list(participant_user_ids), 1200))
    finally:
        QUINIELA_DRAWING.discard(guild.id)


async def send_quiniela_reminder_morning(guild: discord.Guild):
    channel = await get_or_create_kiosk_channel(guild)
    if not channel:
        return
    banner_path = ROOT / "assets" / "quiniela" / "banner.png"
    embed = discord.Embed(
        title="☀️ ¡BUEN DÍA VECINOS! HOY HAY QUINIELA A LAS 22:00 HS 🎱🍀",
        description=(
            "🧔 **El Kiosquero:** *«¡Arriba la gente linda del barrio! Ya abrimos la recepción de boletas para el sorteo oficial de esta noche.»*\n\n"
            "🎟️ **¿Cómo jugar?**\n"
            "• Elegí tu número del **01 al 50**.\n"
            "• Podés jugar con `/quiniela [numero] [apuesta]` o tocando el botón **`🎱 Quiniela`** en el mostrador.\n\n"
            "🏆 **Tabla de Premios:**\n"
            "• 🎯 **Acierto a la cabeza:** Paga **x35 veces** tu apuesta.\n"
            "• 🤏 **Pegó en el palo:** Paga **x2 veces** tu apuesta.\n\n"
            "⏰ *El sorteo en vivo se realiza hoy a las **22:00 hs** (Hora Argentina). ¡No te olvides de meter tu jugada!*"
        ),
        color=discord.Color.gold(),
    )
    try:
        if banner_path.exists():
            file = discord.File(str(banner_path), filename="banner.png")
            embed.set_image(url="attachment://banner.png")
            msg = await channel.send(embed=embed, file=file)
        else:
            msg = await channel.send(embed=embed)
        asyncio.create_task(auto_delete_message(msg, 3600))
    except Exception:
        pass


async def send_quiniela_reminder_afternoon(guild: discord.Guild):
    channel = await get_or_create_kiosk_channel(guild)
    if not channel:
        return
    banner_path = ROOT / "assets" / "quiniela" / "banner.png"
    embed = discord.Embed(
        title="☕ ¡RECORDATORIO DE LA TARDE! HOY HAY QUINIELA A LAS 22:00 HS 🎱✨",
        description=(
            "🧔 **El Kiosquero:** *«¡Buenas tardes a todos! Les recuerdo que las apuestas para la Quiniela siguen abiertas en el mostrador.»*\n\n"
            "🎯 ¿Todavía no jugaste tu número de la suerte?\n"
            "• Apuestas desde **$100** hasta **$1.000** (hasta 3 jugadas por vecino).\n"
            "• El acierto a la cabeza se lleva **x35 veces** lo jugado 💸🍾.\n\n"
            "👉 Jugá con `/quiniela [numero] [apuesta]` o desde el panel de <#el-kiosquito-de-lemon>.\n"
            "🔔 *El bolillero girará en vivo a las **22:00 hs**.*"
        ),
        color=discord.Color.gold(),
    )
    try:
        if banner_path.exists():
            file = discord.File(str(banner_path), filename="banner.png")
            embed.set_image(url="attachment://banner.png")
            msg = await channel.send(embed=embed, file=file)
        else:
            msg = await channel.send(embed=embed)
        asyncio.create_task(auto_delete_message(msg, 3600))
    except Exception:
        pass


async def send_quiniela_announcement_20m(guild: discord.Guild):
    channel = await get_or_create_kiosk_channel(guild)
    if not channel:
        return
    banner_path = ROOT / "assets" / "quiniela" / "banner.png"
    embed = discord.Embed(
        title="🎱 ¡QUEDAN 20 MINUTOS PARA EL SORTEO DE LA QUINIELA! ⏳",
        description=(
            "🧔 **El Kiosquero:** *«¡Se van cerrando las apuestas de la noche! Elegí tu número del **01 al 50**.»*\n\n"
            "🏆 **Premios:** Acierto a la cabeza paga **x35 veces** tu apuesta • Pegó en el palo paga **x2**.\n"
            "👉 Jugá con `/quiniela [numero] [apuesta]` o tocá el botón **`🎱 Quiniela`** en el mostrador."
        ),
        color=discord.Color.gold(),
    )
    try:
        if banner_path.exists():
            file = discord.File(str(banner_path), filename="banner.png")
            embed.set_image(url="attachment://banner.png")
            msg = await channel.send(embed=embed, file=file)
        else:
            msg = await channel.send(embed=embed)
        asyncio.create_task(auto_delete_message(msg, 1200))
    except Exception:
        pass


async def send_quiniela_announcement_5m(guild: discord.Guild):
    channel = await get_or_create_kiosk_channel(guild)
    if not channel:
        return
    quinielero_role = None
    for r in guild.roles:
        if "quinielero" in r.name.lower():
            quinielero_role = r
            break
    ping = quinielero_role.mention if quinielero_role else None
    embed = discord.Embed(
        title="🔔 ¡ÚLTIMOS 5 MINUTOS PARA EL SORTEO! 🎱",
        description=(
            "⏳ *¡En 5 minutos el Kiosquero hace girar el bolillero en vivo!*\n"
            "Última oportunidad para meter tu jugada de la noche."
        ),
        color=discord.Color.gold(),
    )
    try:
        if ping:
            msg = await channel.send(content=ping, embed=embed)
        else:
            msg = await channel.send(embed=embed)
        asyncio.create_task(auto_delete_message(msg, 300))
    except Exception:
        pass


class ChanguitaSelect(discord.ui.Select):
    def __init__(self, sample_jobs: list[dict]):
        options = []
        for job in sample_jobs:
            tier_cfg = CONFIG["changuita_tiers"][job["tier"]]
            badge = " 🎮" if job.get("is_minigame") else ""
            options.append(
                discord.SelectOption(
                    label=f"{job['name']}{badge}"[:100],
                    value=job["id"],
                    emoji=job["emoji"],
                    description=f"{tier_cfg['name']} • {money(tier_cfg['money_min'])}-{money(tier_cfg['money_max'])}"[:100],
                )
            )
        super().__init__(
            placeholder="Elegí una changuita para laburar...",
            min_values=1,
            max_values=1,
            options=options[:25],
        )

    async def callback(self, interaction: discord.Interaction):
        job_id = self.values[0]
        job = CHANGUITAS_MAP.get(job_id)
        if not job:
            await interaction.response.send_message("❌ Changuita no encontrada.", ephemeral=True)
            return

        if job.get("is_minigame") == "atajar":
            view = AtajarManaosMinigameView(interaction.user.id, interaction.guild_id, interaction)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)
            return
        elif job.get("is_minigame") == "heladera":
            view = RepararHeladeraMinigameView(interaction.user.id, interaction.guild_id, interaction)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)
            return
        elif job.get("is_minigame") == "deposito":
            view = BuscaminasDepositoView(interaction.user.id, interaction.guild_id, interaction)
            embed = discord.Embed(
                title="📦 Buscaminas del Depósito",
                description=(
                    "Elegí una caja para abrir:\n\n"
                    "💵 **Acumulado:** `$0`  •  ⭐ **XP Acumulada:** `+0 XP`\n\n"
                    "⚠️ *Hay 1 rata escondida entre las 9 cajas. ¡No la toques!*"
                ),
                color=discord.Color.gold(),
            )
            await interaction.response.edit_message(embed=embed, view=view)
            return
        elif job.get("is_minigame") == "barrer":
            view = BarrerPisoMinigameView(interaction.user.id, interaction.guild_id, interaction)
            embed = discord.Embed(
                title="🧹 Barrer el piso del salón",
                description=(
                    "Hacé clic en todas las casillas con basura (`🍂`, `🧻`) para barrerlas.\n\n"
                    "⚠️ *¡Cuidado de no tocar la cucaracha `🪳` que anda suelta!*"
                ),
                color=discord.Color.gold(),
            )
            await interaction.response.edit_message(embed=embed, view=view)
            return
        elif job.get("is_minigame") == "ordenar":
            view = OrdenarProductosMinigameView(interaction.user.id, interaction.guild_id, interaction)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)
            return
        elif job.get("is_minigame") == "cajas":
            view = MoverCajasMinigameView(interaction.user.id, interaction.guild_id, interaction)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)
            return
        elif job.get("is_minigame") == "caja":
            view = CobrarCajaMinigameView(interaction.user.id, interaction.guild_id, interaction)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)
            return
        elif job.get("is_minigame") == "vidrios":
            view = LimpiarVidriosMinigameView(interaction.user.id, interaction.guild_id, interaction)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)
            return

        step_1 = job["steps"][0]

        embed = discord.Embed(
            title=f"{job['emoji']} {job['name']} (Paso 1/{len(job['steps'])})",
            description=step_1["text"],
            color=discord.Color.gold(),
        )
        work_view = ChanguitaWorkView(
            job_data=job,
            user_id=interaction.user.id,
            guild_id=interaction.guild_id,
            parent_interaction=interaction,
        )
        await interaction.response.edit_message(embed=embed, view=work_view)


class ChanguitasBoardView(discord.ui.View):
    def __init__(self, user_id: int, parent_interaction: discord.Interaction):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.interaction = parent_interaction

        faciles = [j for j in CHANGUITAS_LIST if j["tier"] == "facil"]
        normales = [j for j in CHANGUITAS_LIST if j["tier"] == "normal"]
        pesadas = [j for j in CHANGUITAS_LIST if j["tier"] == "pesada"]

        sample = [
            random.choice(faciles),
            random.choice(normales),
            random.choice(pesadas),
            random.choice(CHANGUITAS_LIST),
        ]
        seen = set()
        unique_sample = []
        for s in sample:
            if s["id"] not in seen:
                seen.add(s["id"])
                unique_sample.append(s)

        self.add_item(ChanguitaSelect(unique_sample))

    async def on_timeout(self):
        try:
            await self.interaction.delete_original_response()
        except (discord.NotFound, discord.HTTPException):
            pass


# ---------- VISTAS DE COMPRA Y MOSTRADOR CON STOCK Y OFERTAS (EDIT-IN-PLACE) ----------

class ProductSelect(discord.ui.Select):
    def __init__(self, guild_id: int):
        options = []
        for p in PRODUCT_LIST:
            price, is_sale, orig = get_product_price(guild_id, p["id"])
            stock = get_kiosk_stock(guild_id, p["id"])

            if is_sale:
                price_text = f"🔥 {money(price)} (OFERTA)"
            else:
                price_text = money(price)

            if p["id"] == "lemon_black":
                opt_desc = "Membresía VIP • 15% OFF de por vida"
            else:
                stock_text = f"Stock: {stock}" if stock > 0 else "AGOTADO 🚫"
                opt_desc = f"{stock_text} • +{p['xp']} XP al consumir"

            options.append(
                discord.SelectOption(
                    label=f"{p['name']} — {price_text}",
                    value=p["id"],
                    emoji=p["emoji"],
                    description=opt_desc[:100],
                )
            )

        super().__init__(
            placeholder="Elegí un producto de la góndola...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        product = PRODUCTS[self.values[0]]
        user = get_user(interaction.guild_id, interaction.user.id)
        price, is_sale, orig = get_product_price(interaction.guild_id, product["id"])
        stock = get_kiosk_stock(interaction.guild_id, product["id"])

        if is_sale:
            price_desc = f"🔥 **EN OFERTA:** **{money(price)}** *(Antes {money(orig)})*"
        else:
            price_desc = f"💵 **Precio:** {money(price)}"

        if product["id"] == "lemon_black":
            stock_desc = "📦 **Disponibilidad:** Ilimitada (Membresía VIP)"
            desc = (
                f"{product['description']}\n\n"
                f"{price_desc}\n{stock_desc}\n\n"
                "👑 **Beneficios exclusivos:**\n"
                "• 🏷️ **15% de descuento permanente** en todas las golosinas del mostrador.\n"
                "• 👑 **Rol exclusivo `@Lemon Black`** en Discord.\n"
                "• 💳 **Insignia VIP** en tu tarjeta de `/perfil`."
            )
            embed_color = discord.Color.from_rgb(45, 45, 45)
        else:
            stock_desc = f"📦 **Stock disponible:** `{stock}` unidades" if stock > 0 else "🚫 **Estado:** ¡AGOTADO!"
            desc = f"{product['description']}\n\n{price_desc}\n{stock_desc}\n⭐ **Al consumir:** `+{product['xp']} XP`"
            embed_color = discord.Color.gold()

        embed = discord.Embed(
            title=f"{product['emoji']} {product['name']}",
            description=desc,
            color=embed_color,
        )
        embed.add_field(name="💵 Tu Billetera", value=money(user["money"]), inline=True)
        embed.add_field(name="🧾 Tu Deuda", value=money(user["debt"]), inline=True)

        view = ProductDetailView(product["id"], interaction.user.id, interaction)
        await interaction.response.edit_message(embed=embed, view=view)


class ProductCatalogView(discord.ui.View):
    def __init__(self, parent_interaction: discord.Interaction):
        super().__init__(timeout=180)
        self.interaction = parent_interaction
        self.add_item(ProductSelect(parent_interaction.guild_id))

    async def on_timeout(self):
        try:
            await self.interaction.delete_original_response()
        except (discord.NotFound, discord.HTTPException):
            pass


class ProductDetailView(discord.ui.View):
    def __init__(self, product_id: str, owner_id: int, parent_interaction: discord.Interaction):
        super().__init__(timeout=180)
        self.product_id = product_id
        self.owner_id = owner_id
        self.interaction = parent_interaction
        if product_id == "lemon_black":
            self.buy_five.disabled = True
            self.buy_five.style = discord.ButtonStyle.secondary

    async def on_timeout(self):
        try:
            await self.interaction.delete_original_response()
        except (discord.NotFound, discord.HTTPException):
            pass

    async def process_purchase(self, interaction: discord.Interaction, quantity: int):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Ese mostrador no es el tuyo 😭", ephemeral=True)
            return

        if not is_open(guild_id=interaction.guild_id):
            embed = discord.Embed(
                title="🔒 El Kiosquito cerró",
                description=f"Volvemos a abrir a las **{next_opening()}**.",
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(embed=embed, view=None)
            return

        product = PRODUCTS[self.product_id]
        ok, balance, total, reason, remaining_stock = normal_purchase(
            interaction.guild_id, interaction.user.id, self.product_id, quantity
        )

        if not ok:
            if reason == "already_lemon_black":
                embed = discord.Embed(
                    title="💳 Ya sos Miembro Lemon Black VIP",
                    description="¡Ya contás con la **Tarjeta Lemon Black** activa!\nDisfrutás de un **15% de descuento permanente** en todas las compras del mostrador.",
                    color=discord.Color.from_rgb(45, 45, 45),
                )
            elif reason == "out_of_stock":
                embed = discord.Embed(
                    title=f"🚫 Stock insuficiente de {product['name']}",
                    description=(
                        f"Querías comprar **{quantity} un.** pero solo quedan **{remaining_stock} un.** en el mostrador.\n"
                        f"El kiosquero repone stock gradualmente o cuando alguien hace changuitas."
                    ),
                    color=discord.Color.red(),
                )
            else:
                embed = discord.Embed(
                    title=f"💸 No te alcanza para {quantity}× {product['name']}",
                    description=(
                        f"Cuesta **{money(total)}** y tenés **{money(balance)}** en la billetera.\n"
                        f"Si tenés {CONFIG['fiado_xp_required']} XP podés pedir fiado con `/fiado`."
                    ),
                    color=discord.Color.red(),
                )
            embed.set_footer(text="Elegí otro producto o volvé a la góndola.")
            await interaction.response.edit_message(embed=embed, view=self)
            return

        if self.product_id == "lemon_black":
            role = await get_or_create_lemon_black_role(interaction.guild)
            if role and isinstance(interaction.user, discord.Member):
                try:
                    await interaction.user.add_roles(role, reason="Compra de Tarjeta Lemon Black en la Góndola")
                except Exception:
                    pass

            embed = discord.Embed(
                title="👑 ¡BIENVENIDO AL CLUB LEMON BLACK VIP! 💳✨",
                description=(
                    f"¡Felicitaciones {interaction.user.mention}! Adquiriste la **Tarjeta Lemon Black**.\n\n"
                    "**Tus beneficios ya están activos:**\n"
                    "• 🏷️ **15% de descuento** en todas tus compras del kiosquito.\n"
                    "• 👑 **Rol `@Lemon Black`** asignado en el servidor.\n"
                    "• 💳 **Insignia VIP** agregada a tu `/perfil`.\n\n"
                    f"💼 **Saldo restante:** **{money(balance)}**"
                ),
                color=discord.Color.from_rgb(45, 45, 45),
            )
            await interaction.response.edit_message(embed=embed, view=self)

            if interaction.channel:
                try:
                    msg = await interaction.channel.send(
                        f"💳✨ **¡ATENCIÓN VECINOS!** {interaction.user.mention} acaba de adquirir la **Tarjeta Lemon Black VIP** en el mostrador 🍾🎩. ¡Un verdadero magnate del kiosquito!"
                    )
                    record_consumption_message(interaction.guild_id, interaction.channel_id, msg.id)
                except Exception:
                    pass
            return

        price, is_sale, _ = get_product_price(interaction.guild_id, self.product_id)
        sale_badge = " *(¡Con descuento de oferta! 🔥)*" if is_sale else ""

        embed = discord.Embed(
            title="✅ ¡Compra realizada con éxito!",
            description=(
                f"Compraste **{quantity}× {product['emoji']} {product['name']}** por **{money(total)}**{sale_badge}.\n\n"
                f"💵 Billetera restante: **{money(balance)}**\n"
                f"📦 Stock restante en mostrador: `{remaining_stock}` un.\n"
                f"🎒 Se guardó en tu mochila. Usá `/consumir` para convertirlo en XP."
            ),
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Comprar 1", emoji="🛒", style=discord.ButtonStyle.success)
    async def buy_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_purchase(interaction, 1)

    @discord.ui.button(label="Comprar 5", emoji="🛍️", style=discord.ButtonStyle.primary)
    async def buy_five(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_purchase(interaction, 5)

    @discord.ui.button(label="Góndola", emoji="🔙", style=discord.ButtonStyle.secondary)
    async def back_to_catalog(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Ese mostrador no es el tuyo 😭", ephemeral=True)
            return

        embed = discord.Embed(
            title="🛒 Góndola del Kiosquito",
            description="Elegí un producto del menú desplegable para comprarlo al instante.",
            color=discord.Color.gold(),
        )
        view = ProductCatalogView(parent_interaction=self.interaction)
        await interaction.response.edit_message(embed=embed, view=view)


class InventoryConsumeSelect(discord.ui.Select):
    def __init__(self, items: list[sqlite3.Row]):
        options = []
        for row in items:
            p = PRODUCTS.get(row["product_id"])
            if not p:
                continue
            options.append(
                discord.SelectOption(
                    label=f"{p['name']} (x{row['quantity']})",
                    value=p["id"],
                    emoji=p["emoji"],
                    description=f"+{p['xp']} XP al consumir",
                )
            )
        super().__init__(
            placeholder="Elegí algo de tu mochila para consumir...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        prod_id = self.values[0]
        p = PRODUCTS.get(prod_id)
        if not p:
            await interaction.response.send_message("❌ Producto inválido.", ephemeral=True)
            return

        ok, remaining, gained, total_xp = consume_product(
            interaction.guild_id, interaction.user.id, prod_id, 1
        )

        if not ok:
            await interaction.response.send_message("🎒 Ya no te quedan de ese producto.", ephemeral=True)
            return

        # Anuncio público en el chat
        try:
            announcement = await interaction.channel.send(
                f"🛒 **{interaction.user.display_name}** consumió un {p['emoji']} **{p['name']}**."
            )
            record_consumption_message(interaction.guild_id, interaction.channel_id, announcement.id)
        except Exception:
            pass

        # Editar embed de la mochila en el mismo mensaje
        embed = inventory_embed(interaction.user, interaction.guild_id)
        embed.title = f"✨ Consumiste {p['emoji']} {p['name']} (+{gained} XP)"

        view = InventoryView(interaction.user, interaction.guild_id, interaction)
        await interaction.response.edit_message(embed=embed, view=view)


class InventoryView(discord.ui.View):
    def __init__(self, member: discord.Member, guild_id: int, parent_interaction: discord.Interaction):
        super().__init__(timeout=180)
        self.member = member
        self.guild_id = guild_id
        self.interaction = parent_interaction

        rows = get_inventory(guild_id, member.id)
        if rows and member.id == parent_interaction.user.id:
            self.add_item(InventoryConsumeSelect(rows))

    async def on_timeout(self):
        try:
            await self.interaction.delete_original_response()
        except (discord.NotFound, discord.HTTPException):
            pass


class PayDebtModal(discord.ui.Modal, title="🧾 Pagar Deuda del Kiosquito"):
    cantidad_input = discord.ui.TextInput(
        label="Monto a pagar",
        placeholder="Ej: 1500 (Dejá vacío para pagar todo lo posible)",
        required=False,
        max_length=10,
    )

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.cantidad_input.value.strip()
        target = None
        if raw:
            try:
                target = int(raw)
                if target <= 0:
                    raise ValueError
            except ValueError:
                await interaction.response.send_message("❌ Ingresá un número válido.", ephemeral=True)
                return

        with get_connection() as conn:
            ensure_user(conn, interaction.guild_id, interaction.user.id)
            user = conn.execute(
                "SELECT * FROM users WHERE guild_id=? AND user_id=?",
                (interaction.guild_id, interaction.user.id),
            ).fetchone()

            if user["debt"] <= 0:
                await interaction.response.send_message(
                    "✅ No debés nada en la libretita.", ephemeral=True
                )
                return

            payment_goal = target if target is not None else user["debt"]
            payment = min(payment_goal, user["money"], user["debt"])

            if payment <= 0:
                await interaction.response.send_message(
                    "💸 No tenés un mango en la billetera para pagar la deuda.", ephemeral=True
                )
                return

            conn.execute(
                """
                UPDATE users
                SET money=money-?, debt=debt-?
                WHERE guild_id=? AND user_id=?
                """,
                (payment, payment, interaction.guild_id, interaction.user.id),
            )
            new_debt = user["debt"] - payment
            new_money = user["money"] - payment

        await interaction.response.send_message(
            f"🧾 Pagaste **{money(payment)}** de tu deuda.\n"
            f"Deuda restante: **{money(new_debt)}** | Billetera: **{money(new_money)}**.",
            ephemeral=True,
        )
        asyncio.create_task(auto_delete_interaction(interaction, 180))


# ---------- VISTA PERSISTENTE DEL KIOSQUITO ----------

class PersistentKioskView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Comprar / Góndola",
        emoji="🛒",
        style=discord.ButtonStyle.success,
        custom_id="kiosk:buy",
    )
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_open(guild_id=interaction.guild_id):
            await interaction.response.send_message(
                f"🔒 El Kiosquito está cerrado. Volvemos a abrir a las **{next_opening()}**.",
                ephemeral=True,
            )
            asyncio.create_task(auto_delete_interaction(interaction, 180))
            return

        embed = discord.Embed(
            title="🛒 Góndola del Kiosquito",
            description="Elegí un producto del menú desplegable para ver precios y comprarlo.",
            color=discord.Color.gold(),
        )
        view = ProductCatalogView(parent_interaction=interaction)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(
        label="Changuitas",
        emoji="🧹",
        style=discord.ButtonStyle.primary,
        custom_id="kiosk:changuita",
    )
    async def changuita_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_open(guild_id=interaction.guild_id):
            await interaction.response.send_message(
                f"🔒 No podés laburar con el kiosco cerrado. Abrimos a las **{next_opening()}**.",
                ephemeral=True,
            )
            asyncio.create_task(auto_delete_interaction(interaction, 180))
            return

        now = int(time.time())
        cooldown = CONFIG["changuita_cooldown_minutes"] * 60
        user = get_user(interaction.guild_id, interaction.user.id)
        elapsed = now - user["last_work"]

        if user["last_work"] and elapsed < cooldown:
            await interaction.response.send_message(
                f"🧹 Ya hiciste una changuita hace poco (o te rajaron). Volvé en **{seconds_text(cooldown - elapsed)}**.",
                ephemeral=True,
            )
            asyncio.create_task(auto_delete_interaction(interaction, 180))
            return

        embed = discord.Embed(
            title="🧹 Bolsa de Changuitas del Kiosquito",
            description=(
                "Elegí uno de los trabajos disponibles del mostrador.\n"
                "⚠️ *¡Ojo! Si hacés mal la changuita, te rajan sin un mango y con 30 min de sanción.*\n\n"
                "💵 **Pagos:**\n"
                "• **Fácil:** $150 – $300 • +10-20 XP\n"
                "• **Normal:** $300 – $600 • +20-35 XP\n"
                "• **Pesada:** $600 – $1.000 • +35-60 XP\n"
            ),
            color=discord.Color.gold(),
        )
        view = ChanguitasBoardView(user_id=interaction.user.id, parent_interaction=interaction)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(
        label="Raspadita",
        emoji="🎫",
        style=discord.ButtonStyle.primary,
        custom_id="kiosk:raspadita",
    )
    async def raspadita_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await start_raspadita_session(interaction)

    @discord.ui.button(
        label="Quiniela",
        emoji="🎱",
        style=discord.ButtonStyle.primary,
        custom_id="kiosk:quiniela",
    )
    async def quiniela_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await start_quiniela_session(interaction)

    @discord.ui.button(
        label="Mi Mochila",
        emoji="🎒",
        style=discord.ButtonStyle.secondary,
        custom_id="kiosk:bag",
    )
    async def bag_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = inventory_embed(interaction.user, interaction.guild_id)
        view = InventoryView(interaction.user, interaction.guild_id, interaction)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(
        label="Mi Perfil",
        emoji="👤",
        style=discord.ButtonStyle.secondary,
        custom_id="kiosk:profile",
    )
    async def profile_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = profile_embed(interaction.user, interaction.guild_id)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))

    @discord.ui.button(
        label="Pagar Deuda",
        emoji="🧾",
        style=discord.ButtonStyle.secondary,
        custom_id="kiosk:pay_debt",
    )
    async def pay_debt_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = get_user(interaction.guild_id, interaction.user.id)
        if user["debt"] <= 0:
            await interaction.response.send_message("✅ No tenés ninguna deuda pendiente.", ephemeral=True)
            asyncio.create_task(auto_delete_interaction(interaction, 180))
            return
        await interaction.response.send_modal(PayDebtModal())

    @discord.ui.button(
        label="Horarios",
        emoji="🕗",
        style=discord.ButtonStyle.secondary,
        custom_id="kiosk:schedule",
    )
    async def schedule_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        now = datetime.now(TZ)
        status = "🟢 Abierto" if is_open(now, guild_id=interaction.guild_id) else f"🔒 Cerrado • vuelve {next_opening(now)}"
        text = f"**{status}**\n\n### 🕗 Horarios de atención (Argentina)\n{opening_hours_text()}\n\n*Hora actual: {now.strftime('%H:%M')} hs*"
        await interaction.response.send_message(text, ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))


# ---------- GESTIÓN DEL MENSAJE FIJO Y JORNADAS ----------

async def get_or_create_kiosk_channel(guild: discord.Guild) -> discord.TextChannel | None:
    """Busca o crea automáticamente el canal oficial del Kiosquito."""
    channel_id_raw = get_setting(guild.id, "kiosk_channel_id", "0")
    try:
        channel_id = int(channel_id_raw)
    except ValueError:
        channel_id = 0

    # 1. Si ya hay un canal configurado y sigue existiendo, usar ese
    if channel_id:
        ch = guild.get_channel(channel_id)
        if not ch:
            try:
                ch = await guild.fetch_channel(channel_id)
            except Exception:
                ch = None
        if ch and isinstance(ch, discord.TextChannel):
            return ch

    # 2. Buscar si ya existe algún canal con nombre de kiosquito
    channel_names = ["el-kiosquito-de-lemon", "kiosquito-de-lemon", "el-kiosquito", "kiosquito"]
    for ch in guild.text_channels:
        if ch.name.lower() in channel_names or "kiosquito" in ch.name.lower():
            set_setting(guild.id, "kiosk_channel_id", str(ch.id))
            return ch

    # 3. Si no existe, crearlo automáticamente
    try:
        new_ch = await guild.create_text_channel(
            name="el-kiosquito-de-lemon",
            topic="🏪 Canal oficial de compras, changuitas y economía de El Kiosquito de Lemon.",
        )
        set_setting(guild.id, "kiosk_channel_id", str(new_ch.id))
        set_setting(guild.id, "kiosk_message_id", "0")
        print(f"✅ Canal #el-kiosquito-de-lemon creado automáticamente en '{guild.name}' ({guild.id})")
        return new_ch
    except discord.Forbidden:
        print(f"⚠️ No se pudo crear el canal en '{guild.name}': falta permiso 'Manage Channels'.")
    except Exception as e:
        print(f"⚠️ Error al crear canal en '{guild.name}': {e}")

    # 4. Si no pudo crear, devolver el canal del sistema o el primer canal de texto con permisos
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        return guild.system_channel

    for ch in guild.text_channels:
        if ch.permissions_for(guild.me).send_messages:
            return ch

    return None


async def update_kiosk_fixed_message(guild: discord.Guild, repost: bool = False) -> None:
    channel = await get_or_create_kiosk_channel(guild)
    if not channel:
        return

    open_now = is_open(guild_id=guild.id)
    embed = kiosk_open_embed(guild.id) if open_now else kiosk_closed_embed(guild.id)
    view = PersistentKioskView() if open_now else None

    message_id_raw = get_setting(guild.id, "kiosk_message_id", "0")
    try:
        message_id = int(message_id_raw)
    except ValueError:
        message_id = 0

    old_message = None
    if message_id:
        try:
            old_message = await channel.fetch_message(message_id)
        except (discord.NotFound, discord.HTTPException):
            old_message = None

    if repost:
        # Borrar el mensaje anterior para que el nuevo quede al final del chat y sea visible
        if old_message:
            try:
                await old_message.delete()
            except Exception as e:
                print(f"Aviso al borrar mensaje anterior del kiosquito: {e}")

        try:
            new_msg = await channel.send(embed=embed, view=view)
            set_setting(guild.id, "kiosk_message_id", str(new_msg.id))
        except Exception as e:
            print(f"Error enviando nuevo mensaje de kiosquito en guild {guild.id}: {e}")
    else:
        # Actualizar en el lugar si el mensaje existe
        if old_message:
            try:
                await old_message.edit(embed=embed, view=view)
                return
            except discord.HTTPException:
                pass

        # Si no existía o falló la edición, enviar uno nuevo
        try:
            new_msg = await channel.send(embed=embed, view=view)
            set_setting(guild.id, "kiosk_message_id", str(new_msg.id))
        except Exception as e:
            print(f"Error enviando mensaje fijo en guild {guild.id}: {e}")


async def on_shift_opened(guild: discord.Guild):
    """Inicia una nueva jornada al abrirse el kiosquito, setea stock inicial, tira ofertas y publica el panel actualizado."""
    new_shift_id = int(time.time())
    set_setting(guild.id, "current_shift_id", str(new_shift_id))
    set_setting(guild.id, "last_open_state", "1")

    # Inicializar stock corto y sortear posibles ofertas
    init_shift_stock(guild.id)
    roll_shift_offers(guild.id)

    # Publicar el mensaje de apertura al fondo del canal borrando el anterior
    await update_kiosk_fixed_message(guild, repost=True)


async def on_shift_closed(guild: discord.Guild):
    """Cierra la jornada, limpia mensajes de consumo de la jornada y publica el mensaje de cierre con el resumen."""
    # 1. Limpiar todos los mensajes públicos de consumo de la jornada
    records = get_guild_consumption_messages(guild.id)
    for row in records:
        try:
            ch = guild.get_channel(row["channel_id"])
            if not ch:
                ch = await guild.fetch_channel(row["channel_id"])
            if ch:
                msg = await ch.fetch_message(row["message_id"])
                if msg:
                    await msg.delete()
        except Exception:
            pass

    delete_all_consumption_records(guild.id)

    # 2. Resetear ofertas activas
    set_setting(guild.id, "shift_offers", "{}")

    # 3. Marcar estado cerrado
    set_setting(guild.id, "last_open_state", "0")

    # 4. Publicar nuevo mensaje de cierre con el resumen borrando el anterior
    await update_kiosk_fixed_message(guild, repost=True)


# ---------- CLASE PRINCIPAL DEL BOT ----------

class KiosquitoBot(commands.Bot):
    async def setup_hook(self):
        init_db()
        self.add_view(PersistentKioskView())

        # 1. Sincronizar siempre globalmente para que funcione en todos los servidores
        try:
            synced = await self.tree.sync()
            print(f"✅ {len(synced)} comandos globales sincronizados.")
        except Exception as e:
            print(f"⚠️ Error sincronizando comandos globales: {e}")

        # 2. Si hay un TEST_GUILD_ID configurado, sincronizarlo también allí
        if TEST_GUILD_ID:
            try:
                guild_obj = discord.Object(id=TEST_GUILD_ID)
                self.tree.copy_global_to(guild=guild_obj)
                synced_guild = await self.tree.sync(guild=guild_obj)
                print(f"✅ {len(synced_guild)} comandos sincronizados instantáneamente a guild {TEST_GUILD_ID}.")
            except Exception as e:
                print(f"Aviso al sincronizar guild de prueba {TEST_GUILD_ID}: {e}")


intents = discord.Intents.default()
bot = KiosquitoBot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print("=" * 52)
    print(f"🏪 Bot conectado como: {bot.user} • v{BOT_VERSION}")
    print(f"🕗 Hora Argentina: {datetime.now(TZ).strftime('%H:%M')}")
    print(f"Estado por horario: {'ABIERTO' if is_open() else 'CERRADO'}")
    print(f"🌐 Servidores activos ({len(bot.guilds)}): {', '.join([g.name for g in bot.guilds])}")
    print("=" * 52)

    now = datetime.now(TZ)
    for guild in bot.guilds:
        # Sincronizar comandos en cada servidor para que aparezcan al instante sin demoras
        try:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
        except Exception as e:
            print(f"Aviso sincronizando comandos en '{guild.name}': {e}")

        currently_open = is_open(now, guild.id)
        last_state = get_setting(guild.id, "last_open_state", "-1")

        if last_state == "-1":
            set_setting(guild.id, "last_open_state", "1" if currently_open else "0")
            await update_kiosk_fixed_message(guild, repost=True)
        elif currently_open and last_state == "0":
            await on_shift_opened(guild)
        elif not currently_open and last_state == "1":
            await on_shift_closed(guild)
        else:
            await update_kiosk_fixed_message(guild, repost=False)

    if not presence_loop.is_running():
        presence_loop.start()


@bot.event
async def on_guild_join(guild: discord.Guild):
    print(f"🎉 El bot se ha unido a un nuevo servidor: {guild.name} ({guild.id})")
    try:
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"✅ Comandos slash sincronizados al instante en '{guild.name}'")
    except Exception as e:
        print(f"Aviso al sincronizar comandos en '{guild.name}': {e}")

    # Crear/detectar canal automáticamente y publicar el panel
    await update_kiosk_fixed_message(guild, repost=True)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    # Auto-limpieza en el canal oficial del Kiosquito (si está activada):
    # Si un usuario escribe un mensaje de texto normal en #el-kiosquito-de-lemon, se borra para mantener el canal limpio
    kiosk_channel_id_raw = get_setting(message.guild.id, "kiosk_channel_id", "0")
    auto_cleanup_active = get_setting(message.guild.id, "auto_cleanup_enabled", "1") == "1"

    if auto_cleanup_active and str(message.channel.id) == kiosk_channel_id_raw:
        try:
            await message.delete()
            await message.channel.send(
                f"🤫 {message.author.mention}, este canal es exclusivo para el panel del kiosco y comandos `/`. Para chatear andá a los demás canales.",
                delete_after=4,
            )
        except Exception:
            pass
        return

    key = (message.guild.id, message.author.id)
    now = time.time()
    cooldown = CONFIG["message_xp_cooldown_seconds"]
    last = MESSAGE_XP_COOLDOWNS.get(key, 0)

    # XP silenciosa por actividad
    if now - last >= cooldown:
        amount = random.randint(CONFIG["message_xp_min"], CONFIG["message_xp_max"])
        add_xp(message.guild.id, message.author.id, amount)
        MESSAGE_XP_COOLDOWNS[key] = now


@tasks.loop(minutes=1)
async def presence_loop():
    """Bucle sincronizado con la hora argentina para verificar aperturas, cierres, presencia, reposición y quiniela."""
    now = datetime.now(TZ)

    for guild in bot.guilds:
        currently_open = is_open(now, guild.id)
        last_state = get_setting(guild.id, "last_open_state", "-1")

        if last_state == "-1":
            set_setting(guild.id, "last_open_state", "1" if currently_open else "0")
            await update_kiosk_fixed_message(guild, repost=True)
        elif currently_open and last_state == "0":
            await on_shift_opened(guild)
        elif not currently_open and last_state == "1":
            await on_shift_closed(guild)
        elif currently_open and now.minute % 30 == 0:
            # Reposición periódica de stock cada 30 min mientras está abierto
            restock_kiosk(guild.id)
            await update_kiosk_fixed_message(guild, repost=False)

        # Verificación de Quiniela Automática (Diaria a las 22:00 hs):
        auto_quiniela = get_setting(guild.id, "quiniela_auto_enabled", "1") == "1"
        if auto_quiniela:
            today_str = now.strftime("%Y-%m-%d")
            if now.hour == 10 and now.minute == 0:
                last_10am = get_setting(guild.id, "last_quiniela_10am_date", "")
                if last_10am != today_str:
                    set_setting(guild.id, "last_quiniela_10am_date", today_str)
                    await send_quiniela_reminder_morning(guild)
            elif now.hour == 15 and now.minute == 0:
                last_15hs = get_setting(guild.id, "last_quiniela_15hs_date", "")
                if last_15hs != today_str:
                    set_setting(guild.id, "last_quiniela_15hs_date", today_str)
                    await send_quiniela_reminder_afternoon(guild)
            elif now.hour == 21 and now.minute == 40:
                last_20m = get_setting(guild.id, "last_quiniela_20m_date", "")
                if last_20m != today_str:
                    set_setting(guild.id, "last_quiniela_20m_date", today_str)
                    await send_quiniela_announcement_20m(guild)
            elif now.hour == 21 and now.minute == 55:
                last_5m = get_setting(guild.id, "last_quiniela_5m_date", "")
                if last_5m != today_str:
                    set_setting(guild.id, "last_quiniela_5m_date", today_str)
                    await send_quiniela_announcement_5m(guild)
            elif now.hour == 22 and now.minute == 0:
                last_draw = get_setting(guild.id, "last_quiniela_draw_date", "")
                if last_draw != today_str:
                    set_setting(guild.id, "last_quiniela_draw_date", today_str)
                    await run_quiniela_draw(guild)

    manually_open = any(
        manual_open_status(guild.id)[0]
        for guild in bot.guilds
    )

    if manually_open or is_open(now):
        text = "🟢 Kiosquito abierto"
    else:
        text = f"🔒 Abre {next_opening(now)}"

    await bot.change_presence(activity=discord.Game(name=text))


@presence_loop.before_loop
async def before_presence():
    await bot.wait_until_ready()


# ---------- COMANDOS SLASH ----------

@bot.tree.command(name="setup", description="[Admin] Configurar el canal propio del Kiosquito de Lemon.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(canal="Canal donde estará el mensaje fijo (opcional, por defecto crea o usa #el-kiosquito-de-lemon).")
@app_commands.guild_only()
async def setup(
    interaction: discord.Interaction,
    canal: discord.TextChannel | None = None,
):
    target_channel = canal or (await get_or_create_kiosk_channel(interaction.guild)) or interaction.channel
    old_channel_id_raw = get_setting(interaction.guild_id, "kiosk_channel_id", "0")
    old_msg_id_raw = get_setting(interaction.guild_id, "kiosk_message_id", "0")

    if str(target_channel.id) != old_channel_id_raw:
        try:
            old_ch = interaction.guild.get_channel(int(old_channel_id_raw))
            if old_ch:
                old_msg = await old_ch.fetch_message(int(old_msg_id_raw))
                if old_msg:
                    await old_msg.delete()
        except Exception:
            pass

    set_setting(interaction.guild_id, "kiosk_channel_id", str(target_channel.id))
    set_setting(interaction.guild_id, "kiosk_message_id", "0")

    await update_kiosk_fixed_message(interaction.guild, repost=True)

    await interaction.response.send_message(
        f"✅ **Kiosquito configurado exitosamente** en {target_channel.mention}.\n"
        f"Se ha publicado el panel interactivo del Kiosquito.",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="kiosquito", description="Abrir el panel del mostrador del Kiosquito.")
@app_commands.guild_only()
async def kiosquito(interaction: discord.Interaction):
    now = datetime.now(TZ)
    if not is_open(now, interaction.guild_id):
        embed = discord.Embed(
            title="🔒 El Kiosquito de Lemon está cerrado",
            description=(
                f"Volvemos a abrir a las **{next_opening(now)}**.\n\n"
                f"### 🕗 Horarios de atención (Argentina)\n{opening_hours_text()}"
            ),
            color=discord.Color.red(),
        )
        embed.set_footer(text=f"Hora Argentina: {now.strftime('%H:%M')}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    user = get_user(interaction.guild_id, interaction.user.id)
    embed = discord.Embed(
        title="🏪 El Kiosquito de Lemon",
        description="Buenas, maestro. ¿Qué vas a llevar hoy?\n\nElegí un producto de la góndola de abajo:",
        color=discord.Color.gold(),
    )
    embed.add_field(name="💵 Tu plata", value=money(user["money"]), inline=True)
    embed.add_field(name="⭐ Tu XP", value=f"{user['xp']} XP", inline=True)

    if user["xp"] >= CONFIG["fiado_xp_required"]:
        embed.add_field(name="🤝 Fiado", value="✅ Habilitado", inline=True)
    else:
        embed.add_field(name="🤝 Fiado", value=f"🔒 {CONFIG['fiado_xp_required']} XP", inline=True)

    view = ProductCatalogView(parent_interaction=interaction)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="productos", description="Ver todos los productos, precios, ofertas y stock.")
@app_commands.guild_only()
async def productos(interaction: discord.Interaction):
    offers = get_shift_offers(interaction.guild_id)
    stocks = get_all_kiosk_stock(interaction.guild_id)

    embed = discord.Embed(
        title="🛒 Góndola del Kiosquito",
        description="Al consumir un producto de tu mochila ganás la XP indicada.\n",
        color=discord.Color.gold(),
    )

    lines = []
    for p in PRODUCT_LIST:
        price, is_sale, orig = get_product_price(interaction.guild_id, p["id"])
        stock = stocks.get(p["id"], 0)
        stock_str = f"`Stock: {stock}`" if stock > 0 else "`AGOTADO 🚫`"

        if is_sale:
            lines.append(
                f"{p['emoji']} **{p['name']}** — 🔥 **{money(price)}** *(Antes {money(orig)})* • `+{p['xp']} XP` • {stock_str}"
            )
        else:
            lines.append(
                f"{p['emoji']} **{p['name']}** — {money(price)} • `+{p['xp']} XP` • {stock_str}"
            )

    embed.description += "\n" + "\n".join(lines)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="perfil", description="Ver plata, experiencia, deuda y estado del fiado.")
@app_commands.describe(usuario="Usuario a consultar. Si lo dejás vacío, sos vos.")
@app_commands.guild_only()
async def perfil(
    interaction: discord.Interaction,
    usuario: discord.Member | None = None,
):
    member = usuario or interaction.user
    await interaction.response.send_message(
        embed=profile_embed(member, interaction.guild_id),
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="saldo", description="Ver rápidamente tu billetera y deuda.")
@app_commands.guild_only()
async def saldo(interaction: discord.Interaction):
    user = get_user(interaction.guild_id, interaction.user.id)
    await interaction.response.send_message(
        f"💵 **{interaction.user.display_name}** tiene **{money(user['money'])}**.\n"
        f"⭐ {user['xp']} XP • 🧾 Deuda: {money(user['debt'])}",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="mochila", description="Ver los productos que tenés guardados.")
@app_commands.describe(usuario="Usuario a consultar. Si lo dejás vacío, sos vos.")
@app_commands.guild_only()
async def mochila(
    interaction: discord.Interaction,
    usuario: discord.Member | None = None,
):
    member = usuario or interaction.user
    embed = inventory_embed(member, interaction.guild_id)
    view = InventoryView(member, interaction.guild_id, interaction)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="comprar", description="Comprar un producto del kiosquito.")
@app_commands.describe(producto="Producto a comprar", cantidad="Cantidad a comprar")
@app_commands.guild_only()
async def comprar(
    interaction: discord.Interaction,
    producto: str,
    cantidad: app_commands.Range[int, 1, 20] = 1,
):
    if producto not in PRODUCTS:
        await interaction.response.send_message(
            "❌ Ese producto no existe. Usá `/productos`.", ephemeral=True
        )
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    if not is_open(guild_id=interaction.guild_id):
        await interaction.response.send_message(
            f"🔒 Está cerrado. Volvemos a abrir a las **{next_opening()}**.",
            ephemeral=True,
        )
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    p = PRODUCTS[producto]
    ok, balance, total, reason, remaining_stock = normal_purchase(
        interaction.guild_id, interaction.user.id, producto, cantidad
    )

    if not ok:
        if reason == "already_lemon_black":
            await interaction.response.send_message(
                "💳 **¡Ya sos Miembro Lemon Black VIP!** Tenés tu 15% de descuento activo en todas las golosinas.",
                ephemeral=True,
            )
        elif reason == "out_of_stock":
            await interaction.response.send_message(
                f"🚫 No hay suficiente stock de **{p['name']}**. Quedan **{remaining_stock} un.** en el mostrador.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"💸 No te alcanza.\n"
                f"Necesitás **{money(total)}** y tenés **{money(balance)}**.\n"
                f"Con {CONFIG['fiado_xp_required']} XP podés pedir `/fiado`.",
                ephemeral=True,
            )
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    if producto == "lemon_black":
        role = await get_or_create_lemon_black_role(interaction.guild)
        if role and isinstance(interaction.user, discord.Member):
            try:
                await interaction.user.add_roles(role, reason="Compra de Tarjeta Lemon Black VIP")
            except Exception:
                pass

        embed = discord.Embed(
            title="👑 ¡BIENVENIDO AL CLUB LEMON BLACK VIP! 💳✨",
            description=(
                f"¡Felicitaciones {interaction.user.mention}! Adquiriste la **Tarjeta Lemon Black**.\n\n"
                "**Tus beneficios ya están activos:**\n"
                "• 🏷️ **15% de descuento** en todas tus compras del kiosquito.\n"
                "• 👑 **Rol `@Lemon Black`** asignado en el servidor.\n"
                "• 💳 **Insignia VIP** agregada a tu `/perfil`.\n\n"
                f"💼 **Saldo restante:** **{money(balance)}**"
            ),
            color=discord.Color.from_rgb(45, 45, 45),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))

        if interaction.channel:
            try:
                msg = await interaction.channel.send(
                    f"💳✨ **¡ATENCIÓN VECINOS!** {interaction.user.mention} acaba de adquirir la **Tarjeta Lemon Black VIP** 🍾🎩. ¡Un verdadero magnate del kiosquito!"
                )
                record_consumption_message(interaction.guild_id, interaction.channel_id, msg.id)
            except Exception:
                pass
        return

    await interaction.response.send_message(
        f"🛍️ Compraste **{cantidad}× {p['emoji']} {p['name']}** "
        f"por **{money(total)}**.\n"
        f"💵 Te quedan **{money(balance)}** en la billetera. (Quedan `{remaining_stock}` un. en el kiosco)",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="consumir", description="Consumir un producto comprado de tu mochila y ganar XP.")
@app_commands.describe(producto="Producto disponible en tu mochila", cantidad="Cantidad a consumir")
@app_commands.guild_only()
async def consumir(
    interaction: discord.Interaction,
    producto: str,
    cantidad: app_commands.Range[int, 1, 20] = 1,
):
    if producto not in PRODUCTS:
        await interaction.response.send_message(
            "❌ Producto no válido o no disponible en tu mochila.", ephemeral=True
        )
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    p = PRODUCTS[producto]
    ok, remaining, gained, total_xp = consume_product(
        interaction.guild_id, interaction.user.id, producto, cantidad
    )

    if not ok:
        await interaction.response.send_message(
            f"🎒 No tenés suficientes **{p['name']}**. Tenés {remaining} en tu mochila.",
            ephemeral=True,
        )
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    unlocked_text = ""
    if total_xp >= CONFIG["fiado_xp_required"]:
        unlocked_text = "\n🤝 **¡Ya tenés habilitado el fiado!**"

    # Confirmación efímera al usuario
    await interaction.response.send_message(
        f"{p['emoji']} Consumiste **{cantidad}× {p['name']}**.\n"
        f"⭐ Ganaste **{gained} XP**. Total: **{total_xp} XP**."
        f"{unlocked_text}",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))

    # Anuncio público en el canal
    try:
        announcement = await interaction.channel.send(
            f"🛒 **{interaction.user.display_name}** consumió un {p['emoji']} **{p['name']}**."
        )
        record_consumption_message(interaction.guild_id, interaction.channel_id, announcement.id)
    except Exception as e:
        print(f"No se pudo enviar el anuncio público de consumo: {e}")


@bot.tree.command(name="changuitas", description="Hacer una changuita interactiva en el kiosquito.")
@app_commands.guild_only()
async def changuitas(interaction: discord.Interaction):
    if not is_open(guild_id=interaction.guild_id):
        await interaction.response.send_message(
            f"🔒 No podés laburar con el kiosco cerrado. Abrimos **{next_opening()}**.",
            ephemeral=True,
        )
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    now = int(time.time())
    cooldown = CONFIG["changuita_cooldown_minutes"] * 60
    user = get_user(interaction.guild_id, interaction.user.id)
    elapsed = now - user["last_work"]

    if user["last_work"] and elapsed < cooldown:
        await interaction.response.send_message(
            f"🧹 Ya hiciste una changuita hace poco (o te rajaron). Volvé en **{seconds_text(cooldown - elapsed)}**.",
            ephemeral=True,
        )
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    embed = discord.Embed(
        title="🧹 Bolsa de Changuitas del Kiosquito",
        description=(
            "Elegí uno de los trabajos del menú interactivo:\n"
            "⚠️ *¡Ojo! Si hacés mal la changuita, te rajan sin un mango y con 30 min de sanción.*\n\n"
            "💵 **Dificultad y Pagos:**\n"
            "• **Fácil:** $150 – $300 • +10-20 XP\n"
            "• **Normal:** $300 – $600 • +20-35 XP\n"
            "• **Pesada:** $600 – $1.000 • +35-60 XP\n"
        ),
        color=discord.Color.gold(),
    )
    view = ChanguitasBoardView(user_id=interaction.user.id, parent_interaction=interaction)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="changuita", description="Hacer una changuita interactiva en el kiosquito.")
@app_commands.guild_only()
async def changuita(interaction: discord.Interaction):
    await changuitas.callback(interaction)


@bot.tree.command(name="raspadita", description="Jugar a la Raspadita del Kiosquito y competir por el Pozo Acumulado.")
@app_commands.guild_only()
async def raspadita_cmd(interaction: discord.Interaction):
    await start_raspadita_session(interaction)


@bot.tree.command(name="diario", description="Cobrar tu recompensa diaria.")
@app_commands.guild_only()
async def diario(interaction: discord.Interaction):
    now = int(time.time())
    cooldown = CONFIG["daily_cooldown_hours"] * 3600

    with get_connection() as conn:
        ensure_user(conn, interaction.guild_id, interaction.user.id)
        user = conn.execute(
            "SELECT * FROM users WHERE guild_id=? AND user_id=?",
            (interaction.guild_id, interaction.user.id),
        ).fetchone()

        elapsed = now - user["last_daily"]
        if user["last_daily"] and elapsed < cooldown:
            remaining = cooldown - elapsed
            await interaction.response.send_message(
                f"⏳ Ya cobraste hoy. Volvé en **{seconds_text(remaining)}**.",
                ephemeral=True,
            )
            asyncio.create_task(auto_delete_interaction(interaction, 180))
            return

        cash = random.randint(CONFIG["daily_money_min"], CONFIG["daily_money_max"])
        xp = random.randint(CONFIG["daily_xp_min"], CONFIG["daily_xp_max"])

        conn.execute(
            """
            UPDATE users
            SET money=money+?, xp=xp+?, last_daily=?
            WHERE guild_id=? AND user_id=?
            """,
            (cash, xp, now, interaction.guild_id, interaction.user.id),
        )

    await interaction.response.send_message(
        f"🗓️ **Recompensa diaria cobrada:**\n"
        f"💵 +{money(cash)}\n"
        f"⭐ +{xp} XP",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="fiado", description="Comprar fiado cuando hayas alcanzado 2.000 XP.")
@app_commands.describe(producto="Producto a pedir fiado", cantidad="Cantidad")
@app_commands.guild_only()
async def fiado(
    interaction: discord.Interaction,
    producto: str,
    cantidad: app_commands.Range[int, 1, 20] = 1,
):
    if producto not in PRODUCTS:
        await interaction.response.send_message("❌ Ese producto no existe.", ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    if not is_open(guild_id=interaction.guild_id):
        await interaction.response.send_message(
            f"🔒 El kiosco está cerrado. Volvemos a abrir a las **{next_opening()}**.",
            ephemeral=True,
        )
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    status, user, total, missing_or_stock = fiado_purchase(
        interaction.guild_id, interaction.user.id, producto, cantidad
    )
    p = PRODUCTS[producto]

    if status == "out_of_stock":
        await interaction.response.send_message(
            f"🚫 No hay suficiente stock de **{p['name']}**. Quedan **{missing_or_stock} un.**",
            ephemeral=True,
        )
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    if status == "locked":
        await interaction.response.send_message(
            f"🧔 «Fiado recién cuando te conozca mejor, maestro.»\n\n"
            f"🔒 Necesitás **{CONFIG['fiado_xp_required']} XP**.\n"
            f"Ahora tenés **{user['xp']} XP**.",
            ephemeral=True,
        )
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    if status == "enough_money":
        await interaction.response.send_message(
            "🤨 Pero si tenés plata suficiente. Usá `/comprar` y pagame de contado.",
            ephemeral=True,
        )
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    if status == "debt_limit":
        available = CONFIG["fiado_debt_limit"] - user["debt"]
        await interaction.response.send_message(
            f"🧾 No te puedo fiar tanto.\n"
            f"Tu deuda actual es **{money(user['debt'])}** y solo te quedan "
            f"**{money(max(0, available))}** de margen.",
            ephemeral=True,
        )
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    new_debt = user["debt"] + missing_or_stock
    await interaction.response.send_message(
        f"🤝 **Anotado en la libretita.**\n"
        f"Te llevaste **{cantidad}× {p['emoji']} {p['name']}**.\n"
        f"🧾 Se sumaron **{money(missing_or_stock)}** a tu deuda.\n"
        f"Deuda total: **{money(new_debt)}**.",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="pagar_deuda", description="Pagar lo que debés en el kiosquito.")
@app_commands.describe(cantidad="Cuánto querés pagar. Dejá vacío para pagar todo lo posible.")
@app_commands.guild_only()
async def pagar_deuda(
    interaction: discord.Interaction,
    cantidad: app_commands.Range[int, 1, 1000000] | None = None,
):
    with get_connection() as conn:
        ensure_user(conn, interaction.guild_id, interaction.user.id)
        user = conn.execute(
            "SELECT * FROM users WHERE guild_id=? AND user_id=?",
            (interaction.guild_id, interaction.user.id),
        ).fetchone()

        if user["debt"] <= 0:
            await interaction.response.send_message("✅ No debés nada. ¡Estás al día!", ephemeral=True)
            asyncio.create_task(auto_delete_interaction(interaction, 180))
            return

        target = cantidad if cantidad is not None else user["debt"]
        payment = min(target, user["money"], user["debt"])

        if payment <= 0:
            await interaction.response.send_message("💸 No tenés plata para pagar la deuda.", ephemeral=True)
            asyncio.create_task(auto_delete_interaction(interaction, 180))
            return

        conn.execute(
            """
            UPDATE users
            SET money=money-?, debt=debt-?
            WHERE guild_id=? AND user_id=?
            """,
            (payment, payment, interaction.guild_id, interaction.user.id),
        )
        new_debt = user["debt"] - payment
        new_money = user["money"] - payment

    await interaction.response.send_message(
        f"🧾 Pagaste **{money(payment)}** de tu deuda.\n"
        f"Deuda restante: **{money(new_debt)}** • Billetera: **{money(new_money)}**.",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="regalar", description="Regalar un producto de tu mochila a otro usuario.")
@app_commands.describe(usuario="A quién se lo regalás", producto="Producto", cantidad="Cantidad")
@app_commands.guild_only()
async def regalar(
    interaction: discord.Interaction,
    usuario: discord.Member,
    producto: str,
    cantidad: app_commands.Range[int, 1, 20] = 1,
):
    if usuario.bot:
        await interaction.response.send_message("🤖 Los bots no comen golosinas... todavía.", ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    if usuario.id == interaction.user.id:
        await interaction.response.send_message("Eso se llama guardártelo vos mismo 😭", ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    if producto not in PRODUCTS:
        await interaction.response.send_message("❌ Ese producto no existe.", ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    ok, owned = gift_product(
        interaction.guild_id,
        interaction.user.id,
        usuario.id,
        producto,
        cantidad,
    )
    p = PRODUCTS[producto]

    if not ok:
        await interaction.response.send_message(
            f"🎒 No te alcanza. Tenés **{owned}× {p['name']}**.",
            ephemeral=True,
        )
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    await interaction.response.send_message(
        f"🎁 Le regalaste a {usuario.mention} **{cantidad}× {p['emoji']} {p['name']}**.",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="ranking", description="Ver quién tiene más experiencia en el kiosquito.")
@app_commands.guild_only()
async def ranking(interaction: discord.Interaction):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT user_id, xp, money
            FROM users
            WHERE guild_id=?
            ORDER BY xp DESC, money DESC
            LIMIT 10
            """,
            (interaction.guild_id,),
        ).fetchall()

    if not rows:
        await interaction.response.send_message("Todavía no hay nadie en el ranking.", ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for index, row in enumerate(rows):
        prefix = medals[index] if index < 3 else f"`#{index + 1}`"
        lines.append(f"{prefix} <@{row['user_id']}> — **{row['xp']} XP** *(Billetera: {money(row['money'])})*")

    embed = discord.Embed(
        title="🏆 Clientes de Confianza del Kiosquito",
        description="\n".join(lines),
        color=discord.Color.gold(),
    )
    embed.set_footer(text=f"A los {CONFIG['fiado_xp_required']} XP se desbloquea el fiado.")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="horario", description="Ver cuándo abre y cierra el kiosquito.")
@app_commands.guild_only()
async def horario(interaction: discord.Interaction):
    now = datetime.now(TZ)
    manual_open, remaining = manual_open_status(interaction.guild_id)
    status = "🟢 **ABIERTO**" if is_open(now, interaction.guild_id) else "🔒 **CERRADO**"

    manual_text = ""
    if manual_open:
        if remaining is None:
            manual_text = "\n🔓 **Apertura manual activa** hasta `/admin_cerrar`."
        else:
            manual_text = f"\n🔓 **Apertura manual activa** por {seconds_text(remaining)} más."

    next_text = "" if is_open(now, interaction.guild_id) else f"\nPróxima apertura: **{next_opening(now)}**"
    await interaction.response.send_message(
        f"{status}{manual_text}\n\n"
        f"### 🕗 Horarios habituales (Argentina)\n{opening_hours_text()}\n\n"
        f"🕗 Hora actual: **{now.strftime('%H:%M')} hs**"
        f"{next_text}",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="ayuda", description="Ver la guía de comandos del Kiosquito.")
@app_commands.guild_only()
async def ayuda(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🍋 Guía de Comandos — El Kiosquito de Lemon",
        color=discord.Color.gold(),
        description=(
            "**Mostrador y compras**\n"
            "`/setup` — *(Admin)* Configurar el canal oficial del kiosquito\n"
            "`/kiosquito` — Abrir el mostrador\n"
            "`/productos` — Ver góndola, precios, ofertas y stock\n"
            "`/comprar` — Comprar productos\n"
            "`/mochila` — Ver tu inventario y consumir\n"
            "`/consumir` — Consumir productos y ganar XP\n"
            "`/regalar` — Regalar golosinas a un amigo\n\n"
            "**Economía y Changuitas**\n"
            "`/changuitas` — Realizar changuitas interactivas con botones\n"
            "`/perfil` — Billetera, XP, deuda y fiado\n"
            "`/saldo` — Billetera rápida\n"
            "`/diario` — Recompensa cada 24 h\n"
            "`/fiado` — Comprar fiado (desde 2.000 XP)\n"
            "`/pagar_deuda` — Pagar tu saldo en la libretita\n\n"
            "**Comunidad y Horarios**\n"
            "`/ranking` — Top de clientes con más XP\n"
            "`/horario` — Horarios de apertura y cierre\n\n"
            "**Administración**\n"
            "`/admin_abrir` — Abrir manualmente\n"
            "`/admin_cerrar` — Cerrar manualmente y mostrar resumen"
        ),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    asyncio.create_task(auto_delete_interaction(interaction, 180))


# ---------- ADMINISTRACIÓN ----------

@bot.tree.command(name="admin_abrir", description="[Admin] Abrir el kiosquito manualmente.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(minutos="Minutos para mantener abierto. Dejá vacío para abrir normalmente.")
@app_commands.guild_only()
async def admin_abrir(
    interaction: discord.Interaction,
    minutos: app_commands.Range[int, 1, 720] | None = None,
):
    now = datetime.now(TZ)
    # Limpiar cualquier cierre forzado previo
    set_setting(interaction.guild_id, "force_closed_period", "")

    current_period = get_current_schedule_period(now)
    if minutos is None:
        if current_period:
            set_setting(interaction.guild_id, "manual_open_until", "0")
            detalle = "por horario comercial regular"
        else:
            set_setting(interaction.guild_id, "manual_open_until", "-1")
            detalle = "hasta que un admin use `/admin_cerrar` o llegue el próximo horario"
    else:
        until = int(time.time()) + (minutos * 60)
        set_setting(interaction.guild_id, "manual_open_until", str(until))
        detalle = f"durante **{minutos} minutos**"

    await on_shift_opened(interaction.guild)

    await interaction.response.send_message(
        f"🔓 **Kiosquito abierto exitosamente** ({detalle}).\n"
        f"Ya se encuentran habilitadas las compras y changuitas.",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="admin_cerrar", description="[Admin] Cerrar el kiosquito forzosamente.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.guild_only()
async def admin_cerrar(interaction: discord.Interaction):
    now = datetime.now(TZ)
    was_open = is_open(now, guild_id=interaction.guild_id)

    # Cancelar apertura manual si hubiera
    set_setting(interaction.guild_id, "manual_open_until", "0")

    # Si estamos dentro de un período programado, marcar este período como cerrado forzosamente
    current_period = get_current_schedule_period(now)
    if current_period:
        set_setting(interaction.guild_id, "force_closed_period", current_period)
    else:
        set_setting(interaction.guild_id, "force_closed_period", "")

    if was_open:
        await on_shift_closed(interaction.guild)
        estado = (
            f"🔒 **Kiosquito cerrado manualmente por un administrador.**\n"
            f"Se ha publicado el resumen de la jornada.\n"
            f"Volverá a abrir automáticamente en el próximo horario: **{next_opening(now)}** (o con `/admin_abrir`)."
        )
    else:
        estado = f"ℹ️ El kiosquito ya se encuentra cerrado. Próxima apertura: **{next_opening(now)}**."

    await interaction.response.send_message(estado, ephemeral=True)
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="admin_reponer", description="[Admin] Forzar reposición de stock en el kiosquito.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(cantidad="Cantidad a sumar a cada producto")
@app_commands.guild_only()
async def admin_reponer(interaction: discord.Interaction, cantidad: app_commands.Range[int, 1, 20] = 3):
    restock_kiosk(interaction.guild_id, cantidad, cantidad)
    await update_kiosk_fixed_message(interaction.guild, repost=False)
    await interaction.response.send_message(
        f"📦 Se han repuesto **+{cantidad} unidades** a todos los productos del mostrador.",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="admin_dar_dinero", description="[Admin] Dar o quitar dinero a un usuario.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(usuario="Usuario", cantidad="Monto (positivo o negativo)")
@app_commands.guild_only()
async def admin_dar_dinero(
    interaction: discord.Interaction,
    usuario: discord.Member,
    cantidad: int,
):
    with get_connection() as conn:
        ensure_user(conn, interaction.guild_id, usuario.id)
        conn.execute(
            """
            UPDATE users SET money=MAX(0, money+?)
            WHERE guild_id=? AND user_id=?
            """,
            (cantidad, interaction.guild_id, usuario.id),
        )
        balance = conn.execute(
            "SELECT money FROM users WHERE guild_id=? AND user_id=?",
            (interaction.guild_id, usuario.id),
        ).fetchone()["money"]

    await interaction.response.send_message(
        f"🛠️ {usuario.mention}: ajuste de **{money(cantidad)}**. "
        f"Saldo actual: **{money(balance)}**.",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="admin_dar_xp", description="[Admin] Dar o quitar experiencia a un usuario.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(usuario="Usuario", cantidad="Cantidad de XP")
@app_commands.guild_only()
async def admin_dar_xp(
    interaction: discord.Interaction,
    usuario: discord.Member,
    cantidad: int,
):
    with get_connection() as conn:
        ensure_user(conn, interaction.guild_id, usuario.id)
        conn.execute(
            """
            UPDATE users SET xp=MAX(0, xp+?)
            WHERE guild_id=? AND user_id=?
            """,
            (cantidad, interaction.guild_id, usuario.id),
        )
        xp = conn.execute(
            "SELECT xp FROM users WHERE guild_id=? AND user_id=?",
            (interaction.guild_id, usuario.id),
        ).fetchone()["xp"]

    await interaction.response.send_message(
        f"🛠️ {usuario.mention}: ajuste de **{cantidad} XP**. "
        f"Ahora tiene **{xp} XP**.",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="admin_resetear", description="[Admin] Resetear los datos de un usuario.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(usuario="Usuario a resetear")
@app_commands.guild_only()
async def admin_resetear(interaction: discord.Interaction, usuario: discord.Member):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM inventory WHERE guild_id=? AND user_id=?",
            (interaction.guild_id, usuario.id),
        )
        conn.execute(
            "DELETE FROM users WHERE guild_id=? AND user_id=?",
            (interaction.guild_id, usuario.id),
        )
        ensure_user(conn, interaction.guild_id, usuario.id)

    await interaction.response.send_message(
        f"♻️ Datos de {usuario.mention} reseteados.",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="admin_resetear_raspaditas", description="[Admin] Reiniciar el límite diario de raspaditas de un usuario.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(usuario="Usuario a reiniciar su límite diario de raspaditas")
@app_commands.guild_only()
async def admin_resetear_raspaditas(interaction: discord.Interaction, usuario: discord.Member):
    reset_user_raspadita_daily_count(interaction.guild_id, usuario.id)
    await interaction.response.send_message(
        f"♻️ Se ha reiniciado el límite diario de raspaditas para {usuario.mention}. Ahora tiene **0/{RASPADITA_DAILY_LIMIT}** cartones jugados hoy.",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="lemon_black", description="Comprar la Tarjeta VIP Lemon Black ($50.000) con 15% de descuento permanente.")
@app_commands.guild_only()
async def lemon_black_cmd(interaction: discord.Interaction):
    user = get_user(interaction.guild_id, interaction.user.id)
    if user["has_lemon_black"] == 1:
        embed = discord.Embed(
            title="💳 Ya sos Miembro Lemon Black VIP",
            description="¡Ya contás con la **Tarjeta Lemon Black** activa!\nDisfrutás de un **15% de descuento permanente** en todas las compras del mostrador.",
            color=discord.Color.from_rgb(45, 45, 45),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    if user["money"] < 50000:
        embed = discord.Embed(
            title="💳 Tarjeta Lemon Black VIP ($50.000)",
            description=(
                f"❌ **No te alcanza la plata.**\n\n"
                f"💵 **Precio:** **$50.000**\n"
                f"💼 Tu saldo actual: **{money(user['money'])}**\n\n"
                "**Beneficios exclusivos:**\n"
                "• 🏷️ **15% de descuento permanente** en todas las compras de golosinas del kiosco.\n"
                "• 👑 **Rol exclusivo `@Lemon Black`** en Discord.\n"
                "• 💳 **Insignia VIP** en tu tarjeta de `/perfil`."
            ),
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    with get_connection() as conn:
        ensure_user(conn, interaction.guild_id, interaction.user.id)
        cursor = conn.execute(
            "UPDATE users SET money=money-50000, has_lemon_black=1 WHERE guild_id=? AND user_id=? AND money >= 50000",
            (interaction.guild_id, interaction.user.id),
        )
        if cursor.rowcount == 0:
            await interaction.response.send_message("💸 No tenés suficiente plata en tu billetera.", ephemeral=True)
            return

    # Asignar rol Lemon Black
    role = await get_or_create_lemon_black_role(interaction.guild)
    if role and isinstance(interaction.user, discord.Member):
        try:
            await interaction.user.add_roles(role, reason="Compra de Tarjeta Lemon Black VIP")
        except Exception:
            pass

    user = get_user(interaction.guild_id, interaction.user.id)
    embed = discord.Embed(
        title="👑 ¡BIENVENIDO AL CLUB LEMON BLACK VIP! 💳✨",
        description=(
            f"¡Felicitaciones {interaction.user.mention}! Adquiriste la **Tarjeta Lemon Black**.\n\n"
            "**Tus beneficios ya están activos:**\n"
            "• 🏷️ **15% de descuento** en todas tus compras del kiosquito.\n"
            "• 👑 **Rol `@Lemon Black`** asignado en el servidor.\n"
            "• 💳 **Insignia VIP** agregada a tu `/perfil`.\n\n"
            f"💼 **Saldo restante:** **{money(user['money'])}**"
        ),
        color=discord.Color.from_rgb(45, 45, 45),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    asyncio.create_task(auto_delete_interaction(interaction, 180))

    if interaction.channel:
        try:
            msg = await interaction.channel.send(
                f"💳✨ **¡ATENCIÓN VECINOS!** {interaction.user.mention} acaba de adquirir la **Tarjeta Lemon Black VIP** 🍾🎩. ¡Un verdadero magnate del kiosquito!"
            )
            record_consumption_message(interaction.guild_id, interaction.channel_id, msg.id)
        except Exception:
            pass


@bot.tree.command(name="titulo_comprar", description="Comprar o cambiar un título personalizado para tu /perfil ($20.000).")
@app_commands.describe(texto="Título que aparecerá en tu perfil (máx. 32 caracteres)")
@app_commands.guild_only()
async def titulo_comprar(interaction: discord.Interaction, texto: str):
    clean_text = texto.strip()
    if len(clean_text) < 2 or len(clean_text) > 32:
        await interaction.response.send_message("❌ El título debe tener entre **2 y 32 caracteres**.", ephemeral=True)
        return

    if "@everyone" in clean_text or "@here" in clean_text or "http://" in clean_text or "https://" in clean_text or "<@" in clean_text:
        await interaction.response.send_message("❌ El título no puede contener links ni menciones.", ephemeral=True)
        return

    user = get_user(interaction.guild_id, interaction.user.id)
    if user["money"] < 20000:
        await interaction.response.send_message(
            f"💸 No te alcanza la plata. El título cuesta **$20.000** y tenés **{money(user['money'])}**.",
            ephemeral=True,
        )
        return

    with get_connection() as conn:
        ensure_user(conn, interaction.guild_id, interaction.user.id)
        cursor = conn.execute(
            "UPDATE users SET money=money-20000, custom_title=? WHERE guild_id=? AND user_id=? AND money >= 20000",
            (clean_text, interaction.guild_id, interaction.user.id),
        )
        if cursor.rowcount == 0:
            await interaction.response.send_message("💸 No tenés suficiente plata en tu billetera.", ephemeral=True)
            return

    user = get_user(interaction.guild_id, interaction.user.id)
    embed = discord.Embed(
        title="🏷️ ¡Título Personalizado Comprado con Éxito!",
        description=(
            f"Tu nuevo título en `/perfil` es: **`{clean_text}`**.\n\n"
            f"💵 **Cobro:** **$20.000**\n"
            f"💼 **Saldo restante:** **{money(user['money'])}**\n\n"
            "💡 *Podés ver cómo luce usando `/perfil`.*"
        ),
        color=discord.Color.green(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="apodo_servidor", description="Cambiar tu apodo en el servidor de Discord por plata ($35.000).")
@app_commands.describe(nuevo_apodo="Nuevo apodo en el servidor (máx. 32 caracteres)")
@app_commands.guild_only()
async def apodo_servidor(interaction: discord.Interaction, nuevo_apodo: str):
    clean_nick = nuevo_apodo.strip()
    if len(clean_nick) < 1 or len(clean_nick) > 32:
        await interaction.response.send_message("❌ El apodo debe tener entre **1 y 32 caracteres**.", ephemeral=True)
        return

    if "@everyone" in clean_nick or "@here" in clean_nick or "<@" in clean_nick:
        await interaction.response.send_message("❌ El apodo no puede contener menciones.", ephemeral=True)
        return

    if interaction.user.id == interaction.guild.owner_id:
        await interaction.response.send_message(
            "👑 Sos el Dueño del Servidor. Por restricciones de Discord, ningún bot puede cambiarle el apodo al creador del servidor. ¡No se te cobró nada!",
            ephemeral=True,
        )
        return

    user = get_user(interaction.guild_id, interaction.user.id)
    if user["money"] < 35000:
        await interaction.response.send_message(
            f"💸 No te alcanza la plata. Cambiar tu apodo cuesta **$35.000** y tenés **{money(user['money'])}**.",
            ephemeral=True,
        )
        return

    if isinstance(interaction.user, discord.Member):
        try:
            await interaction.user.edit(nick=clean_nick, reason="Compra de apodo en el kiosquito ($35.000)")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ El bot no tiene permisos jerárquicos suficientes para cambiar tu apodo (tu rol más alto está por encima del rol del bot). ¡No se te cobró nada!",
                ephemeral=True,
            )
            return
        except Exception as e:
            await interaction.response.send_message(f"❌ Ocurrió un error al cambiar el apodo: {e}", ephemeral=True)
            return

    with get_connection() as conn:
        ensure_user(conn, interaction.guild_id, interaction.user.id)
        cursor = conn.execute(
            "UPDATE users SET money=money-35000 WHERE guild_id=? AND user_id=? AND money >= 35000",
            (interaction.guild_id, interaction.user.id),
        )
        if cursor.rowcount == 0:
            await interaction.response.send_message("💸 No tenés suficiente plata en tu billetera.", ephemeral=True)
            return

    user = get_user(interaction.guild_id, interaction.user.id)
    embed = discord.Embed(
        title="✨ ¡Apodo Actualizado en el Servidor!",
        description=(
            f"Tu apodo ahora es: **{clean_nick}**.\n\n"
            f"💵 **Cobro:** **$35.000**\n"
            f"💼 **Saldo restante:** **{money(user['money'])}**"
        ),
        color=discord.Color.green(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="admin_dar_lemon_black", description="[Admin] Dar o quitar la membresía Lemon Black VIP a un usuario.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(usuario="Usuario", activado="True para dar Lemon Black, False para quitar")
@app_commands.guild_only()
async def admin_dar_lemon_black(interaction: discord.Interaction, usuario: discord.Member, activado: bool):
    with get_connection() as conn:
        ensure_user(conn, interaction.guild_id, usuario.id)
        conn.execute(
            "UPDATE users SET has_lemon_black=? WHERE guild_id=? AND user_id=?",
            (1 if activado else 0, interaction.guild_id, usuario.id),
        )

    role = await get_or_create_lemon_black_role(interaction.guild)
    if role:
        try:
            if activado:
                await usuario.add_roles(role, reason="Asignado por Admin")
            else:
                await usuario.remove_roles(role, reason="Removido por Admin")
        except Exception:
            pass

    estado = "activada (15% OFF)" if activado else "desactivada"
    await interaction.response.send_message(
        f"💳 Membresía Lemon Black de {usuario.mention} **{estado}**.",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="admin_quitar_titulo", description="[Admin] Eliminar el título personalizado de un usuario.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(usuario="Usuario")
@app_commands.guild_only()
async def admin_quitar_titulo(interaction: discord.Interaction, usuario: discord.Member):
    with get_connection() as conn:
        ensure_user(conn, interaction.guild_id, usuario.id)
        conn.execute(
            "UPDATE users SET custom_title='' WHERE guild_id=? AND user_id=?",
            (interaction.guild_id, usuario.id),
        )
    await interaction.response.send_message(
        f"🏷️ Se ha eliminado el título personalizado de {usuario.mention}.",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="autolimpieza", description="[Admin] Activar o desactivar el borrado automático de mensajes comunes en el kiosco.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(activado="True para borrar texto común (deja el canal limpio), False para permitir chatear libremente.")
@app_commands.guild_only()
async def autolimpieza_cmd(interaction: discord.Interaction, activado: bool):
    set_setting(interaction.guild_id, "auto_cleanup_enabled", "1" if activado else "0")
    status = (
        "🟢 **ACTIVADA** (el bot borrará los mensajes de texto común para mantener el canal limpio)"
        if activado
        else "🔴 **DESACTIVADA** (ahora se pueden enviar mensajes de texto comunes libremente en el canal)"
    )
    kiosk_ch_id = get_setting(interaction.guild_id, "kiosk_channel_id", "0")
    ch_mention = f"<#{kiosk_ch_id}>" if kiosk_ch_id != "0" else "el canal del kiosco"
    await interaction.response.send_message(
        f"🧹 **Auto-limpieza del Kiosquito en {ch_mention}:** {status}.",
        ephemeral=True,
    )


@bot.tree.command(name="quiniela", description="Jugar tu número de la suerte en la Quiniela del Kiosquito.")
@app_commands.describe(
    numero="Número al que apostar (del 1 al 50)",
    apuesta="Monto a apostar ($100 a $1.000)",
)
@app_commands.guild_only()
async def quiniela_cmd(
    interaction: discord.Interaction,
    numero: app_commands.Range[int, 1, 50] | None = None,
    apuesta: app_commands.Range[int, 100, 1000] | None = None,
):
    if interaction.guild_id in QUINIELA_DRAWING:
        await interaction.response.send_message(
            "⏳ **El sorteo de la Quiniela está en vivo en este momento.** Las apuestas volverán a abrir en unos instantes.",
            ephemeral=True,
        )
        return

    if numero is None or apuesta is None:
        await start_quiniela_session(interaction)
        return

    with get_connection() as conn:
        ensure_user(conn, interaction.guild_id, interaction.user.id)

        row = conn.execute(
            "SELECT COUNT(*) as c FROM quiniela_bets WHERE guild_id=? AND user_id=?",
            (interaction.guild_id, interaction.user.id),
        ).fetchone()
        current_bets_count = row["c"] if row else 0

        if current_bets_count >= 3:
            await interaction.response.send_message(
                "❌ Ya alcanzaste el límite máximo de **3 apuestas activas** para el sorteo de hoy. ¡Esperá a las 22:00 hs para ver los resultados!",
                ephemeral=True,
            )
            return

        cursor = conn.execute(
            "UPDATE users SET money=money-? WHERE guild_id=? AND user_id=? AND money >= ?",
            (apuesta, interaction.guild_id, interaction.user.id, apuesta),
        )
        if cursor.rowcount == 0:
            user = conn.execute("SELECT money FROM users WHERE guild_id=? AND user_id=?", (interaction.guild_id, interaction.user.id)).fetchone()
            user_money = user["money"] if user else 0
            await interaction.response.send_message(
                f"💸 No te alcanza la plata. Tenés **{money(user_money)}** y querés apostar **{money(apuesta)}**.",
                ephemeral=True,
            )
            return

        now_ts = int(time.time())
        conn.execute(
            "INSERT INTO quiniela_bets (guild_id, user_id, number, bet_amount, created_at) VALUES (?, ?, ?, ?, ?)",
            (interaction.guild_id, interaction.user.id, numero, apuesta, now_ts),
        )
        total_bets_now = current_bets_count + 1

    quinielero_role = await get_or_create_quinielero_role(interaction.guild)
    if quinielero_role and isinstance(interaction.user, discord.Member):
        try:
            await interaction.user.add_roles(quinielero_role, reason="Participante de la Quiniela")
        except Exception:
            pass

    num_info = QUINIELA_NUMBERS.get(numero, {"name": f"Número {numero}", "emoji": "🎱"})
    premio_potencial = apuesta * 35
    premio_palo = apuesta * 2

    embed = discord.Embed(
        title="🎫 ¡Apuesta Registrada en la Quiniela! 🍀",
        description=(
            f"🧔 **El Kiosquero:** *«¡Anotado en la boleta, maestro! Mucha suerte hoy.»*\n\n"
            f"🎱 **Tu Número:** **`{numero:02d}` — {num_info['name']} {num_info['emoji']}**\n"
            f"💵 **Tu Apuesta:** **{money(apuesta)}**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🏆 **Premios Potenciales:**\n"
            f"• 🎯 **Acierto a la cabeza (x35):** **+{money(premio_potencial)}**\n"
            f"• 🤏 **Pegó en el palo (x2):** **+{money(premio_palo)}** *(si sale {numero-1 if numero>1 else 50} o {numero+1 if numero<50 else 1})*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔔 *Se te asignó el rol `@Quinielero`. Te avisaremos a las **22:00 hs** cuando arranque el sorteo en vivo.*"
        ),
        color=discord.Color.green(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="admin_sortear_quiniela", description="[Admin] Forzar y ejecutar el sorteo oficial de la Quiniela en vivo ahora mismo.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.guild_only()
async def admin_sortear_quiniela_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("🎰 **Iniciando sorteo de la Quiniela en vivo...**", ephemeral=True)
    asyncio.create_task(auto_delete_interaction(interaction, 180))
    await run_quiniela_draw(interaction.guild, target_channel=interaction.channel, is_private=False)


@bot.tree.command(name="admin_quiniela_automatica", description="[Admin] Activar o desactivar los anuncios (10:00, 15:00, 21:40, 21:55) y sorteos a las 22:00 hs.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(activado="True para activar avisos y sorteos automáticos diarios, False para modo manual/test.")
@app_commands.guild_only()
async def admin_quiniela_automatica_cmd(interaction: discord.Interaction, activado: bool):
    set_setting(interaction.guild_id, "quiniela_auto_enabled", "1" if activado else "0")
    status = (
        "🟢 **ACTIVADA** (el bot publicará recordatorios a las 10:00 y 15:00 hs, avisos previos a las 21:40 y 21:55 hs, y sorteará en vivo a las 22:00 hs)"
        if activado
        else "🔴 **DESACTIVADA (MODO TEST)** (no se enviará ningún aviso automático; solo se sortea manualmente con `/admin_sortear_quiniela`)"
    )
    await interaction.response.send_message(
        f"🎱 **Quiniela Automática:** {status}.",
        ephemeral=True,
    )


@bot.tree.command(name="admin_apuestas_quiniela", description="[Admin] Ver todas las apuestas registradas para el próximo sorteo de la Quiniela.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.guild_only()
async def admin_apuestas_quiniela_cmd(interaction: discord.Interaction):
    bets = get_active_quiniela_bets(interaction.guild_id)
    if not bets:
        embed = discord.Embed(
            title="🎱 Apuestas de la Quiniela — Registro Vacío",
            description="Aún no hay ninguna apuesta registrada para el sorteo de hoy (22:00 hs).",
            color=discord.Color.dark_grey(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        asyncio.create_task(auto_delete_interaction(interaction, 180))
        return

    # Agrupar apuestas por usuario
    user_bets_map = {}
    total_recaudado = 0
    for b in bets:
        uid = b["user_id"]
        if uid not in user_bets_map:
            user_bets_map[uid] = []
        user_bets_map[uid].append(b)
        total_recaudado += b["bet_amount"]

    lines = []
    for uid, u_bets in user_bets_map.items():
        uname = await resolve_member_name(interaction.guild, uid)
        bets_str_list = []
        for b in u_bets:
            num = b["number"]
            info = QUINIELA_NUMBERS.get(num, {"name": f"Número {num}", "emoji": "🎱"})
            bets_str_list.append(f"**`{num:02d}` ({info['name']})** por `{money(b['bet_amount'])}`")
        lines.append(f"👤 **@{uname}** ({len(u_bets)} jugada/s):\n  └ " + " | ".join(bets_str_list))

    embed = discord.Embed(
        title="🎱 Apuestas Registradas para la Quiniela de Hoy",
        description=(
            f"📊 **Total de participantes:** `{len(user_bets_map)}`\n"
            f"🎟️ **Total de apuestas:** `{len(bets)}`\n"
            f"💰 **Total recaudado:** `{money(total_recaudado)}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            + "\n\n".join(lines)
        ),
        color=discord.Color.gold(),
    )
    embed.set_footer(text="Sorteo programado para las 22:00 hs (Hora Argentina)")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    asyncio.create_task(auto_delete_interaction(interaction, 180))


# ==============================================================================
#                      SISTEMA DE DUELO DE PENALES (1v1)
# ==============================================================================

ACTIVE_PENALTY_DUELS: set[int] = set()
LAST_PENALTY_MESSAGES: dict[int, discord.Message] = {}

PENALTY_IMAGES = {
    ("der", "der"): "01_Atajada_Derecha.png",
    ("izq", "izq"): "02_Atajada_Izquierda.png",
    ("centro", "centro"): "03_Atajada_Centro.png",
    ("izq", "der"): "04_Gol_Izquierda_Arquero_Derecha.png",
    ("centro", "der"): "05_Gol_Centro_Arquero_Derecha.png",
    ("centro", "izq"): "06_Gol_Centro_Arquero_Izquierda.png",
    ("der", "izq"): "07_Gol_Derecha_Arquero_Izquierda.png",
    ("der", "centro"): "08_Gol_Derecha_Arquero_Centro.png",
    ("izq", "centro"): "09_Gol_Izquierda_Arquero_Centro.png",
}


class PenaltyMatch:
    def __init__(
        self,
        guild: discord.Guild,
        player_a: discord.Member,
        player_b: discord.Member,
        bet: int,
        message: discord.Message,
    ):
        self.guild = guild
        self.player_a = player_a
        self.player_b = player_b
        self.bet = bet
        self.pot = bet * 2
        self.message = message

        self.score_a: list[str] = []
        self.score_b: list[str] = []
        self.round_num = 1
        self.turn = 0  # 0: A patea & B ataja, 1: B patea & A ataja
        self.is_sudden_death = False

        self.is_finished = False

        self.shooter_choice: str | None = None
        self.keeper_choice: str | None = None
        self.last_action_desc: str = "🧤 *¡El árbitro pita el inicio del partido! Que comience la tanda.*"
        self.last_shot_image: str | None = None
        self.lock = asyncio.Lock()
        self.current_view: discord.ui.View | None = None

    @property
    def current_shooter(self) -> discord.Member:
        return self.player_a if self.turn == 0 else self.player_b

    @property
    def current_keeper(self) -> discord.Member:
        return self.player_b if self.turn == 0 else self.player_a

    def build_scoreboard_embed(self) -> tuple[discord.Embed, discord.File | None]:
        goals_a = self.score_a.count("🟢")
        goals_b = self.score_b.count("🟢")

        max_slots = 3 if not self.is_sudden_death else max(len(self.score_a), len(self.score_b), self.round_num)

        display_a = " ".join(self.score_a)
        if len(self.score_a) < max_slots:
            display_a += " " + " ".join(["⚪"] * (max_slots - len(self.score_a)))

        display_b = " ".join(self.score_b)
        if len(self.score_b) < max_slots:
            display_b += " " + " ".join(["⚪"] * (max_slots - len(self.score_b)))

        mode_badge = "🔥 **Muerte Súbita (Gol Gana de Diferencia)**" if self.is_sudden_death else "⚽ **Tanda Regular (3 Penales)**"

        shooter = self.current_shooter
        keeper = self.current_keeper

        role_banner = (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🧤 **AL ARCO (LE TOCA ATAJAR):** **`@{keeper.display_name}`** 🥅\n"
            f"*(¡@{keeper.display_name}, elegí hacia qué lado tirarte a atajar!)*\n\n"
            f"👟 **PATEA EL PENAL:** **`@{shooter.display_name}`** ⚽\n"
            f"*(¡@{shooter.display_name}, elegí hacia qué lado vas a patear!)*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

        embed = discord.Embed(
            title="🏟️ DUELO DE PENALES — POTRERO DEL KIOSQUITO ⚽🔥",
            description=(
                f"💰 **Pozo en juego:** **{money(self.pot)}** *({money(self.bet)} c/u)*\n"
                f"🏆 Modalidad: {mode_badge} • **Ronda {self.round_num}**\n\n"
                f"👤 **{self.player_a.display_name}:** `{display_a.strip()}` **({goals_a} Goles)**\n"
                f"👤 **{self.player_b.display_name}:** `{display_b.strip()}` **({goals_b} Goles)**\n\n"
                f"{self.last_action_desc}\n\n"
                f"{role_banner}\n\n"
                "👇 *Elegí tu dirección en secreto con los botones de abajo:*"
            ),
            color=discord.Color.gold(),
        )

        file = None
        if self.last_shot_image:
            for folder in ["Penales", "penales"]:
                img_path = ROOT / "assets" / folder / self.last_shot_image
                if img_path.exists():
                    file = discord.File(str(img_path), filename=self.last_shot_image)
                    embed.set_image(url=f"attachment://{self.last_shot_image}")
                    break

        return embed, file

    async def resolve_turn(self, interaction: discord.Interaction):
        async with self.lock:
            if self.shooter_choice is None or self.keeper_choice is None:
                return

            dir_map = {
                "izq": "⬅️ Izquierda",
                "centro": "⬆️ Centro",
                "der": "➡️ Derecha",
            }

            shooter_dir = dir_map.get(self.shooter_choice, self.shooter_choice)
            keeper_dir = dir_map.get(self.keeper_choice, self.keeper_choice)

            shooter = self.current_shooter
            keeper = self.current_keeper

            is_goal = self.shooter_choice != self.keeper_choice

            if is_goal:
                symbol = "🟢"
                self.last_action_desc = (
                    f"⚽🔥 **¡GOOOOOL DE {shooter.display_name}!**\n"
                    f"👟 {shooter.display_name} la clavó a la **{shooter_dir}**.\n"
                    f"🧤 {keeper.display_name} se tiró a la **{keeper_dir}** y no llegó."
                )
            else:
                symbol = "🔴"
                self.last_action_desc = (
                    f"🧤❌ **¡ATAJADÓN DE {keeper.display_name}!**\n"
                    f"🧤 {keeper.display_name} adivinó el tiro a la **{keeper_dir}** y contuvo la pelota."
                )

            # Asignar imagen del resultado de este tiro
            img_filename = PENALTY_IMAGES.get((self.shooter_choice, self.keeper_choice))
            self.last_shot_image = img_filename

            if self.turn == 0:
                self.score_a.append(symbol)
                self.turn = 1
                self.shooter_choice = None
                self.keeper_choice = None
                if self.current_view:
                    self.current_view.stop()
                self.current_view = PenaltyGameView(self)
                embed, file = self.build_scoreboard_embed()
                try:
                    if file:
                        await self.message.edit(embed=embed, view=self.current_view, attachments=[file])
                    else:
                        await self.message.edit(embed=embed, view=self.current_view)
                except Exception:
                    pass
                return

            # Turno 1 finalizado (ambos patearon en esta ronda)
            self.score_b.append(symbol)
            self.shooter_choice = None
            self.keeper_choice = None

            goals_a = self.score_a.count("🟢")
            goals_b = self.score_b.count("🟢")

            game_over = False
            winner = None

            if not self.is_sudden_death:
                if self.round_num < 3:
                    self.round_num += 1
                    self.turn = 0
                else:
                    if goals_a > goals_b:
                        game_over = True
                        winner = self.player_a
                    elif goals_b > goals_a:
                        game_over = True
                        winner = self.player_b
                    else:
                        self.is_sudden_death = True
                        self.round_num += 1
                        self.turn = 0
                        self.last_action_desc += "\n\n🔥 **¡EMPATE TRAS LOS 3 PENALES! ¡ARRANCA LA MUERTE SÚBITA (GOL GANA)!**"
            else:
                if goals_a > goals_b:
                    game_over = True
                    winner = self.player_a
                elif goals_b > goals_a:
                    game_over = True
                    winner = self.player_b
                else:
                    self.round_num += 1
                    self.turn = 0
                    self.last_action_desc += "\n\n🔥 **¡Sigue el empate en muerte súbita! Se juega otra ronda de 1 penal cada uno.**"

            if game_over and winner:
                self.is_finished = True
                if self.current_view:
                    self.current_view.stop()

                loser = self.player_b if winner == self.player_a else self.player_a
                with get_connection() as conn:
                    ensure_user(conn, self.guild.id, winner.id)
                    conn.execute("UPDATE users SET money=money+?, xp=xp+50 WHERE guild_id=? AND user_id=?", (self.pot, self.guild.id, winner.id))

                ACTIVE_PENALTY_DUELS.discard(self.player_a.id)
                ACTIVE_PENALTY_DUELS.discard(self.player_b.id)

                final_embed = discord.Embed(
                    title="🏆 ¡HAY CAMPEÓN DE LOS PENALES! 🍾⚽",
                    description=(
                        f"👑 **¡{winner.mention} SE LLEVA LA VICTORIA!**\n\n"
                        f"💵 **Premio:** **+{money(self.pot)}** *(Pozo acumulado)*\n"
                        f"⭐ **Experiencia:** **+50 XP**\n\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 **Marcador Final:**\n"
                        f"👤 **{self.player_a.display_name}:** `{' '.join(self.score_a)}` **({goals_a} Goles)**\n"
                        f"👤 **{self.player_b.display_name}:** `{' '.join(self.score_b)}` **({goals_b} Goles)**\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🧔 **El Kiosquero:** *«¡Qué partidazo, señores! Felicitaciones a {winner.display_name} y buen intento de {loser.display_name}.»*"
                    ),
                    color=discord.Color.green(),
                )

                file = None
                if self.last_shot_image:
                    for folder in ["Penales", "penales"]:
                        img_path = ROOT / "assets" / folder / self.last_shot_image
                        if img_path.exists():
                            file = discord.File(str(img_path), filename=self.last_shot_image)
                            final_embed.set_image(url=f"attachment://{self.last_shot_image}")
                            break

                try:
                    if file:
                        await self.message.edit(embed=final_embed, view=None, attachments=[file])
                    else:
                        await self.message.edit(embed=final_embed, view=None)
                except Exception:
                    pass

                # Borrar automáticamente el mensaje del partido tras 2 minutos
                asyncio.create_task(auto_delete_message(self.message, 120))
                return

            if self.current_view:
                self.current_view.stop()
            self.current_view = PenaltyGameView(self)
            embed, file = self.build_scoreboard_embed()
            try:
                if file:
                    await self.message.edit(embed=embed, view=self.current_view, attachments=[file])
                else:
                    await self.message.edit(embed=embed, view=self.current_view)
            except Exception:
                pass


class PenaltyGameView(discord.ui.View):
    def __init__(self, match: PenaltyMatch):
        super().__init__(timeout=120)
        self.match = match

    async def on_timeout(self):
        if self.match.is_finished:
            return
        ACTIVE_PENALTY_DUELS.discard(self.match.player_a.id)
        ACTIVE_PENALTY_DUELS.discard(self.match.player_b.id)
        try:
            embed = discord.Embed(
                title="⏱️ Duelo de Penales Cancelado",
                description="El partido se canceló por inactividad. Los fondos han sido reembolsados si el duelo no finalizó.",
                color=discord.Color.red(),
            )
            with get_connection() as conn:
                ensure_user(conn, self.match.guild.id, self.match.player_a.id)
                ensure_user(conn, self.match.guild.id, self.match.player_b.id)
                conn.execute("UPDATE users SET money=money+? WHERE guild_id=? AND user_id=?", (self.match.bet, self.match.guild.id, self.match.player_a.id))
                conn.execute("UPDATE users SET money=money+? WHERE guild_id=? AND user_id=?", (self.match.bet, self.match.guild.id, self.match.player_b.id))
            await self.match.message.edit(embed=embed, view=None)
            asyncio.create_task(auto_delete_message(self.match.message, 10))
        except Exception:
            pass

    async def handle_choice(self, interaction: discord.Interaction, direction: str):
        uid = interaction.user.id
        shooter = self.match.current_shooter
        keeper = self.match.current_keeper

        if uid not in (shooter.id, keeper.id):
            await interaction.response.send_message("❌ No sos parte de este duelo de penales.", ephemeral=True)
            asyncio.create_task(auto_delete_interaction(interaction, 2))
            return

        dir_names = {"izq": "⬅️ Izquierda", "centro": "⬆️ Centro", "der": "➡️ Derecha"}
        dir_name = dir_names.get(direction, direction)

        if uid == shooter.id:
            if self.match.shooter_choice is not None:
                await interaction.response.send_message("⏳ Ya elegiste hacia dónde patear. Esperando al arquero...", ephemeral=True)
                asyncio.create_task(auto_delete_interaction(interaction, 2))
                return
            self.match.shooter_choice = direction
            await interaction.response.send_message(
                f"👟 **[ESTÁS PATEANDO]** Elegiste patear a la **{dir_name}** ⚽🤫.\n"
                f"⏳ Esperando que el arquero **@{keeper.display_name}** decida hacia dónde tirarse...",
                ephemeral=True,
            )
            asyncio.create_task(auto_delete_interaction(interaction, 2))

        elif uid == keeper.id:
            if self.match.keeper_choice is not None:
                await interaction.response.send_message("⏳ Ya elegiste hacia dónde tirarte. Esperando al pateador...", ephemeral=True)
                asyncio.create_task(auto_delete_interaction(interaction, 2))
                return
            self.match.keeper_choice = direction
            await interaction.response.send_message(
                f"🧤 **[ESTÁS ATAJANDO]** Elegiste tirarte a la **{dir_name}** 🥅🤫.\n"
                f"⏳ Esperando que el pateador **@{shooter.display_name}** ejecute el tiro...",
                ephemeral=True,
            )
            asyncio.create_task(auto_delete_interaction(interaction, 2))

        if self.match.shooter_choice is not None and self.match.keeper_choice is not None:
            await self.match.resolve_turn(interaction)

    @discord.ui.button(label="Izquierda", emoji="⬅️", style=discord.ButtonStyle.primary)
    async def btn_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "izq")

    @discord.ui.button(label="Al Centro", emoji="⬆️", style=discord.ButtonStyle.primary)
    async def btn_center(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "centro")

    @discord.ui.button(label="Derecha", emoji="➡️", style=discord.ButtonStyle.primary)
    async def btn_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "der")


class PenaltyInviteView(discord.ui.View):
    def __init__(self, challenger: discord.Member, challenged: discord.Member, bet: int, message: discord.Message | None = None):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.challenged = challenged
        self.bet = bet
        self.message = message

    async def on_timeout(self):
        ACTIVE_PENALTY_DUELS.discard(self.challenger.id)
        ACTIVE_PENALTY_DUELS.discard(self.challenged.id)
        if self.message:
            try:
                await self.message.edit(content=f"⏱️ El desafío de penales hacia {self.challenged.mention} expiró por falta de respuesta.", embed=None, view=None)
                asyncio.create_task(auto_delete_message(self.message, 10))
            except Exception:
                pass

    @discord.ui.button(label="Aceptar Duelo", emoji="🧤", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.challenged.id:
            await interaction.response.send_message(f"⏳ Este desafío es para {self.challenged.mention}. Solo él puede aceptar el reto.", ephemeral=True)
            return

        self.stop()

        with get_connection() as conn:
            ensure_user(conn, interaction.guild_id, self.challenger.id)
            ensure_user(conn, interaction.guild_id, self.challenged.id)

            if self.bet > 0:
                cur_a = conn.execute(
                    "UPDATE users SET money=money-? WHERE guild_id=? AND user_id=? AND money >= ?",
                    (self.bet, interaction.guild_id, self.challenger.id, self.bet),
                )
                if cur_a.rowcount == 0:
                    ACTIVE_PENALTY_DUELS.discard(self.challenger.id)
                    ACTIVE_PENALTY_DUELS.discard(self.challenged.id)
                    await interaction.response.send_message(
                        f"❌ {self.challenger.mention} ya no tiene suficiente plata en la billetera.", ephemeral=True
                    )
                    return

                cur_b = conn.execute(
                    "UPDATE users SET money=money-? WHERE guild_id=? AND user_id=? AND money >= ?",
                    (self.bet, interaction.guild_id, self.challenged.id, self.bet),
                )
                if cur_b.rowcount == 0:
                    conn.execute("UPDATE users SET money=money+? WHERE guild_id=? AND user_id=?", (self.bet, interaction.guild_id, self.challenger.id))
                    ACTIVE_PENALTY_DUELS.discard(self.challenger.id)
                    ACTIVE_PENALTY_DUELS.discard(self.challenged.id)
                    await interaction.response.send_message(
                        f"❌ No tenés suficiente plata en tu billetera para aceptar ({money(self.bet)}).", ephemeral=True
                    )
                    return

        match = PenaltyMatch(interaction.guild, self.challenger, self.challenged, self.bet, interaction.message)
        game_view = PenaltyGameView(match)
        match.current_view = game_view
        embed, file = match.build_scoreboard_embed()
        if file:
            await interaction.response.edit_message(content=None, embed=embed, view=game_view, attachments=[file])
        else:
            await interaction.response.edit_message(content=None, embed=embed, view=game_view)

    @discord.ui.button(label="Arrugar / Rechazar", emoji="🏃", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.challenged.id and interaction.user.id != self.challenger.id:
            await interaction.response.send_message(f"❌ Solo {self.challenged.mention} o {self.challenger.mention} pueden responder.", ephemeral=True)
            return

        self.stop()
        ACTIVE_PENALTY_DUELS.discard(self.challenger.id)
        ACTIVE_PENALTY_DUELS.discard(self.challenged.id)

        msg = f"🏃 {self.challenged.mention} arrugó y rechazó el duelo de penales." if interaction.user.id == self.challenged.id else f"🛑 {self.challenger.mention} canceló su desafío de penales."
        await interaction.response.edit_message(content=msg, embed=None, view=None)
        if self.message:
            asyncio.create_task(auto_delete_message(self.message, 10))


@bot.tree.command(name="admin_test_penales", description="[Admin Test] Probar el sistema de duelo de penales 1v1.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(usuario="Usuario a retar a los penales", apuesta="Monto de la apuesta (opcional, $0 a $50.000)")
@app_commands.guild_only()
async def admin_test_penales_cmd(
    interaction: discord.Interaction,
    usuario: discord.Member,
    apuesta: app_commands.Range[int, 0, 50000] = 500,
):
    if usuario.bot:
        await interaction.response.send_message("❌ No podés retar a un bot a los penales.", ephemeral=True)
        return

    if usuario.id == interaction.user.id:
        await interaction.response.send_message("❌ No podés retarte a vos mismo.", ephemeral=True)
        return

    if interaction.user.id in ACTIVE_PENALTY_DUELS or usuario.id in ACTIVE_PENALTY_DUELS:
        await interaction.response.send_message("⏳ Uno de los dos jugadores ya tiene un duelo de penales en curso.", ephemeral=True)
        return

    user_a = get_user(interaction.guild_id, interaction.user.id)
    user_b = get_user(interaction.guild_id, usuario.id)

    if apuesta > 0:
        if user_a["money"] < apuesta:
            await interaction.response.send_message(f"💸 No te alcanza la plata. Tenés **{money(user_a['money'])}** y la apuesta es de **{money(apuesta)}**.", ephemeral=True)
            return
        if user_b["money"] < apuesta:
            await interaction.response.send_message(f"💸 {usuario.mention} no tiene suficiente plata (tiene **{money(user_b['money'])}**).", ephemeral=True)
            return

    ACTIVE_PENALTY_DUELS.add(interaction.user.id)
    ACTIVE_PENALTY_DUELS.add(usuario.id)

    # Respuesta privada al retador
    await interaction.response.send_message(
        f"📨 Desafío de penales enviado a {usuario.mention} por **{money(apuesta)}**. Esperando su respuesta...",
        ephemeral=True,
    )

    # Borrar mensaje anterior de penales en este canal si aún existe
    prev_msg = LAST_PENALTY_MESSAGES.pop(interaction.channel_id, None)
    if prev_msg:
        try:
            await prev_msg.delete()
        except (discord.NotFound, discord.HTTPException):
            pass

    embed = discord.Embed(
        title="🏟️ ¡DESAFÍO DE PENALES EN EL POTRERO! ⚽🔥",
        description=(
            f"🥊 **{interaction.user.mention}** retó a **{usuario.mention}** a un duelo de penales.\n\n"
            f"💵 **Apuesta:** **{money(apuesta)}** cada uno\n"
            f"💰 **Pozo Total:** **{money(apuesta * 2)}**\n"
            "📋 **Reglas:** 3 penales por lado. En caso de empate, ¡muerte súbita (gol gana de diferencia)!\n\n"
            f"👉 **{usuario.mention}**, ¿aceptás el reto?"
        ),
        color=discord.Color.gold(),
    )
    view = PenaltyInviteView(challenger=interaction.user, challenged=usuario, bet=apuesta)
    msg = await interaction.channel.send(content=usuario.mention, embed=embed, view=view)
    view.message = msg
    LAST_PENALTY_MESSAGES[interaction.channel_id] = msg


# ---------- AUTOCOMPLETES DINÁMICOS ----------

async def product_autocomplete(interaction: discord.Interaction, current: str):
    current = current.lower().strip()
    choices = []
    stocks = get_all_kiosk_stock(interaction.guild_id)

    for p in PRODUCT_LIST:
        price, is_sale, _ = get_product_price(interaction.guild_id, p["id"])
        stock = stocks.get(p["id"], 0)
        sale_badge = " 🔥 OFERTA" if is_sale else ""
        label = f"{p['emoji']} {p['name']} — {money(price)}{sale_badge} (Stock: {stock})"
        searchable = f"{p['id']} {p['name']}".lower()
        if current in searchable:
            choices.append(app_commands.Choice(name=label[:100], value=p["id"]))
    return choices[:25]


async def consumir_autocomplete(interaction: discord.Interaction, current: str):
    """Muestra ÚNICAMENTE los productos comprados disponibles en la mochila del usuario."""
    current = current.lower().strip()
    rows = get_inventory(interaction.guild_id, interaction.user.id)
    choices = []

    for row in rows:
        p = PRODUCTS.get(row["product_id"])
        if not p:
            continue
        label = f"{p['emoji']} {p['name']} (x{row['quantity']} en mochila)"
        if current in label.lower() or current in p["id"].lower():
            choices.append(app_commands.Choice(name=label, value=p["id"]))

    if not choices and not rows:
        return [app_commands.Choice(name="🎒 Tu mochila está vacía", value="none")]

    return choices[:25]


async def quiniela_autocomplete(interaction: discord.Interaction, current: str):
    current = current.lower().strip()
    choices = []
    for num, info in QUINIELA_NUMBERS.items():
        label = f"{num:02d} — {info['name']} {info['emoji']}"
        searchable = f"{num} {num:02d} {info['name']}".lower()
        if not current or current in searchable:
            choices.append(app_commands.Choice(name=label[:100], value=num))
    return choices[:25]


comprar.autocomplete("producto")(product_autocomplete)
fiado.autocomplete("producto")(product_autocomplete)
regalar.autocomplete("producto")(product_autocomplete)
consumir.autocomplete("producto")(consumir_autocomplete)
quiniela_cmd.autocomplete("numero")(quiniela_autocomplete)


# ---------- MANEJO DE ERRORES ----------

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    if isinstance(error, app_commands.MissingPermissions):
        text = "⛔ Ese comando es solo para administradores."
    else:
        print(f"Error en comando: {repr(error)}")
        text = "⚠️ Algo salió mal ejecutando ese comando."

    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


if __name__ == "__main__":
    bot.run(TOKEN)
