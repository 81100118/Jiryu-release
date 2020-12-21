#!/usr/bin/python3
#encoding=utf-8

import xml.sax
import xml.sax.handler
import urllib
from copy import deepcopy
from utils import *
import gzip

class KyokuInfo:
    def __init__(self):
        self.kyoku = 0
        self.honba = 0
        # self.kyoutaku = 0
        # self.doraIndicator = 0
        # self.ten = [0,0,0,0]
        self.oya = 0
        # self.haipai = [[],[],[],[]]
        self.status = [] # dict[], 每个dict里都有'tag' : char[], 'attributes': dict, 'hands' : int[4][14], 'rivers' : int[4][25][2], 'furos' : Furo[4][], 
                         # 'doraIndicators' : int[], 'kyoutaku' : int, 'ten' : int[4], 'remaining' : int, 'online' : bool[4]
        # TODO
    def p(self):
        print('東南西北'[self.kyoku // 4], self.kyoku % 4 + 1, '局', self.honba, '本場  供託', self.status[0]['kyoutaku'], '本')
        print('どら表示:', tilecodeToString2(self.status[0]['doraIndicators'][0]))
        print(self.status[0]['ten'])
        for i in range(4):
            print(list(map(tilecodeToString2, sorted(self.status[0]['hands'][i]))))
        print('残り', self.status[0]['remaining'], '枚')

class HaifuInfo:
    def __init__(self):
        self.tableInfo = TableInfo()
        self.kyokuInfos = []
    def newKyoku(self):
        # modifies self
        self.kyokuInfos.append(KyokuInfo())
    def p(self):
        ruleString = self.tableInfo.getRuleString()
        print(ruleString)
        for i in range(self.tableInfo.getPlayerNum()):
            print(self.tableInfo.players[i]['name'], str(self.tableInfo.players[i]['dan'] - 9) + '段', 'R'+str(self.tableInfo.players[i]['rate']))
        for i in range(len(self.kyokuInfos)):
            info = self.kyokuInfos[i]
            print('東南西北'[info.kyoku // 4], info.kyoku % 4, '局', info.honba, '本場  供託', info.kyoutaku, '本')


class TableInfo:
    def __init__(self):
        self.rule = 0
        self.lobby = 0
        self.isChampionship = False
        self.players = [{},{},{},{}]
    def getPlayerByIndex(self, index):
        # dict getPlayerByIndex(int)
        return self.players[index]
    def getPlayerIndexByName(self, name):
        for i in range(self.getPlayerNum()):
            if self.players[i]['name'] == name:
                return i
        return -1
    def isAkaAri(self):
        # 是否有赤
        return ((self.rule & 0x02) == 0)
    def isKuitanAri(self):
        # 是否有食断
        return ((self.rule & 0x04) == 0)
    def isTonpusen(self):
        # 是否是东风战
        return ((self.rule & 0x08) == 0)
    def isTonnansen(self):
        # 是否是东南战
        return ((self.rule & 0x08) > 0)
    def isSanma(self):
        # 是否是三麻
        return ((self.rule & 0x10) > 0)
    def isYonma(self):
        # 是否是四麻
        return ((self.rule & 0x10) == 0)
    def getPlayerNum(self):
        if self.isSanma():
            return 3
        else:
            return 4
    def isFast(self):
        # 是否是速
        return ((self.rule & 0x40) > 0)
    def isPVP(self):
        # 是否是打真人
        return ((self.rule & 0x01) > 0)
    def getLevel(self):
        # 般上特疯 0123
        if (self.rule & 0xa0) == 0xa0:
            return 3
        elif (self.rule & 0x20) > 0:
            return 2
        elif (self.rule & 0x80) > 0:
            return 1
        else:
            return 0
    def getLobbyString(self):
        if self.isChampionship:
            return 'C' + str(self.lobby).rjust(8, '0')
        else:
            return 'L' + str(self.lobby).rjust(4, '0')
    def getAverageDan(self):
        # 本桌平均段位
        if self.isYonma():
            return (self.players[0]['dan'] + self.players[1]['dan'] + self.players[2]['dan'] + self.players[3]['dan']) / 4
        else:
            return (self.players[0]['dan'] + self.players[1]['dan'] + self.players[2]['dan']) / 3
    def getAverageRate(self):
        if self.isYonma():
            return (self.players[0]['rate'] + self.players[1]['rate'] + self.players[2]['rate'] + self.players[3]['rate']) / 4
        else:
            return (self.players[0]['rate'] + self.players[1]['rate'] + self.players[2]['rate']) / 3
    def getRuleString(self):
        ruleString = ''
        if self.isSanma():
            ruleString += '三'
        ruleString += '般上特鳳'[self.getLevel()]
        if self.isTonpusen():
            ruleString += '東'
        else:
            ruleString += '南'
        if self.isKuitanAri():
            ruleString += '喰'
        if self.isAkaAri():
            ruleString += '赤'
        if self.isFast():
            ruleString += '速'
        return ruleString
    def getRuleString2(self):
        ruleString = ''
        if self.isSanma():
            ruleString += '三'
        ruleString += '屋林野龙'[self.getLevel()]
        if self.isTonpusen():
            ruleString += '东'
        else:
            ruleString += '南'
        if self.isKuitanAri():
            ruleString += '喰'
        if self.isAkaAri():
            ruleString += '赤'
        if self.isFast():
            ruleString += '速'
        return ruleString
        
class WorksHandler(xml.sax.ContentHandler):
    def __init__(self):
        xml.sax.ContentHandler.__init__(self)
        self.justDrawnTilecode = -1
        self.online = [True] * 4
    #元素开始事件处理
    def startElement(self, tag, attributes):
        if tag == "GO":
            self.haifuInfo.tableInfo.rule = int(attributes['type'])
            if 'lobby' in attributes:
                self.haifuInfo.tableInfo.lobby = int(attributes['lobby'])
        elif tag == 'UN':
            # 可能是开局玩家信息，也可能是有人重连了
            # 目前根据有没有'dan'属性来判断是开局还是重连
            if 'dan' in attributes:
                # 有dan，是开局
                dans = attributes['dan'].split(',')
                rates = attributes['rate'].split(',')
                for i in range(4):
                    p = self.haifuInfo.tableInfo.players[i]
                    p['name'] = urllib.parse.unquote(attributes['n' + str(i)])
                    p['dan'] = int(dans[i])
                    p['rate'] = float(rates[i])
                    print(p['name'], str(p['dan'] - 9) + '段', 'R'+str(p['rate']))
            else:
                # 没dan，是重连
                for i in range(4):
                    if 'n' + str(i) in attributes:
                        self.online[i] = True
                        print(urllib.parse.unquote(attributes['n' + str(i)]), '重连了')
        elif tag == 'TAIKYOKU':
            # 含有'oya' attribute 表明起家的playerIndex 但是似乎必定是0 就不管了
            pass
        elif tag == 'INIT':
            seeds = attributes['seed'].split(',')
            self.haifuInfo.newKyoku()
            info = self.haifuInfo.kyokuInfos[-1]
            status = {}
            status['tag'] = tag
            status['attributes'] = attributes
            status['doraIndicators'] = [int(seeds[5])]
            status['kyoutaku'] = int(seeds[2])
            status['hands'] = [[], [], [], []]
            for i in range(4):
                if attributes['hai' + str(i)] != '':
                    hai = attributes['hai' + str(i)].split(',')
                    for j in range(13):
                        status['hands'][i].append(int(hai[j]))
            status['furos'] = [[], [], [], []]
            status['rivers'] = [[], [], [], []]
            ten = attributes['ten'].split(',')
            status['ten'] = [0, 0, 0, 0]
            status['remaining'] = self.haifuInfo.tableInfo.isSanma() and 55 or 70
            status['online'] = self.online
            for i in range(4):
                status['ten'][i] = int(ten[i])
            info.status.append(status)

            info.kyoku = int(seeds[0])
            info.honba = int(seeds[1])
            info.oya = int(attributes['oya'])
            # info.kyoutaku = int(seeds[2])
            # info.doraIndicator = seeds[5]
            self.justReached = [False] * 4
            info.p()
        else:
            if len(self.haifuInfo.kyokuInfos) == 0:
                print("tag:", tag)
                for key in attributes.keys():
                    print("attributes: ", key, "=", attributes[key])
                return
            info = self.haifuInfo.kyokuInfos[-1]
            status = deepcopy(info.status[-1])
            status['tag'] = tag
            status['attributes'] = attributes
            status['online'] = deepcopy(self.online)
            if tag == 'N':
                # 副露
                # TODO add to info
                who = int(attributes['who'])
                m = int(attributes['m'])
                furo = decodeFuro(m)
                # 接下来判断被副露的牌是否是摸切的 以及更新status里的副露信息
                if furo.isKan == 2: # 加杠
                    if status['hands'][who][-1] in furo.tilecodes:
                        # 摸切加杠
                        furo.isKakanTsumogiri = 1
                    # 加杠不会产生新的副露，只是修改了原先的副露
                    for i in range(len(status['furos'][who])):
                        origClaimedTile = status['furos'][who][i].tilecodes[status['furos'][who][i].whichTileIsClaimed]
                        claimedTile = furo.tilecodes[furo.whichTileIsClaimed]
                        if origClaimedTile == claimedTile:
                            # 找到了原先的副露
                            origTsumogiri = status['furos'][who][i].isTsumogiri
                            # 新副露里还没分析手模切，所以要把老副露里的手模切复制到新副露里
                            status['furos'][who][i] = furo
                            status['furos'][who][i].isTsumogiri = origTsumogiri
                            break
                else:
                    if furo.isKan == 1 and furo.fromWhoRelative == 0: # 暗杠
                        if status['hands'][who][-1] in furo.tilecodes: # 摸杠
                            furo.isTsumogiri = 1
                        else:
                            furo.isTsumogiri = 0
                    elif furo.isKita:
                        if status['hands'][who][-1] in furo.tilecodes: # 摸拔
                            furo.isTsumogiri = 1
                        else:
                            furo.isTsumogiri = 0
                    else:
                        [hai, tsumogiri] = status['rivers'][relativeToAbsolute(furo.fromWhoRelative, who)][-1] # 副露的牌 必定是被副露家刚切的牌
                        if hai != furo.tilecodes[furo.whichTileIsClaimed]:
                            print('ERROR: 副露的牌不是刚切的牌')
                        furo.isTsumogiri = tsumogiri
                        status['rivers'][relativeToAbsolute(furo.fromWhoRelative, who)][-1][1] |= 2 # 设置牌河中的牌为'被副露'
                        if tsumogiri & 4:
                            # 有人的立直宣言牌被副露掉了
                            self.justReached[relativeToAbsolute(furo.fromWhoRelative, who)] = True
                    
                    status['furos'][who].append(furo) # 加入此玩家的副露列表
                
                # 从手牌中移除副露的牌
                for i in range(4):
                    for j in range(len(status['hands'][who])):
                        if status['hands'][who][j] in furo.tilecodes:
                            status['hands'][who].pop(j)
                            break
                
                print('Player', who, self.haifuInfo.tableInfo.getPlayerByIndex(who)['name'], furo.getFuroTypeString(), ['自己', '下家', '对家', '上家'][furo.fromWhoRelative])
                print(furo.isTsumogiri == 1 and '被副露的牌是摸切的' or '被副露的牌是手切的')
                print(furo.isKakanTsumogiri == 1 and '摸切加杠')
                # print('面子代码', m)
                print(list(map(tilecodeToString2, furo.tilecodes)))
                print('副露后手牌', list(map(tilecodeToString2, sorted(status['hands'][who]))))
                print('他/她的所有副露：')
                for f in status['furos'][who]:
                    print(list(map(tilecodeToString2, f.tilecodes)))
            elif tag == 'DORA':
                hai = int(attributes['hai'])
                status['doraIndicators'].append(hai)
                print('新dora指示牌', tilecodeToString2(hai))
            elif tag == 'REACH':
                who = int(attributes['who'])
                step = int(attributes['step'])
                if step == 1:
                    print('Player', who, self.haifuInfo.tableInfo.getPlayerByIndex(who)['name'], '立直')
                    self.justReached[who] = True
                else:
                    ten = attributes['ten'].split(',')
                    for i in range(4):
                        status['ten'][i] = int(ten[i])
                    status['kyoutaku'] += 1
            elif tag == 'AGARI':
                #TODO
                who = int(attributes['who'])
                fromWho = int(attributes['fromWho'])
                print('Player', who, self.haifuInfo.tableInfo.getPlayerByIndex(who)['name'], '和了')
                if fromWho == who:
                    print('自摸')
                else:
                    print('Player', fromWho, self.haifuInfo.tableInfo.getPlayerByIndex(fromWho)['name'], '放铳')
                if 'paoWho' in attributes:
                    paoWho = int(attributes['paoWho'])
                    print('Player', paoWho, self.haifuInfo.tableInfo.getPlayerByIndex(paoWho)['name'], '包牌')
                for key in attributes.keys():
                    print("attributes: ", key, "=", attributes[key])
            elif tag == 'RYUUKYOKU':
                #TODO
                print('流局')
                for key in attributes.keys():
                    print("attributes: ", key, "=", attributes[key])
            elif tag[0] in 'TUVW' and tag[1] in '0123456789':
                who = ord(tag[0]) - ord('T')
                hai = int(tag[1:])
                self.justDrawnTilecode = hai
                status['hands'][who].append(hai) # 放入手牌
                status['remaining'] -= 1 # 残牌-1
                print('Player', who, self.haifuInfo.tableInfo.getPlayerByIndex(who)['name'], '摸', tilecodeToString2(hai))
                pass
            elif tag[0] in 'DEFG' and tag[1] in '0123456789':
                who = ord(tag[0]) - ord('D')
                hai = int(tag[1:])
                tsumogiri = 1 if hai == self.justDrawnTilecode else 0
                reachDeclare = 0
                if self.justReached[who]:
                    self.justReached[who] = False
                    reachDeclare = 4
                discardInfo = tsumogiri | reachDeclare
                status['rivers'][who].append([hai, discardInfo])
                status['hands'][who].remove(hai)
                print('Player', who, self.haifuInfo.tableInfo.getPlayerByIndex(who)['name'], ['手切', '摸切'][tsumogiri], tilecodeToString2(hai))
                print('手牌', list(map(tilecodeToString2, sorted(status['hands'][who]))))
                print('牌河', list(map(lambda tileAndInfo : (['', '摸切', '被副露', '摸切被副露'][tileAndInfo[1] % 4]) + ('立直' if tileAndInfo[1] & 4 else '') +  tilecodeToString2(tileAndInfo[0]), (status['rivers'][who]))))
                self.justDrawnTilecode = -1
            elif tag == 'BYE':
                # 'who' 掉线了
                who = int(attributes['who'])
                self.online[who] = False
                status['online'][who] = False
                print(self.haifuInfo.tableInfo.players[who]['name'], '掉线了')
            else:
                print("Unexpected tag:", tag)
                for key in attributes.keys():
                    print("attributes: ", key, "=", attributes[key])
            info.status.append(status)

    #元素结束事件处理
    def endElement(self, tag):
        pass
    #内容事件处理
    def characters(self, content):
        print('content: ', content)
    def setHaifuInfo(self, haifuInfo):
        # void setHaifuInfo(HaifuInfo)
        # MUST be run before parsing
        self.haifuInfo = haifuInfo

def readHaifuFromFile(filename):
    # 读取牌谱文件
    # 返回牌谱信息，一个HaifuInfo对象，包含牌谱中的所有信息
    parser = xml.sax.make_parser()
    parser.setFeature(xml.sax.handler.feature_namespaces,0)
    #重写ContextHandler
    handler = WorksHandler()
    parser.setContentHandler(handler)
    haifuInfo = HaifuInfo()
    handler.setHaifuInfo(haifuInfo)

    GZIP_MAGIC_NUMBER = b'\x1f\x8b'
    
    f = open(filename, 'rb')
    if f.read(2) == GZIP_MAGIC_NUMBER:
        print('gz')
        f.close()
        f = gzip.open(filename, 'r')
        parser.parse(f)
    else:
        print('not gz')
        f.close()
        parser.parse(filename)
    #except:
    #    print('Cannot open file!');

    
    return haifuInfo

if (__name__ == "__main__"):
    readHaifuFromFile("2020050104gm-0039-0000-cdaa92c2&tw=2.mjlog")
    #readHaifuFromFile("cure_log/2019071110gm-0061-0000-5dafa870&tw=3.mjlog")
