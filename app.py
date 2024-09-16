import asyncio
from flask import Flask
import threading
from discord.ext import commands
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import discord

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot 啟動!"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

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
        if member.id in self.timeout_users and after.channel and after.channel != self.timeout_users[member.id]:
            await member.move_to(self.timeout_users[member.id])
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

@bot.command(name="cm")
async def help_command(ctx):
    help_text = """
**機器人指令列表：**

- `!ping`：測試機器人是否在線。
- `!timeout @用戶名`：將指定用戶移至 "禁閉室" 頻道，並進行 1 分鐘的 Timeout。
- `!unban @用戶名`：解除指定用戶的 Timeout 狀態。
- `!details`：顯示所有用戶的語音連接資訊。
- `!check`：查找最近斷線的使用者。
"""
    await ctx.send(help_text)

@bot.command(name="timeout")
@commands.has_permissions(administrator=True)
async def timeout(ctx, member: discord.Member):
    target_channel = discord.utils.get(ctx.guild.voice_channels, name="禁閉室")
    
    if target_channel is None:
        await ctx.send("找不到名稱為 '禁閉室' 的語音頻道。")
        return

    if member.voice:
        await member.move_to(target_channel)
        voice_manager.timeout_users[member.id] = target_channel
        await ctx.send(f"{member.name}，乖乖在裡面蹲 1 分鐘吧。")

        await asyncio.sleep(60)

        if member.id in voice_manager.timeout_users:
            del voice_manager.timeout_users[member.id]
            await ctx.send(f"{member.name} 的 Timeout 已結束。")
    else:
        await ctx.send(f"{member.name} 不在語音頻道中，無法進行 Timeout。")

@bot.command(name="unban")
@commands.has_permissions(administrator=True)
async def unban(ctx, member: discord.Member):
    if voice_manager.timeout_users.pop(member.id, None):
        await ctx.send(f"{member.name} 的 Timeout 已解除。")
    else:
        await ctx.send(f"{member.name} 並不在 Timeout 狀態中。")

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

    # 篩選出已經斷線的使用者
    disconnected_logs = [
        log for log in voice_manager.user_logs.values()
        if log['disconnect_time']
    ]

    if disconnected_logs:
        # 找到最近斷線的使用者
        most_recent_log = max(disconnected_logs, key=lambda log: log['disconnect_time'])

        # 使用使用者 ID 獲取 Member 對象
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
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("你沒有權限使用這個指令。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("請指定需要 Timeout 的使用者。用法: `!timeout @使用者名`")

@unban.error
async def unban_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("你沒有權限使用這個指令。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("請指定需要 Unban 的使用者。用法: `!unban @使用者名`")

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("Pong!")

def run_bot():
    try:
        bot.run('BOT_TOKEN')
    except Exception as e:
        print(f"Bot 啟動失敗: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8081))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port)).start()
    run_bot()
