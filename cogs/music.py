import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
from collections import deque

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = deque()
        self.current_song = None
        self.is_playing = False
        
        # yt-dlp options to avoid IP bans
        self.ydl_options = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'default_search': 'ytsearch',
            'quiet': True,
            'no_warnings': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            # Add these options to avoid IP bans
            'socket_timeout': 30,
            'skip_unavailable_fragments': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                }
            }
        }
        
        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -q:a 5 -bufsize 10000k'
        }

    @commands.command(name='play', help='Play a song from YouTube')
    async def play(self, ctx, *, query):
        """Queue a song to play"""
        
        # Check if user is in a voice channel
        if not ctx.author.voice:
            await ctx.send('❌ You need to be in a voice channel first!')
            return
        
        # Try to connect to voice channel
        try:
            voice_channel = ctx.author.voice.channel
            if ctx.voice_client is None:
                print(f'Attempting to connect to {voice_channel.name}...')
                await voice_channel.connect(timeout=60.0, reconnect=True)
                print(f'Connected to {voice_channel.name}')
            else:
                print(f'Already connected to voice channel')
        except Exception as e:
            error_msg = f'❌ Could not connect to voice channel: {str(e)}'
            print(error_msg)
            await ctx.send(error_msg)
            return
        
        async with ctx.typing():
            try:
                # Search and get video info
                with yt_dlp.YoutubeDL(self.ydl_options) as ydl:
                    info = ydl.extract_info(query, download=False)
                    
                    if 'entries' in info:
                        # If it's a search result, take the first one
                        info = info['entries'][0]
                    
                    url = info['url']
                    title = info['title']
                    duration = info['duration']
                
                # Add to queue
                song_info = {
                    'url': url,
                    'title': title,
                    'duration': duration,
                    'channel': info.get('channel', 'Unknown')
                }
                
                self.queue.append(song_info)
                
                embed = discord.Embed(
                    title='🎵 Added to Queue',
                    description=title,
                    color=discord.Color.blue()
                )
                embed.add_field(name='Duration', value=f'{duration // 60}:{duration % 60:02d}')
                embed.add_field(name='Queue Position', value=len(self.queue))
                
                await ctx.send(embed=embed)
                
                # Start playing if not already playing
                if not self.is_playing:
                    await self.play_next(ctx)
                    
            except Exception as e:
                await ctx.send(f'❌ Error: Could not find or play that song. {str(e)[:100]}')

    async def play_next(self, ctx):
        """Play the next song in queue"""
        # Check if bot still in voice channel
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            self.is_playing = False
            self.current_song = None
            self.queue.clear()
            return
        
        if not self.queue:
            self.is_playing = False
            self.current_song = None
            return
        
        self.is_playing = True
        song_info = self.queue.popleft()
        self.current_song = song_info
        
        # Create and play audio source
        try:
            audio_source = discord.FFmpegPCMAudio(song_info['url'], **self.ffmpeg_options)
            
            def after_playing(error):
                if error and not isinstance(error, discord.ClientException):
                    print(f'Player error: {error}')
                
                # Schedule the next song only if still connected
                if ctx.voice_client and ctx.voice_client.is_connected():
                    asyncio.run_coroutine_threadsafe(
                        self.play_next(ctx),
                        self.bot.loop
                    )
            
            ctx.voice_client.play(audio_source, after=after_playing)
            
            # Send now playing message
            embed = discord.Embed(
                title='🎶 Now Playing',
                description=song_info['title'],
                color=discord.Color.green()
            )
            embed.add_field(name='Channel', value=song_info['channel'])
            embed.add_field(name='Duration', value=f'{song_info["duration"] // 60}:{song_info["duration"] % 60:02d}')
            embed.add_field(name='Queue Size', value=len(self.queue))
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            print(f'Error playing song: {e}')
            self.is_playing = False
            await ctx.send(f'❌ Error playing song: {str(e)[:100]}')
            # Try next song if available
            if self.queue:
                await self.play_next(ctx)

    @commands.command(name='skip', help='Skip the current song')
    async def skip(self, ctx):
        """Skip the current song"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send('⏭️ Skipped!')
        else:
            await ctx.send('❌ Nothing is playing!')

    @commands.command(name='leave', help='Make the bot leave the voice channel')
    async def leave(self, ctx):
        """Disconnect bot from voice channel"""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            self.queue.clear()
            self.is_playing = False
            self.current_song = None
            await ctx.send('👋 Goodbye!')
        else:
            await ctx.send('❌ I\'m not in a voice channel!')

    @commands.command(name='queue', help='Show the current queue')
    async def show_queue(self, ctx):
        """Display current queue"""
        if not self.queue and not self.current_song:
            await ctx.send('❌ Queue is empty!')
            return
        
        embed = discord.Embed(
            title='🎵 Music Queue',
            color=discord.Color.blue()
        )
        
        if self.current_song:
            embed.add_field(
                name='Now Playing',
                value=self.current_song['title'],
                inline=False
            )
        
        if self.queue:
            queue_list = '\n'.join(
                [f'{i}. {song["title"]}' for i, song in enumerate(self.queue, 1)]
            )
            embed.add_field(
                name=f'Up Next ({len(self.queue)})',
                value=queue_list[:1024],  # Discord field limit
                inline=False
            )
        
        await ctx.send(embed=embed)

    @commands.command(name='stop', help='Stop playing and clear the queue')
    async def stop(self, ctx):
        """Stop playing music and clear queue"""
        if ctx.voice_client:
            ctx.voice_client.stop()
            self.queue.clear()
            self.is_playing = False
            self.current_song = None
            await ctx.send('⏹️ Music stopped and queue cleared!')
        else:
            await ctx.send('❌ I\'m not in a voice channel!')

async def setup(bot):
    await bot.add_cog(Music(bot))
