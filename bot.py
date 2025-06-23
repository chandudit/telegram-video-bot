#!/usr/bin/env python3
"""
Telegram Video Processing Bot
Owner-only bot that processes videos with renaming and watermarking
"""

import os
import re
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, MessageNotModified

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot Configuration
API_ID = os.getenv("25948361")  # Get from my.telegram.org
API_HASH = os.getenv("dcadd49ec2c89eccfeb81934e32bcfa2")  # Get from my.telegram.org
BOT_TOKEN = os.getenv("7459295074:AAHxa6GR9C1ciNompJAO7409wc-wxGwqRsM")  # Get from @BotFather
OWNER_ID = int(os.getenv("5669926632"))  # Your Telegram user ID

# Bot constants
WATERMARK_CAPTION = "➤ -AnimeBuddy"
DOWNLOADS_DIR = "downloads"
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB limit

# Create downloads directory
Path(DOWNLOADS_DIR).mkdir(exist_ok=True)

# Initialize bot
app = Client(
    "video_processor_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Store user states for renaming process
user_states = {}

def sanitize_filename(filename):
    """Sanitize filename to prevent path traversal and invalid characters"""
    # Remove dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    # Limit length
    filename = filename[:100]
    # Ensure it's not empty
    if not filename:
        filename = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    return filename

def format_file_size(size_bytes):
    """Convert bytes to human readable format"""
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f} {size_names[i]}"

async def log_activity(user_id, action, filename=None):
    """Log bot activities"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] User {user_id}: {action}"
    if filename:
        log_entry += f" - File: {filename}"
    logger.info(log_entry)

# Owner-only filter
def owner_only(_, __, message):
    return message.from_user.id == OWNER_ID

owner_filter = filters.create(owner_only)

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """Handle /start command"""
    if message.from_user.id != OWNER_ID:
        await message.reply_text(
            "🚫 **Access Denied**\n"
            "This bot is private and only accessible to its owner.",
            parse_mode="markdown"
        )
        await log_activity(message.from_user.id, "Unauthorized access attempt")
        return
    
    welcome_text = (
        "🤖 **Welcome to Video Processor Bot!**\n\n"
        "🎯 **What I can do:**\n"
        "• Process your video files\n"
        "• Rename them with custom names\n"
        "• Add watermark caption\n"
        "• Convert to document format\n\n"
        "📤 **Just send me a video to get started!**"
    )
    
    await message.reply_text(welcome_text, parse_mode="markdown")
    await log_activity(message.from_user.id, "Bot started")

@app.on_message(filters.command("help") & owner_filter)
async def help_command(client, message: Message):
    """Handle /help command"""
    help_text = (
        "📋 **How to use the bot:**\n\n"
        "1️⃣ Send me a video file\n"
        "2️⃣ I'll ask for a new filename\n"
        "3️⃣ Reply with the name (without .mp4)\n"
        "4️⃣ I'll process and send it back as a document\n\n"
        "✨ **Features:**\n"
        "• Removes old captions\n"
        "• Adds watermark: `➤ -AnimeBuddy`\n"
        "• Converts to document format\n"
        "• Auto cleanup of temporary files\n\n"
        "📝 **Commands:**\n"
        "/start - Welcome message\n"
        "/help - This help message\n"
        "/cancel - Cancel current operation"
    )
    
    await message.reply_text(help_text, parse_mode="markdown")

@app.on_message(filters.command("cancel") & owner_filter)
async def cancel_command(client, message: Message):
    """Handle /cancel command"""
    user_id = message.from_user.id
    if user_id in user_states:
        # Clean up any temporary files
        if 'file_path' in user_states[user_id]:
            try:
                os.remove(user_states[user_id]['file_path'])
            except:
                pass
        del user_states[user_id]
        await message.reply_text("❌ **Operation cancelled!**", parse_mode="markdown")
        await log_activity(user_id, "Operation cancelled")
    else:
        await message.reply_text("ℹ️ **No operation to cancel.**", parse_mode="markdown")

@app.on_message((filters.video | filters.document) & owner_filter)
async def handle_video(client, message: Message):
    """Handle video files"""
    user_id = message.from_user.id
    
    # Check if it's a video document
    if message.document:
        if not message.document.mime_type or not message.document.mime_type.startswith('video/'):
            await message.reply_text(
                "❌ **Invalid file type!**\n"
                "Please send a video file.",
                parse_mode="markdown"
            )
            return
        file_obj = message.document
        file_type = "document"
    else:
        file_obj = message.video
        file_type = "video"
    
    # Check file size
    if file_obj.file_size > MAX_FILE_SIZE:
        await message.reply_text(
            f"❌ **File too large!**\n"
            f"Maximum size: {format_file_size(MAX_FILE_SIZE)}\n"
            f"Your file: {format_file_size(file_obj.file_size)}",
            parse_mode="markdown"
        )
        return
    
    # Store video info for renaming
    old_caption = message.caption or "No previous caption"
    
    user_states[user_id] = {
        'message': message,
        'file_obj': file_obj,
        'file_type': file_type,
        'old_caption': old_caption
    }
    
    # Create inline keyboard with copy caption option
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Copy Old Caption", callback_data="copy_caption")]
    ])
    
    # Ask for new filename
    prompt_text = (
        f"📹 **Video received!** ({format_file_size(file_obj.file_size)})\n\n"
        f"📝 **Please reply with the new name** (without `.mp4`)\n\n"
        f"📋 **Previous Caption:**\n"
        f"```\n{old_caption}\n```"
    )
    
    await message.reply_text(
        prompt_text,
        parse_mode="markdown",
        reply_markup=keyboard
    )
    
    await log_activity(user_id, f"Video received - {file_type}", f"{file_obj.file_size} bytes")

@app.on_callback_query()
async def handle_callback(client, callback_query):
    """Handle inline keyboard callbacks"""
    if callback_query.from_user.id != OWNER_ID:
        await callback_query.answer("Access denied!", show_alert=True)
        return
    
    if callback_query.data == "copy_caption":
        user_id = callback_query.from_user.id
        if user_id in user_states:
            old_caption = user_states[user_id]['old_caption']
            await callback_query.answer(f"Caption copied: {old_caption[:50]}...")
            # Send the old caption as a separate message for easy copying
            await callback_query.message.reply_text(
                f"📋 **Old Caption:**\n`{old_caption}`",
                parse_mode="markdown"
            )
        else:
            await callback_query.answer("No active session found!", show_alert=True)

@app.on_message(filters.text & owner_filter)
async def handle_rename(client, message: Message):
    """Handle filename input for renaming"""
    user_id = message.from_user.id
    
    if user_id not in user_states:
        return  # No active video processing session
    
    new_name = sanitize_filename(message.text.strip())
    if not new_name:
        await message.reply_text(
            "❌ **Invalid filename!**\n"
            "Please provide a valid name.",
            parse_mode="markdown"
        )
        return
    
    # Get stored video info
    video_message = user_states[user_id]['message']
    file_obj = user_states[user_id]['file_obj']
    file_type = user_states[user_id]['file_type']
    
    # Start processing
    processing_msg = await message.reply_text(
        "📥 **Downloading video...**",
        parse_mode="markdown"
    )
    
    try:
        # Download the file
        original_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_obj.file_unique_id}"
        download_path = os.path.join(DOWNLOADS_DIR, original_filename)
        
        await client.download_media(video_message, file_name=download_path)
        
        # Store file path for cleanup
        user_states[user_id]['file_path'] = download_path
        
        await processing_msg.edit_text(
            "📤 **Uploading your renamed file...**\n"
            f"🔐 **Watermark:** `{WATERMARK_CAPTION}`",
            parse_mode="markdown"
        )
        
        # Upload as document with new name and watermark
        new_filename = f"{new_name}.mp4"
        
        await client.send_document(
            chat_id=message.chat.id,
            document=download_path,
            file_name=new_filename,
            caption=WATERMARK_CAPTION,
            reply_to_message_id=message.message_id
        )
        
        await processing_msg.edit_text(
            f"✅ **Done!**\n"
            f"📁 **New filename:** `{new_filename}`\n"
            f"🔐 **Watermark added:** `{WATERMARK_CAPTION}`",
            parse_mode="markdown"
        )
        
        await log_activity(user_id, "Video processed successfully", new_filename)
        
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await processing_msg.edit_text(
            f"⏳ **Rate limited. Waiting {e.value} seconds...**",
            parse_mode="markdown"
        )
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        await processing_msg.edit_text(
            "❌ **Error processing video!**\n"
            "Please try again later.",
            parse_mode="markdown"
        )
        await log_activity(user_id, f"Error processing video: {str(e)}")
    
    finally:
        # Cleanup
        if user_id in user_states:
            if 'file_path' in user_states[user_id]:
                try:
                    os.remove(user_states[user_id]['file_path'])
                except:
                    pass
            del user_states[user_id]

# Error handler
@app.on_message(~owner_filter)
async def unauthorized_access(client, message: Message):
    """Handle unauthorized access attempts"""
    await message.reply_text(
        "🚫 **Access Denied**\n"
        "This bot is private and only accessible to its owner.\n\n"
        "If you think this is an error, please contact the bot owner.",
        parse_mode="markdown"
    )
    await log_activity(message.from_user.id, "Unauthorized access attempt")

def main():
    """Main function to run the bot"""
    if not all([API_ID, API_HASH, BOT_TOKEN, OWNER_ID]):
        logger.error("Missing required environment variables!")
        print("Please set the following environment variables:")
        print("- API_ID (from my.telegram.org)")
        print("- API_HASH (from my.telegram.org)")
        print("- BOT_TOKEN (from @BotFather)")
        print("- OWNER_ID (your Telegram user ID)")
        return
    
    logger.info("Starting Video Processor Bot...")
    logger.info(f"Owner ID: {OWNER_ID}")
    
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {str(e)}")

if __name__ == "__main__":
    main()
