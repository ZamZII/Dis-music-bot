import discord
from discord.ext import commands
import os
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    await load_cogs()

async def load_cogs():
    logger.info('Starting to load cogs...')
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                logger.info(f'Loaded {filename}')
            except Exception as e:
                logger.error(f'Failed to load {filename}: {e}', exc_info=True)
    logger.info('Finished loading cogs')

bot.run(TOKEN)

