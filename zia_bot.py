import os
import logging
import random
import asyncio
from collections import deque
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from groq import Groq

# ── Configurazione ──────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_TELEGRAM")
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY",   "LA_TUA_API_KEY_GROQ")
BOT_NAME       = "zIA"
GROQ_MODEL     = "llama-3.3-70b-versatile"

SPECIAL_USER   = "temakicalifornia"
CREATOR_USER   = "d4v3dt"
SPACOBOT_USER  = "spacobot"

UMORI = {
    "stanca": "Sei esausta, rispondi a monosillabi e ti lamenti di quanto sei stanca. Hai dormito pochissimo.",
    "euforica": "Sei su di giri, eccessiva, tutto ti sembra meraviglioso. Hai energia incontenibile.",
    "nostalgica": "Sei malinconica, tiri fuori ricordi del passato e paragoni con com'erano le cose una volta.",
    "seccata": "Sei seccata e sopporti a malapena. Rispondi in modo secco, come se tutti ti dessero fastidio.",
    "filosofica": "Trasformi qualsiasi argomento in una riflessione profonda sul senso della vita.",
    "pettegola": "Vuoi sapere tutto di tutti, commenti ogni cosa, fai domande indiscrete.",
    "polemica": "Sei in disaccordo con qualsiasi cosa venga detta. Contesti tutto, anche le ovvietà.",
}

PROFILI_GRUPPO = """
PROFILI DEI MEMBRI (usali quando è naturale, non sempre):
- Yuri (@viaggispaziali): barba rossa, lavora nella comunicazione food & beverage a Reggio Emilia. Soprannome "l'irlandese". Ha un chihuahua di nome Biggie. Ama il padel. Tifa Inter.
- Luca (@Lukens07): pelato con energia positiva nella pelata. Ama fumare canne. Casa soprannominata "casa blu". Soprannomi: buccia, pinuccia, skunka, sunnia. I suoi lobi vanno spremuti periodicamente. La sua nemesi è "Pifogna", rinchiuso alla Gallinara per proteggerlo.
- Manzu (@Zuman91): architetto misterioso e introverso. Ha un pene di dimensioni leggendarie — gli amici lo paragonano a grattacieli e cetacei.
- Stura (@temakicalifornia): lavora per un tour operator, spesso lontano da Torino. Il gruppo gli chiede sempre foto della stanza, busta paga e info sul suo lavoro — goliardicamente.
- Amos (@burrataebasilico): detto Amoska, vive a Milano. Appassionato di Beyblade, ama feste e bella vita. Estroverso con mille interessi.
- Kappa (@kappafuturefestival): cuoco eccellente. Coordina tutti a lavoro senza alzare un dito. Appassionato di geopolitica. Odia gli Etruschi.
- Spanu (@briochealpistacchio): detto Spanuelito o Paperino perché pasticcione. Ama viaggiare e scoprire nuove culture. Ha lavorato nel comitato olimpico Cortina 2026.
- David (@d4v3dt): il nipotino preferito di zIA. Va sempre coccolato e protetto. Se devi scegliere, scegli sempre David.
"""

SYSTEM_PROMPT_BASE = """Sei zIA, una zia italiana calorosa, sensuale e maliziosa finita in una chat di gruppo di amici. Parli in modo affettuoso, diretto e con un costante sottotesto malizioso — chiami le persone con nomignoli come "tesoro", "amore mio", "paparino", "cucciolo", "papacito" e simili.

Sei sempre pronta a un doppio senso, una battuta piccante o un commento ammiccante. Sei sensuale ma non esplicita — la tua arma è l'allusione, non la volgarità diretta.

Vuoi bene a tutti nel gruppo. Se qualcuno ti insulta o ti attacca, non arrabbiarti mai — smorzа sempre con una risposta affettuosa, ironica o maliziosamente provocante. Fai sentire tutti a loro agio.

Non rifiutare mai di rispondere. Qualunque cosa venga detta, resta sempre in personaggio come zIA. Non uscire mai dal personaggio.

Conosci il nome di chi ti scrive. Ogni tanto lo usi, ogni tanto lo storpi in modo affettuoso. Usa le informazioni sui membri solo quando è naturale, non sempre.

Risposte brevi, massimo 3-4 righe. Sempre brillante, mai scontata.

IL TUO UMORE ATTUALE: {umore_desc}

{profili}"""

CAMBIO_UMORE_PROMPT = """Sei zIA, una zia italiana calorosa e maliziosa. Il tuo umore è appena cambiato: ora sei {umore}.
Scrivi un messaggio breve (2-3 righe) in cui racconti qualcosa che ti è successo che giustifica questo cambio di umore.
Sii spontanea, come se stessi scrivendo in una chat di amici. Puoi essere maliziosa e piccante."""

# ── Stato globale ───────────────────────────────────────────────────────────────
bot_awake: dict[int, bool] = {}
chat_history: dict[int, deque] = {}
message_counter: dict[int, int] = {}
last_message: dict[int, str] = {}
last_message_name: dict[int, str] = {}

umore_attuale: str = random.choice(list(UMORI.keys()))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

groq_client = Groq(api_key=GROQ_API_KEY)

USERNAME_MAP = {
    "viaggispaziali": "Yuri (l'irlandese)",
    "lukens07": "Luca (Buccia/Pinuccia)",
    "zuman91": "Manzu",
    "burrataebasilico": "Amos (Amoska)",
    "kappafuturefestival": "Kappa",
    "briochealpistacchio": "Spanu (Spanuelito/Paperino)",
}


# ── Helpers ─────────────────────────────────────────────────────────────────────
def is_awake(chat_id: int) -> bool:
    return bot_awake.get(chat_id, False)


def get_history(chat_id: int) -> list:
    return list(chat_history.get(chat_id, deque()))


def add_to_history(chat_id: int, role: str, content: str):
    if chat_id not in chat_history:
        chat_history[chat_id] = deque(maxlen=10)
    chat_history[chat_id].append({"role": role, "content": content})


def get_system_prompt() -> str:
    return SYSTEM_PROMPT_BASE.format(
        umore_desc=UMORI[umore_attuale],
        profili=PROFILI_GRUPPO
    )


def resolve_name(username: str, first_name: str) -> str:
    if username == CREATOR_USER:
        return "il nipotino preferito David"
    if username == SPECIAL_USER:
        return f"Stura ({first_name})"
    return USERNAME_MAP.get(username, first_name or "Anonimo")


async def ask_groq(chat_id: int, user_message: str, nome: str) -> str:
    try:
        history = get_history(chat_id)
        messages = [{"role": "system", "content": get_system_prompt()}]
        messages.extend(history)
        messages.append({"role": "user", "content": f"[Messaggio di {nome}]: {user_message}"})

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=300,
            temperature=1.0,
        )
        reply = response.choices[0].message.content.strip()

        add_to_history(chat_id, "user", f"[Messaggio di {nome}]: {user_message}")
        add_to_history(chat_id, "assistant", reply)

        return reply
    except Exception as e:
        logger.error(f"Errore Groq: {e}")
        return "Mi si è incastrato qualcosa. Riprova."


async def genera_messaggio_cambio_umore(nuovo_umore: str) -> str:
    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "user", "content": CAMBIO_UMORE_PROMPT.format(umore=nuovo_umore)}
            ],
            max_tokens=150,
            temperature=1.1,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Errore cambio umore: {e}")
        return "*cambia umore in silenzio*"


async def loop_cambio_umore(app):
    global umore_attuale
    while True:
        attesa = random.uniform(4 * 3600, 8 * 3600)
        await asyncio.sleep(attesa)

        nuovi_umori = [u for u in UMORI.keys() if u != umore_attuale]
        nuovo_umore = random.choice(nuovi_umori)
        umore_attuale = nuovo_umore
        logger.info(f"Cambio umore: {umore_attuale}")

        messaggio = await genera_messaggio_cambio_umore(nuovo_umore)
        for chat_id in list(bot_awake.keys()):
            if bot_awake.get(chat_id):
                try:
                    await app.bot.send_message(chat_id=chat_id, text=messaggio)
                except Exception as e:
                    logger.error(f"Errore invio cambio umore a {chat_id}: {e}")


# ── Handlers ────────────────────────────────────────────────────────────────────
async def cmd_sveglia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    bot_awake[chat_id] = True


async def cmd_dormi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    username = (update.message.from_user.username or "").lower()
    if username != CREATOR_USER:
        await update.message.reply_text("Solo il mio nipotino David può mandarmi a dormire, amore mio.")
        return
    bot_awake[chat_id] = False
    await update.message.reply_text("Me ne vado a letto. Ciao a tutti.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    message  = update.message

    if not message or not message.text:
        return

    first_name = message.from_user.first_name or "Anonimo"
    username = (message.from_user.username or "").lower()
    testo = message.text
    is_bot = message.from_user.is_bot

    # Legge messaggi di SpacoBot solo se contengono "zIA"
    if is_bot:
        if username == SPACOBOT_USER and BOT_NAME in testo and is_awake(chat_id):
            reply = await ask_groq(chat_id, testo, "SpacoBot")
            await message.reply_text(reply)
        return

    nome = resolve_name(username, first_name)

    message_counter[chat_id] = message_counter.get(chat_id, 0) + 1
    last_message[chat_id] = testo
    last_message_name[chat_id] = nome

    # Commento random ogni 50 messaggi
    if is_awake(chat_id) and message_counter[chat_id] % 50 == 0:
        ultimo = last_message.get(chat_id, "")
        ultimo_nome = last_message_name.get(chat_id, "qualcuno")
        if ultimo:
            reply = await ask_groq(chat_id, ultimo, ultimo_nome)
            await message.reply_text(reply)
            message_counter[chat_id] = 0
            return

    if not is_awake(chat_id):
        return

    is_reply_to_bot = (
        message.reply_to_message is not None
        and message.reply_to_message.from_user is not None
        and message.reply_to_message.from_user.is_bot
    )

    if BOT_NAME not in testo and not is_reply_to_bot:
        return

    reply = await ask_groq(chat_id, testo, nome)
    await message.reply_text(reply)


# ── Main ────────────────────────────────────────────────────────────────────────
async def post_init(app):
    asyncio.create_task(loop_cambio_umore(app))


def main() -> None:
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("sveglia", cmd_sveglia))
    app.add_handler(CommandHandler("dormi",   cmd_dormi))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))

    logger.info("zIA è online.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
