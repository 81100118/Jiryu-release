import requests
import json
import base64
import const
from analyzer import TableInfo

def get_monthly_rankings(criterion, rulecode):
    # criterion: aag, ahj, ...
    success = False
    retry_count = 3
    while not success:
        try:
            resp = requests.get('http://tenhou.net/sc/' + criterion + '-' + str(rulecode) + '.js', timeout=5)
            success = True
        except:
            if retry_count == 0:
                return
            retry_count -= 1
        
    '''
    with open('data/ahj-57.js', 'wb') as f:
        f.write(resp.content)
        f.close()

    with open('data/ahj-57.js', 'r', encoding='utf-8') as f:
        text = f.readlines()
        # print(text)
        f.close()
    '''
    resp.encoding = 'utf-8'
    lines = resp.text.split('\r\n')
    tr = []
    for i in range(len(lines)):
        if lines[i][:2] == 'tr':
            tr = eval(lines[i][3:-1])
            # print(tr)
            
    for i in range(len(tr) // 2):
        if tr[2 * i] in ['二階堂美樹', '小可愛', '81100118', '天才麻将杏杏', '理論力学', '>_0@杏杏軍團']:
            print(tr[2 * i], '月间', tr[2 * i + 1].split(',')[0], i + 1, '/', len(tr) // 2, '位')

def get_wg_info(rulecode):
    temp_table_info = TableInfo()
    temp_table_info.rule = rulecode
    print(temp_table_info.getRuleString2())

    success = False
    retry_count = 3
    while not success:
        try:
            resp = requests.get('https://mjv.jp/0/wg/0000.js', timeout=5)
            success = True
        except:
            if retry_count == 0:
                return
            retry_count -= 1
    text = resp.text[3:-2]
    j = json.loads(text)
    player_data = {}
    for line in j:
        table_info_array = line.split(',')
        # print(base64.b64decode(table_info_array[4]).decode('utf-8'))
        if int(table_info_array[3]) == rulecode:
            for i in [4, 7, 10]:
                name = base64.b64decode(table_info_array[i]).decode('utf-8')
                dan = int(table_info_array[i + 1])
                r = float(table_info_array[i + 2])
                player_data[name] = [dan, r]
    dan_sum = 0
    r_sum = 0
    if len(player_data) == 0:
        print('没人')
        return
    for player in player_data:
        dan_sum += player_data[player][0]
        r_sum += player_data[player][1]
    dan_avg = dan_sum / len(player_data)
    print('平均段位', const.RANKS[int(dan_avg)], '+', dan_avg - int(dan_avg))
    print('平均雀力', r_sum / len(player_data))


get_monthly_rankings('aag', 57)
get_monthly_rankings('ahj', 57)
get_monthly_rankings('aag', 185)
get_monthly_rankings('ahj', 185)
get_wg_info(57)
get_wg_info(185)
