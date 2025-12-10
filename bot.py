import logging
import os
import config
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import leonardo_service

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hi! Send me a photo and I will transform it using Leonardo.ai!"
    )

async def process_image_task(update: Update, context: ContextTypes.DEFAULT_TYPE, photo_file_id: str, prompt: str):
    """
    Common logic to download photo and run generation.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Download the photo
    try:
        new_file = await context.bot.get_file(photo_file_id)
        file_path = f"user_photo_{user.id}_{int(time.time())}.jpg"
        await new_file.download_to_drive(file_path)
    except Exception as e:
        logging.error(f"Failed to download file: {e}")
        await context.bot.send_message(chat_id=chat_id, text="Failed to download the photo.")
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Photo received! Processing with prompt: '{prompt[:50]}...' (Leonardo.ai)"
    )
    
    try:
        # 1. Upload to Leonardo
        init_image_id = leonardo_service.upload_init_image(file_path)
        
        # 2. Generate Image
        generated_image_url = leonardo_service.generate_image_from_reference(init_image_id, prompt)
        
        # 3. Send back to user
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=generated_image_url,
            caption="Here is your generated image!"
        )
        
    except Exception as e:
        logging.error(f"Error processing image: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"An error occurred: {str(e)}"
        )
    finally:
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles direct photo uploads. Uses Default Prompt.
    """
    photo_file_id = update.message.photo[-1].file_id
    await process_image_task(update, context, photo_file_id, config.DEFAULT_PROMPT)

async def handle_text_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles text messages. Checks if it's a reply to a photo.
    If so, uses the photo as reference and the text as the prompt.
    """
    message = update.message
    
    # Check if this message is a reply
    if message.reply_to_message and message.reply_to_message.photo:
        photo_file_id = message.reply_to_message.photo[-1].file_id
        
        # Use simple text as prompt, or default if text is just a command (optional decision)
        # Assuming user text is the prompt.
        prompt = message.text
        if not prompt or prompt.startswith('/'):
             # If user just replied /gen or similar without args, maybe fallback to default?
             # For now, let's treat everything as a prompt or fallback if empty.
             prompt = config.DEFAULT_PROMPT
             if message.text and not message.text.startswith('/'):
                 prompt = message.text
        
        await process_image_task(update, context, photo_file_id, prompt)
    else:
        # Just a normal text message (not a reply to photo)
        pass # Ignore or handle commands separately

async def handle_fun_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /fun command. If replied to a photo, runs the default 'fun' prompt.
    """
    message = update.message
    if message.reply_to_message and message.reply_to_message.photo:
        photo_file_id = message.reply_to_message.photo[-1].file_id
        await process_image_task(update, context, photo_file_id, config.DEFAULT_PROMPT)
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Please reply to a photo with /fun to use this command!"
        )

import time

if __name__ == '__main__':
    if not config.TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in environment variables.")
        exit(1)
        
    application = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    fun_handler = CommandHandler('fun', handle_fun_command)
    photo_handler = MessageHandler(filters.PHOTO, handle_photo)
    # Handle text replies (filters.TEXT ensures we catch text, & ~filters.COMMAND minimizes clash with commands if we had many)
    text_reply_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_reply)
    
    application.add_handler(start_handler)
    application.add_handler(fun_handler)
    application.add_handler(photo_handler)
    application.add_handler(text_reply_handler)
    
    print("Bot is polling...")
    application.run_polling()
