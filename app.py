import asyncio
from flask import Flask
import threading
import discord
from discord.ext import commands
from datetime import datetime, timedelta
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot 啟動!"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

user_logs = {}
timeout_users = {}

def clean_old_logs():
    # 移除超過12小時的舊紀錄
    global user_logs
    cutoff_time = datetime.now() - timedelta(hours=12)
    user_logs = {k: v for k, v in user_logs.items() if v['connect_time'] > cutoff_time}

@bot.event
async def on_voice_state_update(member, before, after):
    global user_logs, timeout_users

    # 清除舊的紀錄
    clean_old_logs()

    # 檢查是否有在 timeout 列表中的用戶切換了頻道
    if member.id in timeout_users and after.channel and after.channel != timeout_users[member.id]:
        await member.move_to(timeout_users[member.id])
        await member.guild.system_channel.send(f"{member.mention} 還想逃阿乖乖蹲好")

    # 記錄用戶的連接和斷開時間，保留上次斷開時間
    current_time = datetime.now() 
    if before.channel is None and after.channel:
        user_logs[member.id] = {
            "username": member.name,
            "connect_time": current_time,
            "disconnect_time": None,
            "last_disconnect_time": user_logs.get(member.id, {}).get("disconnect_time")
        }
    elif before.channel and after.channel is None and member.id in user_logs:
        user_logs[member.id]["disconnect_time"] = current_time

@bot.command(name="timeout")
@commands.has_permissions(administrator=True)
async def timeout(ctx, member: discord.Member):
    # 將用戶移到禁閉室並開始計時
    global timeout_users
    target_channel = discord.utils.get(ctx.guild.voice_channels, name="禁閉室")
    
    if target_channel is None:
        await ctx.send("找不到名稱為'禁閉室'的語音頻道。")
        return

    if member.voice:
        await member.move_to(target_channel)
        timeout_users[member.id] = target_channel
        await ctx.send(f"{member.name} 乖乖在裡面蹲1分鐘吧。")

        await asyncio.sleep(60)

        if member.id in timeout_users:
            del timeout_users[member.id]
            await ctx.send(f"{member.name} 的 Timeout 已結束。")
    else:
        await ctx.send(f"{member.name} 不在語音頻道中，無法進行 Timeout。")

@bot.command(name="unban")
@commands.has_permissions(administrator=True)
async def unban(ctx, member: discord.Member):
    # 立即解除 ban
    if timeout_users.pop(member.id, None):
        await ctx.send(f"{member.name} 的 Timeout 已結束。")
    else:
        await ctx.send(f"{member.name} 並不在 Timeout 狀態中。")

@bot.command(name="check")
async def check_log(ctx):
    clean_old_logs()

    if user_logs:
        response = "\n".join(
            f"Username: {log['username']}\n"
            f"連接時間: {log['connect_time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"斷開時間: {log['disconnect_time'].strftime('%Y-%m-%d %H:%M:%S') if log['disconnect_time'] else '連接中'}\n"
            f"上次斷開時間: {log.get('last_disconnect_time').strftime('%Y-%m-%d %H:%M:%S') if log.get('last_disconnect_time') else '無紀錄'}\n"
            for log in user_logs.values()
        )
        await ctx.send(response.strip())
    else:
        await ctx.send("無紀錄。")

@timeout.error
async def timeout_error(ctx, error):
    # 處理 timeout 指令中的錯誤
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("你沒有權限使用這個指令。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("請指定需要 Timeout 的用戶。用法: `!timeout @user`")

@unban.error
async def unban_error(ctx, error):
    # 處理 unban 指令中的錯誤
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("你沒有權限使用這個指令。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("請指定需要 Unban 的用戶。用法: `!unban @user`")

# 測試指令
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
