import os
from dotenv import load_dotenv
from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
from datetime import datetime

# 確保在本地開發時可以從 .env 檔案載入變數
load_dotenv()

# 從環境變數中讀取金鑰
line_channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
line_channel_secret = os.environ.get('LINE_CHANNEL_SECRET') # 修正：新增這行

# 使用從環境變數讀取到的金鑰來初始化 LineBotApi 和 WebhookHandler
line_bot_api = LineBotApi(line_channel_access_token)
handler = WebhookHandler(line_channel_secret)

app = Flask(__name__)

# Webhook 路由：這是 LINE 傳送訊息過來的網址
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

# 訊息處理器
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="我收到訊息了！正在處理中...")
    )
    user_message = event.message.text
    message_parts = user_message.split(' ')

    # 讀取 costs.txt 檔案並回傳字典的函式
    def load_costs():
        costs = {}
        try:
            with open('costs.txt', 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(':')
                    location = parts[0]
                    cost_str = parts[1]
                    if "平日" in cost_str or "假日" in cost_str:
                        weekday_cost_str, holiday_cost_str = cost_str.split(',')
                        weekday_cost = int(weekday_cost_str.split('-')[1])
                        holiday_cost = int(holiday_cost_str.split('-')[1])
                        costs[location] = {"平日": weekday_cost, "假日": holiday_cost}
                    else:
                        costs[location] = int(cost_str)
        except FileNotFoundError:
            return {}
        return costs

    # 將字典內容寫回檔案的函式
    def save_costs(costs_dict):
        with open('costs.txt', 'w', encoding='utf-8') as file:
            for location, cost_value in costs_dict.items():
                if isinstance(cost_value, dict):
                    line = f"{location}:平日-{cost_value['平日']},假日-{cost_value['假日']}\n"
                else:
                    line = f"{location}:{cost_value}\n"
                file.write(line)
    
    # 處理新增人名
    def add_name(name):
        try:
            with open('names.txt', 'a', encoding='utf-8') as file:
                file.write(f"{name}\n")
            return f"已成功新增人名：{name}"
        except Exception as e:
            return f"新增人名失敗：{e}"

    # 讀取人名列表
    def load_names():
        names = []
        try:
            with open('names.txt', 'r', encoding='utf-8') as file:
                for line in file:
                    names.append(line.strip())
        except FileNotFoundError:
            return []
        return names

    # 處理刪除紀錄
    def delete_record(date_to_delete, name_to_delete):
        try:
            with open('record.txt', 'r', encoding='utf-8') as file:
                lines = file.readlines()
            
            new_lines = []
            found = False
            
            # 保留標題列
            if lines and lines[0].startswith("日期,人名,地點,金額"):
                new_lines.append(lines[0])
                data_lines = lines[1:]
            else:
                data_lines = lines

            for line in data_lines:
                parts = line.strip().split(',')
                if len(parts) >= 2 and parts[0] == date_to_delete and parts[1] == name_to_delete:
                    found = True
                else:
                    new_lines.append(line)
            
            if found:
                with open('record.txt', 'w', encoding='utf-8') as file:
                    file.writelines(new_lines)
                return f"已成功刪除 {date_to_delete} {name_to_delete} 的紀錄。"
            else:
                return f"找不到 {date_to_delete} {name_to_delete} 的紀錄。"
        except FileNotFoundError:
            return "找不到 record.txt 檔案，無法刪除。"
        except Exception as e:
            return f"刪除失敗：{e}"

    # 處理刪除指令
    if message_parts[0] == "刪除":
        if len(message_parts) >= 2:
            delete_type = message_parts[1]
            if delete_type == "地點":
                if len(message_parts) == 3:
                    location_to_delete = message_parts[2]
                    current_costs = load_costs()
                    if location_to_delete in current_costs:
                        del current_costs[location_to_delete]
                        save_costs(current_costs)
                        reply_text = f"已成功刪除地點：{location_to_delete}"
                    else:
                        reply_text = f"找不到地點：{location_to_delete}"
                else:
                    reply_text = "刪除地點指令格式錯誤！請使用「刪除 地點 地點名稱」"
            elif delete_type == "人名":
                if len(message_parts) == 3:
                    name_to_delete = message_parts[2]
                    names = load_names()
                    if name_to_delete in names:
                        names.remove(name_to_delete)
                        try:
                            with open('names.txt', 'w', encoding='utf-8') as file:
                                for name in names:
                                    file.write(f"{name}\n")
                            reply_text = f"已成功刪除人名：{name_to_delete}"
                        except Exception as e:
                            reply_text = f"刪除人名失敗：{e}"
                    else:
                        reply_text = f"找不到人名：{name_to_delete}"
                else:
                    reply_text = "刪除人名指令格式錯誤！請使用「刪除 人名 人名」"
            elif delete_type == "紀錄":
                if len(message_parts) == 4:
                    date_to_delete = message_parts[2]
                    name_to_delete = message_parts[3]
                    date_only = date_to_delete.split('(')[0]
                    reply_text = delete_record(date_only, name_to_delete)
                else:
                    reply_text = "刪除紀錄指令格式錯誤！請使用「刪除 紀錄 月/日(星期) 人名」"
            else:
                reply_text = "刪除指令格式錯誤！請使用「刪除 地點/人名/紀錄...」"
        else:
            reply_text = "刪除指令格式錯誤！請使用「刪除 地點/人名...」"
        
        reply_message = TextSendMessage(text=reply_text)
        line_bot_api.reply_message(event.reply_token, reply_message)


    # 處理清單指令
    elif message_parts[0] == "清單":
        if len(message_parts) == 2:
            list_type = message_parts[1]
            if list_type == "地點":
                locations = load_costs()
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
                names = load_names()
                if names:
                    reply_text = "人名清單：\n" + "\n".join(names)
                else:
                    reply_text = "目前沒有任何人名紀錄。"
            else:
                reply_text = "清單指令格式錯誤！請使用「清單 地點」或「清單 人名」。"
        else:
            reply_text = "清單指令格式錯誤！請使用「清單 地點」或「清單 人名」。"
        
        reply_message = TextSendMessage(text=reply_text)
        line_bot_api.reply_message(event.reply_token, reply_message)

    # 處理新增指令
    elif message_parts[0] == "新增":
        current_costs = load_costs()
        if len(message_parts) == 3:
            location = message_parts[1]
            try:
                cost = int(message_parts[2])
                current_costs[location] = cost
                save_costs(current_costs)
                reply_text = f"已新增/更新地點：{location}，金額：{cost}"
            except ValueError:
                reply_text = "錯誤：金額必須是數字！"
        elif len(message_parts) == 6 and message_parts[2] == "平日" and message_parts[4] == "假日":
            location = message_parts[1]
            try:
                weekday_cost = int(message_parts[3])
                holiday_cost = int(message_parts[5])
                current_costs[location] = {"平日": weekday_cost, "假日": holiday_cost}
                save_costs(current_costs)
                reply_text = f"已新增/更新地點：{location}，平日：{weekday_cost}，假日：{holiday_cost}"
            except ValueError:
                reply_text = "錯誤：平日或假日金額必須是數字！"
        else:
            reply_text = "新增指令格式錯誤！請使用「新增 地點 金額」或「新增 地點 平日 金額 假日 金額」"
        reply_message = TextSendMessage(text=reply_text)
        line_bot_api.reply_message(event.reply_token, reply_message)
    
    # 處理新增人名指令
    elif message_parts[0] == "新增人名":
        if len(message_parts) == 2:
            name_to_add = message_parts[1]
            reply_text = add_name(name_to_add)
        else:
            reply_text = "新增人名指令格式錯誤！請使用「新增人名 人名」的格式。"
        reply_message = TextSendMessage(text=reply_text)
        line_bot_api.reply_message(event.reply_token, reply_message)
    
    # 處理統計指令
    elif message_parts[0] == "統計":
        if len(message_parts) == 2:
            target_name = message_parts[1]
            total_cost = 0
            found_records = False
            
            try:
                with open('record.txt', 'r', encoding='utf-8') as file:
                    for line in file:
                        if line.startswith("日期,人名,地點,金額"):
                            continue
                        parts = line.strip().split(',')
                        if len(parts) == 4 and parts[1] == target_name:
                            try:
                                cost = int(parts[3])
                                total_cost += cost
                                found_records = True
                            except ValueError:
                                continue
                
                if found_records:
                    reply_text = f"{target_name} 的通路費總計為：{total_cost}"
                else:
                    reply_text = f"找不到 {target_name} 的任何通路費紀錄。"
            except FileNotFoundError:
                reply_text = "找不到 record.txt 檔案，無法進行統計。"
        else:
            reply_text = "統計指令格式錯誤！請使用「統計 人名」的格式。"
        reply_message = TextSendMessage(text=reply_text)
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif len(message_parts) == 3:
        # 處理「日期 人名 地點」的紀錄格式
        try:
            location_costs_reloaded = load_costs()
            date_only = message_parts[0].split('(')[0]
            current_year = datetime.now().year
            full_date_string = f"{date_only}/{current_year}"
            
            try:
                date_object = datetime.strptime(full_date_string, "%m/%d/%Y")
                weekday_number = date_object.weekday()
                is_weekend = weekday_number >= 5
            except ValueError:
                reply_message = TextSendMessage(text="日期格式錯誤！請使用「月/日」或「月/日(星期)」的格式。")
                line_bot_api.reply_message(event.reply_token, reply_message)
                return

            name = message_parts[1]
            location = message_parts[2]
            if location in location_costs_reloaded:
                cost_value = location_costs_reloaded[location]
                if isinstance(cost_value, dict):
                    if is_weekend:
                        cost = cost_value["假日"]
                    else:
                        cost = cost_value["平日"]
                else:
                    cost = cost_value
            else:
                cost = "未知金額"

            file_exists = os.path.isfile('record.txt')
            file_is_empty = not file_exists or os.stat('record.txt').st_size == 0
            record_line = f"{date_only},{name},{location},{cost}\n"

            with open('record.txt', 'a', encoding='utf-8') as file:
                if file_is_empty:
                    file.write("日期,人名,地點,金額\n")
                file.write(record_line)
            
            reply_message = TextSendMessage(text=f"已成功紀錄：{date_only}, {name}, {location}")
            line_bot_api.reply_message(event.reply_token, reply_message)

        except IndexError:
            reply_message = TextSendMessage(text="格式錯誤！請使用「日期 人名 地點」的格式。")
            line_bot_api.reply_message(event.reply_token, reply_message)
    
    else:
        # 如果不是任何指令，就將原訊息回傳
        reply_message = TextSendMessage(text=user_message)
        line_bot_api.reply_message(event.reply_token, reply_message)