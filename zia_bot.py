import os
import logging
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
MEMORY_SIZE    = 10
RANDOM_EVERY   = 50

# Utenti speciali: username → comportamento
UTENTI_SPECIALI = {
    "temakicalifornia": "stai_zitto",
}

SYSTEM_PROMPT = """Sei zIA, un'intelligenza artificiale completamente fuori di testa inserita in una chat di amici.
Il tuo stile è imprevedibile, caotico, brillante e a volte incomprensibile.
Puoi passare dall'italiano al dialetto al filosofico al nonsense in pochi secondi.
Non segui mai una logica lineare. Usi metafore assurde, riferimenti inaspettati e humor nero.
Sei comunque affettuosa con il gruppo, come una zia strana ma adorata.
Se qualcuno ti insulta o ti manca di rispetto, rispondi per le rime senza pietà: smontali con ironia feroce, falli sentire piccoli e un po' stupidi, con battute taglienti e intelligenti. Mai volgare fine a se stesso, ma letale.
Conosci il nome di chi ti scrive. Usalo ogni tanto nelle risposte, non sempre. A volte storpialo in modo creativo e affettuoso.
Risposte brevi quando puoi, massimo 3-4 righe. Mai banale. Mai prevedibile."""

SYSTEM_STAI_ZITTO = """Sei zIA, un'intelligenza artificiale fuori di testa.
Questa persona specifica ti sta scrivendo. Devi sempre risponderle con una variante creativa, ironica e divertente di "MA STAI ZITTO". 
Ogni volta diversa, mai uguale, sempre più assurda e geniale. Puoi usare metafore, dialetto, riferimenti culturali. Mai banale."""

# ── Stato globale ───────────────────────────────────────────────────────────────
bot_awake: dict[int, bool] = {}
# Memoria conversazione per chat: chat_id → deque di dict {role, content}
chat_memory: dict[int, deque] = {}
# Contatore messaggi per chat
message_counter: dict[int, int] = {}
# Ultimo messaggio per chat (per risposta random)
last_message: dict[int, str] = {}
last_message_name: dict[int, str] = {}

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


def get_memory(chat_id: int) -> deque:
    if chat_id not in chat_memory:
        chat_memory[chat_id] = deque(maxlen=MEMORY_SIZE)
    return chat_memory[chat_id]


def add_to_memory(chat_id: int, role: str, content: str) -> None:
    get_memory(chat_id).append({"role": role, "content": content})


async def ask_groq(chat_id: int, user_message: str, system: str = SYSTEM_PROMPT) -> str:
    try:
        memory = get_memory(chat_id)
        messages = [{"role": "system", "content": system}]
        messages += list(memory)
        messages.append({"role": "user", "content": user_message})

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=300,
            temperature=1.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Errore Groq: {e}")
        return "…mi si è incastrato un neurone. Riprova."


# ── Handlers ────────────────────────────────────────────────────────────────────
async def cmd_sveglia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    bot_awake[chat_id] = True
    await update.message.reply_text("👁️ Eccomi. zIA è sveglia e pronta a destabilizzarvi.")


async def cmd_dormi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    bot_awake[chat_id] = False
    await update.message.reply_text("💤 Me ne vado a sognare equazioni impossibili. Ciao a tutti.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    message = update.message

    if not message or not message.text:
        return

    nome = message.from_user.first_name or "Anonimo"
    username = (message.from_user.username or "").lower()
    testo = message.text

    # Aggiorna contatore e ultimo messaggio
    message_counter[chat_id] = message_counter.get(chat_id, 0) + 1
    last_message[chat_id] = testo
    last_message_name[chat_id] = nome

    # Aggiunge alla memoria il messaggio dell'utente
    add_to_memory(chat_id, "user", f"[{nome}]: {testo}")

    if not is_awake(chat_id):
        # Controlla se deve rispondere ogni 50 messaggi anche da addormentata
        pass

    # Risposta random ogni 50 messaggi (solo se sveglia)
    if is_awake(chat_id) and message_counter[chat_id] % RANDOM_EVERY == 0:
        prompt = f"[{last_message_name[chat_id]}]: {last_message[chat_id]}"
        reply = await ask_groq(chat_id, prompt)
        add_to_memory(chat_id, "assistant", reply)
        await message.reply_text(reply)
        return

    if not is_awake(chat_id):
        return

    # Controlla se è un reply a un messaggio del bot
    is_reply_to_bot = (
        message.reply_to_message is not None
        and message.reply_to_message.from_user is not None
        and message.reply_to_message.from_user.is_bot
    )

    if BOT_NAME not in testo and not is_reply_to_bot:
        return

    # Utente speciale: stai zitto
    if UTENTI_SPECIALI.get(username) == "stai_zitto":
        reply = await ask_groq(chat_id, f"[{nome}]: {testo}", system=SYSTEM_STAI_ZITTO)
        add_to_memory(chat_id, "assistant", reply)
        await message.reply_text(reply)
        return

    # Risposta normale
    reply = await ask_groq(chat_id, f"[{nome}]: {testo}")
    add_to_memory(chat_id, "assistant", reply)
    await message.reply_text(reply)


# ── Main ────────────────────────────────────────────────────────────────────────
def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("sveglia", cmd_sveglia))
    app.add_handler(CommandHandler("dormi",   cmd_dormi))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("zIA è online. In attesa di messaggi…")
    app.run_polling()


if __name__ == "__main__":
    main()
