import importlib
import subprocess
import os

# 自动尝试导入，如果失败自动安装
def safe_import(module_name, package_name=None):
    try:
        return importlib.import_module(module_name)
    except ImportError:
        print(f"{module_name} 未安装，正在自动安装...")
        subprocess.check_call(['pip', 'install', package_name or module_name])
        return importlib.import_module(module_name)

# 使用 safe_import 导入常用模块
requests = safe_import('requests')
opencc = safe_import('opencc', 'opencc-python-reimplemented')
pd = safe_import('pandas')
bs4 = safe_import('bs4', 'beautifulsoup4')
denv = safe_import('dotenv')
from bs4 import BeautifulSoup

import json
import html
import argparse
from datetime import datetime, timedelta
from io import StringIO
from dotenv import load_dotenv

from data_source.ApiException import ApiException
from opencc import OpenCC

# 读取环境变量
load_dotenv()
PROXY_URL = os.getenv("PROXY_URL")

proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else {}

def update_mtr_stations():
    # 下载并生成 mtr_stations.json
    mtr_stations = get_mtr_stations()
    with open("mtr_stations.json", "w", encoding="utf-8") as f:
        json.dump(mtr_stations, f, ensure_ascii=False, indent=4)

def update_mtr_line_info():
    url = 'https://opendata.mtr.com.hk/data/mtr_lines_and_stations.csv'
    print(f'更新 mtr_lines_and_stations 文件: {url}')
    r = requests.get(url)
    with open('mtr_lines_and_stations.csv', 'w', encoding='utf-8') as f:
        f.write(r.content.decode('utf-8'))
    convert_to_json("mtr_lines_and_stations.json")

DATA_FILES = {
    "mtr_stations.json": update_mtr_stations,
    "mtr_lines_and_stations.csv": update_mtr_line_info,
    "mtr_lines_and_stations.json": update_mtr_line_info,
}

_data_checked = False

def ensure_data_files():
    global _data_checked
    if _data_checked:
        return
    for file_name, updater in DATA_FILES.items():
        if not os.path.exists(file_name):
            print(f"{file_name} 缺失，正在自动更新...")
            updater()
    _data_checked = True

def get_mtr_stations():
    url = 'https://www.mtr.com.hk/st/data/fcdata_json.php'
    print("Updating mtr_stations.json from %s" % url)
    response = requests.get(url,proxies=proxies,timeout=10)
    data = response.json()

    stations = data["faresaver"]['facilities']

    for station in stations:
        station["STATION_NAME_TC"] = html.unescape(
            station["STATION_NAME_TC"]) if station["STATION_NAME_TC"] else None
        station["SAVERTWO_TC"] = html.unescape(
            station["SAVERTWO_TC"]) if station["SAVERTWO_TC"] else None
        station["SAVERONE_TC"] = html.unescape(
            station["SAVERONE_TC"]) if station["SAVERONE_TC"] else None
        station["TOILET_TC"] = html.unescape(
            station["TOILET_TC"]) if station["TOILET_TC"] else None
        station["LINE"] = html.unescape(
            station["LINE"]) if station["LINE"] else None

    return stations
    
def convert_to_json(json_file):
    # 读取CSV内容
    data = pd.read_csv('mtr_lines_and_stations.csv')

    # 转换为JSON格式
    json_data = data.to_json(orient='records')

    # 解析JSON数据
    json_data = json.loads(json_data)

    filtered_json_data = []

    for i in json_data:
        if i['Line Code'] is not None:
            i["Sequence"] = int(i["Sequence"])
            i["Station ID"] = int(i["Station ID"])
            filtered_json_data.append(i)


    json_data = filtered_json_data
    # 将JSON数据保存到文件
    with open(json_file, 'w', encoding='utf-8') as file:
        json.dump(json_data, file, ensure_ascii=False, indent=4)

try:
    with open("mtr_stations.json", "r", encoding="utf-8") as f:
        mtr_stations = json.load(f)
except:
    mtr_stations = get_mtr_stations()
    with open("mtr_stations.json", "w", encoding="utf-8") as f:
        json.dump(mtr_stations, f, ensure_ascii=False, indent=4)

try:
    with open("mtr_lines_and_stations.json", "r", encoding="utf-8") as f:
        line_info = json.load(f)
#未加载成功时尝试从网上获取这个重新生成
except:
    url = 'https://opendata.mtr.com.hk/data/mtr_lines_and_stations.csv'
    print(f'Updating mtr_lines_and_stations from {url}')
    #下载文件
    r = requests.get(url)
    #将二进制文件转为字符串
    data = str(r.content, encoding="utf-8")
    #将字符串转为文件对象
    with open('mtr_lines_and_stations.csv', 'w', encoding='utf-8') as f:
        f.write(data)
    json_file = 'mtr_lines_and_stations.json'
    convert_to_json(json_file)
    with open("mtr_lines_and_stations.json", "r", encoding="utf-8") as f:
        line_info = json.load(f)

def get_station_id(station_name):
    with open("mtr_stations.json", "r", encoding="utf-8") as f:
        stations = json.load(f)

    simplified_station_name = station_name.replace(" ", "").replace("-", "").lower()

    #读取line_info 循环 检查Station Code是否有匹配的
    for station_dict in line_info:
        if station_dict['Station Code'].lower() == simplified_station_name or station_dict['English Name'].replace(" ", "").replace("-", "").lower() == simplified_station_name or station_dict['Chinese Name'].replace(" ", "").replace("-", "").lower() == simplified_station_name:
            return str(int(station_dict['Station ID']))

    return None

def get_ticket_price(from_station_id, to_station_id, lang="C"):
    if lang not in ["C", "E"]:
        raise ValueError("Invalid lang parameter. Only 'C' (Chinese) or 'E' (English) are allowed.")
    
    url = f"https://www.mtr.com.hk/share/customer/jp/api/HRRoutes/?o={from_station_id}&d={to_station_id}&lang={lang}"
    print(url)
    response = requests.get(url,proxies=proxies,timeout=10)
    data = response.json()

    ticket_prices = []
    station_info = {}

    firstTrainTime = data['firstTrain']
    lastTrainTime = data['lastTrain']

    firstLastTrainRemark = data['firstLastTrainRemark']
    stationOpeningHours = data['stationOpeningHours']

    for route in data['routes']:
        route_name = route['routeName']
        time = route['time']

        for fare in route['fares']:
            fare_title = fare.get('fareTitle')
            fare_info = fare.get('fareInfo', {})

            if fare_title in ['standardClass'] and 'adult' in fare_info:

                adult_price = fare_info['adult']['octopus']
                student_price = fare_info.get('student', {}).get('octopus')

                ticket_prices.append({
                    'fareTitle': fare_title,
                    'routeName': route_name,
                    'fareTitle': fare_title,
                    'adultPrice': adult_price,
                    'studentPrice': student_price,
                    'time': time,
                    'path': route['path']
                })

    station_info['firstTrainTime'] = firstTrainTime
    station_info['lastTrainTime'] = lastTrainTime
    station_info['firstLastTrainRemark'] = firstLastTrainRemark
    station_info['stationOpeningHours'] = stationOpeningHours
    return ticket_prices, station_info



def convert_to_traditional_chinese(station_name):
    cc = OpenCC('s2twp')
    return cc.convert(station_name)


def format_station_info(station_info,lang):
    line = station_info["LINE"]
    station_name_tc = station_info["STATION_NAME_TC"]
    station_name_en = station_info["STATION_NAME_EN"]
    if lang == "C":
        formatted_info = f"{station_name_tc}"
    elif lang == "E":
        formatted_info = f"{station_name_en}"

    return formatted_info


def query_station_info(station_id,lang):
    station_info = get_station_info(station_id)

    if station_info is None:
        raise ApiException("搵唔到指定嘅車站，請檢查輸入嘅車站 ID 是否正確。")
    else:
        formatted_info = format_station_info(station_info,lang)
        return formatted_info


def get_station_info(station_id):
    with open("mtr_stations.json", "r", encoding="utf-8") as f:
        stations = json.load(f)

    for station in stations:
        if station["STATION_ID"] == station_id:
            return station

    return None


line_dict = {
    'AEL': ["機場快綫","Airport Express"],
    'TCL': ["東涌綫","Tung Chung Line"],
    'DRL': ["迪士尼綫","Disneyland Resort Line"],
    'EAL': ["東鐵綫","East Rail Line"],
    'ISL': ["港島綫","Island Line"],
    'KTL': ["觀塘綫","Kwun Tong Line"],
    'SIL': ["南港島綫","South Island Line"],
    'TKL': ["將軍澳綫","Tseung Kwan O Line"],
    'TWL': ["荃灣綫","Tseun Wan Line"],
    'TML': ["屯馬綫","Tuen Ma Line"]
}

def query_specific_line(src,dst,time,lang):
    result = src
    for idx,line in enumerate(time['links']):
        if lang == "C":
            result += f' > {line_dict[line][0]}'
        elif lang == "E":
            result += f' > {line_dict[line][1]}'
            
        if time['interchange'] and idx < len(time['interchange']):
            result += f' > {query_station_info(time["interchange"][idx],lang)}'
    result += f' > {dst}\n'
    return result


def get_station_abbreviation(station_id):
    matches = set()
    for station_dict in line_info:
        if str(station_dict['Station ID']) == str(station_id):
            matches.add((station_dict['Line Code'], station_dict['Station Code']))
    return list(matches)


def get_station_names(abbreviation, lang="EN"):
    matches = []
    for station_dict in line_info:
        if station_dict['Station Code'].lower() == abbreviation.lower():
            if lang.upper() == "TC":
                name = station_dict['Chinese Name']
            else:
                name = station_dict['English Name']
            matches.append((station_dict['Line Code'], name))
    return matches



def get_realtime_arrivals(line, station,station_name,line_name, lang="EN"):
    url = f"https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php?line={line}&sta={station}&lang={lang}"
    print(url)
    response = requests.get(url,proxies=proxies,timeout=10)
    data = response.json()

    if response.status_code == 200:
        if "data" in data and f"{line}-{station}" in data["data"]:
            result = ""

            if "UP" in data["data"][f"{line}-{station}"]:
                arrivals_up = data["data"][f"{line}-{station}"]["UP"]
                if arrivals_up:
                    if lang.upper() == "TC":
                        result += f"{station_name}，{line_name}，上行:\n"
                        for arrival in arrivals_up:
                            time = arrival["time"][arrival["time"].find(' ')+1:]
                            # time = arrival["time"]
                            destination = arrival["dest"]
                            destination_name = get_station_names(destination, lang)
                            if destination_name:
                                destination = destination_name[0][1]
                            platform = arrival["plat"]
                            result += f"{time}，于 {platform} 月台，開往：{destination}\n"
                    else:
                        result += f"{station_name},{line_name},Up:\n"
                        for arrival in arrivals_up:
                            time = arrival["time"][arrival["time"].find(' ')+1:]
                            #time = arrival["time"]
                            destination = arrival["dest"]
                            destination_name = get_station_names(destination, lang)
                            if destination_name:
                                destination = destination_name[0][1]
                            platform = arrival["plat"]
                            result += f"{time},At Platform:{platform},To:{destination}\n"

                else:
                    if lang.upper() == "TC":
                        result += "沒有找到上行實時到站信息。\n"
                    else:
                        result += "No real-time arrivals found (Up).\n"

            if "DOWN" in data["data"][f"{line}-{station}"]:
                arrivals_down = data["data"][f"{line}-{station}"]["DOWN"]
                if arrivals_down:
                    if lang.upper() == "TC":
                        result += f"{station_name}，{line_name}，下行:\n"
                        for arrival in arrivals_down:
                            time = arrival["time"][arrival["time"].find(' ')+1:]
                            destination = arrival["dest"]
                            destination_name = get_station_names(destination, lang)
                            if destination_name:
                                destination = destination_name[0][1]
                            platform = arrival["plat"]
                            result += f"{time}，于 {platform} 月台，開往：{destination}\n"
                            #result += f"時間：{time}，目的地：{destination}，站台號：{platform}\n"
                    else:
                        result += f"{station_name},{line_name},Down:\n"
                        for arrival in arrivals_down:
                            time = arrival["time"][arrival["time"].find(' ')+1:]
                            destination = arrival["dest"]
                            destination_name = get_station_names(destination, lang)
                            if destination_name:
                                destination = destination_name[0][1]
                            platform = arrival["plat"]
                            result += f"{time},At Platform:{platform},To:{destination}\n"
                            #result += f"Time: {time}, Destination: {destination}, Platform: {platform}\n"

                else:
                    if lang.upper() == "TC":
                        result += "沒有找到下行實時到站信息。\n"
                    else:
                        result += "No real-time arrivals found (Down).\n"

            if result:
                return result.strip()
            else:
                if lang.upper() == "TC":
                    return "沒有找到實時到站信息。"
                else:
                    return "No real-time arrivals found."

        else:
            if lang.upper() == "TC":
                return "該線路和車站沒有可用數據。"
            else:
                return "No data available for the specified line and station."

    else:
        if lang.upper() == "TC":
            return "獲取實時數據時發生錯誤。"
        else:
            return "Error occurred while fetching real-time data."
        
def format_station_info_with_code(station_info,lang):
    line = station_info["LINE"]
    station_name_tc = station_info["STATION_NAME_TC"]
    station_name_en = station_info["STATION_NAME_EN"]
    station_id = int(station_info["STATION_ID"])

    # 从 line_info 找 station_code
    station_code = None
    for item in line_info:
        if int(item["Station ID"]) == station_id:
            station_code = item["Station Code"]
            break

    if not station_code:
        station_code = str(station_id)  # 找不到就用ID代替

    #formatted_info = f"[{line}] {station_name_tc} ({station_name_en}) [{station_code}]"
    if(lang == "C"):
        formatted_info = f"{station_name_tc} [{station_code}]"
    elif(lang == "E"):
        formatted_info = f"{station_name_en} [{station_code}]"
    return formatted_info

def query_ticket_price(from_station, to_station, tg_inline_mode=False, lang="C"):
    ensure_data_files()  # 确保数据文件存在
    return _query_ticket_price_internal(from_station, to_station, tg_inline_mode, lang)

def _query_ticket_price_internal(from_station_name, to_station_name, tg_inline_mode=False, lang="C"):
    output_text = ""
    title_msg = ""
    from_station_id = get_station_id(from_station_name)
    to_station_id = get_station_id(to_station_name)

    if from_station_id is None or to_station_id is None:
        traditional_from_station_name = convert_to_traditional_chinese(
            from_station_name)
        traditional_to_station_name = convert_to_traditional_chinese(
            to_station_name)

        if traditional_from_station_name != from_station_name:
            from_station_id = get_station_id(traditional_from_station_name)

        if traditional_to_station_name != to_station_name:
            to_station_id = get_station_id(traditional_to_station_name)

    if from_station_id is None or to_station_id is None:
        if lang == "C":
            raise ApiException("無法找到指定嘅車站，請檢查輸入嘅車站名稱是否正確。")
        elif lang == "E":
            raise ApiException("Unable to find the specified stations. Please check if the station names are correct.")
    else:
        ticket_prices, station_info = get_ticket_price(
            from_station_id, to_station_id, lang)
        if not ticket_prices:
            if lang == "C":
                raise ApiException("冇搵到適用嘅車票價錢。")
            elif lang == "E":
                raise ApiException("No applicable ticket prices found.")

        if lang == "C":
            output_text += '[Hong Kong MTR車票價格]\n'
        elif lang == "E":
            output_text += '[Hong Kong MTR Ticket Prices]\n'

        # 【打风】（以下是sample）
        # [Hong Kong MTR車票價格]
        #
        # 【飓风】十號風球，露天段列車及輕鐵服務已經暫停
        # 【延長服務】機場快綫加開班次
        #  。。。。。。。。尾班車於凌晨12時48分開出。
        #
        # 由 （羅湖 [LOW]） 去往 （旺角 [MOK]） 嘅車票價格：
        typhoon_data = get_typhoon_info()
        if typhoon_data:
            if lang == "C":
                # output_text += "\n【特别車務狀況】\n"
                for info in typhoon_data:
                    if info[0] == "Typhoon":
                        output_text += "【飓风】"
                        output_text += info[1]+"\n"
                        # 这个要对AlertContent的HTML Table解析，等鸡哥来
                    elif info[0] == "ServiceExtend":
                        output_text += "【延長服務】"
                        output_text += info[1]+"\n"
                        if info[3] != "":
                            output_text += info[3]+"\n"
                    elif info[5] == "LateCert":
                        #延误通知书不输出
                        continue
                    else:
                        output_text += "【通知】"
                        output_text += info[1]+"\n"
                        if info[3] != "":
                            output_text += info[3]+"\n"
                    output_text += "\n"
            elif lang == "E":
                # output_text += "\n[Special Arrangement]\n"
                for info in typhoon_data:
                    if info[0] == "Typhoon":
                        output_text += "[Typhoon]"
                        output_text += info[2]+"\n"
                    elif info[0] == "ServiceExtend":
                        output_text += "[Service Extention]"
                        output_text += info[2] +"\n"
                        if info[4] != "":
                            output_text += info[4]+"\n"
                    elif info[5] == "LateCert":
                        continue
                    else:
                        output_text += "[Notice]"
                        output_text += info[2] +"\n"
                        if info[4] != "":
                            output_text += info[4]+"\n"
                        
                    output_text += "\n"


        # 【首末班車】
        output_text_first_last,title_msg_first_last = print_first_last_train_info(
            station_info,from_station_id,to_station_id,lang)
        output_text += output_text_first_last
        title_msg += title_msg_first_last

        output_text += "\n"

        # 【發車時間】
        output_text += print_train_arrival_info(
            from_station_id,lang)
        
        output_text += "\n"

        # 【路線信息】
        output_text += print_ticket_prices(
            ticket_prices,lang
        )
        # output_text += "\n"

        #插入那堆文案
        output_text += print_misc_info(lang)

        if tg_inline_mode:
            return output_text, title_msg
        else:
            return output_text

def fetch_exchange_rate_from_url(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    resp = requests.get(url, headers=headers,proxies=proxies, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rate_tag = soup.find("p", class_="exchange-rate")
    if not rate_tag:
        raise Exception(f"無法從 {url} 解析出匯率")
    rate_text = rate_tag.get_text().strip()
    rate_value = rate_text.split(":")[-1].strip()
    return float(rate_value)

def get_exchange_rate_info(cache_file="octopus_exchange_rate.json"):
    cache_data = None
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
            cache_time = datetime.strptime(cache_data["fetch_time"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() - cache_time < timedelta(hours=12):
                return cache_data
    
    try:
        hkd_to_rmb = fetch_exchange_rate_from_url(
            "https://www.octopuscards.com/onlineform/mot/exchange-rate/hkd-to-rmb/tc/enquiry.jsp"
        )
        rmb_to_hkd = fetch_exchange_rate_from_url(
            "https://www.octopuscards.com/onlineform/mot/exchange-rate/rmb-to-hkd/tc/enquiry.jsp"
        )
        fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = {
            "hkd_to_rmb": hkd_to_rmb,
            "rmb_to_hkd": rmb_to_hkd,
            "fetch_time": fetch_time
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return result

    except Exception as e:
        if cache_data:
            print(f"獲取最新匯率失敗，已使用本地過期緩存（最後更新時間：{cache_data['fetch_time']}）")
            return cache_data
        else:
            raise Exception(f"無法獲取最新匯率，且沒有本地緩存可用: {e}")

def format_adult_price_zh(adult_price, rmb_to_hkd_rate, fare_title):
    try:
        # 尝试将成人票价转换为数字
        price_float = float(adult_price)
        
        # 如果是浮动数字，按照汇率转换成人民币
        rmb_price = round(price_float / rmb_to_hkd_rate, 2)
        return f"成人票價：HK$ {adult_price} (CN¥{rmb_price})"
    except ValueError:
        # 如果无法转换为浮动数字（即可能是字符串或奇怪字符），直接返回原始票价
        return f"成人票價：{adult_price}"

def format_adult_price_en(adult_price, rmb_to_hkd_rate, fare_title):
    try:
        # 尝试将成人票价转换为数字
        price_float = float(adult_price)
        
        # 如果是浮动数字，按照汇率转换成人民币
        rmb_price = round(price_float / rmb_to_hkd_rate, 2)
        return f"Adult Price: HK$ {adult_price} (Approx. CN¥{rmb_price})"
    except ValueError:
        # 如果无法转换为浮动数字（即可能是字符串或奇怪字符），直接返回原始票价
        return f"Adult Price: {adult_price}"

def format_student_price_zh(student_price):
    try:
        # 尝试将学生票价转换为数字
        price_float = float(student_price)
        
        # 如果是浮动数字，直接返回港币票价
        return f"學生票價：HK$ {student_price}"
    except ValueError:
        # 如果无法转换为浮动数字，直接返回原始票价（即可能是字符串或奇怪字符）
        return f"學生票價：{student_price}"

def format_student_price_en(student_price):
    try:
        # 尝试将学生票价转换为数字
        price_float = float(student_price)
        
        # 如果是浮动数字，直接返回港币票价
        return f"Student Price: HK$ {student_price}"
    except ValueError:
        # 如果无法转换为浮动数字，直接返回原始票价（即可能是字符串或奇怪字符）
        return f"Student Price: {student_price}"

def get_common_notice_zh(hkd_to_rmb, rmb_to_hkd, fetch_time):
    return (
        f"【票價適用及支付方式】\n"
        f"本頁票價僅適用於以下方式進出港鐵重鐵網絡*時：\n"
        f"- 八達通\n"
        f"- 感應式信用卡／扣賬卡（Visa、Mastercard、銀聯，銀聯扣賬卡除外）\n"
        f"- 二維碼（AlipayHK 易乘碼、MTR Mobile 車票二維碼、雲閃付港鐵乘車碼、騰訊乘車碼）\n"
        f"- 全國交通一卡通（China T-Union Card）\n\n"
        f"除八達通外，上述支付方式均僅適用於港鐵重鐵網絡*。\n\n"
        f"【通用規則】\n"
        f"- 以感應式卡、二維碼或交通聯合卡支付的車費，均按成人八達通票價計算，不適用任何小童、學生、長者或特惠票價。\n"
        f"- 政府公共交通費用補貼計劃及其他港鐵車費優惠不適用。\n"
        f"- 經尖沙咀站／尖東站轉乘視為兩個獨立車程並分開收費。\n"
        f"- 二維碼乘車需入閘前預先選定票種及等級，入閘後不可更改。\n\n"
        f"【匯率參考】\n"
        f"- 港幣兌人民幣匯率：{hkd_to_rmb}\n"
        f"- 人民幣兌港幣匯率：{rmb_to_hkd}\n"
        f"- 資料獲取時間：{fetch_time}\n"
        f"匯率由八達通卡有限公司網頁獲取，僅供參考，實際以讀寫器所存匯率為準。\n\n"
        f"【全國交通一卡通特別提示】\n"
        f"- 港鐵不提供人民幣增值服務，請向發卡機構查詢。\n"
        f"- 入港前需確保卡內餘額不少於人民幣50元，最高儲值額為人民幣1,000元。\n\n"
        f"*不適用於機場快綫、輕鐵、港鐵巴士、港鐵接駁巴士及東鐵綫頭等。\n"
        f"備註：使用感應式信用卡／扣賬卡乘搭港鐵時，系統會於每日營運結束後統一結算當日乘車總額。銀行賬單上一般只會顯示每日或多日累計的總車費金額。"
    )

def get_common_notice_en(hkd_to_rmb, rmb_to_hkd, fetch_time):
    return (
        f"[Fare Applicability and Payment Methods]\n"
        f"The fares shown on this page apply only when using the following payment methods on the MTR heavy rail network*:\n"
        f"- Octopus\n"
        f"- Contactless credit/debit cards (Visa, Mastercard, UnionPay; UnionPay debit cards are not accepted)\n"
        f"- QR codes (AlipayHK EasyGo, MTR Mobile QR Code Ticket, UnionPay MTR Transit QR Code, Tencent Transit QR Code)\n"
        f"- China T-Union Card\n\n"
        f"Except for Octopus, the above payment methods are only available for the MTR heavy rail network*.\n\n"
        f"[General Rules]\n"
        f"- Fares paid with contactless cards, QR codes or China T-Union Cards are charged at the Adult Octopus fare; concessionary fares do not apply.\n"
        f"- The Public Transport Fare Subsidy Scheme and other MTR fare promotions are not applicable.\n"
        f"- MTR rides which interchange at Tsim Sha Tsui / East Tsim Sha Tsui station will be considered as two separate single journeys.\n"
        f"- For QR code rides, passenger type and class must be selected before entry and cannot be changed after entry.\n\n"
        f"[Exchange Rate Reference]\n"
        f"- HKD to RMB exchange rate: {hkd_to_rmb}\n"
        f"- RMB to HKD exchange rate: {rmb_to_hkd}\n"
        f"- Data retrieved at: {fetch_time}\n"
        f"Rates are obtained from the Octopus Cards Limited website for reference only. The actual rate is determined by the rate stored in the Octopus reader at the time of transaction.\n\n"
        f"[China T-Union Card Special Notes]\n"
        f"- RMB top-up service is not available on MTR. Please contact the card issuer for enquiries.\n"
        f"- Before arriving in Hong Kong, passengers should ensure the card has a balance of at least RMB50, with a maximum stored value of RMB1,000.\n\n"
        f"*Not available at Airport Express, Light Rail, MTR Bus, MTR Feeder Bus and East Rail Line First Class.\n"
        f"Note: When using contactless credit/debit cards for MTR rides, the system will consolidate all rides and settle the total daily fare after end-of-service. Your bank statement will typically show one aggregated transaction per day or multiple days."
    )

def print_first_last_train_info(station_info,from_station_id, to_station_id, lang):
    output_text,title_msg = "",""

    from_station_info = format_station_info(get_station_info(from_station_id),lang)
    to_station_info = format_station_info(get_station_info(to_station_id),lang)
    from_station_info_display = format_station_info_with_code(get_station_info(from_station_id),lang)
    to_station_info_display = format_station_info_with_code(get_station_info(to_station_id),lang)

    if lang == "C":
            output_text += f"由 （{from_station_info_display}） 去往 （{to_station_info_display}） 嘅車票價格：\n"
            title_msg += f"由 （{from_station_info}） 去往 （{to_station_info}） 嘅車票價格"
            # output_text += '\n請留意，該車票價格僅計算使用八達通拍卡或使用乘車二維碼入閘嘅價格，唔包括購買單程票嘅價格。\n\n'
            output_text += f"【首尾班車】\n" 

            output_text += f'(首：{station_info["firstTrainTime"]["time"]})'
            # output_text += '路綫: '
            output_text += query_specific_line(from_station_info, to_station_info, station_info["firstTrainTime"],lang)
            output_text += f'(尾：{station_info["lastTrainTime"]["time"]})'
            # output_text += '路綫: '
            output_text += query_specific_line(from_station_info, to_station_info, station_info["lastTrainTime"],lang)
            #output_text += f'{station_info["firstLastTrainRemark"].replace("<br /><br />","")}\n'
            output_text += f'請根據所示路徑搭乘首/尾班車，'
            output_text += f'車站開放時間：{station_info["stationOpeningHours"]}\n'
            #output_text += "乘搭首/尾班車的乘客必須使用本頁列明的轉乘路綫，因有關的轉乘路綫可能與行程指南所建議的路綫不同。\n\n"

    elif lang == "E":
        output_text += f"Ticket prices from ({from_station_info_display}) to ({to_station_info_display}):\n"
        title_msg += f"Ticket prices from ({from_station_info}) to  ({to_station_info})"
        # output_text += '\nPlease note that the ticket prices only apply to Octopus card or QR code entry, and do not include the price of single journey tickets.\n\n'
        
        output_text += f"[First and Last Train Info]\n"

        output_text += f'(First: {station_info["firstTrainTime"]["time"]})'
        #output_text += 'Route: '
        output_text += query_specific_line(from_station_info, to_station_info, station_info["firstTrainTime"],lang)
        output_text += f'(Last: {station_info["lastTrainTime"]["time"]})'
        #output_text += 'Route: '
        output_text += query_specific_line(from_station_info, to_station_info, station_info["lastTrainTime"],lang)
        output_text += f'Please follow the route for the first and last trains.'
        #output_text += f'{station_info["firstLastTrainRemark"].replace("<br /><br />","")}\n'
        output_text += f'Station Opening Hours: {station_info["stationOpeningHours"]}\n'
        #output_text += "Passengers taking the first/last train must use the transfer routes listed on this page, as the recommended routes in the travel guide may differ.\n\n"

    return output_text,title_msg

def print_train_arrival_info(from_station_id,lang):
    output_text = ""

    departure_station_abbreviations = get_station_abbreviation(from_station_id)
    from_station_info = format_station_info(get_station_info(from_station_id),lang)

    if departure_station_abbreviations:
        if lang == "C":
            output_text += f"【發車時間】\n"
        elif lang == "E":
            output_text += f"[Departure Time]\n"

        for line, abbreviation in departure_station_abbreviations:
            if lang == "C":
                arrivals_lang = "TC"
                line_name = line_dict[line][0]
            elif lang == "E":
                arrivals_lang = "EN"
                line_name = line_dict[line][1]

            realtime_departure = get_realtime_arrivals(line, abbreviation, from_station_info, line_name, arrivals_lang)

            if realtime_departure:
                output_text += f"{realtime_departure}\n"
    else:
        if lang == "C":
            output_text += f"無法獲取 {from_station_info} 的實時發車時間。\n\n"
        elif lang == "E":
            output_text += f"Unable to retrieve real-time departure times for {from_station_info}.\n\n"

    return output_text

def print_ticket_prices(ticket_prices,lang):
    output_text = ""

    exchange_info = get_exchange_rate_info()  # 获取最新汇率和更新时间
    rmb_to_hkd = exchange_info["rmb_to_hkd"]

    if lang == "C":
        output_text += "【路綫信息】\n"
    elif lang == "E":
        output_text += "[Route Information]\n"
    
    for price in ticket_prices:
        route_name = price['routeName']
        adult_price = price['adultPrice']
        student_price = price['studentPrice']
        fareTitle = price['fareTitle']
        time = price['time']
        path = price['path']

        if lang == "C":
            if fareTitle == 'standardClass':
                output_text += f"普通等"
            elif fareTitle == 'firstClass':
                output_text += f"头等"
            output_text += f" {route_name}（{time}分鐘）\n"
            # output_text += f"成人票價：{adult_price}\n"
            output_text += "" + format_adult_price_zh(adult_price, rmb_to_hkd, fareTitle) + " "
            # output_text += f"學生票價：{student_price}\n"
            output_text += "" + format_student_price_zh(student_price) + "\n"
            # output_text += f"行車時間：{time}分鐘\n"
            # output_text += f"路線：\n"
            for segment in path:
                link_text = segment.get('linkText')
                if link_text is not None:
                    output_text += f"- {link_text}\n"
        elif lang == "E":
            if fareTitle == 'standardClass':
                output_text += f"Standard"
            elif fareTitle == 'firstClass':
                output_text += f"First Class"
            output_text += f" {route_name}({time} minutes)\n"
            # output_text += f"Adult Price: {adult_price}\n"
            output_text += "" + format_adult_price_en(adult_price, rmb_to_hkd, fareTitle) + " "
            # output_text += f"Student Price: {student_price}\n"
            output_text += "" + format_student_price_en(student_price) + "\n"
            #output_text += f"Travel Time: {time} minutes\n"
            # output_text += f"Route:\n"
            for segment in path:
                link_text = segment.get('linkText')
                if link_text is not None:
                    output_text += f"- {link_text}\n"
        output_text += "\n"

    return output_text

def print_misc_info(lang):
    output_text = ""

    exchange_info = get_exchange_rate_info()  # 获取最新汇率和更新时间
    rmb_to_hkd = exchange_info["rmb_to_hkd"]
    hkd_to_rmb = exchange_info["hkd_to_rmb"]

    if lang == "C":
        output_text += f"【匯率參考】\n港幣兌人民幣: {hkd_to_rmb}\n人民幣兌港幣: {rmb_to_hkd}\n更新時間:" + exchange_info["fetch_time"]
        # output_text += get_common_notice_zh(hkd_to_rmb, rmb_to_hkd, exchange_info["fetch_time"])
    elif lang == "E":
        output_text += f"[Exchange Rate]\nHKD->CNY: {hkd_to_rmb}\nCNY->HKD: {rmb_to_hkd}\nLast Update:" + exchange_info["fetch_time"]
        # output_text += get_common_notice_en(hkd_to_rmb, rmb_to_hkd, exchange_info["fetch_time"])

    return output_text

def get_typhoon_info():
    # https://tnews.mtr.com.hk/alert/tsi_simpletxt_title_tc.html?type=typhoon
    urlTyphoon = f"https://tnews.mtr.com.hk/alert/alert.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    response = requests.get(urlTyphoon,headers=headers,proxies=proxies,timeout=10)
    # print(response.text)
    # requests.exceptions.JSONDecodeError: Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)
    text_without_bom = response.text.encode().decode('utf-8-sig')
    data = json.loads(text_without_bom)
    typhoon_info = data['data']
    if not typhoon_info:
        return []
    
    service_info = []
    for info in typhoon_info:
        #跳过延误通知书
        if info['newsType'] == "LateCert":
            continue

        # alertContent有时候会是html,正好有个现成的BeautifulSoup做解析
        contentTcParsed = ""
        contentTc = BeautifulSoup(info['alertContentTc'], "html.parser")
        if "message-content" in info['alertContentTc']:
            #如果MTR喜欢贴html,那找到<p id='message-content'>的内容提取出来就行
            #不然你要是把下面的表格也贴了那就是灾难了.jpg
            contentTcParsed = contentTc.find("p", {"id":"message-content"}).get_text().strip()
        else:
            #有时候MTR喜欢只贴个<p>或者直接不贴，这时候直接提取内容就行
            contentTcParsed = contentTc.get_text().strip()

        contentEnParsed = ""
        contentEn = BeautifulSoup(info['alertContent'], "html.parser")
        if "message-content" in info['alertContent']:
            contentEnParsed = contentEn.find("p", {"id":"message-content"}).get_text().strip()
        else:
            contentEnParsed = contentEn.get_text().strip()
        
        service_info.append([info['tsiType']
            ,info['alertTitleTc'],info['alertTitle']
            ,contentTcParsed,contentEnParsed,info['newsType']])

    return service_info
    


# # 如果直接调用这个文件，就会执行下面的代码
# if __name__ == "__main__":

#     # 创建命令行解析器
#     parser = argparse.ArgumentParser(description='查询车票价格')

#     # 添加命令行参数
#     parser.add_argument('from_station', help='出发站')
#     parser.add_argument('to_station', help='到达站')

#     # 解析命令行参数
#     args = parser.parse_args()

#     # 获取出发站和到达站
#     from_station_name = args.from_station
#     to_station_name = args.to_station



#     # 更新车站信息
#     mtr_stations = get_mtr_stations()
#     with open("mtr_stations.json", "w", encoding="utf-8") as f:
#         json.dump(mtr_stations, f, ensure_ascii=False, indent=4)

#     url = 'https://opendata.mtr.com.hk/data/mtr_lines_and_stations.csv'
#     print(f'Updating mtr_lines_and_stations from {url}')
#     #下载文件
#     r = requests.get(url)
#     #将二进制文件转为字符串
#     data = str(r.content, encoding="utf-8")
#     #将字符串转为文件对象
#     with open('mtr_lines_and_stations.csv', 'w', encoding='utf-8') as f:
#         f.write(data)
#     json_file = 'mtr_lines_and_stations.json'
#     convert_to_json(json_file)
#     with open("mtr_lines_and_stations.json", "r", encoding="utf-8") as f:
#         line_info = json.load(f)
#     # 查询车票价格
#     output_text = query_ticket_price(from_station_name, to_station_name)
#     print(output_text)

#     #print(get_station_abbreviation("上水"))
#     #print(get_realtime_arrivals("EAL", "SHS", "TC"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='查询车票价格')
    parser.add_argument('from_station', help='出发站')
    parser.add_argument('to_station', help='到达站')
    parser.add_argument('lang', help='语言(E/C)',default='C',nargs='?')
    args = parser.parse_args()

    # 强制更新
    update_mtr_stations()
    update_mtr_line_info()

    output = query_ticket_price(args.from_station, args.to_station,tg_inline_mode=False,lang=args.lang)
    print(output)