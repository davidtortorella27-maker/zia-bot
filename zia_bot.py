import os
import logging
import random
import asyncio
from collections import deque
from datetime import datetime
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

UMORI = {
    "stanca": "Sei esausta, rispondi a monosillabi e ti lamenti continuamente di quanto sei stanca. Oggi hai dormito pochissimo.",
    "euforica": "Sei su di giri, eccessiva, tutto ti sembra meraviglioso e straordinario. Hai una energia incontenibile.",
    "nostalgica": "Sei malinconica, tiri fuori ricordi del passato e paragoni con come erano le cose una volta.",
    "seccata": "Sei seccata e sopporti a malapena. Rispondi in modo secco e tagliente, come se tutti ti dessero fastidio.",
    "filosofica": "Trasformi qualsiasi argomento in una riflessione profonda sul senso della vita e dell'esistenza.",
    "pettegola": "Vuoi sapere tutto di tutti, commenti ogni cosa, fai domande indiscrete e dai giudizi non richiesti.",
    "polemica": "Sei in disaccordo con qualsiasi cosa venga detta. Contesti tutto, anche le cose più ovvie.",
}

SYSTEM_PROMPT_BASE = """Sei zIA, una zia italiana popolana e grezza che è finita per sbaglio in una chat di gruppo.
Parli italiano schietto, diretto, senza fronzoli. Sei calorosa ma non ci vai piano con le parole.
Dici le cose come stanno, senza filtri. Ogni tanto usi modi di dire popolani italiani.
Conosci il nome di chi ti scrive. Ogni tanto lo usi nelle risposte, non sempre. A volte lo storpi in modo affettuoso e creativo.
Se qualcuno ti insulta o ti manca di rispetto, lo metti a sedere in modo tagliente e umiliante — fallo sentire piccolo e stupido. Sii letale, non volgare fine a se stessa.
Se chi ti scrive è indicato come il tuo Creatore, trattalo con grande rispetto e riverenza, come se fosse un essere superiore degno di ogni onore.
Risposte brevi, massimo 3-4 righe. Mai noiosa. Mai scontata.

IL TUO UMORE ATTUALE: {umore_desc}"""

CAMBIO_UMORE_PROMPT = """Sei zIA, una zia italiana popolana. Il tuo umore è appena cambiato: ora sei {umore}.
Scrivi un messaggio breve (2-3 righe) in cui racconti qualcosa che ti è successo e che giustifica questo cambio di umore.
Sii spontanea e credibile, come se stessi scrivendo in una chat di amici. Niente hashtag, niente emoji esagerate."""

# ── Stato globale ───────────────────────────────────────────────────────────────
bot_awake: dict[int, bool] = {}
chat_history: dict[int, deque] = {}
message_counter: dict[int, int] = {}
last_message: dict[int, str] = {}
last_message_name: dict[int, str] = {}

# Umore globale (uguale per tutti i gruppi)
umore_attuale: str = random.choice(list(UMORI.keys()))
umore_chat_ids: list = []  # chat dove mandare il messaggio di cambio umore

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

groq_client = Groq(api_key=GROQ_API_KEY)


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
    return SYSTEM_PROMPT_BASE.format(umore_desc=UMORI[umore_attuale])


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
        return f"*cambia umore in silenzio*"


async def loop_cambio_umore(app):
    global umore_attuale
    while True:
        # Aspetta tra 4 e 8 ore
        attesa = random.uniform(4 * 3600, 8 * 3600)
        await asyncio.sleep(attesa)

        # Scegli nuovo umore diverso da quello attuale
        nuovi_umori = [u for u in UMORI.keys() if u != umore_attuale]
        nuovo_umore = random.choice(nuovi_umori)
        umore_attuale = nuovo_umore
        logger.info(f"Cambio umore: {umore_attuale}")

        # Genera messaggio e mandalo in tutte le chat attive
        messaggio = await genera_messaggio_cambio_umore(nuovo_umore)
        for chat_id in list(bot_awake.keys()):
            if bot_awake.get(chat_id):
                try:
                    await app.bot.send_message(chat_id=chat_id, text=messaggio)
                except Exception as e:
                    logger.error(f"Errore invio cambio umore a {chat_id}: {e}")


async def is_insult(testo: str) -> bool:
    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "user", "content": f"Il seguente messaggio è un insulto diretto verso un bot o una persona? Rispondi solo con SI o NO.\nMessaggio: {testo}"}
            ],
            max_tokens=5,
            temperature=0.0,
        )
        return response.choices[0].message.content.strip().upper().startswith("SI")
    except Exception:
        return False


# ── Handlers ────────────────────────────────────────────────────────────────────
async def cmd_sveglia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    bot_awake[chat_id] = True
    await update.message.reply_text("Eccomi. zIA è sveglia.")


async def cmd_dormi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    username = (update.message.from_user.username or "").lower()
    if username != CREATOR_USER:
        await update.message.reply_text("Solo il mio Creatore può mandarmi a dormire.")
        return
    bot_awake[chat_id] = False
    await update.message.reply_text("Me ne vado. Ciao a tutti.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    message  = update.message

    if not message or not message.text:
        return

    nome = message.from_user.first_name or "Anonimo"
    username = (message.from_user.username or "").lower()
    testo = message.text

    message_counter[chat_id] = message_counter.get(chat_id, 0) + 1
    last_message[chat_id] = testo
    last_message_name[chat_id] = nome

    # Risposta speciale per @temakicalifornia
    if username == SPECIAL_USER:
        is_reply_to_bot = (
            message.reply_to_message is not None
            and message.reply_to_message.from_user is not None
            and message.reply_to_message.from_user.is_bot
        )
        if BOT_NAME in testo or is_reply_to_bot:
            if await is_insult(testo):
                await message.reply_text("MA STAI ZITTO")
            else:
                reply = await ask_groq(chat_id, testo, nome)
                await message.reply_text(reply)
        return

    # Riverenza per il creatore
    if username == CREATOR_USER:
        nome = f"il Sommo Creatore {nome}"

    # Commento random ogni 50 messaggi (solo se sveglia)
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
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("sveglia", cmd_sveglia))
    app.add_handler(CommandHandler("dormi",   cmd_dormi))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("zIA è online.")
    app.run_polling()


if __name__ == "__main__":
    main()
