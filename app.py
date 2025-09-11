@handler.add(MessageEvent)
def handle_message(event):
    if not isinstance(event.message, TextMessageContent):
        return
    user_message = event.message.text.strip()
    message_parts = user_message.split(' ')
    reply_text = "無法辨識的指令，請檢查格式。"
    
    try:
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
            if len(message_parts) == 3:
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
                reply_text = "統計指令格式錯誤！請使用「統計 人名 月份」。"
        
        # Handle '日期 人名 地點' and '日期 人名 地點 金額' format
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