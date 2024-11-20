import asyncio
from flask import Flask
import threading
from discord.ext import commands
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import discord
import json

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot 啟動!"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 允許列表，存放可以使用 !timeout 指令的使用者 ID
allow_list = set()
ALLOW_LIST_FILE = 'allow_list.json'

def load_allow_list():
    global allow_list
    try:
        with open(ALLOW_LIST_FILE, 'r') as f:
            data = json.load(f)
            allow_list = set(data)
    except FileNotFoundError:
        allow_list = set()
    except json.JSONDecodeError:
        allow_list = set()

def save_allow_list():
    with open(ALLOW_LIST_FILE, 'w') as f:
        json.dump(list(allow_list), f)

class VoiceStateManager:
    def __init__(self):
        self.user_logs = {}
        self.timeout_users = {}

    def clean_old_logs(self):
        current_time = datetime.now(ZoneInfo('Asia/Taipei'))
        cutoff_time = current_time - timedelta(hours=12)
        self.user_logs = {k: v for k, v in self.user_logs.items() if v['connect_time'] > cutoff_time}

    async def handle_voice_state_update(self, member, before, after):
        self.clean_old_logs()

        # 檢查 Timeout 使用者是否試圖切換頻道
        if member.id in self.timeout_users and after.channel and after.channel != self.timeout_users[member.id]['timeout_channel']:
            await member.move_to(self.timeout_users[member.id]['timeout_channel'])
            await member.guild.system_channel.send(f"{member.mention} 還想逃啊，乖乖蹲好！")

        current_time = datetime.now(ZoneInfo('Asia/Taipei'))
        if before.channel is None and after.channel:
            self.user_logs[member.id] = {
                "user_id": member.id,
                "username": member.name,
                "connect_time": current_time,
                "disconnect_time": None,
                "last_disconnect_time": self.user_logs.get(member.id, {}).get("disconnect_time")
            }
        elif before.channel and after.channel is None and member.id in self.user_logs:
            self.user_logs[member.id]["disconnect_time"] = current_time

voice_manager = VoiceStateManager()

@bot.event
async def on_voice_state_update(member, before, after):
    await voice_manager.handle_voice_state_update(member, before, after)

def is_admin_or_allowed():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator or ctx.author.id in allow_list
    return commands.check(predicate)

@bot.command(name="cm")
async def help_command(ctx):
    help_text = """
**機器人指令列表：**

- `!ping`：測試機器人是否在線。
- `!timeout @用戶名 [秒數]`：將指定用戶移至 "禁閉室" 頻道，並進行指定秒數的 Timeout。（預設 60 秒）Ex : `!timeout @使用者名 600`
- `!unban @用戶名`：解除指定用戶的 Timeout 狀態。
- `!details`：顯示所有用戶的語音連接資訊。
- `!check`：查找最近斷線的使用者。
- `!adduser @用戶名`：將使用者添加到允許列表，可以使用 `!timeout` 指令。（僅限管理員）
- `!removeuser @用戶名`：將使用者從允許列表中移除。（僅限管理員）
"""
    await ctx.send(help_text)

@bot.command(name="timeout")
@is_admin_or_allowed()
async def timeout(ctx, member: discord.Member, duration: int = 60):
    target_channel = discord.utils.get(ctx.guild.voice_channels, name="禁閉室")
    
    if target_channel is None:
        await ctx.send("找不到名稱為 '禁閉室' 的語音頻道。")
        return

    if member.voice:
        # 記錄使用者原本的頻道
        original_channel = member.voice.channel

        await member.move_to(target_channel)
        voice_manager.timeout_users[member.id] = {
            'timeout_channel': target_channel,
            'original_channel': original_channel
        }
        await ctx.send(f"{member.name}，乖乖在裡面蹲 {duration} 秒吧。")

        async def remove_timeout():
            await asyncio.sleep(duration)
            if member.id in voice_manager.timeout_users:
                # 在移動之前先移除使用者的 Timeout 狀態
                original_channel = voice_manager.timeout_users[member.id]['original_channel']
                del voice_manager.timeout_users[member.id]
                # 將使用者移回原本的頻道
                if original_channel is not None:
                    await member.move_to(original_channel)
                await ctx.send(f"{member.name} 的 Timeout 已結束，可以回去了")

        # 使用 asyncio.create_task 來啟動非阻塞的協程
        asyncio.create_task(remove_timeout())
    else:
        await ctx.send(f"{member.name} 不在語音頻道中，無法進行 Timeout。")

@bot.command(name="unban")
@commands.has_permissions(administrator=True)
async def unban(ctx, member: discord.Member):
    if member.id in voice_manager.timeout_users:
        # 在移動之前先移除使用者的 Timeout 狀態
        original_channel = voice_manager.timeout_users[member.id]['original_channel']
        del voice_manager.timeout_users[member.id]
        # 將使用者移回原本的頻道
        if original_channel is not None:
            await member.move_to(original_channel)
        await ctx.send(f"{member.name} 的 Timeout 已解除，可以回去了")
    else:
        await ctx.send(f"{member.name} 並不在 Timeout 狀態中。")

@bot.command(name="adduser")
@commands.has_permissions(administrator=True)
async def adduser(ctx, member: discord.Member):
    allow_list.add(member.id)
    save_allow_list()  
    await ctx.send(f"{member.name} 已被加到allowlist中，可以使用 `!timeout` 指令。")

@bot.command(name="removeuser")
@commands.has_permissions(administrator=True)
async def removeuser(ctx, member: discord.Member):
    if member.id in allow_list:
        allow_list.remove(member.id)
        save_allow_list()  
        await ctx.send(f"{member.name} 已被從allowlist中移除。")
    else:
        await ctx.send(f"{member.name} 不在list中。")

@bot.command(name="details")
async def details_log(ctx):
    voice_manager.clean_old_logs()

    if voice_manager.user_logs:
        response = "\n\n".join(
            f"使用者名: {log['username']}\n"
            f"連接時間: {log['connect_time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"斷開時間: {log['disconnect_time'].strftime('%Y-%m-%d %H:%M:%S') if log['disconnect_time'] else '連接中'}\n"
            f"上次斷開時間: {log.get('last_disconnect_time').strftime('%Y-%m-%d %H:%M:%S') if log.get('last_disconnect_time') else '無紀錄'}"
            for log in voice_manager.user_logs.values()
        )
        await ctx.send(response.strip())
    else:
        await ctx.send("無紀錄。")

@bot.command(name="check")
async def check_most_recent_offline(ctx):
    voice_manager.clean_old_logs()

    disconnected_logs = [
        log for log in voice_manager.user_logs.values()
        if log['disconnect_time']
    ]

    if disconnected_logs:
        # 找到最近斷線的使用者
        most_recent_log = max(disconnected_logs, key=lambda log: log['disconnect_time'])

        member = ctx.guild.get_member(most_recent_log['user_id'])
        disconnect_time_str = most_recent_log['disconnect_time'].strftime('%Y-%m-%d %H:%M:%S')

        if member:
            await ctx.send(f"抓到是 {member.mention}，上次斷線時間是 {disconnect_time_str}")
        else:
            await ctx.send(f"抓到是 {most_recent_log['username']}，上次斷線時間是 {disconnect_time_str}")
    else:
        await ctx.send("目前沒有離線的使用者。")

@timeout.error
async def timeout_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("你沒有權限使用這個指令。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("請指定需要 Timeout 的使用者。用法: `!timeout @使用者名 [秒數]` Ex : `!timeout @使用者名 600`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("請提供有效的秒數。用法: `!timeout @使用者名 [秒數]`Ex : `!timeout @使用者名 600`")
    else:
        await ctx.send("unknown error，等等再試一次")

@unban.error
async def unban_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("你沒有權限使用這個指令。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("請指定需要 Unban 的使用者。用法: `!unban @使用者名`")
    else:
        await ctx.send("unknown error，等等再試一次")

@adduser.error
async def adduser_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("你沒有權限使用這個指令。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("請指定需要加的使用者。用法: `!adduser @使用者名`")
    else:
        await ctx.send("unknown error，等等再試一次")

@removeuser.error
async def removeuser_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("你沒有權限使用這個指令。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("指定需要移除的使用者。用法: `!removeuser @使用者名`")
    else:
        await ctx.send("unknown error，等等再試一次")

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("Pong!")

def run_bot():
    try:
        bot.run('BOT_TOKEN')
    except Exception as e:
        print(f"Bot 啟動失敗: {e}")

if __name__ == "__main__":
    load_allow_list()
    port = int(os.environ.get("PORT", 8081))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port)).start()
    run_bot()