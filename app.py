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

# 啟用所有 Intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

user_logs = {}

def clean_old_logs():
    """移除超過12小時的舊紀錄"""
    global user_logs
    current_time = datetime.utcnow() + timedelta(hours=8)
    cutoff_time = current_time - timedelta(hours=12)
    user_logs = {k: v for k, v in user_logs.items() if v['connect_time'] > cutoff_time}

@bot.event
async def on_voice_state_update(member, before, after):
    global user_logs
    current_time = datetime.utcnow() + timedelta(hours=8)

    clean_old_logs()

    print(f"偵測到語音狀態變化: {member.name} 在 {before.channel} -> {after.channel}")

    if before.channel is None and after.channel is not None:
        # 使用者連接到語音頻道
        user_logs[member.id] = {
            "username": member.name,
            "connect_time": current_time,
            "disconnect_time": None,
            "last_disconnect_time": user_logs.get(member.id, {}).get("disconnect_time")
        }
    elif before.channel is not None and after.channel is None:
        # 使用者斷開語音頻道
        if member.id in user_logs:
            user_logs[member.id]["disconnect_time"] = current_time

@bot.command(name="check")
async def check_log(ctx):
    global user_logs
    current_time = datetime.utcnow() + timedelta(hours=8)
    cutoff_time = current_time - timedelta(hours=12)

    # 清除舊的紀錄
    clean_old_logs()

    if user_logs:
        response = ""
        for log in user_logs.values():
            last_disconnect_time = log.get("last_disconnect_time", "無紀錄")

            if log["disconnect_time"]:
                disconnect_time_str = log["disconnect_time"].strftime('%Y-%m-%d %H:%M:%S')
            else:
                disconnect_time_str = "連接中"

            if isinstance(last_disconnect_time, datetime):
                last_disconnect_time_str = last_disconnect_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                last_disconnect_time_str = "無紀錄"

            response += (
                f"Username: {log['username']}\n"
                f"連接時間: {log['connect_time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"斷開時間: {disconnect_time_str}\n"
                f"上次斷開時間: {last_disconnect_time_str}\n\n"
            )

        await ctx.send(response.strip())
    else:
        await ctx.send("無紀錄。")

# 測試指令，確保 Bot 能夠正常接收指令
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
