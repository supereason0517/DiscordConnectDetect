## 設計目的

受不了每次有人一直進進出出DC。此專案包含一個簡單的 Flask 伺服器，並且運行一個 Discord Bot，該 Bot 可以追蹤使用者何時連接和斷開語音頻道。

## 功能介紹

- **語音狀態追蹤**
  - Bot 會追蹤使用者何時連接和斷開語音頻道，並記錄連接和斷開的時間。這些紀錄只會保留最近 12 小時的資料。
  
- **查詢指令**
  - 使用 `!check` 指令，使用者可以查詢自己的連接與斷開時間紀錄，包含上一次斷開的時間。
  
- **測試指令**
  - 使用 `!ping` 指令，Bot 會回應 "Pong!"，確認 Bot 是否正常運行。
 
## 設定 Discord Token

在 `bot_run()` 中找到 Token 並自行更換為您的 Discord Bot Token。

```python
def run_bot():
    try:
        bot.run('BOT_TOKEN')
    except Exception as e:
        print(f"Bot 啟動失敗: {e}")
