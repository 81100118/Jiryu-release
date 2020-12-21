# -*- coding: utf-8 -*-

ID = 'NoName'
#ID = 'ID00112233-aabbccdd'

LOBBY = 0000
IS_CHAMPIONSHIP = False
GAME_TYPE = 16

MIDDLE_CLICK_DISCONNECT = True # 在线时，按鼠标中键拔线
AUTO_ACTION_DELAY = 0.5 # 自动摸切时，从摸牌到切牌的延迟时间
FORCE_DELAY = False # 是否在每次摸牌切牌之后都强制等一段时间再播放下一步
DISP_SELF_NAME = False # 是否在自己手牌下方显示自己的名字段位等
DISP_NOT_PASSED_SUJIS = True # 是否显示通过的筋根数
DISP_NOT_PASSED_SUJIS_THRESHOLD = 7 # <=这个值时才显示通过的筋根数
DISP_NOT_PASSED_TILES = False # 是否显示通过的牌的种类数
DISP_NOT_PASSED_SELF = True # 是否显示自己通过的筋和牌
DISP_MACHI = True # 是否显示听牌提示
AUTO_DISCONNECT_WHEN_SEND_ERROR = True # 当发送出错时，是否自动断线
DISP_SHORT_LAG = True # 是否提示短卡顿
SHORT_LAG_THRESHOLD_MIN = 0.15 # 视为短卡顿的卡顿时间下限（秒）
SHORT_LAG_THRESHOLD_MAX = 0.7 # 视为短卡顿的卡顿时间上限（秒）
DISP_HIGHLIGHT = True # 是否显示相同牌高亮
