# -*- coding: utf-8 -*-
import pygame
import pygame.freetype
from pygame.color import THECOLORS
import logging
from copy import deepcopy
import analyzer
from decoder import TenhouDecoder
import utils
import sys

logger = logging.getLogger('tenhou')


def setupLogging():
    logger = logging.getLogger('tenhou')
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    ch.setFormatter(formatter)
    logger.addHandler(ch)


class HaifuViewer:
    def __init__(self):
        #arrow_strings = pygame.cursors.thickarrow_strings
        #cursor = pygame.cursors.compile(arrow_strings)
        #pygame.mouse.set_cursor((24,24), (0,0), *cursor)
        self.screen = pygame.display.set_mode([1024,768])
        pygame.display.set_caption('地龍 牌谱')
        #pygame.mouse.set_cursor(*pygame.cursors.arrow)
        self.bg = pygame.image.load('img/bg.jpg')
        self.bg = pygame.transform.smoothscale(self.bg, [1024, 768]).convert()
        # self.screen.blit(pygame.transform.smoothscale(self.bg, [1024, 768]), [0, 0])
        
        
        self.display_ratio = 1
        self.TILE_WIDTH = int(45 * self.display_ratio)
        self.TILE_HEIGHT = int(68 * self.display_ratio)
        self.display_ratios = [1,1,1,1]
        self.display_ratios[0] = 1
        self.TILE_WIDTHS = [0,0,0,0] 
        self.TILE_HEIGHTS = [0,0,0,0] 
        self.TILE_HEIGHT_EFF = [0,0,0,0] 
        self.TILE_WIDTHS[0] = int(37 * self.display_ratios[0])
        self.TILE_HEIGHTS[0] = int(56 * self.display_ratios[0])
        self.TILE_HEIGHT_EFF[0] = int(42 * self.display_ratios[0])
        self.display_ratios[1] = 1
        self.TILE_WIDTHS[1] = int(50 * self.display_ratios[1])
        self.TILE_HEIGHTS[1] = int(46 * self.display_ratios[1])
        self.TILE_HEIGHT_EFF[1] = int(32 * self.display_ratios[1])
        self.display_ratios[2] = 1
        self.TILE_WIDTHS[2] = int(37 * self.display_ratios[2])
        self.TILE_HEIGHTS[2] = int(56 * self.display_ratios[2])
        self.TILE_HEIGHT_EFF[2] = int(42 * self.display_ratios[2])
        self.display_ratios[3] = 1
        self.TILE_WIDTHS[3] = int(50 * self.display_ratios[3])
        self.TILE_HEIGHTS[3] = int(46 * self.display_ratios[3])
        self.TILE_HEIGHT_EFF[3] = int(32 * self.display_ratios[3])

        self.img_mytiles = pygame.image.load('img/tiles.png')
        if self.display_ratio != 1:
            self.img_mytiles = pygame.transform.smoothscale(self.img_mytiles, [int(self.TILE_WIDTH * 10), int(self.TILE_HEIGHT * 4)])
        self.img_shadow = pygame.image.load('img/shadow.png')
        # self.img_shadow = pygame.transform.smoothscale(self.img_shadow, [int(42 * self.display_ratio), int(60 * self.display_ratio)])
        
        self.img_tiles = []
        for i in range(4):
            img_tile = pygame.image.load('img/tiles' + str(i) + '.png')
            if self.display_ratios[i] != 1:
                img_tile = pygame.transform.smoothscale(img_tile, [int(self.TILE_WIDTHS[i] * 10), int(self.TILE_HEIGHTS[i] * 4)])
            self.img_tiles.append(img_tile)

        self.black_surfs = []
        for i in range(4):
            temp_surf = pygame.Surface((self.TILE_WIDTHS[i], self.TILE_HEIGHTS[i]))  # the size of your rect
            temp_surf.fill((25, 125, 243))
            temp_surf.set_alpha(48)                # alpha level
            temp_surf.blit(self.img_tiles[i % 2], [0, 0], [self.TILE_WIDTHS[i] * 8, self.TILE_HEIGHTS[i] * 3, self.TILE_WIDTHS[i], self.TILE_HEIGHTS[i]])           # this fills the surface with image
            temp_surf.set_colorkey((25, 125, 243))
            self.black_surfs.append(temp_surf)

        self.kyoku_font = pygame.font.Font('C:\\windows\\fonts\\simhei.ttf', 32)
        self.kyoku_font_small = pygame.font.Font('C:\\windows\\fonts\\simhei.ttf', 16)
        self.ten_font = pygame.font.Font('C:\\windows\\fonts\\simhei.ttf', 22)
        self.wind_font = pygame.font.Font('C:\\windows\\fonts\\simhei.ttf', 22)
        self.player_font = pygame.freetype.Font('C:\\windows\\fonts\\simhei.ttf', 16)
        self.rule_font = pygame.font.Font('C:\\windows\\fonts\\simhei.ttf', 14)
        self.yaku_font = pygame.font.Font('C:\\windows\\fonts\\simhei.ttf', 28)
        self.calltext_group = pygame.sprite.Group()

        # self.screen.fill([40,70,120])
        # pygame.display.flip()
        self.perspective = 0
        self.haifuInfo = None
    def open(self, filename):
        self.haifuInfo = analyzer.readHaifuFromFile(filename)
        if '&tw=' in filename:
            self.perspective = int(filename[filename.find('&tw=') + 4]) % 4
        else:
            self.perspective = 0
    def initTable(self):
        self.currentKyoku = 0
        self.currentStep = 1
        self.whosTurn = self.haifuInfo.kyokuInfos[self.currentKyoku].oya
        self.justDrawn = False
        #self.displayBackground()
        #self.displayPlayerInfo()
        #self.displayRuleInfo()
        #self.displayKyokuInfo(self.currentKyoku)
        #pygame.display.update()

    def displayBackground(self):
        self.screen.blit(self.bg, [0, 0])

    def displayPlayerInfo(self):
        disp_pos = [[200, 735], [950, 250], [550, 20], [50, 250]]
        for i in range(4):
            playerIndex = (i + self.perspective) % 4
            p = self.haifuInfo.tableInfo.players[playerIndex]
            if p['name'] != '':
                # logger.debug(p['name'])
                (ft1_surf, _) = self.player_font.render(p['name'] + '  ' + TenhouDecoder.RANKS[p['dan']] + '  ' + '力量' + str(int(p['rate'])), THECOLORS['white'])
                ft1_surf = pygame.transform.rotozoom(ft1_surf, i * 90, 1)
                self.screen.blit(ft1_surf, disp_pos[i])
        
    def displayRuleInfo(self):
        disp_pos = [930, 10]
        ft1_surf = self.rule_font.render(self.haifuInfo.tableInfo.getRuleString2(), 1, THECOLORS['white'])
        self.screen.blit(ft1_surf, disp_pos)
    
    def blit_text(self, surface, text, pos, font, color=pygame.Color('white')): 
        words = [word.split(' ') for word in text.splitlines()] # 2D array where each row is a list of words. 
        space = font.size(' ')[0] # The width of a space. 
        max_width, max_height = surface.get_size() 
        x, y = pos 
        for line in words: 
            for word in line: 
                word_surface = font.render(word, True, color) 
                word_width, word_height = word_surface.get_size() 
                if x + word_width >= max_width: 
                    x = pos[0] # Reset the x. 
                    y += word_height # Start on new row. 
                surface.blit(word_surface, (x, y)) 
                x += word_width + space
            x = pos[0] # Reset the x. 
            y += word_height # Start on new row. 
    def blit_tile(self, dest, direction, tilecode, pos, mask=0):
        # blit 小牌（牌河牌、副露牌）
        # dest: destination surface; direction: 牌的朝向（0：自己牌河朝向，1：下家牌河朝向...），
        # tilecode: 牌代码，-1表示牌背，-2表示跳过不blit; pos：[x, y], mask: 1为暗转
        if tilecode == -2:
            return
        num = utils.tilecodeToNum(tilecode)
        if utils.isAka(tilecode):
            num = 0
        suit = utils.tilecodeToSuit(tilecode)
        if tilecode == -1:
            num, suit = 0, 3
            if direction >= 2:
                direction -= 2 # 因为tiles3的0z不是牌背，tiles2的0z是立着的牌背。。
        self._blit_tile_helper(dest, self.img_tiles[direction], \
            [self.TILE_WIDTHS[direction] * num, self.TILE_HEIGHTS[direction] * suit, self.TILE_WIDTHS[direction], self.TILE_HEIGHTS[direction]], \
            pos)
        if mask & 1:
            self._blit_tile_helper(dest, self.black_surfs[direction], None, pos)

    def blit_handtile(self, dest, direction, tilecode, pos, mask=0):
        # blit 手牌，如果direction是0，则blit大牌，否则blit小牌。另外牌背也是手牌的牌背（立着的）
        # 暂无法blit自己背面朝上的手牌。上下家的牌背也不是立着的。。
        if tilecode == -2:
            return
        num = utils.tilecodeToNum(tilecode)
        if utils.isAka(tilecode):
            num = 0
        suit = utils.tilecodeToSuit(tilecode)
        if tilecode == -1:
            num, suit = 0, 3
            if direction == 3:
                direction = 1 # 因为tiles3的0z不是牌背。。
        if direction == 0:
            # 自己手牌
            self._blit_tile_helper(dest, self.img_mytiles, \
                [self.TILE_WIDTH * num, self.TILE_HEIGHT * suit, self.TILE_WIDTH, self.TILE_HEIGHT], \
                pos)
            if mask & 1:
                # TODO
                pass
                #self._blit_tile_helper(dest, self.black_surf, None, pos)
        else:
            self._blit_tile_helper(dest, self.img_tiles[direction], \
                [self.TILE_WIDTHS[direction] * num, self.TILE_HEIGHTS[direction] * suit, self.TILE_WIDTHS[direction], self.TILE_HEIGHTS[direction]], \
                pos)
            if mask & 1:
                self._blit_tile_helper(dest, self.black_surfs[direction], None, pos)

    def _blit_tile_helper(self, dest, img, rect, pos):
        # dest: destination surface; direction: 牌的朝向（0：自己牌河朝向，1：下家牌河朝向...），
        # tilecode: 牌代码，-1表示牌背，-2表示跳过不blit; pos：[x, y], mask: 1为暗转
        dest.blit(img, pos, rect)

    def displayScoreChange(self, sc):
        # sc is the attribute (string)
        sc_split = sc.split(',')
        for tableDirection in range(4):
            playerIndex = (tableDirection + self.perspective) % 4
            if self.haifuInfo.tableInfo.isYonma() or (self.haifuInfo.tableInfo.isSanma() and playerIndex <= 2):
                temp_str = '東南西北'[-self.haifuInfo.kyokuInfos[self.currentKyoku].oya + playerIndex]
                temp_str += ' ' + self.haifuInfo.tableInfo.players[playerIndex]['name']
                temp_str += ' ' + sc_split[playerIndex * 2] + '00'
                sc_change = int(sc_split[playerIndex * 2 + 1])
                if sc_change > 0:
                    temp_str += ' +' + str(sc_change * 100)
                elif sc_change < 0:
                    temp_str += ' ' + str(sc_change * 100)
                self.blit_text(self.screen, temp_str, [300, 450 + tableDirection * 30], self.ten_font)

    def displayAgariInfo(self, attributes):
        disp_pos = [(1024 - 600) // 2, (740 - 450) // 2]
        # 显示和牌框背景
        s = pygame.Surface((600, 450))  # the size of your rect
        s.set_alpha(192)                # alpha level
        s.fill((0, 0, 0))           # this fills the entire surface
        self.screen.blit(s, disp_pos)
        yaku_string = ''
        han = 0
        if 'yaku' in attributes:
            yakus = attributes['yaku'].split(',')
            for i in range(len(yakus) // 2):
                yaku_string += (utils.yakucodeToString(int(yakus[2 * i])))
                yaku_string += (' ' + yakus[2 * i + 1] + '翻\n')
                han += int(yakus[2 * i + 1])
        if 'yakuman' in attributes:
            yakus = attributes['yakuman'].split(',')
            for i in range(len(yakus)):
                yaku_string += utils.yakucodeToString(int(yakus[i]))
                yaku_string += '\n'
                han += 13
        value = attributes['ten'].split(',')
        fu = int(value[0])
        score = int(value[1])
        limit = int(value[2])

        yaku_string += (str(fu) + '符' + str(han) + '翻 ' + str(score) + '点 ' + ['', '满贯', '跳满', '倍满', '三倍满', '役满'][limit] + '\n')
        

        disp_pos = [300, 200]
        # yaku_surf = self.yaku_font.render(yaku_string, True, THECOLORS['white'])
        self.blit_text(self.screen, yaku_string, disp_pos, self.yaku_font)
        self.displayScoreChange(attributes['sc'])
    def displayRyukyokuInfo(self, attributes):
        disp_pos = [(1024 - 600) // 2, (740 - 450) // 2]
        # 显示流局框背景
        s = pygame.Surface((600, 450))  # the size of your rect
        s.set_alpha(192)                # alpha level
        s.fill((0, 0, 0))           # this fills the entire surface
        self.screen.blit(s, disp_pos)
        
        ryukyoku_string = '流局'
        if 'type' in attributes:
            ryukyoku_string += '\n' + {'yao9' : '九种九牌', 'reach4' : '四家立直', 'ron3' : '三家和了', 'kan4' : '四杠散了', 'kaze4' : '四风连打', 'nm' : '流局满贯'}[attributes['type']]
            

        disp_pos = [300, 200]
        # yaku_surf = self.yaku_font.render(yaku_string, True, THECOLORS['white'])
        self.blit_text(self.screen, ryukyoku_string, disp_pos, self.yaku_font)
        self.displayScoreChange(attributes['sc'])
    def displayGameEndInfo(self):
        # 显示终局信息(各家点数、顺位等)
        if len(self.haifuInfo.kyokuInfos) == 0:
            return
        owari = self.haifuInfo.kyokuInfos[-1].status[-1]['attributes']['owari']
        sc_string = owari.split(',')
        playerScores = [(0, int(sc_string[0])), (1, int(sc_string[2])), (2, int(sc_string[4])), (3, int(sc_string[6]))]
        if self.haifuInfo.tableInfo.isSanma():
            playerScores.pop(-1)
        playerScores.sort(key = lambda ps : - ps[1] * 100 + ps[0])
        disp_string = '终局\n\n\n'
        for i in range(len(playerScores)):
            playerIndex = playerScores[i][0]
            score = playerScores[i][1] * 100
            disp_string += str(i+1) + '位 ' + self.haifuInfo.tableInfo.players[playerIndex]['name'] + ' (' + '东南西北'[playerIndex] + '起)'
            disp_string += ' ' + str(score) + '点\n\n'
        
        disp_pos = [(1024 - 600) // 2, (740 - 450) // 2]
        # 显示游戏结束框背景
        s = pygame.Surface((600, 450))  # the size of your rect
        s.set_alpha(192)                # alpha level
        s.fill((0, 0, 0))           # this fills the entire surface
        self.screen.blit(s, disp_pos)
        disp_pos = [350, 250]
        self.blit_text(self.screen, disp_string, disp_pos, self.ten_font)


    def displayKyokuInfo(self, action = False):
        # 显示第n局（n从0开始）的局信息（其实是第step步的全部信息..）
        # 若action为真，则显示发声
        if self.currentKyoku >= len(self.haifuInfo.kyokuInfos):
            logger.error('局数越界')
            return
        info = self.haifuInfo.kyokuInfos[self.currentKyoku]
        step = self.currentStep

        # 显示桌子中间的黑框
        disp_pos = [(1024 - 6 * self.TILE_WIDTHS[0]) // 2, (740 - 6 * self.TILE_HEIGHT_EFF[1]) // 2]
        s = pygame.Surface((6 * self.TILE_WIDTHS[0], 6 * self.TILE_HEIGHT_EFF[1]))  # the size of your rect
        s.set_alpha(128)                # alpha level
        s.fill((0, 0, 0))           # this fills the entire surface
        self.screen.blit(s, disp_pos)

        # 显示牌河
        self.displayRivers(info.status[step])
        # 显示副露
        self.displayFuros(info.status[step])
        # 显示dora指示牌
        x, y = 419, 260
        for i in range(5):
            # 默认为未翻开 0z(tilecode is -1)牌画为牌背
            if i < len(info.status[step]['doraIndicators']):
                tile = info.status[step]['doraIndicators'][i]
            else:
                tile = -1
            self.blit_tile(self.screen, 0, tile, [x + i * self.TILE_WIDTHS[0], y])


        # 显示局次
        disp_pos = [473, 352]
        kyoku_surf = self.kyoku_font.render('東南西北'[info.kyoku // 4] + str(info.kyoku % 4 + 1) + '局', True, THECOLORS['white'])
        self.screen.blit(kyoku_surf, disp_pos)

        # 显示本场 场供 残余枚数
        disp_pos = [458, 392]
        kyoku_surf = self.kyoku_font_small.render(str(info.honba) + '本 ' + str(info.status[step]['kyoutaku']) + '供' + ' 残' + str(info.status[step]['remaining']) + '枚', 1, THECOLORS['white'])
        self.screen.blit(kyoku_surf, disp_pos)
        
        # 显示点数及亲子
        who = utils.whosTurn(info.status[step]['tag'], info.status[step]['attributes']) 
        if who != -1:
            self.whosTurn = who
        wind_disp_pos = [[466, 420], [590, 401], [532, 320], [410, 336]]
        ten_disp_pos = [[496, 420], [590, 341], [470, 320], [410, 363]]
        for i in range(4):
            playerIndex = (i + self.perspective) % 4
            if self.haifuInfo.tableInfo.isYonma() or (self.haifuInfo.tableInfo.isSanma() and playerIndex <= 2):
                if self.whosTurn == playerIndex:
                    wind_surf = self.wind_font.render('東南西北'[-info.oya + playerIndex], True, (255,227,60))
                else:
                    wind_surf = self.wind_font.render('東南西北'[-info.oya + playerIndex], True, (160,160,160))
                ten_surf = self.ten_font.render(str(info.status[step]['ten'][playerIndex] * 100), True, \
                    THECOLORS['white'] if info.status[step]['online'][playerIndex] else THECOLORS['red'])
                wind_surf = pygame.transform.rotozoom(wind_surf, i * 90, 1)
                ten_surf = pygame.transform.rotozoom(ten_surf, i * 90, 1)
                self.screen.blit(wind_surf, wind_disp_pos[i])
                self.screen.blit(ten_surf, ten_disp_pos[i])

        tag = info.status[step]['tag']
        attributes = info.status[step]['attributes']
        
        if step >= 1:
            prev_tag = info.status[step - 1]['tag']
            if prev_tag[0] in 'DEFG' and prev_tag[1] in '0123456789':
                self.justDrawn = False
            
        hands = info.status[step]['hands']
        if tag[0] in 'TUVW' and tag[1] in '0123456789':
            self.justDrawn = True
        for i in range(4):
            is_kakan_or_kita = False
            if tag == 'N':
                m = int(attributes['m'])
                furo = utils.decodeFuro(m)
                if furo.isKan == 2 or furo.isKita:
                    is_kakan_or_kita = True            
            if (ord(tag[0]) - ord('D') == i and tag[1] in '0123456789') or is_kakan_or_kita:
                # 刚切牌(加杠、拔北)还没通过，手牌先不理牌，留出空位以清楚表示手模切
                hands[i] = deepcopy(info.status[step - 1]['hands'][i])
                if is_kakan_or_kita:
                    hai = furo.tilecodes[-1]
                else:
                    hai = int(tag[1:])
                hands[i] = [hands[i][j] if hands[i][j] != hai else -2 for j in range(len(hands[i]))]
            elif len(hands[i]) % 3 == 2 and self.justDrawn:
                tsumo = hands[i].pop(-1)
                hands[i].sort()
                hands[i].append(tsumo)
            else:
                hands[i].sort()
        self.displayHands(hands)
        

        # 显示发声
        if action:
            if tag == 'N':
                m = int(attributes['m'])
                furo = utils.decodeFuro(m)
                self.displayCall(int(attributes['who']), furo.getFuroTypeString())
            elif tag == 'AGARI':
                who = int(attributes['who'])
                fromWho = int(attributes['fromWho'])
                self.displayCall(who, '自摸' if who == fromWho else '荣')
                if 'paoWho' in attributes:
                    paoWho = int(attributes['paoWho'])
                    self.displayCall(paoWho, 'pao')
            elif tag == 'REACH':
                who = int(attributes['who'])
                reach_step = int(attributes['step'])
                if reach_step == 1:
                    self.displayCall(who, '立直')
        # 显示和牌、流局
        if tag == 'AGARI':
            self.displayAgariInfo(attributes)
        elif tag == 'RYUUKYOKU':
            self.displayRyukyokuInfo(attributes)
        '''
        class KyokuInfo:
            def __init__(self):
                self.kyoku = 0
                self.honba = 0
                self.oya = 0
                self.status = [] # dict[], 每个dict里都有'tag' : char[], 'attributes': dict, 'hands' : int[4][14], 'rivers' : int[4][25], 'furos' : Furo[4][], 
                                # 'doraIndicators' : int[], 'kyoutaku' : int, 'ten' : int[4], 'remaining' : int

        '''
    def displayRivers(self, status):
        # rivers: int[4][][2]
        rivers = status['rivers']

        indexAndPos = [[]] # 由于非自家牌河需要很诡异的绘图顺序，我们先把所有贴图的位置存起来，最后一起画
        # 这是一个(directionOnMap, [x, y])[4][]
        # indexAndPos[0]留空 所以初始化为[[]]

        # 显示下家的牌河
        playerIndex = (1 + self.perspective) % 4
        river = rivers[playerIndex]
        x, y = (1024 + 6 * self.TILE_WIDTHS[0]) // 2, (740 + 6 * self.TILE_HEIGHT_EFF[1]) // 2
        length = len(river)
        col, row = 0, 0
        x_offset, y_offset = 0, 0 # offset 是左下角的坐标 相对于 下家视角里的牌河左上角 的偏移量
        i = 0
        indexAndPos.append([])
        while i < length:
            [_, discardInfo] = river[i]
            if discardInfo & 2:
                # 被副露走了
                i += 1
                continue
            if (i == length - 1) and status['tag'][0] in 'DEFG' and status['tag'][1] in '0123456789':
                who = ord(status['tag'][0]) - ord('D')
                if who == playerIndex:
                    # 有人刚切了牌，把牌往右下角移动一下，表示还未通过
                    x_offset += 5
                    y_offset -= 5
            if (discardInfo & 4) and not (discardInfo & 2):
                # (伪)立直宣言
                indexAndPos[1].append( (i, [x + x_offset + (self.TILE_WIDTHS[1] - self.TILE_WIDTHS[2]), y + y_offset - (self.TILE_HEIGHTS[2])]) )
            else:
                indexAndPos[1].append( (i, [x + x_offset, y + y_offset - self.TILE_HEIGHTS[1]]) ) # 因为blit要牌的左上角坐标，而offset是牌的左下角坐标 所以y要减去牌的高度
            
            col += 1
            if col == 6 and row < 3:
                row += 1
                x_offset += self.TILE_WIDTHS[1]
                col = 0
                y_offset = 0
            else:
                y_offset -= (self.TILE_HEIGHT_EFF[1] if not discardInfo & 4 else self.TILE_HEIGHT_EFF[2])
            i += 1

        # 显示对家的牌河
        playerIndex = (2 + self.perspective) % 4
        river = rivers[playerIndex]
        x, y = (1024 + 6 * self.TILE_WIDTHS[0]) // 2, (740 - 6 * self.TILE_HEIGHT_EFF[1]) // 2
        length = len(river)
        col, row = 0, 0
        x_offset, y_offset = 0, 0 # offset 是右下角的坐标 相对于 对家视角里的牌河左上角 的偏移量
        i = 0
        indexAndPos.append([])
        while i < length:
            [_, discardInfo] = river[i]
            if discardInfo & 2:
                # 被副露走了
                i += 1
                continue
            if (i == length - 1) and status['tag'][0] in 'DEFG' and status['tag'][1] in '0123456789':
                who = ord(status['tag'][0]) - ord('D')
                if who == playerIndex:
                    # 有人刚切了牌，把牌往右下角移动一下，表示还未通过
                    x_offset -= 5
                    y_offset -= 5
            if (discardInfo & 4) and not (discardInfo & 2):
                # (伪)立直宣言
                indexAndPos[2].append( (i, [x + x_offset - self.TILE_WIDTHS[3], y + y_offset - self.TILE_HEIGHTS[2]]) )
            else:
                indexAndPos[2].append( (i, [x + x_offset - self.TILE_WIDTHS[2], y + y_offset - self.TILE_HEIGHTS[2]]) )
            
            col += 1
            if col == 6 and row < 3:
                row += 1
                y_offset -= self.TILE_HEIGHT_EFF[2]
                col = 0
                x_offset = 0
            else:
                x_offset -= (self.TILE_WIDTHS[2] if not discardInfo & 4 else self.TILE_WIDTHS[3])
            i += 1

        # 显示上家的牌河
        playerIndex = (3 + self.perspective) % 4
        river = rivers[playerIndex]
        x, y = (1024 - 6 * self.TILE_WIDTHS[0]) // 2, (740 - 6 * self.TILE_HEIGHT_EFF[1]) // 2 - (self.TILE_HEIGHTS[3] - self.TILE_HEIGHT_EFF[3])
        length = len(river)
        col, row = 0, 0
        x_offset, y_offset = 0, 0 # offset 是牌的右上角的坐标 相对于 上家视角里的牌河左上角 的偏移量
        i = 0
        indexAndPos.append([])
        while i < length:
            [_, discardInfo] = river[i]
            if discardInfo & 2:
                # 被副露走了
                i += 1
                continue
            if (i == length - 1) and status['tag'][0] in 'DEFG' and status['tag'][1] in '0123456789':
                who = ord(status['tag'][0]) - ord('D')
                if who == playerIndex:
                    # 有人刚切了牌，把牌往左下角移动一下，表示还未通过
                    x_offset -= 5
                    y_offset += 5
            if (discardInfo & 4) and not (discardInfo & 2):
                # (伪)立直宣言
                indexAndPos[3].append( (i, [x + x_offset - self.TILE_WIDTHS[3], y + y_offset]) )
            else:
                indexAndPos[3].append( (i, [x + x_offset - self.TILE_WIDTHS[3], y + y_offset]) )
            
            col += 1
            if col == 6 and row < 3:
                row += 1
                x_offset -= self.TILE_WIDTHS[3]
                col = 0
                y_offset = 0
            else:
                y_offset += (self.TILE_HEIGHT_EFF[3] if not discardInfo & 4 else self.TILE_HEIGHT_EFF[0])
            i += 1


        # 把牌河真正显示在桌面上

        # order是blit的顺序 以产生正确的3d效果
        order = [[], \
            [5,4,3,2,1,0,11,10,9,8,7,6,24,23,22,21,20,19,18,17,16,15,14,13,12], \
            [24,23,22,21,20,19,18,17,16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,1,0], \
            [12,13,14,15,16,17,18,19,20,21,22,23,24,6,7,8,9,10,11,0,1,2,3,4,5] ]
        for direction in [1, 2, 3]:
            playerIndex = (direction + self.perspective) % 4
            river = rivers[playerIndex]
            for j in order[direction]:
                if j >= len(indexAndPos[direction]):
                    continue
                (i, pos) = indexAndPos[direction][j]
                [tile, discardInfo] = river[i]
                if discardInfo & 4:
                    # (伪)立直宣言
                    self.blit_tile(self.screen, (direction+1)%4, tile, pos, discardInfo)
                else:
                    self.blit_tile(self.screen, direction, tile, pos, discardInfo)

        # 显示自己的牌河
        playerIndex = (0 + self.perspective) % 4
        river = rivers[playerIndex]
        x, y = (1024 - 6 * self.TILE_WIDTHS[0]) // 2, (740 + 6 * self.TILE_HEIGHT_EFF[1]) // 2 - (self.TILE_HEIGHTS[0] - self.TILE_HEIGHT_EFF[0])
        length = len(river)
        col, row = 0, 0
        x_offset, y_offset = 0, 0
        i = 0
        while i < length:
            [tile, discardInfo] = river[i]
            if discardInfo & 2:
                # 被副露走了
                i += 1
                continue
            if (i == length - 1) and status['tag'][0] in 'DEFG' and status['tag'][1] in '0123456789':
                who = ord(status['tag'][0]) - ord('D')
                if who == playerIndex:
                    # 有人刚切了牌，把牌往右下角移动一下，表示还未通过
                    x_offset += 5
                    y_offset += 5

            if (discardInfo & 4) and not (discardInfo & 2):
                # (伪)立直宣言
                self.blit_tile(self.screen, 1, tile, [x + x_offset, y + y_offset + (self.TILE_HEIGHTS[0] - self.TILE_HEIGHTS[1])], discardInfo)
            else:
                self.blit_tile(self.screen, 0, tile, [x + x_offset, y + y_offset], discardInfo)
            
            col += 1
            if col == 6 and row < 3:
                row += 1
                y_offset += self.TILE_HEIGHT_EFF[0]
                col = 0
                x_offset = 0
            else:
                x_offset += (self.TILE_WIDTHS[0] if not discardInfo & 4 else self.TILE_WIDTHS[1])
            i += 1

    def displayFuros(self, status):
        # 显示所有副露
        '''
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
        '''
        # 显示副露
        for tableDirection in range(4):
            # 为防止和子循环里的i和direction重名，大for循环变量用了个新名字
            playerIndex = (tableDirection + self.perspective) % 4
            furos = status['furos'][playerIndex]
            tileDrawInfo = [] # [tilecode, discardInfo, direction, (x, y)][]
            kitaDrawInfo = [] # [tilecode, discardInfo, direction, (x, y)][]
            [x, y] = [[930, 725], [944, 50], [90, 40], [80, 710]][tableDirection]
            [kita_x, kita_y] = [[830, 645], [864, 200], [190, 120], [160, 560]][tableDirection] # 拔北的初始位置
            x_offset, y_offset = 0, 0 # 这是累积offset
            horiz_width = self.TILE_WIDTHS[1]
            horiz_height_eff = self.TILE_HEIGHT_EFF[1]
            horiz_height = self.TILE_HEIGHTS[1]
            vert_width = self.TILE_WIDTHS[0]
            vert_height_eff = self.TILE_HEIGHT_EFF[0]
            vert_height = self.TILE_HEIGHTS[0]
            
            # 对上下家来说，horiz才是vertical，vertical才是horiz。所以对上下家，vertical和horiz的offset交换了一下
            [horiz_tile_disp_x_offset, horiz_tile_disp_y_offset] = [[-horiz_width, -horiz_height], [-vert_width, 0], [0, 0], [0, -vert_height]][tableDirection]
            [vert_tile_disp_x_offset, vert_tile_disp_y_offset] = [[-vert_width, -vert_height],[-horiz_width, 0], [0, 0], [0, -horiz_height]][tableDirection]
            [horiz_tile_change_x_offset, horiz_tile_change_y_offset] = [[-horiz_width, 0], [0, vert_height_eff], [horiz_width, 0], [0, -vert_height_eff]][tableDirection]
            [vert_tile_change_x_offset, vert_tile_change_y_offset] = [[-vert_width, 0], [0, horiz_height_eff], [vert_width, 0], [0, -horiz_height_eff]][tableDirection]
            [stack_disp_x_offset, stack_disp_y_offset] = [[0, -horiz_height_eff], [-vert_width, 0], [0, horiz_height_eff], [vert_width, 0]][tableDirection]
            for furo in furos:
                tilecodes = deepcopy(furo.tilecodes)
                if furo.isKita:
                    kitaDrawInfo.append([tilecodes[0], furo.isTsumogiri, tableDirection, (kita_x + vert_tile_disp_x_offset + vert_tile_change_x_offset * len(kitaDrawInfo), kita_y + vert_tile_disp_y_offset + vert_tile_change_y_offset * len(kitaDrawInfo))])
                    continue
                if furo.isChi or furo.isPon:
                    temp = tilecodes[furo.whichTileIsClaimed]
                    tilecodes[furo.whichTileIsClaimed] = tilecodes[3 - furo.fromWhoRelative]
                    tilecodes[3 - furo.fromWhoRelative] = temp
                    for i in [2, 1, 0]:
                        if furo.fromWhoRelative == 3 - i:
                            tile = tilecodes[i]
                            discardInfo = furo.isTsumogiri
                            direction = ([3, 1, 1][furo.fromWhoRelative - 1] + tableDirection) % 4
                            tileDrawInfo.append([tile, discardInfo, direction, (x + x_offset + horiz_tile_disp_x_offset, y + y_offset + horiz_tile_disp_y_offset)])
                            x_offset += horiz_tile_change_x_offset
                            y_offset += horiz_tile_change_y_offset
                        else:
                            tile = tilecodes[i]
                            discardInfo = 0
                            direction = tableDirection
                            tileDrawInfo.append([tile, discardInfo, direction, (x + x_offset + vert_tile_disp_x_offset, y + y_offset + vert_tile_disp_y_offset)])
                            x_offset += vert_tile_change_x_offset
                            y_offset += vert_tile_change_y_offset
                elif furo.isKan == 1 and furo.fromWhoRelative != 0:
                    # 大明杠
                    temp = tilecodes[furo.whichTileIsClaimed]
                    target_index = [-1, 3, 1, 0][furo.fromWhoRelative]
                    tilecodes[furo.whichTileIsClaimed] = tilecodes[target_index]
                    tilecodes[target_index] = temp
                    for i in [3, 2, 1, 0]:
                        if i == target_index:
                            tile = tilecodes[i]
                            discardInfo = furo.isTsumogiri
                            direction = ([3, 1, 1][furo.fromWhoRelative - 1] + tableDirection) % 4
                            tileDrawInfo.append([tile, discardInfo, direction, (x + x_offset + horiz_tile_disp_x_offset, y + y_offset + horiz_tile_disp_y_offset)])
                            x_offset += horiz_tile_change_x_offset
                            y_offset += horiz_tile_change_y_offset
                        else:
                            tile = tilecodes[i]
                            discardInfo = 0
                            direction = tableDirection
                            tileDrawInfo.append([tile, discardInfo, direction, (x + x_offset + vert_tile_disp_x_offset, y + y_offset + vert_tile_disp_y_offset)])
                            x_offset += vert_tile_change_x_offset
                            y_offset += vert_tile_change_y_offset
                elif furo.isKan == 1 and furo.fromWhoRelative == 0:
                    # 暗杠
                    # 把刚摸到的牌放在index 1
                    tilecodes[1], tilecodes[furo.whichTileIsClaimed] = tilecodes[furo.whichTileIsClaimed], tilecodes[1]
                    if tilecodes[0] % 4 == 0:
                        # 把0交换到index 2，从而展示出赤
                        tilecodes[0], tilecodes[2] = tilecodes[2], tilecodes[0]
                    for i in [3, 2, 1, 0]:
                        tile = tilecodes[i]
                        discardInfo = furo.isTsumogiri
                        if i == 3 or i == 0:
                            tile = -1
                            discardInfo = 0
                        direction = tableDirection
                        tileDrawInfo.append([tile, discardInfo, direction, (x + x_offset + vert_tile_disp_x_offset, y + y_offset + vert_tile_disp_y_offset)])
                        x_offset += vert_tile_change_x_offset
                        y_offset += vert_tile_change_y_offset
                elif furo.isKan == 2:
                    # 加杠
                    temp = tilecodes[furo.whichTileIsClaimed]
                    tilecodes[furo.whichTileIsClaimed] = tilecodes[3 - furo.fromWhoRelative]
                    tilecodes[3 - furo.fromWhoRelative] = temp
                    for i in [2, 1, 0]:
                        if furo.fromWhoRelative == 3 - i:
                            tile = tilecodes[i]
                            discardInfo = furo.isTsumogiri
                            direction = ([3, 1, 1][furo.fromWhoRelative - 1] + tableDirection) % 4
                            # 叠着显示两张牌。需要加上stack_disp_xy_offset
                            tdi2 = [tile, furo.isKakanTsumogiri, direction, (x + x_offset + horiz_tile_disp_x_offset + stack_disp_x_offset, y + y_offset + horiz_tile_disp_y_offset + stack_disp_y_offset)]
                            tdi1 = [tile, discardInfo, direction, (x + x_offset + horiz_tile_disp_x_offset, y + y_offset + horiz_tile_disp_y_offset)]
                            if tableDirection == 0 or tableDirection == 2:
                                tileDrawInfo.append(tdi1)
                                tileDrawInfo.append(tdi2)
                            else:
                                tileDrawInfo.append(tdi2)
                                tileDrawInfo.append(tdi1)  
                            x_offset += horiz_tile_change_x_offset
                            y_offset += horiz_tile_change_y_offset
                        else:
                            tile = tilecodes[i]
                            discardInfo = 0
                            direction = tableDirection
                            tileDrawInfo.append([tile, discardInfo, direction, (x + x_offset + vert_tile_disp_x_offset, y + y_offset + vert_tile_disp_y_offset)])
                            x_offset += vert_tile_change_x_offset
                            y_offset += vert_tile_change_y_offset
            
            # 真正画出来
            for drawInfo in [tileDrawInfo, kitaDrawInfo]:
                if tableDirection == 0 or tableDirection == 3:
                    r = range(len(drawInfo) - 1, -1, -1)
                else:
                    r = range(len(drawInfo))
                for i in r:
                    (tile, discardInfo, direction, pos) = drawInfo[i]
                    self.blit_tile(self.screen, direction, tile, pos, discardInfo)

        
    def displayHands(self, hands):
        # hands: int[4][]
        playerIndex = (0 + self.perspective) % 4
        hand = hands[playerIndex]
        x = 200
        y = 660
        length = len(hand)
        if length % 3 == 2 and self.justDrawn:
            length -= 1
        self.screen.blit(self.img_shadow, [x + length * self.TILE_WIDTH - int(7 * self.display_ratio), y + int(32 * self.display_ratio)])
        for i in range(length):
            tile = hand[i]
            self.blit_handtile(self.screen, 0, tile, [x + i * self.TILE_WIDTH, y], 0)
        if len(hand) % 3 == 2 and self.justDrawn:
            tile = hand[-1]
            if tile != -2:
                self.screen.blit(self.img_shadow, [x + 4 + (length + 1) * self.TILE_WIDTH - int(7 * self.display_ratio), y + int(32 * self.display_ratio)])
            self.blit_handtile(self.screen, 0, tile, [x + 4 + length * self.TILE_WIDTH, y], 0)
            #self.screen.blit(self.img_mytiles, [x + 4 + length * self.TILE_WIDTH, y], [self.TILE_WIDTH * num, self.TILE_HEIGHT * suit, self.TILE_WIDTH, self.TILE_HEIGHT])


        playerIndex = (1 + self.perspective) % 4
        hand = hands[playerIndex]
        length = len(hand)
        if length % 3 == 2 and self.justDrawn:
            length -= 1
        x, y = 894, 540
        if len(hand) % 3 == 2 and self.justDrawn:
            tile = hand[-1]
            self.blit_handtile(self.screen, 1, tile, [x, y - 3 - length * self.TILE_HEIGHT_EFF[1]], 0)

        for i in range(length - 1, -1, -1):
            tile = hand[i]
            self.blit_handtile(self.screen, 1, tile, [x, y - i * self.TILE_HEIGHT_EFF[1]], 0)

        playerIndex = (2 + self.perspective) % 4
        hand = hands[playerIndex]
        length = len(hand)
        if length % 3 == 2 and self.justDrawn:
            length -= 1
        x, y = 720, 40
        if len(hand) % 3 == 2 and self.justDrawn:
            tile = hand[-1]
            self.blit_handtile(self.screen, 2, tile, [x - 3 - length * self.TILE_WIDTHS[2], y], 0)

        for i in range(length - 1, -1, -1):
            tile = hand[i]
            self.blit_handtile(self.screen, 2, tile, [x - i * self.TILE_WIDTHS[2], y], 0)


        playerIndex = (3 + self.perspective) % 4
        hand = hands[playerIndex]
        length = len(hand)
        if length % 3 == 2 and self.justDrawn:
            length -= 1
        x, y = 80, 160
        for i in range(length):
            tile = hand[i]
            self.blit_handtile(self.screen, 3, tile, [x, y + i * self.TILE_HEIGHT_EFF[3]], 0)
        if len(hand) % 3 == 2 and self.justDrawn:
            tile = hand[-1]
            self.blit_handtile(self.screen, 3, tile, [x, y + 3 + length * self.TILE_HEIGHT_EFF[3]], 0)

    def displayCall(self, who, call):
        # 显示发声（例如副露 立直 自摸）
        text = call
        if call == 'chi':
            text = '吃'
        elif call == 'pon':
            text = '碰'
        elif call == 'kan':
            text = '杠'
        elif call == 'kita':
            text = '拔北'
        elif call == 'reach' or call == 'riichi':
            text = '立直'
        elif call == 'ron':
            text = '荣'
        elif call == 'tsumo':
            text = '自摸'
        elif call == 'pao':
            text = '包牌'
        sp = CallTextSprite((who - self.perspective) % 4, text)
        self.calltext_group.add(sp)

    def changeKyoku(self, newKyoku):
        if newKyoku != self.currentKyoku:
            self.currentKyoku = newKyoku % len(self.haifuInfo.kyokuInfos)
            self.justDrawn = False

    def displayNextStep(self):
        info = self.haifuInfo.kyokuInfos[self.currentKyoku]
        if self.currentStep >= len(info.status) - 1:
            if self.currentKyoku >= len(self.haifuInfo.kyokuInfos) - 1:
                if self.currentStep == len(info.status) - 1:
                    self.currentStep += 1
                    return
            self.changeKyoku(self.currentKyoku + 1)
            self.currentStep = 1
            self.calltext_group.empty()
        else:
            self.currentStep += 1
        self.displayBackground()
        self.displayPlayerInfo()
        self.displayRuleInfo()
        self.displayKyokuInfo(True)
        #self.calltext_group.update()
        self.calltext_group.draw(haifuViewer.screen)
    def displayPreviousStep(self):
        tag = ''
        while not (len(tag) >= 2 and tag[0] in 'TUVW' and tag[1] in '0123456789'):
            if self.currentStep <= 1:
                #if self.currentKyoku <= 0:
                #    return
                self.changeKyoku(self.currentKyoku - 1)
                self.currentStep = len(self.haifuInfo.kyokuInfos[self.currentKyoku].status) - 1
            else:
                self.currentStep -= 1
            tag = self.haifuInfo.kyokuInfos[self.currentKyoku].status[self.currentStep]['tag']
        

        self.calltext_group.empty()

        self.displayBackground()
        self.displayPlayerInfo()
        self.displayRuleInfo()
        self.displayKyokuInfo(False)
        #self.calltext_group.update()
        self.calltext_group.draw(haifuViewer.screen)
    def displayNextKyoku(self):
        #if self.currentKyoku >= len(self.haifuInfo.kyokuInfos) - 1:
        #    return
        self.changeKyoku(self.currentKyoku + 1)
        self.currentStep = 1
    def displayPreviousKyoku(self):
        #if self.currentKyoku <= 0:
        #    return
        self.changeKyoku(self.currentKyoku - 1)
        self.currentStep = 1
    def display(self):
        self.displayBackground()
        if self.currentKyoku == len(self.haifuInfo.kyokuInfos) - 1 and self.currentStep == len(self.haifuInfo.kyokuInfos[self.currentKyoku].status):
            self.displayGameEndInfo()
            return
        self.displayPlayerInfo()
        self.displayRuleInfo()
        self.displayKyokuInfo(False)
        self.calltext_group.update()
        self.calltext_group.draw(self.screen)



class CallTextSprite(pygame.sprite.Sprite):

    def __init__(self, who, calltext):
        # Call the parent class (Sprite) constructor
        pygame.sprite.Sprite.__init__(self)
        self.who = who
        self.calltext = calltext
        # Create an image of the block, and fill it with a color.
        # This could also be an image loaded from the disk.
        self.call_font = pygame.freetype.Font('C:\\windows\\fonts\\simhei.ttf', 48)

        self.orig_image, self.rect = self.call_font.render(calltext, THECOLORS['white'])

        # Fetch the rectangle object that has the dimensions of the image
        # Update the position of this object by setting the values of rect.x and rect.y
        # self.rect = self.image.get_rect()
        self.alpha = 255
        # self.image.set_alpha(self.alpha)
        self.image = self.orig_image.copy()
        self.image.fill((255,255,255,self.alpha), None, pygame.BLEND_RGBA_MULT)

        self.rect.center = [(500, 600), (799, 350), (500, 150), (225, 350)][who]

    def update(self, *args):
        # self.rect.x += 2
        # self.rect.y += 2
        if self.alpha > 8:
            self.alpha -= 8
        else:
            self.kill()
        self.image = self.orig_image.copy()
        self.image.fill((255,255,255,self.alpha), None, pygame.BLEND_RGBA_MULT)
        # self.image = self.call_font.render(self.calltext, True, THECOLORS['white'])
        


if __name__ == "__main__":
    setupLogging()
    pygame.init()
    pygame.freetype.init()
    haifuViewer = HaifuViewer()

    # 0: cure log, 1: SB log, 2: 加杠, 3: 四杠, 4: 99、一炮双响, 
    # 5: 三家拔线、三个noname、两家同分, 6: 掉线重连, 7: 包牌, 8: 一家碰了同一家两次，然后加杠
    haifuTestset = ['cure_log/2019071110gm-0061-0000-5dafa870&tw=3.mjlog', \
        '2020050104gm-0039-0000-cdaa92c2&tw=2.mjlog', \
    '2020052721gm-0009-8141-739a27c4&tw=2.mjlog', \
    "2014050722gm-0069-0000-27288fe7&tw=0.mjlog", \
    '202005/2020050913gm-0039-0000-b7118611&tw=0.mjlog', \
    '2010072807gm-0101-0000-09632ebd&tw=0.mjlog', \
    '2020022411gm-00b9-0000-d17f0ebe掉线重连&tw=2.mjlog', \
    '2020053112gm-0089-0000-73280cdc包牌&tw=0.mjlog', \
    '2020060513gm-0011-0000-efb377c6加杠bug&tw=0.mjlog']
    if len(sys.argv) >= 2:
        haifuViewer.open(sys.argv[1])
    else:
        haifuViewer.open(haifuTestset[8])
    
    haifuViewer.initTable()
    clock = pygame.time.Clock()
    pygame.key.set_repeat(500, 30)
    running = True
    counter = 0
    while running:
        #counter += 1
        #if counter % 5 == 0:
        #    haifuViewer.displayNextStep()
        #    pygame.display.flip()
        #else:
        #    haifuViewer.display()
        #    pygame.display.flip()
        haifuViewer.display()
        pygame.display.flip()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RSHIFT or event.key == pygame.K_LSHIFT:
                    haifuViewer.perspective = (haifuViewer.perspective + 1) % 4
                    if haifuViewer.haifuInfo.tableInfo.isSanma() and haifuViewer.perspective == 3:
                        haifuViewer.perspective = 0
                elif event.key == pygame.K_RIGHT:
                    haifuViewer.displayNextStep()
                elif event.key == pygame.K_LEFT:
                    haifuViewer.displayPreviousStep()
                elif event.key == pygame.K_UP:
                    haifuViewer.displayPreviousKyoku()
                elif event.key == pygame.K_DOWN:
                    haifuViewer.displayNextKyoku()
        clock.tick(30)

