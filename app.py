import os
from dotenv import load_dotenv
from flask import Flask, request, abort
import psycopg2
from psycopg2 import sql
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

load_dotenv()

line_channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
line_channel_secret = os.environ.get('LINE_CHANNEL_SECRET')

app = Flask(__name__)

configuration = Configuration(access_token=line_channel_access_token)
handler = WebhookHandler(line_channel_secret)

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('PGHOST'),
        database=os.environ.get('PGDATABASE'),
        user=os.environ.get('PGUSER'),
        password=os.environ.get('PGPASSWORD'),
        port=os.environ.get('PGPORT', '5432')
    )

def create_tables():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS costs (
                location VARCHAR(255) PRIMARY KEY,
                weekday_cost INTEGER,
                holiday_cost INTEGER
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS names (
                name VARCHAR(255) PRIMARY KEY
            )
        """)
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

create_tables()

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

def get_monthly_cost_for_name(target_name, target_month):
    total_cost = 0
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT cost FROM records WHERE name = %s AND date LIKE %s", (target_name, f'{target_month}/%',))
        records = cur.fetchall()
        for record in records:
            total_cost += record[0]
        cur.close()
        return total_cost
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error getting monthly cost for name: {error}")
        return 0
    finally:
        if conn is not None:
            conn.close()

def get_monthly_summary(target_month, target_year):
    summary = {}
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name, cost FROM records WHERE date LIKE %s", (f'{target_month}/%',))
        records = cur.fetchall()
        if not records:
            return None
        for name, cost in records:
            summary[name] = summary.get(name, 0) + cost
        cur.close()
        return summary
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error getting monthly summary: {error}")
        return None
    finally:
        if conn is not None:
            conn.close()

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

@handler.add(MessageEvent)
def handle_message(event):
    if not isinstance(event.message, TextMessageContent):
        return
    user_message = event.message.text.strip()
    message_parts = user_message.split(' ')
    reply_text = "無法辨識的指令，請檢查格式。需要協助請輸入「說明書」或「說明」。"
    
    try:
        if message_parts[0] == "說明書" or message_parts[0] == "說明":
            reply_text = """通路費記錄小幫手使用說明：

所有指令都以文字訊息發送，參數之間請使用半形空格。

✅ 主要功能與指令

👉 新增地點
- 新增 地點 金額：新增或更新一個地點的通路費。
  - 例：新增 彰化 150
- 新增 地點 平日 金額 假日 金額：新增或更新平日與假日金額。
  - 例：新增 彰化 平日 150 假日 200

👉 新增人名
- 新增人名 人名：新增一個使用者名字。
  - 例：新增人名 小明

👉 記錄通路費
- 月/日 人名 地點：自動套用地點預設金額。
  - 例：12/25(一) 小明 彰化
- 月/日 人名 地點 金額：強制使用指定金額。
  - 例：12/25(一) 小明 彰化 180

👉 查詢清單
- 清單 地點：顯示所有已記錄的地點與費用。
- 清單 人名：顯示所有已記錄的使用者。

👉 統計費用
- 統計 人名：計算某位使用者所有通路費總和。
  - 例：統計 小明
- 統計 月份：計算某個月份所有使用者通路費總和。
  - 例：統計 12月
- 統計 人名 月份：計算某位使用者在指定月份的總和。
  - 例：統計 小明 12月

👉 刪除紀錄
- 刪除 地點 地點名稱：刪除地點紀錄。
  - 例：刪除 地點 彰化
- 刪除 人名 人名：刪除使用者名字。
  - 例：刪除 人名 小明
- 刪除 紀錄 日期 人名：刪除某天某位使用者的紀錄。
  - 例：刪除 紀錄 12/25 小明"""
            
        elif message_parts[0] == "刪除":
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
        
        elif message_parts[0] == "統計":
            if len(message_parts) == 2:
                if message_parts[1].endswith("月"):
                    try:
                        month_str = message_parts[1].replace("月", "")
                        target_month = int(month_str)
                        current_year = datetime.now().year
                        current_month = datetime.now().month
                        if target_month > current_month:
                            target_year = current_year - 1
                        else:
                            target_year = current_year
                        summary = get_monthly_summary(target_month, target_year)
                        if summary:
                            reply_text = f"{target_year}年{target_month}月總通路費統計：\n"
                            for name, total_cost in summary.items():
                                reply_text += f"{name}: {total_cost}\n"
                            reply_text += "\n若需刪除紀錄，請使用「刪除 紀錄 月/日(星期) 人名」"
                        else:
                            reply_text = f"{target_year}年{target_month}月沒有任何通路費紀錄。"
                    except ValueError:
                        reply_text = "統計月份指令格式錯誤！請使用「統計 月份」(例如：統計 12月)。"
                else:
                    target_name = message_parts[1]
                    total_cost = get_total_cost_for_name(target_name)
                    if total_cost > 0:
                        reply_text = f"{target_name} 的通路費總計為：{total_cost}"
                    else:
                        reply_text = f"找不到 {target_name} 的任何通路費紀錄。"
            elif len(message_parts) == 3:
                target_name = message_parts[1]
                target_month_str = message_parts[2]
                if target_month_str.endswith("月"):
                    try:
                        target_month = int(target_month_str.replace("月", ""))
                        total_cost = get_monthly_cost_for_name(target_name, target_month)
                        if total_cost > 0:
                            reply_text = f"{target_name} 在 {target_month}月 的通路費總計為：{total_cost}"
                        else:
                            reply_text = f"找不到 {target_name} 在 {target_month}月 的任何通路費紀錄。"
                    except ValueError:
                        reply_text = "統計指令格式錯誤！月份必須是數字。(例如：統計 小明 12月)。"
                else:
                    reply_text = "統計指令格式錯誤！月份必須是「數字+月」。(例如：統計 小明 12月)。"
            else:
                reply_text = "統計指令格式錯誤！請使用「統計 人名」、「統計 月份」或「統計 人名 月份」。"
        
        elif len(message_parts) >= 3:
            try:
                date_only = message_parts[0].split('(')[0]
                try:
                    current_year = datetime.now().year
                    full_date_string = f"{date_only}/{current_year}"
                    date_object = datetime.strptime(full_date_string, "%m/%d/%Y")
                    weekday_number = date_object.weekday()
                    is_weekend = weekday_number >= 5
                except ValueError:
                    reply_text = "日期格式錯誤！請使用「月/日」或「月/日(星期)」的格式。"
                    raise Exception(reply_text)
                name = message_parts[1]
                location = message_parts[2]
                cost = None
                if len(message_parts) == 4:
                    try:
                        cost = int(message_parts[3])
                    except ValueError:
                        reply_text = "錯誤：金額必須是數字！"
                        raise Exception(reply_text)
                else:
                    location_costs = load_costs_from_db()
                    if location in location_costs:
                        cost_value = location_costs[location]
                        if isinstance(cost_value, dict):
                            cost = cost_value["假日"] if is_weekend else cost_value["平日"]
                        else:
                            cost = cost_value
                    else:
                        cost = 0
                if cost is not None:
                    result = add_record_to_db(date_only, name, location, cost)
                    if result == "success":
                        reply_text = f"已成功紀錄：{date_only}, {name}, {location}, 金額: {cost}"
                    else:
                        reply_text = f"紀錄失敗：{result}"
            except IndexError:
                reply_text = "格式錯誤！請使用「日期 人名 地點」或「日期 人名 地點 金額」的格式。"
    
    except Exception as e:
        reply_text = f"處理您的訊息時發生未知錯誤。錯誤訊息：{e}"

    # Send the final reply
    with ApiClient(configuration) as api_client:
        line_bot_api_v3 = MessagingApi(api_client)
        line_bot_api_v3.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=os.getenv('PORT'))