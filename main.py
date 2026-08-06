import os
import time
import requests
import logging
import threading
from flask import Flask
import yfinance as ticker_data

# ==========================================
# 1. 輕量 Web 伺服器 (防止 Render 服務休眠)
# ==========================================
app = Flask(__name__)

@app.route('/')
@app.route('/health')
def health_check():
    # 供外部 Ping (如 UptimeRobot / Cron-Job) 呼叫，保持 24/7 運作
    return "OK - Trading Bot is Running Alive", 200

def start_web_server():
    # Render 會自動提供 PORT 環境變數，預設為 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ==========================================
# 2. 系統配置與環境變數 (安全管理)
# ==========================================
# 美金對港元聯繫匯率
USD_TO_HKD = 7.80 

# 由 Render 環境變數 (Environment Variables) 讀取機密 Token
TELEGRAM_TOKEN = os.environ.get("TG_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TG_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

# 設定系統 Log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def send_telegram(message):
    """ 發送 Telegram 即時訊息與 Heartbeat """
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logging.warning("未設定 Telegram Token，僅於 Console 印出訊息：\n" + message)
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Telegram 發送失敗: {e}")

# ==========================================
# 3. 24/7 市場分析與高息股篩選邏輯
# ==========================================
# 候選高息美股/ETF 標的池
CANDIDATE_TICKERS = ["O", "SCHD", "VZ", "PFE", "JEPI", "MO"]

def analyze_and_screen_stocks():
    """ 自動分析市場並根據風控條件篩選合適標的 """
    selected_stocks = []
    
    for symbol in CANDIDATE_TICKERS:
        try:
            stock = ticker_data.Ticker(symbol)
            info = stock.info
            
            dividend_yield = info.get('dividendYield', 0) or 0
            payout_ratio = info.get('payoutRatio', 1) or 1
            debt_to_equity = info.get('debtToEquity', 999) or 999
            current_price_usd = info.get('currentPrice') or info.get('regularMarketPrice', 0)

            # 風控防禦指標：
            # 1. 股息率 >= 4%
            # 2. 派息比率 < 80% (避免公司透支)
            # 3. 負債比率 < 150%
            if dividend_yield >= 0.04 and payout_ratio < 0.80 and debt_to_equity < 150:
                price_hkd = current_price_usd * USD_TO_HKD
                selected_stocks.append({
                    "symbol": symbol,
                    "yield_pct": round(dividend_yield * 100, 2),
                    "price_usd": current_price_usd,
                    "price_hkd": round(price_hkd, 2)
                })
        except Exception as e:
            logging.error(f"分析 {symbol} 時發生錯誤: {e}")
        time.sleep(3)            
    return selected_stocks

def run_trading_strategy():
    """ 執行篩選並報告結果 """
    selected = analyze_and_screen_stocks()
    
    if not selected:
        msg = "【24/7 市場分析】目前無符合防禦型風控條件的高息標的。"
        logging.info(msg)
        send_telegram(msg)
        return

    report = "【24/7 自動交易篩選報告】\n"
    report += f"美金/港元 匯率: {USD_TO_HKD}\n\n"
    
    for item in selected:
        report += (
            f"標的: {item['symbol']}\n"
            f"預期股息率: {item['yield_pct']}%\n"
            f"現價: ${item['price_usd']} USD\n"
            f"折算: ${item['price_hkd']} HKD\n"
            f"------------------------\n"
        )
    
    send_telegram(report)

# ==========================================
# 4. 主程序與 24/7 循環執行
# ==========================================
def main_trading_loop():
    send_telegram("🚀 24/7 自動交易程式已在 Render 雲端成功啟動！")
    heartbeat_counter = 0

    while True:
        try:
            # 執行市場分析與策略
            run_trading_strategy()
            
            # 每 12 小時執行一次市場掃描
            time.sleep(43200) 
            heartbeat_counter += 1
            
            # 每 24 小時發送一次心跳報告
            if heartbeat_counter >= 2:
                send_telegram("💓 [Heartbeat] 系統正常運作中。")
                heartbeat_counter = 0

        except Exception as e:
            error_msg = f"⚠️ 交易程式捕捉到異常: {str(e)}"
            logging.error(error_msg)
            send_telegram(error_msg)
            time.sleep(60)

if __name__ == "__main__":
    # 1. 喺背景背景開啟 Flask Web 伺服器 (防止 Render 睡眠)
    server_thread = threading.Thread(target=start_web_server)
    server_thread.daemon = True
    server_thread.start()

    # 2. 啟動 24/7 交易主迴圈
    main_trading_loop()