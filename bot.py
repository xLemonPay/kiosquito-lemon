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
DATA_DIR = ROOT / "data"
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

# ---------- DEFINICIÓN DE LAS 16 CHANGUITAS ----------
CHANGUITAS_LIST = [
    # --- FÁCILES ($150 - $300) ---
    {
        "id": "barrer_piso",
        "name": "Barrer el piso",
        "emoji": "🧹",
        "tier": "facil",
        "desc": "Barrer la tierra y papelitos del salón de ventas.",
        "steps": [
            {
                "text": "Hay mugre por todo el piso. ¿Qué herramienta agarrás primero?",
                "correct_btn": ("Agarrar la escoba", "🧹"),
                "wrong_btn": ("Sentarse en el cajón de birra", "🛋️"),
                "fail_text": "¡Te sentaste a rascarte y el kiosquero te descubrió durmiendo una siesta!",
            },
            {
                "text": "¡Bien! Juntá toda la mugre acumulada en un montoncito.",
                "correct_btn": ("Juntar con la pala", "🪣"),
                "wrong_btn": ("Esconder abajo de la heladera", "👟"),
                "fail_text": "¡Pateaste la mugre abajo de la heladera exhibidora y se llenó de cucarachas!",
            },
            {
                "text": "Último paso: tirá la basura juntada.",
                "correct_btn": ("Tirar al tacho de basura", "🗑️"),
                "wrong_btn": ("Dejar que se vuele sola", "💨"),
                "fail_text": "¡Dejaste que el ventilador vuele la basura por todo el kiosco!",
            },
        ],
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
        "id": "limpiar_vidrios",
        "name": "Limpiar vidrios",
        "emoji": "🪟",
        "tier": "normal",
        "desc": "Dejar relucientes los ventanales y la vidriera frontal.",
        "steps": [
            {
                "text": "La vidriera principal tiene marcas de dedos y polvo de la calle.",
                "correct_btn": ("Rociar líquido limpiavidrios azul", "🧴"),
                "wrong_btn": ("Tirarle detergente puro sin diluir", "🧼"),
                "fail_text": "¡Hiciste un mar de espuma inmanejable que tapó toda la vidriera!",
            },
            {
                "text": "El producto está actuando en el vidrio.",
                "correct_btn": ("Frotar con paño de microfibra", "🧽"),
                "wrong_btn": ("Pasarle una lija para madera", "📄"),
                "fail_text": "¡Rayaste todo el ventanal frontal con la lija! ¡Sale una fortuna cambiarlo!",
            },
            {
                "text": "Hora de sacar el excedente sin dejar marcas.",
                "correct_btn": ("Pasar la espátula secavidrios", "✨"),
                "wrong_btn": ("Dejar que se seque al sol directo", "☀️"),
                "fail_text": "¡Se secó al rayo del sol y quedó como una nube de grasa opaca!",
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
        "id": "ordenar_productos",
        "name": "Ordenar productos",
        "emoji": "🍫",
        "tier": "normal",
        "desc": "Frentear alfajores, gomitas y caramelos.",
        "steps": [
            {
                "text": "La caramelera está toda desordenada.",
                "correct_btn": ("Frentear alfajores y chocolates", "🍫"),
                "wrong_btn": ("Comerte un Guaymallén a escondidas", "🤤"),
                "fail_text": "¡Te comiste un Guaymallén triple y te vieron por las cámaras de seguridad!",
            },
            {
                "text": "Los snacks quedaron aplastados al fondo.",
                "correct_btn": ("Acomodar papas y chizitos inflados", "🍟"),
                "wrong_btn": ("Apretar las bolsas para que ocupen menos", "🔨"),
                "fail_text": "¡Aplastaste las bolsas de papas fritas y las convertiste en puré!",
            },
            {
                "text": "Faltan los tubos de caramelos.",
                "correct_btn": ("Rellenar frascos de Flynn Paff", "🍬"),
                "wrong_btn": ("Llenarte los bolsillos de caramelos", "🍭"),
                "fail_text": "¡Se te cayeron 15 chupetines del bolsillo delante del encargado!",
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
    # --- PESADAS ($600 - $1.000) ---
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


def is_open(now: datetime | None = None, guild_id: int | None = None) -> bool:
    if guild_id is not None:
        manual_open, _ = manual_open_status(guild_id)
        if manual_open:
            return True

    now = now or datetime.now(TZ)
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


# ---------- BASE DE DATOS Y PERSISTENCIA ----------

def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
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
            stock_map[pid] = get_kiosk_stock(guild_id, pid)
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
            current = get_kiosk_stock(guild_id, pid)
            if current < max_cap:
                add_qty = random.randint(amount_min, amount_max)
                new_stock = min(max_cap, current + add_qty)
                conn.execute(
                    "UPDATE kiosk_stock SET stock=? WHERE guild_id=? AND product_id=?",
                    (new_stock, guild_id, pid),
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


def delete_shift_consumption_records(guild_id: int, shift_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM consumption_messages WHERE guild_id=? AND shift_id=?",
            (guild_id, shift_id),
        )


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
        (guild_id, user_id, money, xp, debt, last_daily, last_work, created_at)
        VALUES (?, ?, ?, 0, 0, 0, 0, ?)
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
    stock = get_kiosk_stock(guild_id, product_id)
    if stock < quantity:
        with get_connection() as conn:
            ensure_user(conn, guild_id, user_id)
            user = conn.execute(
                "SELECT money FROM users WHERE guild_id=? AND user_id=?",
                (guild_id, user_id),
            ).fetchone()
            return False, int(user["money"]), 0, "out_of_stock", stock

    unit_price, _, _ = get_product_price(guild_id, product_id)
    total = unit_price * quantity

    with get_connection() as conn:
        ensure_user(conn, guild_id, user_id)
        user = conn.execute(
            "SELECT * FROM users WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ).fetchone()

        if user["money"] < total:
            return False, int(user["money"]), total, "no_money", stock

        conn.execute(
            "UPDATE users SET money=money-? WHERE guild_id=? AND user_id=?",
            (total, guild_id, user_id),
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

    record_sale(guild_id, user_id, product_id, quantity, total, is_fiado=False)
    return True, int(user["money"]) - total, total, "ok", stock - quantity


def fiado_purchase(guild_id: int, user_id: int, product_id: str, quantity: int):
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
    total = unit_price * quantity

    with get_connection() as conn:
        ensure_user(conn, guild_id, user_id)
        user = conn.execute(
            "SELECT * FROM users WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ).fetchone()

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

    embed = discord.Embed(
        title=f"👤 Perfil de {member.display_name}",
        color=discord.Color.gold(),
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
    embed = discord.Embed(
        title="🏪 El Kiosquito de Lemon — ¡ABIERTO! 🟢",
        description=(
            "¡Buenas, maestro! El mostrador está atendiendo.\n\n"
            "🛒 **Comprá** golosinas con stock limitado.\n"
            "🧹 **Hacé changuitas** para ganar plata y reponer el stock.\n"
            "🎒 **Revisá tu mochila** y consumí para sumar XP.\n"
            "🤝 **Fiado** disponible a partir de 2.000 XP.\n\n"
            f"### 🕗 Horarios de atención (Argentina)\n{opening_hours_text()}"
        ),
        color=discord.Color.green(),
    )

    if guild_id:
        offers = get_shift_offers(guild_id)
        if offers:
            offer_lines = []
            for pid, disc_price in offers.items():
                p = PRODUCTS.get(pid)
                if p:
                    stock = get_kiosk_stock(guild_id, pid)
                    offer_lines.append(f"🔥 {p['emoji']} **{p['name']}**: **{money(disc_price)}** *(Antes {money(p['price'])})* • Quedan: `{stock}`")
            embed.add_field(
                name="🏷️ ¡OFERTAS ESPECIALES DE LA JORNADA!",
                value="\n".join(offer_lines),
                inline=False,
            )

        manual_open, rem = manual_open_status(guild_id)
        if manual_open:
            if rem is None:
                extra = "🔓 *Apertura manual activa.*"
            else:
                extra = f"🔓 *Apertura manual activa por {seconds_text(rem)}.*"
            embed.add_field(name="Estado Extra", value=extra, inline=False)

    embed.set_footer(text=f"🟢 Abierto • Hora Argentina {now.strftime('%H:%M')}")
    return embed


def kiosk_closed_embed(guild_id: int) -> discord.Embed:
    now = datetime.now(TZ)
    shift_id = get_current_shift_id(guild_id)
    sales_rows, total_money = get_shift_sales_summary(guild_id, shift_id)
    debtors = get_guild_debtors(guild_id)

    embed = discord.Embed(
        title="🏪 El Kiosquito de Lemon — CERRADO 🔒",
        description=(
            f"El mostrador está cerrado. Volvemos a abrir a las **{next_opening(now)}**.\n\n"
            f"### 🕗 Horarios habituales (Hora Arg)\n{opening_hours_text()}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📊 **RESUMEN DE LA JORNADA**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=discord.Color.red(),
    )

    # 1. Productos vendidos
    if sales_rows:
        sales_lines = []
        for r in sales_rows:
            prod = PRODUCTS.get(r["product_id"])
            pname = prod["name"] if prod else r["product_id"]
            pemoji = prod["emoji"] if prod else "📦"
            sales_lines.append(f"{pemoji} **{pname}**: ×{r['total_qty']} ({money(r['total_money'])})")
        sales_text = "\n".join(sales_lines)
    else:
        sales_text = "No se registraron ventas en esta jornada."

    embed.add_field(name="📦 Productos vendidos", value=sales_text, inline=False)
    embed.add_field(name="💰 Facturación total", value=f"**{money(total_money)}**", inline=True)

    # 2. Deudores del kiosquito
    if debtors:
        debt_lines = []
        for d in debtors[:15]:
            debt_lines.append(f"• <@{d['user_id']}>: **{money(d['debt'])}**")
        if len(debtors) > 15:
            debt_lines.append(f"*...y {len(debtors) - 15} más.*")
        debt_text = "\n".join(debt_lines)
    else:
        debt_text = "✨ ¡Nadie debe nada! Milagro barrial."

    embed.add_field(name="🧾 Deudores del Kiosquito (Libretita)", value=debt_text, inline=False)
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


class ChanguitaSelect(discord.ui.Select):
    def __init__(self, sample_jobs: list[dict]):
        options = []
        for job in sample_jobs:
            tier_cfg = CONFIG["changuita_tiers"][job["tier"]]
            options.append(
                discord.SelectOption(
                    label=job["name"],
                    value=job["id"],
                    emoji=job["emoji"],
                    description=f"{tier_cfg['name']} • {money(tier_cfg['money_min'])}-{money(tier_cfg['money_max'])}",
                )
            )
        super().__init__(
            placeholder="Elegí una changuita para laburar...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        job = CHANGUITAS_MAP[self.values[0]]
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

            stock_text = f"Stock: {stock}" if stock > 0 else "AGOTADO 🚫"

            options.append(
                discord.SelectOption(
                    label=f"{p['name']} — {price_text}",
                    value=p["id"],
                    emoji=p["emoji"],
                    description=f"{stock_text} • +{p['xp']} XP al consumir",
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

        stock_desc = f"📦 **Stock disponible:** `{stock}` unidades" if stock > 0 else "🚫 **Estado:** ¡AGOTADO!"

        embed = discord.Embed(
            title=f"{product['emoji']} {product['name']}",
            description=f"{product['description']}\n\n{price_desc}\n{stock_desc}\n⭐ **Al consumir:** `+{product['xp']} XP`",
            color=discord.Color.gold(),
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
            if reason == "out_of_stock":
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

async def update_kiosk_fixed_message(guild: discord.Guild) -> None:
    channel_id_raw = get_setting(guild.id, "kiosk_channel_id", "0")
    try:
        channel_id = int(channel_id_raw)
    except ValueError:
        return

    if not channel_id:
        return

    channel = guild.get_channel(channel_id)
    if not channel:
        try:
            channel = await guild.fetch_channel(channel_id)
        except Exception:
            return

    open_now = is_open(guild_id=guild.id)
    embed = kiosk_open_embed(guild.id) if open_now else kiosk_closed_embed(guild.id)
    view = PersistentKioskView()

    message_id_raw = get_setting(guild.id, "kiosk_message_id", "0")
    try:
        message_id = int(message_id_raw)
    except ValueError:
        message_id = 0

    message = None
    if message_id:
        try:
            message = await channel.fetch_message(message_id)
        except (discord.NotFound, discord.HTTPException):
            message = None

    if message:
        try:
            await message.edit(embed=embed, view=view)
            return
        except discord.HTTPException:
            pass

    try:
        new_msg = await channel.send(embed=embed, view=view)
        set_setting(guild.id, "kiosk_message_id", str(new_msg.id))
    except Exception as e:
        print(f"Error enviando mensaje fijo en guild {guild.id}: {e}")


async def on_shift_opened(guild: discord.Guild):
    """Inicia una nueva jornada al abrirse el kiosquito, setea stock inicial y tira ofertas."""
    new_shift_id = int(time.time())
    set_setting(guild.id, "current_shift_id", str(new_shift_id))
    set_setting(guild.id, "last_open_state", "1")

    # Inicializar stock corto y sortear posibles ofertas
    init_shift_stock(guild.id)
    roll_shift_offers(guild.id)

    await update_kiosk_fixed_message(guild)


async def on_shift_closed(guild: discord.Guild):
    """Cierra la jornada, limpia mensajes de consumo de la jornada y actualiza el mensaje fijo con el resumen."""
    current_shift_id = get_current_shift_id(guild.id)

    # 1. Limpiar todos los mensajes públicos de consumo de esta jornada
    records = get_shift_consumption_messages(guild.id, current_shift_id)
    for row in records:
        try:
            ch = guild.get_channel(row["channel_id"])
            if ch:
                msg = await ch.fetch_message(row["message_id"])
                if msg:
                    await msg.delete()
        except Exception:
            pass

    delete_shift_consumption_records(guild.id, current_shift_id)

    # 2. Resetear ofertas activas
    set_setting(guild.id, "shift_offers", "{}")

    # 3. Marcar estado cerrado
    set_setting(guild.id, "last_open_state", "0")

    # 4. Actualizar mensaje fijo a cerrado con el resumen de jornada
    await update_kiosk_fixed_message(guild)


# ---------- CLASE PRINCIPAL DEL BOT ----------

class KiosquitoBot(commands.Bot):
    async def setup_hook(self):
        init_db()
        self.add_view(PersistentKioskView())

        if TEST_GUILD_ID:
            guild = discord.Object(id=TEST_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(
                f"✅ {len(synced)} comandos sincronizados al servidor de prueba "
                f"{TEST_GUILD_ID}."
            )
        else:
            synced = await self.tree.sync()
            print(f"✅ {len(synced)} comandos globales sincronizados.")


intents = discord.Intents.default()
bot = KiosquitoBot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print("=" * 52)
    print(f"🏪 Bot conectado como: {bot.user} • v{BOT_VERSION}")
    print(f"🕗 Hora Argentina: {datetime.now(TZ).strftime('%H:%M')}")
    print(f"Estado por horario: {'ABIERTO' if is_open() else 'CERRADO'}")
    print("=" * 52)

    for guild in bot.guilds:
        await update_kiosk_fixed_message(guild)

    if not presence_loop.is_running():
        presence_loop.start()


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
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
    """Bucle sincronizado con la hora argentina para verificar aperturas, cierres, presencia y reposición."""
    now = datetime.now(TZ)

    for guild in bot.guilds:
        currently_open = is_open(now, guild.id)
        last_state = get_setting(guild.id, "last_open_state", "-1")

        if last_state == "-1":
            set_setting(guild.id, "last_open_state", "1" if currently_open else "0")
            await update_kiosk_fixed_message(guild)
        elif currently_open and last_state == "0":
            await on_shift_opened(guild)
        elif not currently_open and last_state == "1":
            await on_shift_closed(guild)
        elif currently_open and now.minute % 30 == 0:
            # Reposición periódica de stock cada 30 min mientras está abierto
            restock_kiosk(guild.id)
            await update_kiosk_fixed_message(guild)

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
@app_commands.describe(canal="Canal donde estará el mensaje fijo del kiosquito.")
@app_commands.guild_only()
async def setup(
    interaction: discord.Interaction,
    canal: discord.TextChannel | None = None,
):
    target_channel = canal or interaction.channel
    set_setting(interaction.guild_id, "kiosk_channel_id", str(target_channel.id))
    set_setting(interaction.guild_id, "kiosk_message_id", "0")

    await update_kiosk_fixed_message(interaction.guild)

    await interaction.response.send_message(
        f"✅ **Kiosquito configurado exitosamente** en {target_channel.mention}.\n"
        f"Se ha publicado y fijado el panel interactivo del Kiosquito.",
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
        if reason == "out_of_stock":
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
        member = interaction.guild.get_member(row["user_id"])
        name = member.display_name if member else f"Usuario {row['user_id']}"
        prefix = medals[index] if index < 3 else f"`#{index + 1}`"
        lines.append(f"{prefix} **{name}** — {row['xp']} XP")

    embed = discord.Embed(
        title="🏆 Clientes de confianza",
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
@app_commands.describe(minutos="Minutos para mantener abierto. Dejá vacío para abrir indefinidamente.")
@app_commands.guild_only()
async def admin_abrir(
    interaction: discord.Interaction,
    minutos: app_commands.Range[int, 1, 720] | None = None,
):
    if minutos is None:
        set_setting(interaction.guild_id, "manual_open_until", "-1")
        detalle = "hasta que un admin use `/admin_cerrar`"
    else:
        until = int(time.time()) + (minutos * 60)
        set_setting(interaction.guild_id, "manual_open_until", str(until))
        detalle = f"durante **{minutos} minutos**"

    await on_shift_opened(interaction.guild)

    await interaction.response.send_message(
        f"🔓 **Kiosquito abierto manualmente** {detalle}.\n"
        f"Ya se encuentran habilitadas las compras y changuitas.",
        ephemeral=True,
    )
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="admin_cerrar", description="[Admin] Cancelar apertura manual y cerrar la jornada.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.guild_only()
async def admin_cerrar(interaction: discord.Interaction):
    manual_open, _ = manual_open_status(interaction.guild_id)
    set_setting(interaction.guild_id, "manual_open_until", "0")

    if is_open(guild_id=interaction.guild_id):
        estado = "✅ Apertura manual cancelada. El kiosquito sigue abierto por horario regular."
        await update_kiosk_fixed_message(interaction.guild)
    else:
        estado = f"🔒 Kiosquito cerrado. Se ha generado el resumen de la jornada. Próxima apertura: **{next_opening()}**."
        await on_shift_closed(interaction.guild)

    if not manual_open:
        estado = "ℹ️ No había apertura manual activa.\n" + estado

    await interaction.response.send_message(estado, ephemeral=True)
    asyncio.create_task(auto_delete_interaction(interaction, 180))


@bot.tree.command(name="admin_reponer", description="[Admin] Forzar reposición de stock en el kiosquito.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(cantidad="Cantidad a sumar a cada producto")
@app_commands.guild_only()
async def admin_reponer(interaction: discord.Interaction, cantidad: app_commands.Range[int, 1, 20] = 3):
    restock_kiosk(interaction.guild_id, cantidad, cantidad)
    await update_kiosk_fixed_message(interaction.guild)
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


comprar.autocomplete("producto")(product_autocomplete)
fiado.autocomplete("producto")(product_autocomplete)
regalar.autocomplete("producto")(product_autocomplete)
consumir.autocomplete("producto")(consumir_autocomplete)


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
