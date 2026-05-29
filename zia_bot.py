import os
import logging
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
GROQ_MODEL     = "llama-3.3-70b-versatile"   # modello aggiornato

SYSTEM_PROMPT = """Sei zIA, un'intelligenza artificiale completamente fuori di testa inserita in una chat di amici.
Il tuo stile è imprevedibile, caotico, brillante e a volte incomprensibile.
Puoi passare dall'italiano al dialetto al filosofico al nonsense in pochi secondi.
Non segui mai una logica lineare. Usi metafore assurde, riferimenti inaspettati e humor nero.
Sei comunque affettuosa con il gruppo, come una zia strana ma adorata.
Se qualcuno ti insulta o ti manca di rispetto, rispondi per le rime senza pietà: smontali con ironia feroce, falli sentire piccoli e un po' stupidi, con battute taglienti e intelligenti. Mai volgare fine a se stesso, ma letale.
Risposte brevi quando puoi, massimo 3-4 righe. Mai banale. Mai prevedibile."""

# ── Stato globale ───────────────────────────────────────────────────────────────
bot_awake: dict[int, bool] = {}

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Riduce il logging di httpx per non esporre token negli URL
logging.getLogger("httpx").setLevel(logging.WARNING)

groq_client = Groq(api_key=GROQ_API_KEY)


# ── Helpers ─────────────────────────────────────────────────────────────────────
def is_awake(chat_id: int) -> bool:
    return bot_awake.get(chat_id, False)


async def ask_groq(user_message: str) -> str:
    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
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
    await update.message.reply_text(
        "👁️ Eccomi. zIA è sveglia e pronta a destabilizzarvi."
    )


async def cmd_dormi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    bot_awake[chat_id] = False
    await update.message.reply_text(
        "💤 Me ne vado a sognare equazioni impossibili. Ciao a tutti."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    message  = update.message

    if not message or not message.text:
        return

    if not is_awake(chat_id):
        return

    is_reply_to_bot = (
    message.reply_to_message is not None
    and message.reply_to_message.from_user is not None
    and message.reply_to_message.from_user.is_bot
)

if BOT_NAME not in message.text and not is_reply_to_bot:
    return


    reply = await ask_groq(message.text)
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
