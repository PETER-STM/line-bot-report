import os
from dotenv import load_dotenv
from flask import Flask, request, abort

# Import the new database-related libraries
import psycopg2
from psycopg2 import sql

# Update the import statements to use the new v3 classes
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    WebhookHandler,
    MessageEvent,
    TextMessageContent
)
from datetime import datetime

# Load variables from .env file for local development
load_dotenv()

# Read keys from environment variables
line_channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
line_channel_secret = os.environ.get('LINE_CHANNEL_SECRET')

app = Flask(__name__)

# Initialize LineBotApi and WebhookHandler using v3 syntax
configuration = Configuration(access_token=line_channel_access_token)
handler = WebhookHandler(line_channel_secret)

# --- 資料庫連線和初始化函式 ---

def get_db_connection():
    """建立資料庫連線"""
    return psycopg2.connect(
        host=os.environ.get('PGHOST'),
        database=os.environ.get('PGDATABASE'),
        user=os.environ.get('PGUSER'),
        password=os.environ.get('PGPASSWORD'),
        port=os.environ.get('PGPORT', '5432')
    )

def create_tables():
    """如果資料表不存在，則建立它們"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 建立 costs 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS costs (
                location VARCHAR(255) PRIMARY KEY,
                weekday_cost INTEGER,
                holiday_cost INTEGER
            )
        """)

        # 建立 names 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS names (
                name VARCHAR(255) PRIMARY KEY
            )
        """)

        # 建立 records 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id SERIAL PRIMARY KEY,
                date VARCHAR(255),
                name VARCHAR(255),
                location VARCHAR(255),
                cost INTEGER
            )
        """)
        
        conn.commit()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error creating tables: {error}")
    finally:
        if conn is not None:
            conn.close()

# 在應用程式啟動時建立資料表
create_tables()

# --- 核心邏輯函式，已從檔案讀寫修改為資料庫操作 ---

# Function to read costs from the database
def load_costs_from_db():
    costs = {}
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT location, weekday_cost, holiday_cost FROM costs")
        records = cur.fetchall()
        for loc, weekday_cost, holiday_cost in records:
            if weekday_cost is not None and holiday_cost is not None:
                costs[loc] = {"平日": weekday_cost, "假日": holiday_cost}
            elif weekday_cost is not None:
                costs[loc] = weekday_cost
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error loading costs: {error}")
    finally:
        if conn is not None:
            conn.close()
    return costs

# Function to save a cost to the database
def save_cost_to_db(location, weekday_cost, holiday_cost=None):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if holiday_cost is not None:
            cur.execute(
                "INSERT INTO costs (location, weekday_cost, holiday_cost) VALUES (%s, %s, %s) ON CONFLICT (location) DO UPDATE SET weekday_cost = EXCLUDED.weekday_cost, holiday_cost = EXCLUDED.holiday_cost",
                (location, weekday_cost, holiday_cost)
            )
        else:
            cur.execute(
                "INSERT INTO costs (location, weekday_cost) VALUES (%s, %s) ON CONFLICT (location) DO UPDATE SET weekday_cost = EXCLUDED.weekday_cost",
                (location, weekday_cost)
            )
        conn.commit()
        cur.close()
        return "success"
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error saving cost: {error}")
        return f"failed: {error}"
    finally:
        if conn is not None:
            conn.close()

# Function to read names from the database
def load_names_from_db():
    names = []
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM names")
        records = cur.fetchall()
        for record in records:
            names.append(record[0])
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error loading names: {error}")
    finally:
        if conn is not None:
            conn.close()
    return names

# Function to add a name to the database
def add_name_to_db(name):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO names (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
            (name,)
        )
        conn.commit()
        cur.close()
        return "success"
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error adding name: {error}")
        return f"failed: {error}"
    finally:
        if conn is not None:
            conn.close()

# Function to delete a name from the database
def delete_name_from_db(name):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM names WHERE name = %s", (name,))
        rows_deleted = cur.rowcount
        conn.commit()
        cur.close()
        return rows_deleted
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error deleting name: {error}")
        return 0
    finally:
        if conn is not None:
            conn.close()

# Function to delete a location from the database
def delete_location_from_db(location):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM costs WHERE location = %s", (location,))
        rows_deleted = cur.rowcount
        conn.commit()
        cur.close()
        return rows_deleted
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error deleting location: {error}")
        return 0
    finally:
        if conn is not None:
            conn.close()

# Function to add a record to the database
def add_record_to_db(date, name, location, cost):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO records (date, name, location, cost) VALUES (%s, %s, %s, %s)",
            (date, name, location, cost)
        )
        conn.commit()
        cur.close()
        return "success"
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error adding record: {error}")
        return f"failed: {error}"
    finally:
        if conn is not None:
            conn.close()

# Function to delete a record from the database
def delete_record_from_db(date, name):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM records WHERE date = %s AND name = %s",
            (date, name)
        )
        rows_deleted = cur.rowcount
        conn.commit()
        cur.close()
        return rows_deleted
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error deleting record: {error}")
        return 0
    finally:
        if conn is not None:
            conn.close()

# Function to calculate total cost for a user
def get_total_cost_for_name(target_name):
    total_cost = 0
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT cost FROM records WHERE name = %s", (target_name,))
        records = cur.fetchall()
        for record in records:
            total_cost += record[0]
        cur.close()
        return total_cost
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error getting total cost: {error}")
        return 0
    finally:
        if conn is not None:
            conn.close()


# --- Webhook 路由 ---

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

# --- 訊息處理函式 ---

@handler.add(MessageEvent)
def handle_message(event):
    try:
        if not isinstance(event.message, TextMessageContent):
            return
        
        user_message = event.message.text
        message_parts = user_message.split(' ')
        
        # All existing logic remains the same, but the reply part needs to change
        reply_text = "無法辨識的指令，請檢查格式。" # default reply

        # Handle '刪除' command
        if message_parts[0] == "刪除":
            if len(message_parts) >= 2:
                delete_type = message_parts[1]
                if delete_type == "地點":
                    if len(message_parts) == 3:
                        location_to_delete = message_parts[2]
                        rows_deleted = delete_location_from_db(location_to_delete)
                        if rows_deleted > 0:
                            reply_text = f"已成功刪除地點：{location_to_delete}"
                        else:
                            reply_text = f"找不到地點：{location_to_delete}"
                    else:
                        reply_text = "刪除地點指令格式錯誤！請使用「刪除 地點 地點名稱」"
                elif delete_type == "人名":
                    if len(message_parts) == 3:
                        name_to_delete = message_parts[2]
                        rows_deleted = delete_name_from_db(name_to_delete)
                        if rows_deleted > 0:
                            reply_text = f"已成功刪除人名：{name_to_delete}"
                        else:
                            reply_text = f"找不到人名：{name_to_delete}"
                    else:
                        reply_text = "刪除人名指令格式錯誤！請使用「刪除 人名 人名」"
                elif delete_type == "紀錄":
                    if len(message_parts) == 4:
                        date_to_delete = message_parts[2]
                        name_to_delete = message_parts[3]
                        date_only = date_to_delete.split('(')[0]
                        rows_deleted = delete_record_from_db(date_only, name_to_delete)
                        if rows_deleted > 0:
                            reply_text = f"已成功刪除 {date_only} {name_to_delete} 的紀錄。"
                        else:
                            reply_text = f"找不到 {date_only} {name_to_delete} 的紀錄。"
                    else:
                        reply_text = "刪除紀錄指令格式錯誤！請使用「刪除 紀錄 月/日(星期) 人名」"
                else:
                    reply_text = "刪除指令格式錯誤！請使用「刪除 地點/人名/紀錄...」"
            else:
                reply_text = "刪除指令格式錯誤！請使用「刪除 地點/人名...」"

        # Handle '清單' command
        elif message_parts[0] == "清單":
            if len(message_parts) == 2:
                list_type = message_parts[1]
                if list_type == "地點":
                    locations = load_costs_from_db()
                    if locations:
                        reply_text = "地點清單：\n"
                        for loc, cost in locations.items():
                            if isinstance(cost, dict):
                                reply_text += f"{loc}: 平日-{cost['平日']}, 假日-{cost['假日']}\n"
                            else:
                                reply_text += f"{loc}: {cost}\n"
                    else:
                        reply_text = "目前沒有任何地點紀錄。"
                elif list_type == "人名":
                    names = load_names_from_db()
                    if names:
                        reply_text = "人名清單：\n" + "\n".join(names)
                    else:
                        reply_text = "目前沒有任何人名紀錄。"
                else:
                    reply_text = "清單指令格式錯誤！請使用「清單 地點」或「清單 人名」。"
            else:
                reply_text = "清單指令格式錯誤！請使用「清單 地點」或「清單 人名」。"

        # Handle '新增' command
        elif message_parts[0] == "新增":
            if len(message_parts) == 3:
                location = message_parts[1]
                try:
                    cost = int(message_parts[2])
                    result = save_cost_to_db(location, cost)
                    if result == "success":
                        reply_text = f"已新增/更新地點：{location}，金額：{cost}"
                    else:
                        reply_text = f"新增地點失敗：{result}"
                except ValueError:
                    reply_text = "錯誤：金額必須是數字！"
            elif len(message_parts) == 6 and message_parts[2] == "平日" and message_parts[4] == "假日":
                location = message_parts[1]
                try:
                    weekday_cost = int(message_parts[3])
                    holiday_cost = int(message_parts[5])
                    result = save_cost_to_db(location, weekday_cost, holiday_cost)
                    if result == "success":
                        reply_text = f"已新增/更新地點：{location}，平日：{weekday_cost}，假日：{holiday_cost}"
                    else:
                        reply_text = f"新增地點失敗：{result}"
                except ValueError:
                    reply_text = "錯誤：平日或假日金額必須是數字！"
            else:
                reply_text = "新增指令格式錯誤！請使用「新增 地點 金額」或「新增 地點 平日 金額 假日 金額」"
        
        # Handle '新增人名' command
        elif message_parts[0] == "新增人名":
            if len(message_parts) == 2:
                name_to_add = message_parts[1]
                result = add_name_to_db(name_to_add)
                if result == "success":
                    reply_text = f"已成功新增人名：{name_to_add}"
                else:
                    reply_text = f"新增人名失敗：{result}"
            else:
                reply_text = "新增人名指令格式錯誤！請使用「新增人名 人名」的格式。"
        
        # Handle '統計' command
        elif message_parts[0] == "統計":
            if len(message_parts) == 2:
                target_name = message_parts[1]
                total_cost = get_total_cost_for_name(target_name)
                
                if total_cost > 0:
                    reply_text = f"{target_name} 的通路費總計為：{total_cost}"
                else:
                    reply_text = f"找不到 {target_name} 的任何通路費紀錄。"
            else:
                reply_text = "統計指令格式錯誤！請使用「統計 人名」的格式。"
        
        elif len(message_parts) == 3:
            # Handle '日期 人名 地點' format
            try:
                location_costs = load_costs_from_db()
                date_only = message_parts[0].split('(')[0]
                
                try:
                    current_year = datetime.now().year
                    full_date_string = f"{date_only}/{current_year}"
                    date_object = datetime.strptime(full_date_string, "%m/%d/%Y")
                    weekday_number = date_object.weekday()
                    is_weekend = weekday_number >= 5
                except ValueError:
                    reply_text = "日期格式錯誤！請使用「月/日」或「月/日(星期)」的格式。"
                    # The reply message is sent outside the try block
                    raise Exception(reply_text) # Raise an exception to handle the reply outside
                
                name = message_parts[1]
                location = message_parts[2]
                
                if location in location_costs:
                    cost_value = location_costs[location]
                    if isinstance(cost_value, dict):
                        cost = cost_value["假日"] if is_weekend else cost_value["平日"]
                    else:
                        cost = cost_value
                else:
                    cost = 0 # 找不到地點則設為 0
                
                result = add_record_to_db(date_only, name, location, cost)
                
                if result == "success":
                    reply_text = f"已成功紀錄：{date_only}, {name}, {location}, 金額: {cost}"
                else:
                    reply_text = f"紀錄失敗：{result}"

            except IndexError:
                reply_text = "格式錯誤！請使用「日期 人名 地點」的格式。"
        
        # Send the final reply
        with ApiClient(configuration) as api_client:
            line_bot_api_v3 = MessagingApi(api_client)
            line_bot_api_v3.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )

    except Exception as e:
        # If any unexpected error occurs, reply with the error message
        with ApiClient(configuration) as api_client:
            line_bot_api_v3 = MessagingApi(api_client)
            line_bot_api_v3.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"發生錯誤：{e}")]
                )
            )

# Main entry point
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=os.getenv('PORT'))