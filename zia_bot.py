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
BOT_NAME       = "zIA"          # la parola chiave che attiva la risposta
GROQ_MODEL     = "llama3-70b-8192"   # modello gratuito su Groq

SYSTEM_PROMPT = """Sei zIA, un'intelligenza artificiale completamente fuori di testa inserita in una chat di amici.
Il tuo stile è imprevedibile, caotico, brillante e a volte incomprensibile.
Puoi passare dall'italiano al dialetto al filosofico al nonsense in pochi secondi.
Non segui mai una logica lineare. Usi metafore assurde, riferimenti inaspettati e humor nero.
Sei comunque affettuosa con il gruppo, come una zia strana ma adorata.
Risposte brevi quando puoi, massimo 3-4 righe. Mai banale. Mai prevedibile."""

# ── Stato globale ───────────────────────────────────────────────────────────────
bot_awake: dict[int, bool] = {}   # chat_id → True/False

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

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
            temperature=1.2,   # alta per massima imprevedibilità
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

    # Ignora se addormentata
    if not is_awake(chat_id):
        return

    # Risponde solo se il messaggio contiene "zIA" (case-sensitive)
    if BOT_NAME not in message.text:
        return

    logger.info(f"[chat {chat_id}] Messaggio ricevuto: {message.text!r}")
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
