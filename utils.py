#!/usr/bin/python3
#encoding=utf-8
from urllib.parse import unquote

def isAka(tilecode):
    return tilecode < 108 and tilecode % 36 == 16

def tilecodeToNum(tilecode):
    # tilecode is 0-135, num is 1-9 (字牌为1-7)
    # 特殊：-1为牌背 -2为不显示
    return tilecode % 36 // 4 + 1

def tilecodeToSuit(tilecode):
    # 0123 mpsz
    return tilecode // 36

def encodeTile(suit, num, offset):
    return suit * 36 + (num - 1) * 4 + offset

def tilecodeToString(tilecode):
    # tilecode is 0-135
    # return format: 1s, 2m, 3z, etc.
    if isAka(tilecode):
        return '0' + 'mpsz'[tilecodeToSuit(tilecode)]
    return str(tilecodeToNum(tilecode)) + 'mpsz'[tilecodeToSuit(tilecode)]

def tilecodeToString2(tilecode):
    # tilecode is 0-135
    # return format: 1s, 2m, 西, etc.
    if tilecode < 0:
        return '？'
    suit = tilecodeToSuit(tilecode)
    num = tilecodeToNum(tilecode)
    if suit == 3:
        return '東南西北白發中'[num - 1]
    if isAka(tilecode):
        return '0' + 'mps'[suit]
    return str(num) + 'mps'[suit]

def tilecodeToString3(tilecode):
    # return format: １, 二, 西, etc.
    suit = tilecodeToSuit(tilecode)
    num = tilecodeToNum(tilecode)
    if isAka(tilecode):
        num = 0
    if suit == 0:
        return '〇一二三四五六七八九'[num]
    elif suit == 1:
        return '⓪①②③④⑤⑥⑦⑧⑨'[num]
    elif suit == 2:
        return '０１２３４５６７８９'[num]
    elif suit == 3:
        return '東南西北白發中'[num]
    else:
        return ''

TILE_UNICODE_STRING = '🀇🀈🀉🀊🀋🀌🀍🀎🀏🀙🀚🀛🀜🀝🀞🀟🀠🀡🀐🀑🀒🀓🀔🀕🀖🀗🀘🀀🀁🀂🀃🀆🀅🀄'
def tilecodeToUnicodeString(tilecode):
    if tilecode >= 0 and tilecode < 136:
        return TILE_UNICODE_STRING[tilecode >> 2]

def is_shuntsu(tilecodes):
    if len(tilecodes) != 3:
        return False
    suits = list(map(tilecodeToSuit, tilecodes))
    if suits[0] != suits[1] or suits[1] != suits[2]:
        return False
    nums = list(map(tilecodeToNum, tilecodes))
    nums.sort()
    if nums[0] + 1 == nums[1] and nums[1] + 1 == nums[2]:
        return True
    else:
        return False

def tilecodesTo34(tilecodes):
    result = [0] * 34
    for tile in tilecodes:
        result[tile >> 2] += 1
    return result

def relativeToAbsolute(relativePos, selfAbsolutePos):
    # 参数为 目标玩家的相对位置 参照物的绝对位置（牌谱开始时的参照物的index）
    # 返回 目标玩家的绝对位置
    return (relativePos + selfAbsolutePos) % 4

def absoluteToRelative(absolutePos, selfAbsolutePos):
    # 参数为 目标玩家的绝对位置 参照物的绝对位置（牌谱开始时的参照物的index）
    # 返回 目标玩家的相对位置 0:自己 1下家 2对家 3上家
    return (absolutePos - selfAbsolutePos) % 4

class Furo:
    def __init__(self):
        self.fromWhoRelative = 0
        self.isChi = 0
        self.isPon = 0
        self.isKan = 0 # 2为加杠 1为大明杠或暗杠
        self.isKita = 0 # 拔北
        self.tilecodes = []
        self.whichTileIsClaimed = -1 #被鸣的牌是哪一枚，1表示是中间大小的那一枚（0表示数字最小，2表示最大）
        # 加杠的话，被鸣的牌是指碰的时候鸣的牌，而不是加杠的时候加上去的那一张
        # 加杠的话，加上去的那张等于tilecodes[3]
        self.isTsumogiri = 0 # 被鸣的牌是摸切还是手切 0手切
        self.isKakanTsumogiri = 0 # 若副露为加杠，此成员表示加杠的牌是不是摸切
    def getFuroTypeString(self):
        if self.isChi:
            return '吃'#'チー'
        elif self.isPon:
            return '碰'#'ポン'
        elif self.isKan:
            return '杠'#'カン'
        else:
            return '拔北'#'キタ'
    def getFuroTypeString2(self):
        if self.isChi:
            return 'chi'
        elif self.isPon:
            return 'pon'
        elif self.isKan:
            return 'kan'
        else:
            return 'kita'
        
    

def decodeFuro(mentsucode):
    # Furo decodeFuro(int)
    # mentsucode is 副露的面子代码 e.g. 31008
    furo = Furo()
    furo.fromWhoRelative = mentsucode & 0x03
    if (mentsucode & 0x04):
        furo.isChi = 1
        patternCode = (mentsucode & 0xFC00) >> 10
        furo.whichTileIsClaimed = patternCode % 3 #被鸣的牌是哪一枚，1表示是中间大小的那一枚（0表示数字最小，2表示最大）
        suit = patternCode // 3 // 7
        smallestNumInShuntsu = patternCode // 3 % 7 + 1
        offset1 = (mentsucode & 0x0018) >> 3
        offset2 = (mentsucode & 0x0060) >> 5
        offset3 = (mentsucode & 0x0180) >> 7
        furo.tilecodes = [encodeTile(suit, smallestNumInShuntsu, offset1), encodeTile(suit, smallestNumInShuntsu + 1, offset2), encodeTile(suit, smallestNumInShuntsu + 2, offset3)]
    elif (mentsucode & 0x0018) == 0:
        # 暗杠或大明杠或拔北
        if mentsucode & 0x0020:
            furo.isKita = 1
            claimedTilecode = (mentsucode & 0xff00) >> 8
            furo.tilecodes = [claimedTilecode]
            furo.whichTileIsClaimed = 0
        else:
            furo.isKan = 1
            claimedTilecode = (mentsucode & 0xff00) >> 8
            furo.tilecodes = [claimedTilecode // 4 * 4, claimedTilecode // 4 * 4 + 1, claimedTilecode // 4 * 4 + 2, claimedTilecode // 4 * 4 + 3]
            furo.whichTileIsClaimed = claimedTilecode % 4
    else:
        # 碰或加杠
        if mentsucode & 0x0008:
            furo.isPon = 1
        else:
            furo.isKan = 2
        patternCode = (mentsucode & 0xFE00) >> 9
        furo.whichTileIsClaimed = patternCode % 3 #被鸣的牌是哪一枚
        suitAndNum = patternCode // 3 #== suit * 9 + (num - 1)
        unusedTileOffset = (mentsucode & 0x0060) >> 5
        if furo.isPon:
            offsets = [[1, 2, 3], [0, 2, 3], [0, 1, 3], [0, 1, 2]][unusedTileOffset]
            furo.tilecodes = [(suitAndNum << 2) + offsets[i] for i in range(3)]
        else:
            offsets = [[1, 2, 3, 0], [0, 2, 3, 1], [0, 1, 3, 2], [0, 1, 2, 3]][unusedTileOffset]
            furo.tilecodes = [(suitAndNum << 2) + offsets[i] for i in range(4)]
    return furo

class PlayerData:
    def __init__(self, message = None):
        self.uname = ''
        self.expire = None
        self.expireDays = 0
        self.yonmaStat = {'dan' : 0, 'pt' : 0, 'rate': 1500.0, 'totalScore' : 0.0, \
            'count1' : 0, 'count2' : 0, 'count3' : 0, 'count4': 0, 'countTobi' : 0, \
            'countKyoku' : 0, 'countAgari' : 0, 'countHouju' : 0, 'countReach' : 0, \
            'countFuro' : 0}
        self.sanmaStat = {'dan' : 0, 'pt' : 0, 'rate': 1500.0, 'totalScore' : 0.0, \
            'count1' : 0, 'count2' : 0, 'count3' : 0, 'count4': 0, 'countTobi' : 0, \
            'countKyoku' : 0, 'countAgari' : 0, 'countHouju' : 0, 'countReach' : 0, \
            'countFuro' : 0}
        if message:
            self.decode(message)
            self.calc_stats()
    def _decode_stats(self, stat_string, dest):
        tmp = stat_string.split(',')
        # 14,370,1865.42,1289.0,144,124,133,120,37,5276,1243,692,1869,898
        try:
            dest['dan'] = int(tmp[0])
            dest['pt'] = int(tmp[1])
            dest['rate'] = float(tmp[2])
            dest['totalScore'] = float(tmp[3])
            dest['count1'] = int(tmp[4])
            dest['count2'] = int(tmp[5])
            dest['count3'] = int(tmp[6])
            dest['count4'] = int(tmp[7])
            dest['countTobi'] = int(tmp[8])
            dest['countKyoku'] = int(tmp[9])
            dest['countAgari'] = int(tmp[10])
            dest['countHouju'] = int(tmp[11])
            dest['countFuro'] = int(tmp[12])
            dest['countReach'] = int(tmp[13])
        except:
            print('statistics info received is not complete')
        
    def decode(self, message):
        # message :: dict，HELO的attributes
        self.uname = unquote(message['uname'])
        if 'expire' in message:
            self.expire = message['expire']
        else:
            self.expire = None
        if 'expiredays' in message:
            self.expireDays = int(message['expiredays'])
        else:
            self.expireDays = 0
        if 'PF4' in message:
            self._decode_stats(message['PF4'], self.yonmaStat)
        if 'PF3' in message:
            self._decode_stats(message['PF3'], self.sanmaStat)

    def calc_stats(self):
        self._calc_stats(self.yonmaStat)
        self._calc_stats(self.sanmaStat)
    def _calc_stats(self, stat):
        stat['countGames'] = stat['count1'] + stat['count2'] + stat['count3'] + stat['count4']
        if stat['countGames'] == 0:
            pass
        else:
            for i in range(1, 5):
                stat['rate' + str(i)] = stat['count' + str(i)] / stat['countGames']
            stat['rateTobi'] = stat['countTobi'] / stat['countGames']
            stat['avgScore'] = stat['totalScore'] / stat['countGames']
            stat['avgRank'] = (stat['count1'] + 2 * stat['count2'] + 3 * stat['count3'] + 4 * stat['count4']) / stat['countGames']
        if stat['countKyoku'] == 0:
            pass
        else:
            stat['rateAgari'] = stat['countAgari'] / stat['countKyoku']
            stat['rateHouju'] = stat['countHouju'] / stat['countKyoku']
            stat['rateReach'] = stat['countReach'] / stat['countKyoku']
            stat['rateFuro'] = stat['countFuro'] / stat['countKyoku']

class MonthlyStats:
    def __init__(self, message=None):
        self.gameCount = [0, 0, 0, 0]
        self.totalGameCount = 0
        self.totalScore = 0.0
        self.overallRanking = 0
        self.totalScoreRanking = 0
        self.avgScoreRanking = 0
        self.totalPositionRanking = 0
        self.avgPositionRanking = 0
        self.topRateRanking = 0
        self.topTwoRateRanking = 0
        self.lastRateRanking = 0
        self.rateRanking = 0
        if message:
            self.decode(message)
    def decode(self, message):
        if 'v2' in message:
            # {"tag":"RANKING","v2":"16,18,8,0,414.0,,281,465,210,401,179,515,0,69,4963"}
            # 16+18+8 通算得点 414.0 465位 综合 281位 平得 210位 总顺 401位 平顺 179位 top 515位 连对 0位 last 69位 r 4963位
            tmp = message['v2'].split(',')
            self.totalGameCount = 0
            for i in range(4):
                self.gameCount[i] = int(tmp[i])
                self.totalGameCount += int(tmp[i])
            self.totalScore = float(tmp[4])
            self.overallRanking = int(tmp[6])
            self.totalScoreRanking = int(tmp[7])
            self.avgScoreRanking = int(tmp[8])
            self.totalPositionRanking = int(tmp[9])
            self.avgPositionRanking = int(tmp[10])
            self.topRateRanking = int(tmp[11])
            self.topTwoRateRanking = int(tmp[12])
            self.lastRateRanking = int(tmp[13])
            self.rateRanking = int(tmp[14])


class LobbyData:
    def __init__(self, message=None):
        self.totalOnline = 0
        self.thisLobbyOnline = 0
        self.idle = 0
        self.alllast = 0
        self.joining = [0] * 80
        self.playing = [0] * 80
        if message:
            self.decode(message)
    def decode(self, message):
        if 'n' in message:
            num_online = [0, 0, 0, 0]
            tmp = message['n'].split(',')
            for i in range(len(tmp)):
                num_online[i] = int(tmp[i])
            self.totalOnline = num_online[0]
            self.thisLobbyOnline = num_online[1]
            self.idle = num_online[2]
            self.alllast = num_online[3]
        if 'j' in message:
            self.joining = [0] * 80
            tmp = message['j'].split(',')[:80] # 今天发现可能超过80个，怀疑是雀庄
            # e.g. "g":"528,,,4,840,,,40,76,,,,12,,,,,,,,796,,,20,260,,,,,,,,,,,,528,,,,104,,,,,,,,,,,,88,,,,4,,,,,,,,18,279,,150,,144,,15,60,27,9,63,,3,,,,,,,,,,,,,,,,,,,,,,,,,,3"
            for i in range(len(tmp)):
                if tmp[i] != '':
                    self.joining[i] = int(tmp[i])
        if 'g' in message:
            self.playing = [0] * 80
            tmp = message['g'].split(',')[:80]
            for i in range(len(tmp)):
                if tmp[i] != '':
                    self.playing[i] = int(tmp[i])



def whosTurn(tag, attributes):
    # determine from tag and attributes 谁在操作（谁的回合）
    # 如果标签是DORA之类，无法确定是谁的回合，返回-1
    # 如果标签是BYE(掉线)，也返回-1
    if tag == 'BYE':
        return -1
    if 'who' in attributes:
        return int(attributes['who'])
    elif tag[0] in 'TUVW' and tag[1] in '0123456789':
        who = ord(tag[0]) - ord('T')
        return who
    elif tag[0] in 'DEFG' and tag[1] in '0123456789':
        who = ord(tag[0]) - ord('D')
        return who
    else:
        # cannot determine
        return -1

yaku_string_jp = ['門前清自摸和', '立直', '一発', '槍槓', '嶺上開花',\
    '海底摸月', '河底撈魚', '平和', '断幺九', '一盃口',\
    '自風 東', '自風 南', '自風 西', '自風 北', '場風 東',\
    '場風 南', '場風 西', '場風 北', '役牌 白', '役牌 發',\
    '役牌 中', '両立直', '七対子', '混全帯幺九', '一気通貫',\
    '三色同順', '三色同刻', '三槓子', '対々和', '三暗刻',\
    '小三元', '混老頭', '二盃口', '純全帯幺九', '混一色',\
    '清一色', '人和', '天和', '地和', '大三元',\
    '四暗刻', '四暗刻単騎', '字一色', '緑一色', '清老頭',\
    '九蓮宝燈', '純正九蓮宝燈', '国士無双', '国士無双１３面', '大四喜',\
    '小四喜', '四槓子', 'ドラ', '裏ドラ', '赤ドラ']
yaku_string = ['门前清自摸和', '立直', '一发', '枪杠', '岭上开花',\
    '海底摸月', '河底捞鱼', '平和', '断幺九', '一杯口',\
    '自风 東', '自风 南', '自风 西', '自风 北', '场风 東',\
    '场风 南', '场风 西', '场风 北', '役牌 白', '役牌 發',\
    '役牌 中', '两立直', '七对子', '混全带幺九', '一气通贯',\
    '三色同顺', '三色同刻', '三杠子', '对对和', '三暗刻',\
    '小三元', '混老头', '二杯口', '纯全带幺九', '混一色',\
    '清一色', '人和', '天和', '地和', '大三元',\
    '四暗刻', '四暗刻单骑', '字一色', '绿一色', '清老头',\
    '九莲宝灯', '纯正九莲宝灯', '国士无双', '国士无双十三面', '大四喜',\
    '小四喜', '四杠子', '宝牌', '里宝牌', '赤宝牌']
def yakucodeToString(yakucode):
    return yaku_string[yakucode]
