import os
from flask import Flask, request, abort
from linebot.v3.webhooks import WebhookHandler
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
import psycopg2
from psycopg2 import sql

app = Flask(__name__)

# 從環境變數中讀取 LINE Channel Access Token 和 Channel Secret
line_channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
line_channel_secret = os.environ.get('LINE_CHANNEL_SECRET')

# 設定 LINE Bot SDK 的 Configuration
configuration = Configuration(access_token=line_channel_access_token)
handler = WebhookHandler(line_channel_secret)

# 資料庫連線設定
def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('PGHOST'),
        database=os.environ.get('PGDATABASE'),
        user=os.environ.get('PGUSER'),
        password=os.environ.get('PGPASSWORD'),
        port=os.environ.get('PGPORT')
    )

# Webhook 路由
@app.route("/callback", methods=['POST'])
def callback():
    # 取得 X-Line-Signature
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        # 處理 Webhook 事件
        handler.handle(body, signature)
    except Exception as e:
        print(f"Webhook handler error: {e}")
        abort(400)

    return 'OK'

# 處理訊息事件
@handler.add(MessageEvent)
def handle_message(event):
    # 這裡才建立資料庫連線
    conn = get_db_connection()
    cur = conn.cursor()
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        if isinstance(event.message, TextMessage):
            user_message = event.message.text
            
            # 回覆訊息
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"你說了: {user_message}")]
                )
            )

    # 關閉資料庫連線
    cur.close()
    conn.close()


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))