import asyncio
from flask import Flask
import threading
import discord
from discord.ext import commands
from discord.ext.commands import MissingPermissions
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
    #移除超過12小時的舊紀錄
    global user_logs
    current_time = datetime.utcnow() + timedelta(hours=8)
    cutoff_time = current_time - timedelta(hours=12)
    user_logs = {k: v for k, v in user_logs.items() if v['connect_time'] > cutoff_time}

@bot.event
async def on_voice_state_update(member, before, after):
    global user_logs, timeout_users

    current_time = datetime.utcnow() + timedelta(hours=8)

    # 清除舊的紀錄
    clean_old_logs()

    # 檢查是否有在 timeout 列表中的user切換了頻道
    if member.id in timeout_users:
        timeout_info = timeout_users[member.id]
        target_channel = timeout_info["target_channel"]
        
        # 檢查user是否已經連接到某個頻道
        if after.channel is not None and after.channel != target_channel:
            # 將user移回到禁閉室
            await member.move_to(target_channel)
            await member.guild.system_channel.send(f"{member.mention} 還想逃阿乖乖蹲好")

    # 記錄user的連接和斷開時間
    if before.channel is None and after.channel is not None:
        user_logs[member.id] = {
            "username": member.name,
            "connect_time": current_time,
            "disconnect_time": None,
            "last_disconnect_time": user_logs.get(member.id, {}).get("disconnect_time")
        }
    elif before.channel is not None and after.channel is None:
        if member.id in user_logs:
            user_logs[member.id]["disconnect_time"] = current_time

@bot.command(name="timeout")
@commands.has_permissions(administrator=True)
async def timeout(ctx, member: discord.Member):
    #將用戶移到禁閉室並開始計時
    global timeout_users

    # 找到禁閉室頻道
    guild = ctx.guild
    target_channel = discord.utils.get(guild.voice_channels, name="禁閉室")
    
    if target_channel is None:
        await ctx.send("找不到名為'禁閉室'的語音頻道。")
        return

    # 檢查user是否已經在某個頻道中
    if member.voice is not None:
        # 將用戶移動到"禁閉室"
        await member.move_to(target_channel)

        # 記錄這個用戶的 timeout 狀態
        timeout_users[member.id] = {
            "target_channel": target_channel,
            "end_time": datetime.utcnow() + timedelta(minutes=1)
        }

        await ctx.send(f"{member.name} 你就乖乖蹲個1分鐘吧。")

        # 啟動計時器
        await asyncio.sleep(60)

        # 解除 timeout 狀態
        if member.id in timeout_users:
            del timeout_users[member.id]
        await ctx.send(f"{member.name} 的 Timeout 結束。")
    else:
        await ctx.send(f"{member.name} 不在語音頻道中，ban不了。")

@bot.command(name="unban")
@commands.has_permissions(administrator=True)
async def unban(ctx, member: discord.Member):
    #立即解除用戶的 timeout 狀態
    global timeout_users

    if member.id in timeout_users:
        del timeout_users[member.id]
        await ctx.send(f"{member.name} 的 Timeout 結束。")
    else:
        await ctx.send(f"{member.name} 沒被ban阿。")

@timeout.error
async def timeout_error(ctx, error):
    if isinstance(error, MissingPermissions):
        await ctx.send("你沒有權限使用這個指令")

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