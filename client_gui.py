# -*- coding: utf-8 -*-
import pygame
import pygame.freetype
from pygame.color import THECOLORS
import logging
from copy import deepcopy
import utils
import furo_select
from efficiency.agari_checker import AgariChecker
from analyzer import TableInfo
import const
import tenhou_client
from haifu_downloader import HaifuDownloader
import settings
import time
import random
import queue
from urllib.parse import unquote
import os
import threading

logger = logging.getLogger('tenhou')

def setupLogging():
    logger = logging.getLogger('tenhou')
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

class KyokuInfo:
    def __init__(self):
        self.sanma = False # 这里设计得有点烂，gameinfo里有是否是三麻的信息，但kyokuinfo不知道。现在kyokuinfo需要用到这个信息，只能再搞一个变量
        self.kyoku = 0
        self.honba = 0
        self.kyoutaku = 0
        self.doraIndicators = []
        self.ten = [0,0,0,0]
        self.oya = 0
        self.remaining = 0
        self.revealedTiles = set()
        self.remainingTiles = [4] * 34
        self.hands = [[], [], [], []]
        self.rivers = [[], [], [], []]
        self.temporarilyPassedTiles = [[], [], [], []]
        self.furos = [[], [], [], []] # Furo[4][]
        self.numNotPassedTiles = [34] * 4
        self.numNotPassedSujis = [18] * 4
        self.reached = [False] * 4 # 是否立直了
        self.furiten = False
        self.machi = []
        self.discardToMachi = {}
        self.whosTurn = 0 # 谁的回合
        self.playerState = 0 # 0: 没人的回合 1：摸了牌 2：切了牌还没通过 3：副露后 4: 加杠/拔北牌还没通过
        self.agariInfo = [] # 有可能多家和了 所以是个空列表
        self.ryukyokuInfo = None
        self.owariInfo = None
    def init_sanma(self):
        # 如果是三麻，要先调用这个函数
        self.sanma = True
        self.numNotPassedTiles = [27] * 4
        self.numNotPassedSujis = [12] * 4
        for i in range(1, 8):
            self.remainingTiles[i] = 0
    def reveal_tile(self, tilecode):
        if tilecode >= 0:
            if tilecode not in self.revealedTiles:
                self.revealedTiles.add(tilecode)
                self.remainingTiles[tilecode >> 2] -= 1
                for i in range(4):
                    self.numNotPassedTiles[i], self.numNotPassedSujis[i] = self.calc_not_passed_tiles_and_sujis(i)
    def calc_not_passed_tiles_and_sujis(self, playerIndex):
        # 返回对玩家playerIndex尚未通过的牌的种类数和筋根数
        passedTiles34 = set()
        passedSujis = [False] * 18 # 18组筋，分别表示14m 25m ... 69m 14p 25p ... 69p 14s ... 69s，True表示已通过
        for [tile, _] in self.rivers[playerIndex]:
            passedTiles34.add(tile >> 2)
        for tile in self.temporarilyPassedTiles[playerIndex]:
            passedTiles34.add(tile >> 2)
        for tile34 in passedTiles34:
            if tile34 < 27: # 不是字牌
                from_zero = tile34 % 9 # 数牌的数字，从0开始，例如1p是0 2p是1 ...
                if from_zero < 6: # 123456
                    passedSujis[tile34 // 9 * 6 + from_zero] = True
                if tile34 % 9 >= 3: # 456789
                    passedSujis[tile34 // 9 * 6 + from_zero - 3] = True
        # 接下来考虑壁对通过的筋的贡献
        for tile34 in range(27): # 仅考虑数牌的壁 所以是27
            num = self.remainingTiles[tile34]
            if num == 0: # 壁
                from_zero = tile34 % 9
                if from_zero >= 1 and from_zero <= 6: # 234567
                    passedSujis[tile34 // 9 * 6 + from_zero - 1] = True # 若n壁了，则(n-1, n+2)这组筋过了
                if from_zero >= 2 and from_zero <= 7: # 345678
                    passedSujis[tile34 // 9 * 6 + from_zero - 2] = True # 若n壁了，则(n-2, n+1)这组筋过了
        
        num_not_passed_tiles = 27 - len(passedTiles34) if self.sanma else 34 - len(passedTiles34)
        return num_not_passed_tiles, passedSujis.count(False)


class GameControlInfo:
    def __init__(self):
        self.canDiscard = False
        self.rotateNextTile = [False] * 4 # 下一张牌是否要横过来显示
        self.suggestion = 0 # 对手切牌标签中的't'
        self.suggestedTile = -1 # 含有't'的那张牌
        self.kanSuggestions = [] # 自己摸完牌之后，可以怎么杠 [[杠种类，tilecode]] 杠种类：暗杠为4 加杠为5 tilecode：暗杠为tilecode>>2<<2 加杠为那张加杠牌本身
        self.selectedTiles = []
        self.displayScoreDiff = False # 桌子中间显示分差还是绝对分数
        
class GameInfo:
    def __init__(self):
        self.tableInfo = TableInfo()
        self.kyokuInfo = KyokuInfo()
        self.gameControlInfo = GameControlInfo()
        self.initialOya = 0
        self.playerExist = [False] * 4
        self.online = [True] * 4
        self.gpid = ''
        self.log = ''
    def p(self):
        ruleString = self.tableInfo.getRuleString()
        print(ruleString)
        for i in range(self.tableInfo.getPlayerNum()):
            print(self.tableInfo.players[i]['name'], str(self.tableInfo.players[i]['dan'] - 9) + '段', 'R'+str(self.tableInfo.players[i]['rate']))
        info = self.kyokuInfo
        print('東南西北'[info.kyoku // 4], info.kyoku % 4, '局', info.honba, '本場  供託', info.kyoutaku, '本')

class ImageResources:
    instance = None
    @classmethod
    def getInstance(cls):
        if ImageResources.instance == None:
            ImageResources.instance = ImageResources()
        return ImageResources.instance
    def __init__(self):
        self.bg = pygame.image.load('img/bg.jpg')

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
        self.TILEBACK_WIDTH = 26
        self.TILEBACK_HEIGHT = 60

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

        self.img_tileback1 = pygame.image.load('img/back1.png')
        self.img_tileback3 = pygame.image.load('img/back3.png')

        def makeTransparentSurf(image, area, alpha = 48):
            temp_surf = pygame.Surface((area[2], area[3]))  # the size of your rect
            temp_surf.fill((225, 125, 43))
            temp_surf.set_alpha(alpha)                # alpha level
            temp_surf.blit(image, [0, 0], area)           # this fills the surface with image
            temp_surf.set_colorkey((225, 125, 43))
            return temp_surf
        self.mytile_black_surf = makeTransparentSurf(self.img_mytiles, \
            [self.TILE_WIDTH * 8, self.TILE_HEIGHT * 3, self.TILE_WIDTH, self.TILE_HEIGHT])
        self.black_surfs = []
        for i in range(4):
            self.black_surfs.append(makeTransparentSurf(self.img_tiles[i % 2], \
                [self.TILE_WIDTHS[i] * 8, self.TILE_HEIGHTS[i] * 3, self.TILE_WIDTHS[i], self.TILE_HEIGHTS[i]]))
        self.mytile_green_surf = makeTransparentSurf(self.img_mytiles, \
            [self.TILE_WIDTH * 0, self.TILE_HEIGHT * 3, self.TILE_WIDTH, self.TILE_HEIGHT])
        self.mytile_red_surf = makeTransparentSurf(self.img_mytiles, \
            [self.TILE_WIDTH * 9, self.TILE_HEIGHT * 3, self.TILE_WIDTH, self.TILE_HEIGHT])


        
        self.img_button = pygame.image.load('img/button.png')

class FontResources:
    instance = None
    @classmethod
    def getInstance(cls):
        if FontResources.instance == None:
            FontResources.instance = FontResources()
        return FontResources.instance
    def __init__(self):
        font_path = './font/'
        self.simhei32 = pygame.font.Font(font_path + 'simhei.ttf', 32)
        self.simhei16 = pygame.font.Font(font_path + 'simhei.ttf', 16)
        self.simhei22 = pygame.font.Font(font_path + 'simhei.ttf', 22)
        self.simheif16 = pygame.freetype.Font(font_path + 'simhei.ttf', 16)
        self.simheif22 = pygame.freetype.Font(font_path + 'simhei.ttf', 22)
        self.simhei14 = pygame.font.Font(font_path + 'simhei.ttf', 14)
        self.simhei28 = pygame.font.Font(font_path + 'simhei.ttf', 28)
        self.simhei18 = pygame.font.Font(font_path + 'simhei.ttf', 18)
        self.consolas18 = pygame.font.Font(font_path + 'consola.ttf', 18)
        self.simheif20 = pygame.freetype.Font(font_path + 'simhei.ttf', 20)
        self.simheif28 = pygame.freetype.Font(font_path + 'simhei.ttf', 28)
        self.symbolf22 = pygame.freetype.Font(font_path + 'seguisym.ttf', 22)
        self.symbolf32 = pygame.freetype.Font(font_path + 'seguisym.ttf', 32)
        self.simheif48 = pygame.freetype.Font(font_path + 'simhei.ttf', 48)

class SoundResources:
    instance = None
    @classmethod
    def getInstance(cls):
        if SoundResources.instance == None:
            SoundResources.instance = SoundResources()
        return SoundResources.instance
    def __init__(self):
        self.sound = {}
        self.sound['chi'] = pygame.mixer.Sound('sound/act_chi.wav')
        self.sound['pon'] = pygame.mixer.Sound('sound/act_pon.wav')
        self.sound['kan'] = pygame.mixer.Sound('sound/act_kan.wav')
        self.sound['reach'] = pygame.mixer.Sound('sound/act_rich.wav')
        self.sound['ron'] = pygame.mixer.Sound('sound/act_ron.wav')
        self.sound['tsumo'] = pygame.mixer.Sound('sound/act_tumo.wav')
        self.sound['button'] = pygame.mixer.Sound('sound/button.wav')
        self.sound['countdown'] = pygame.mixer.Sound('sound/countdown.wav')
        self.sound['discard'] = pygame.mixer.Sound('sound/discard.wav')
        self.sound['draw'] = pygame.mixer.Sound('sound/draw.wav')
        self.sound['kita'] = pygame.mixer.Sound('sound/kita.wav')
        self.sound['yakuman'] = pygame.mixer.Sound('sound/yakuman.wav')
        self.sound['winlose'] = pygame.mixer.Sound('sound/winlose.wav')
        self.channels = [None] * 8
        for i in range(8):
            self.channels[i] = pygame.mixer.Channel(i)



class ClientGUI:
    def __init__(self):
        self.screen = pygame.display.set_mode([1024,768])
        pygame.display.set_caption('地龍')
        pygame.mixer.init()
        
        self.imageResources = ImageResources.getInstance()
        self.bg = self.imageResources.bg
        self.display_ratio = self.imageResources.display_ratio
        self.TILE_WIDTH = self.imageResources.TILE_WIDTH
        self.TILE_HEIGHT = self.imageResources.TILE_HEIGHT
        self.display_ratios = self.imageResources.display_ratios
        self.TILE_WIDTHS = self.imageResources.TILE_WIDTHS
        self.TILE_HEIGHTS = self.imageResources.TILE_HEIGHTS
        self.TILE_HEIGHT_EFF = self.imageResources.TILE_HEIGHT_EFF
        self.TILEBACK_WIDTH = self.imageResources.TILEBACK_WIDTH
        self.TILEBACK_HEIGHT = self.imageResources.TILEBACK_HEIGHT
        self.img_mytiles = self.imageResources.img_mytiles
        self.img_shadow = self.imageResources.img_shadow
        self.img_tiles = self.imageResources.img_tiles
        self.img_tileback1 = self.imageResources.img_tileback1
        self.img_tileback3 = self.imageResources.img_tileback3

        self.black_surfs = self.imageResources.black_surfs


        self.bg = pygame.transform.smoothscale(self.bg, [1024, 768]).convert()
        # self.screen.blit(pygame.transform.smoothscale(self.bg, [1024, 768]), [0, 0])

        self.fontResources = FontResources.getInstance()
        self.kyoku_font = self.fontResources.simhei32
        self.kyoku_font_small = self.fontResources.simhei16
        self.ten_font = self.fontResources.simhei22
        self.wind_font = self.fontResources.simhei22
        self.player_font = self.fontResources.simheif16
        self.rule_font = self.fontResources.simhei14
        self.yaku_font = self.fontResources.simhei28

        self.soundResources = SoundResources.getInstance()

        self.calltext_group = pygame.sprite.Group()
        self.gamemsg_group = pygame.sprite.Group()
        self.myHandTileSpriteGroup = MyHandTileSpriteGroup()
        self.textButtonSpriteGroup = TextButtonSpriteGroup()
        self.controlButtonSpriteGroup = ControlButtonSpriteGroup()
        self.ruleSelectionButtonSpriteGroup = RuleSelectionButtonSpriteGroup()
        self.popUpWindow = None

        # self.screen.fill([40,70,120])
        # pygame.display.flip()
        self.playerData = None #utils.PlayerData(message)
        self.monthlyStats = None
        self.lobbyData = utils.LobbyData()
        self.perspective = 0
        self.gameInfo = None
        self.messageQueue = queue.Queue()
        self.busy = 0
        self.state = 0 # 0: unauthenticated 1: authenticated, idle 2: joining 3: playing
        self.waitingForReady = 0 # 0: 没弹窗，没在等 1: 弹出了窗 自己还没nextready 2: 自己已经nextready了
        self.nextFunction = None # 等用户右键确认以后执行的函数
        self.actionTimestamp = 0.0
        self.rtt = 0

        self.timer = None
        self.autoActionTimer = None
        self.remainingTime = 0
        self.remainingOvertime = 0
        self.enableOvertime = False
    def countdown(self):
        if self.remainingTime == -1:
            logger.warning('Timer is running while it should have been disabled')
            return
        else:
            if self.remainingTime == 0:
                if self.remainingOvertime == 0 or self.enableOvertime == False:
                    # self.defaultAction()
                    return
                else:
                    self.remainingOvertime -= 1
            else:
                self.remainingTime -= 1
            if self.remainingTime + self.remainingOvertime < 5 or (self.remainingTime < 5 and self.enableOvertime == False):
                self.soundResources.sound['countdown'].play()
            self.timer = threading.Timer(1, self.countdown)
            self.timer.start()
    def setTimer(self, time, enableOvertime=True):
        # 设置倒计时time秒 非负整数。不改变剩余长考时间。需要改变长考时间请自行设置
        if self.timer:
            self.timer.cancel()
        self.remainingTime = time
        self.enableOvertime = enableOvertime
        if time >= 0:
            self.timer = threading.Timer(1.0, self.countdown)
            self.timer.start()
            logger.debug('Timer set: ' + str(time) + ' s')
    def stopTimer(self):
        if self.timer:
            self.timer.cancel()
    
    def displayCountdown(self):
        time_str = str(self.remainingTime)
        if self.enableOvertime:
            time_str += '+' + str(self.remainingOvertime)
        disp_pos = [970, 730]
        surf = self.rule_font.render(time_str, 1, (128,128,128))
        self.screen.blit(surf, disp_pos)
        
    def displayBackground(self):
        self.screen.blit(self.bg, [0, 0])

    def displayPlayerInfo(self):
        disp_pos = [[200, 735], [950, 250], [550, 20], [50, 250]]
        for i in range(4):
            if not self.gameInfo.playerExist[i]:
                continue
            if i == 0 and not settings.DISP_SELF_NAME:
                continue
            playerIndex = (i + self.perspective) % 4
            p = self.gameInfo.tableInfo.players[playerIndex]
            if p['name'] != '':
                # logger.debug(p['name'])
                (ft1_surf, _) = self.player_font.render(p['name'] + '  ' + const.RANKS[p['dan']] + '  ' + '雀力' + str(int(p['rate'])), THECOLORS['white'])
                ft1_surf = pygame.transform.rotate(ft1_surf, i * 90)
                self.screen.blit(ft1_surf, disp_pos[i])
        
    def displayRuleInfo(self):
        disp_pos = [930, 10]
        ft1_surf = self.rule_font.render(self.gameInfo.tableInfo.getRuleString2(), 1, THECOLORS['white'])
        self.screen.blit(ft1_surf, disp_pos)
        disp_pos = [930, 30]
        ft2_surf = self.rule_font.render(self.gameInfo.tableInfo.getLobbyString(), 1, THECOLORS['white'])
        self.screen.blit(ft2_surf, disp_pos)

    def displayRtt(self):
        disp_pos = [970, 750]
        ft1_surf = self.rule_font.render(str(self.rtt) + 'ms', 1, (128,128,128))
        self.screen.blit(ft1_surf, disp_pos)

    @classmethod
    def blit_text(cls, surface, text, pos, font, color=pygame.Color('white')): 
        #words = [word.split(' ') for word in text.splitlines()] # 2D array where each row is a list of words. 
        lines = text.splitlines()
        x, y = pos 
        for line in lines: 
            line_surface = font.render(line, True, color)
            surface.blit(line_surface, (x, y))
            (_, height) = font.size(line)
            y += height # Start on new row. 
    @classmethod
    def blit_text_freetype(cls, surface, text, pos, font, color=pygame.Color('white')): 
        words = [word.split(' ') for word in text.splitlines()] # 2D array where each row is a list of words. 
        space = 0
        max_width, max_height = surface.get_size() 
        x, y = pos 
        for line in words: 
            for word in line: 
                word_surface, rect = font.render(word, color)
                word_width, word_height = rect.size
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
            if direction == 1:
                self._blit_tile_helper(dest, self.img_tileback1, None, (pos[0] + self.TILE_WIDTHS[1] - self.TILEBACK_WIDTH, pos[1] + self.TILE_HEIGHTS[1] - self.TILEBACK_HEIGHT))
                return
            if direction == 3:
                self._blit_tile_helper(dest, self.img_tileback3, None, (pos[0], pos[1] + self.TILE_HEIGHTS[1] - self.TILEBACK_HEIGHT))
                return
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
    
    def dismissWindow(self):
        self.popUpWindow = None
    
    def displayNinteiInfo(self, ninteiString):
        # 显示升段认定信息
        s = pygame.Surface((600, 450))  # the size of your rect
        #s.set_alpha(192)                # alpha level
        s.fill((0, 0, 0))           # this fills the entire surface

        title = '認定'
        ClientGUI.blit_text_freetype(s, title, [300 - 48, 60], self.fontResources.simheif48, pygame.Color('White'))

        text_surface = pygame.Surface((510, 250))
        ClientGUI.blit_text(text_surface, ninteiString, [0, 0], self.fontResources.simhei18)
        s.blit(text_surface, [45, 160])
        self.popUpWindow = s
        logger.info('pop up window set to nintei info')
        
        self.nextFunction = self.dismissWindow

    def displayGameStartInfo(self):
        # 显示开局窗口
        s = pygame.Surface((600, 450))  # the size of your rect
        # s.set_alpha(192)                # alpha level
        s.fill((0, 0, 0))           # this fills the entire surface

        title = '对局'
        ClientGUI.blit_text_freetype(s, title, [300 - 48, 60], self.fontResources.simheif48, pygame.Color('White'))

        # 显示玩家起家及段位等
        wind_disp_pos = [[225, 340], [405, 275], [225, 210], [80, 275]]
        player_disp_pos = [[260, 338], [440, 273], [260, 208], [115, 273]]
        # 三麻东南西北家和东南西北方位可能不一样 这坨代码就是为了解决这个问题
        wind_index = [0,0,0,0]
        current_wind = 0
        oya = self.gameInfo.initialOya
        for i in range(1, 4):
            if self.gameInfo.playerExist[(oya + i) % 4]:
                current_wind += 1
                wind_index[(oya + i) % 4] = current_wind
        # 解决完了 接下来真正显示
        for i in range(4):
            playerIndex = i
            if self.gameInfo.playerExist[i]:
                wind_surf = self.fontResources.simhei28.render('東南西北'[wind_index[playerIndex]], True, (255,255,255))
                p = self.gameInfo.tableInfo.players[i]
                player_str = p['name'] + '\n' + const.RANKS[p['dan']] + ' ' + '雀力' + str(int(p['rate']))
                s.blit(wind_surf, wind_disp_pos[i])
                ClientGUI.blit_text(s, player_str, player_disp_pos[i], self.fontResources.simhei16)

        
        self.popUpWindow = s
    
    def displayGameResumeInfo(self, message):
        # 显示开局窗口
        s = pygame.Surface((600, 450))  # the size of your rect
        # s.set_alpha(192)                # alpha level
        s.fill((0, 0, 0))           # this fills the entire surface

        title = '重连成功'
        ClientGUI.blit_text_freetype(s, title, [300 - 48 * 2, 60], self.fontResources.simheif48, pygame.Color('White'))

        # 显示玩家起家及段位等
        wind_disp_pos = [[225, 340], [405, 275], [225, 210], [80, 275]]
        player_disp_pos = [[260, 338], [440, 273], [260, 208], [115, 273]]
        # 三麻东南西北家和东南西北方位可能不一样 这坨代码就是为了解决这个问题
        wind_index = [0,0,0,0]
        current_wind = 0
        oya = int(message['oya'])
        for i in range(1, 4):
            if self.gameInfo.playerExist[(oya + i) % 4]:
                current_wind += 1
                wind_index[(oya + i) % 4] = current_wind
        # 解决完了 接下来真正显示
        tmp_sc_list = message['sc'].split(',')
        for i in range(4):
            playerIndex = i
            if self.gameInfo.playerExist[i]:
                wind_surf = self.fontResources.simhei28.render('東南西北'[wind_index[playerIndex]], True, (255,255,255))
                p = self.gameInfo.tableInfo.players[i]
                player_str = p['name'] + '\n' + str(int(tmp_sc_list[playerIndex * 2]) * 100)
                s.blit(wind_surf, wind_disp_pos[i])
                ClientGUI.blit_text(s, player_str, player_disp_pos[i], self.fontResources.simhei16)

        
        self.popUpWindow = s
    def displayScoreChange(self, sc):
        # sc is the attribute (string)
        info = self.gameInfo.kyokuInfo
        wind_index = [0,0,0,0]
        current_wind = 0
        for i in range(1, 4):
            if self.gameInfo.playerExist[(info.oya + i) % 4]:
                current_wind += 1
                wind_index[(info.oya + i) % 4] = current_wind

        sc_split = sc.split(',')
        for tableDirection in range(4):
            playerIndex = (tableDirection + self.perspective) % 4
            if self.gameInfo.playerExist[playerIndex]:
                temp_str = '東南西北'[wind_index[playerIndex]]
                temp_str += ' ' + self.gameInfo.tableInfo.players[playerIndex]['name']
                temp_str += ' ' + sc_split[playerIndex * 2] + '00'
                sc_change = int(sc_split[playerIndex * 2 + 1])
                if sc_change > 0:
                    temp_str += ' +' + str(sc_change * 100)
                elif sc_change < 0:
                    temp_str += ' ' + str(sc_change * 100)
                ClientGUI.blit_text(self.screen, temp_str, [300, 450 + tableDirection * 30], self.ten_font)

    def displayAgariInfo(self):
        attributes = self.gameInfo.kyokuInfo.agariInfo[0]
        bg_disp_pos = [(1024 - 600) // 2, (740 - 450) // 2]
        # 显示和牌框背景
        bg_surf = pygame.Surface((600, 450))  # the size of your rect
        bg_surf.set_alpha(192)                # alpha level
        bg_surf.fill((0, 0, 0))           # this fills the entire surface
        self.screen.blit(bg_surf, bg_disp_pos)
        
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

        if 'doraHai' in attributes:
            doraIndicators = list(map(int, attributes['doraHai'].split(',')))
        else:
            doraIndicators = []
        self.blitDoraIndicators(self.screen, doraIndicators, [270, 400])
        if 'doraHaiUra' in attributes:
            doraIndicators = list(map(int, attributes['doraHaiUra'].split(',')))
        else:
            doraIndicators = []
        self.blitDoraIndicators(self.screen, doraIndicators, [540, 400])
        

        text_disp_pos = [300, 200]
        # yaku_surf = self.yaku_font.render(yaku_string, True, THECOLORS['white'])
        ClientGUI.blit_text(self.screen, yaku_string, text_disp_pos, self.yaku_font)
        self.displayScoreChange(attributes['sc'])
    def displayRyukyokuInfo(self):
        attributes = self.gameInfo.kyokuInfo.ryukyokuInfo
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
        ClientGUI.blit_text(self.screen, ryukyoku_string, disp_pos, self.yaku_font)
        self.displayScoreChange(attributes['sc'])
    def displayGameEndInfo(self):
        # 显示终局信息(各家点数、顺位等)
        s = pygame.Surface((600, 450))  # the size of your rect
        #s.set_alpha(192)                # alpha level
        s.fill((0, 0, 0))           # this fills the entire surface

        title = '终局'
        ClientGUI.blit_text_freetype(s, title, [300 - 48, 60], self.fontResources.simheif48, pygame.Color('White'))

        owari = self.gameInfo.kyokuInfo.owariInfo
        sc_string = owari.split(',')
        playerScores = [(0, int(sc_string[0])), (1, int(sc_string[2])), (2, int(sc_string[4])), (3, int(sc_string[6]))]
        if self.gameInfo.tableInfo.isSanma():
            for i in range(4):
                if not self.gameInfo.playerExist[i]:
                    playerScores.pop(i)
        playerScores.sort(key = lambda ps : - ps[1] * 100 + ps[0])
        disp_string = ''
        for i in range(len(playerScores)):
            playerIndex = playerScores[i][0]
            score = playerScores[i][1] * 100
            disp_string += str(i+1) + '位 ' + self.gameInfo.tableInfo.players[playerIndex]['name'] #+ ' (' + '东南西北'[playerIndex] + '起)'
            disp_string += ' ' + str(score) + '点\n\n'
        
        disp_pos = [180, 185]
        ClientGUI.blit_text(s, disp_string, disp_pos, self.ten_font)
        self.popUpWindow = s
        self.gameInfo = None
        logger.info('pop up window set to game end info')
        self.nextFunction = self.autoLogin

    def displayKyokuInfo(self, action = False):
        # action似乎没用。。
        info = self.gameInfo.kyokuInfo

        # 显示桌子中间的黑框
        disp_pos = [(1024 - 6 * self.TILE_WIDTHS[0]) // 2, (740 - 6 * self.TILE_HEIGHT_EFF[1]) // 2]
        s = pygame.Surface((6 * self.TILE_WIDTHS[0], 6 * self.TILE_HEIGHT_EFF[1]))  # the size of your rect
        s.set_alpha(128)                # alpha level
        s.fill((0, 0, 0))           # this fills the entire surface
        self.screen.blit(s, disp_pos)

        # 显示牌河
        self.displayRivers()
        # 显示副露
        self.displayFuros()
        # 显示dora指示牌
        x, y = 419, 260
        self.blitDoraIndicators(self.screen, info.doraIndicators, [x, y])


        # 显示局次
        kyoku_surf = self.kyoku_font.render('東南西北'[info.kyoku // 4] + str(info.kyoku % 4 + 1) + '局', True, THECOLORS['white'])
        disp_pos = [512 - kyoku_surf.get_width() // 2, 352]
        self.screen.blit(kyoku_surf, disp_pos)

        # 显示本场 场供 残余枚数
        kyoku_surf = self.kyoku_font_small.render(str(info.honba) + '本 ' + str(info.kyoutaku) + '供' + ' 残' + '{:2n}'.format(info.remaining) + '枚', 1, THECOLORS['white'])
        disp_pos = [512 - kyoku_surf.get_width() // 2, 392]
        self.screen.blit(kyoku_surf, disp_pos)
        
        # 显示点数及亲子
        wind_disp_pos = [[469, 420], [590, 404], [533, 320], [410, 336]]
        ten_disp_pos = [[512, 420], [590, 380], [512, 320], [410, 380]] # 这里的横（纵向显示则为纵）坐标是中心的坐标而不是左边（顶边）位置
        # 三麻东南西北家和东南西北方位可能不一样 这坨代码就是为了解决这个问题
        wind_index = [0,0,0,0]
        current_wind = 0
        for i in range(1, 4):
            if self.gameInfo.playerExist[(info.oya + i) % 4]:
                current_wind += 1
                wind_index[(info.oya + i) % 4] = current_wind
        # 解决完了 接下来真正显示点数和亲子
        for i in range(4):
            playerIndex = i
            if self.gameInfo.playerExist[i]:
                if self.gameInfo.gameControlInfo.displayScoreDiff and i != 0:
                    score_diff = (info.ten[playerIndex] - info.ten[0]) * 100
                    if score_diff > 0:
                        ten_string = '+' + str(score_diff)
                    else:
                        ten_string = str(score_diff)
                else:
                    if info.whosTurn == playerIndex:
                        wind_surf = self.wind_font.render('東南西北'[wind_index[playerIndex]], True, (255,227,60))
                    else:
                        wind_surf = self.wind_font.render('東南西北'[wind_index[playerIndex]], True, (160,160,160))
                    wind_surf = pygame.transform.rotate(wind_surf, i * 90)
                    self.screen.blit(wind_surf, wind_disp_pos[i])
                    ten_string = str(info.ten[playerIndex] * 100)
                ten_surf = self.ten_font.render(ten_string, True, \
                    THECOLORS['white'] if self.gameInfo.online[playerIndex] else THECOLORS['red'])
                ten_surf = pygame.transform.rotate(ten_surf, i * 90)
                if i == 0:
                    ten_disp_pos[0][0] -= ten_surf.get_width() // 2
                    ten_disp_pos[0][0] += 13
                elif i == 1:
                    ten_disp_pos[1][1] -= ten_surf.get_height() // 2
                    if not self.gameInfo.gameControlInfo.displayScoreDiff:
                        ten_disp_pos[1][1] -= 10
                elif i == 2:
                    ten_disp_pos[2][0] -= ten_surf.get_width() // 2
                    if not self.gameInfo.gameControlInfo.displayScoreDiff:
                        ten_disp_pos[2][0] -= 14
                elif i == 3:
                    ten_disp_pos[3][1] -= ten_surf.get_height() // 2
                    if not self.gameInfo.gameControlInfo.displayScoreDiff:
                        ten_disp_pos[3][1] += 10
                self.screen.blit(ten_surf, ten_disp_pos[i])

        #tag = info.status[step]['tag']
        #attributes = info.status[step]['attributes']
        
        # 显示手牌
        hands = info.hands
        self.displayHands(hands)

        # 显示振听
        if self.gameInfo.kyokuInfo.furiten:
            self.displayFuriten()

        # 显示按钮
        self.textButtonSpriteGroup.draw(self.screen)
        self.controlButtonSpriteGroup.draw(self.screen)
    
    def blitDoraIndicators(self, dest, doraIndicators, pos):
        for i in range(5):
            # 默认为未翻开 0z(tilecode is -1)牌画为牌背
            if i < len(doraIndicators):
                tile = doraIndicators[i]
            else:
                tile = -1
            self.blit_tile(dest, 0, tile, [pos[0] + i * self.TILE_WIDTHS[0], pos[1]])

    def displayNotPassedTilesInfo(self):
        info = self.gameInfo.kyokuInfo
        disp_pos = [[(1024 - 6 * self.TILE_WIDTHS[0]) // 2 - 40, (740 + 6 * self.TILE_HEIGHT_EFF[1]) // 2 + 7], 
            [(1024 + 6 * self.TILE_WIDTHS[0]) // 2 + 10, (740 + 6 * self.TILE_HEIGHT_EFF[1]) // 2 + 5], 
            [(1024 + 6 * self.TILE_WIDTHS[0]) // 2 + 5, (740 - 6 * self.TILE_HEIGHT_EFF[1]) // 2 - 40], 
            [(1024 - 6 * self.TILE_WIDTHS[0]) // 2 - 28, (740 - 6 * self.TILE_HEIGHT_EFF[1]) // 2 - (self.TILE_HEIGHTS[3] - self.TILE_HEIGHT_EFF[3]) - 40]]
        for i in range(4):
            if self.gameInfo.playerExist[i]:
                if i == 0 and not settings.DISP_NOT_PASSED_SELF:
                    continue
                if info.numNotPassedSujis[i] > settings.DISP_NOT_PASSED_SUJIS_THRESHOLD:
                    continue
                string = str(info.numNotPassedSujis[i])
                if settings.DISP_NOT_PASSED_TILES:
                    string += ',' + str(info.numNotPassedTiles[i])
                else:
                    string += '   '
                surf = self.fontResources.simhei14.render(string, True, (127,127,127))
                surf = pygame.transform.rotate(surf, i * 90)
                self.screen.blit(surf, disp_pos[i])

    def displayRivers(self):
        # rivers: int[4][][2]
        rivers = self.gameInfo.kyokuInfo.rivers

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
            if (i == length - 1) and self.gameInfo.kyokuInfo.playerState == 2:
                who = self.gameInfo.kyokuInfo.whosTurn
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
            if col == 6 and row < 2:
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
            if (i == length - 1) and self.gameInfo.kyokuInfo.playerState == 2:
                who = self.gameInfo.kyokuInfo.whosTurn
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
            if col == 6 and row < 2:
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
            if (i == length - 1) and self.gameInfo.kyokuInfo.playerState == 2:
                who = self.gameInfo.kyokuInfo.whosTurn
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
            if col == 6 and row < 2:
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
            if (i == length - 1) and self.gameInfo.kyokuInfo.playerState == 2:
                who = self.gameInfo.kyokuInfo.whosTurn
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
            if col == 6 and row < 2:
                row += 1
                y_offset += self.TILE_HEIGHT_EFF[0]
                col = 0
                x_offset = 0
            else:
                x_offset += (self.TILE_WIDTHS[0] if not discardInfo & 4 else self.TILE_WIDTHS[1])
            i += 1

    def displayFuros(self):
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
        info = self.gameInfo.kyokuInfo
        # 显示副露
        for tableDirection in range(4):
            # 为防止和子循环里的i和direction重名，大for循环变量用了个新名字
            playerIndex = (tableDirection + self.perspective) % 4
            furos = info.furos[playerIndex]
            tileDrawInfo = [] # [tilecode, discardInfo, direction, (x, y)][]
            kitaDrawInfo = [] # [tilecode, discardInfo, direction, (x, y)][]
            [x, y] = [[944, 730], [944, 47], [80, 47], [80, 730]][tableDirection]
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
        justDrawn = (self.gameInfo.kyokuInfo.playerState == 1)

        self.myHandTileSpriteGroup.draw(self.screen)
        '''
        playerIndex = (0 + self.perspective) % 4
        hand = hands[playerIndex]
        x = 200
        y = 660
        length = len(hand)
        if length % 3 == 2 and justDrawn:
            length -= 1
        self.screen.blit(self.img_shadow, [x + length * self.TILE_WIDTH - int(7 * self.display_ratio), y + int(32 * self.display_ratio)])
        for i in range(length):
            tile = hand[i]
            self.blit_handtile(self.screen, 0, tile, [x + i * self.TILE_WIDTH, y], 0)
        if len(hand) % 3 == 2 and justDrawn:
            tile = hand[-1]
            if tile != -2:
                self.screen.blit(self.img_shadow, [x + 4 + (length + 1) * self.TILE_WIDTH - int(7 * self.display_ratio), y + int(32 * self.display_ratio)])
            self.blit_handtile(self.screen, 0, tile, [x + 4 + length * self.TILE_WIDTH, y], 0)
            #self.screen.blit(self.img_mytiles, [x + 4 + length * self.TILE_WIDTH, y], [self.TILE_WIDTH * num, self.TILE_HEIGHT * suit, self.TILE_WIDTH, self.TILE_HEIGHT])
        '''

        playerIndex = (1 + self.perspective) % 4
        hand = hands[playerIndex]
        length = len(hand)
        if length % 3 == 2 and justDrawn:
            length -= 1
        x, y = 894, 540
        if len(hand) % 3 == 2 and justDrawn:
            tile = hand[-1]
            self.blit_handtile(self.screen, 1, tile, [x, y - 3 - length * self.TILE_HEIGHT_EFF[1]], 0)

        for i in range(length - 1, -1, -1):
            tile = hand[i]
            self.blit_handtile(self.screen, 1, tile, [x, y - i * self.TILE_HEIGHT_EFF[1]], 0)

        playerIndex = (2 + self.perspective) % 4
        hand = hands[playerIndex]
        length = len(hand)
        if length % 3 == 2 and justDrawn:
            length -= 1
        x, y = 720, 40
        if len(hand) % 3 == 2 and justDrawn:
            tile = hand[-1]
            self.blit_handtile(self.screen, 2, tile, [x - 3 - length * self.TILE_WIDTHS[2], y], 0)

        for i in range(length - 1, -1, -1):
            tile = hand[i]
            self.blit_handtile(self.screen, 2, tile, [x - i * self.TILE_WIDTHS[2], y], 0)


        playerIndex = (3 + self.perspective) % 4
        hand = hands[playerIndex]
        length = len(hand)
        if length % 3 == 2 and justDrawn:
            length -= 1
        x, y = 80, 160
        for i in range(length):
            tile = hand[i]
            self.blit_handtile(self.screen, 3, tile, [x, y + i * self.TILE_HEIGHT_EFF[3]], 0)
        if len(hand) % 3 == 2 and justDrawn:
            tile = hand[-1]
            self.blit_handtile(self.screen, 3, tile, [x, y + 3 + length * self.TILE_HEIGHT_EFF[3]], 0)
    
    def displayFuriten(self):
        pos = [170, 670]
        ClientGUI.blit_text(self.screen, '振\n听', pos, self.fontResources.simhei28)

    def displayMachi(self, machiList34, discard34=None):
        # 显示自己听的牌 暂不支持判断有没有役
        # discard34是切哪张牌听 用来判断是否振听
        furiten = False
        if discard34 and discard34 in machiList34:
            furiten = True
        else:
            for tile34 in machiList34:
                for [tile, _] in self.gameInfo.kyokuInfo.rivers[0]:
                    if tile34 == (tile >> 2):
                        furiten = True
                        break

        width = len(machiList34) * (self.TILE_WIDTH + 15) + 25
        if furiten:
            width += 24
        surf = pygame.Surface((width, 100), pygame.SRCALPHA)
        surf.set_alpha(255)
        surf.fill((0, 0, 0, 192), None)
        current_x = 5
        if furiten:
            ClientGUI.blit_text(surf, '振\n听', [current_x, 16], self.fontResources.simhei28)
            current_x = 44
        else:
            current_x = 20
            
        for i in range(len(machiList34)):
            tile34 = machiList34[i]
            remaining_num = self.gameInfo.kyokuInfo.remainingTiles[tile34]
            self.blit_handtile(surf, 0, (tile34 << 2) + 1, [current_x, 7])
            self.blit_text(surf, str(remaining_num) + '枚', [current_x + 12, 77], self.fontResources.simhei16)
            current_x += self.TILE_WIDTH + 15
        self.screen.blit(surf, [(1024 - width) // 2, 550])

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

    def display(self):
        self.displayBackground()
        if self.gameInfo:
            self.displayPlayerInfo()
            self.displayRuleInfo()
            self.displayKyokuInfo(False)
            if settings.DISP_NOT_PASSED_SUJIS:
                self.displayNotPassedTilesInfo()
            if self.gameInfo.kyokuInfo.agariInfo:
                self.displayAgariInfo()
            if self.gameInfo.kyokuInfo.ryukyokuInfo:
                self.displayRyukyokuInfo()
            if self.rtt:
                self.displayRtt()
            self.calltext_group.update()
            self.calltext_group.draw(self.screen)
            # now countdown always displays
            # TODO display only when timer running for >=1s
            # self.displayCountdown()

        elif self.state == 1 or self.state == 2:
            self.displayIdleUI()
        if self.popUpWindow:
            disp_pos = [(1024 - 600) // 2, (740 - 450) // 2]
            self.screen.blit(self.popUpWindow, disp_pos)
            # logger.info('displaying pop up window')
        self.gamemsg_group.update()
        self.gamemsg_group.draw(self.screen)

    def displayIdleUI(self):
        # 显示在大厅中挂机和预约的界面
        if self.playerData:
            playerDataSurf = pygame.Surface((800, 200), pygame.SRCALPHA)
            ClientGUI.blit_text(playerDataSurf, self.playerData.uname, [0, 0], self.fontResources.simhei22)

            self._blit_stats(playerDataSurf, 4, [0, 0])
            self._blit_stats(playerDataSurf, 3, [400, 0])
            self.screen.blit(playerDataSurf, [112, 100])
        
        rulecode = self.ruleSelectionButtonSpriteGroup.getRulecode()
        tempTableInfo = TableInfo()
        tempTableInfo.rule = rulecode

        if self.lobbyData:
            lobbyDataSurf = pygame.Surface((800, 200), pygame.SRCALPHA)
            ClientGUI.blit_text(lobbyDataSurf, '总在线人数：' + str(self.lobbyData.totalOnline) + ' 当前房间在线人数：' + str(self.lobbyData.thisLobbyOnline)\
                + ' 待机中：' + str(self.lobbyData.idle) \
                + ' 终局：' + str(self.lobbyData.alllast), [0, 0], self.fontResources.simhei18)
            
            self.screen.blit(lobbyDataSurf, [112, 310])
            
            if rulecode & 1:
                joiningAndPlayingSurf = pygame.Surface((120, 40), pygame.SRCALPHA)
                if tempTableInfo.isSanma():
                    index = 64
                    if tempTableInfo.isTonnansen():
                        index += 1
                    if tempTableInfo.isFast():
                        index += 8
                    if (rulecode & 0xa0) == 0xa0:
                        index += 6
                    elif (rulecode & 0x20) > 0:
                        index += 4
                    elif (rulecode & 0x80) > 0:
                        index += 2
                else:
                    index = ((rulecode & 0x0F) >> 1) | ((rulecode & 0x40) >> 3)
                    if (rulecode & 0xa0) == 0xa0:
                        index += 48
                    elif (rulecode & 0x20) > 0:
                        index += 32
                    elif (rulecode & 0x80) > 0:
                        index += 16

                joiningAndPlayingText = "{:4n}人预约中\n{:4n}人对战中".format(self.lobbyData.joining[index], self.lobbyData.playing[index])
                ClientGUI.blit_text(joiningAndPlayingSurf, joiningAndPlayingText, [0, 0], self.fontResources.simhei18)
                self.screen.blit(joiningAndPlayingSurf, [512, 350])
            
            requirementSurf = pygame.Surface((600, 100), pygame.SRCALPHA)
            if rulecode & 1:
                if settings.LOBBY == 0000:
                    level = tempTableInfo.getLevel()
                    requirementText = tempTableInfo.getRuleString2()
                    requirementText += '\n入场条件：' + const.REQUIREMENTS[level]
                    if self.isRequirementSatisfied(rulecode):
                        if tempTableInfo.isSanma():
                            if tempTableInfo.isTonnansen():
                                ptchange = [[45, 75, 105, 135][level], 0, min((self.playerData.sanmaStat['dan'] - 7) * (-15), 0)]
                            else:
                                ptchange = [[30, 50, 70, 90][level], 0, min((self.playerData.sanmaStat['dan'] - 7) * (-10), 0)]
                            requirementText += '\n1位{:+n}龙玉 2位{:+n}龙玉 3位{:+n}龙玉'.format(ptchange[0], ptchange[1], ptchange[2])
                        else:
                            if tempTableInfo.isTonnansen():
                                ptchange = [[30, 60, 75, 90][level], [15, 15, 30, 45][level], 0, min((self.playerData.yonmaStat['dan'] - 7) * (-15), 0)]
                            else:
                                ptchange = [[20, 40, 50, 60][level], [10, 10, 20, 30][level], 0, min((self.playerData.yonmaStat['dan'] - 7) * (-10), 0)]
                            requirementText += '\n1位{:+n}龙玉 2位{:+n}龙玉 3位{:+n}龙玉 4位{:+n}龙玉'.format(ptchange[0], ptchange[1], ptchange[2], ptchange[3])
                    else:
                        requirementText += '\n您未满足入场条件'
                else:
                    requirementText = tempTableInfo.getRuleString2() + '\n个室仅开放茅屋，无入场条件'
                ClientGUI.blit_text(requirementSurf, requirementText, [0, 0], self.fontResources.simhei18)
                self.screen.blit(requirementSurf, [112, 410])
            
        if self.monthlyStats:
            monthlyStatsSurf = pygame.Surface((600, 220), pygame.SRCALPHA)
            self._blit_monthly_stats(monthlyStatsSurf, tempTableInfo.getPlayerNum(), [0, 0])
            self.screen.blit(monthlyStatsSurf, [112, 500])

        disp_pos = [930, 30]
        lobbystring_surf = self.rule_font.render('C' + str(settings.LOBBY).rjust(8, '0') if settings.IS_CHAMPIONSHIP else 'L' + str(settings.LOBBY).rjust(4, '0'), 1, THECOLORS['white'])
        self.screen.blit(lobbystring_surf, disp_pos)

        self.ruleSelectionButtonSpriteGroup.draw(self.screen)
    def _blit_stats(self, surface, num_players, pos):
        if num_players == 4:
            stat = self.playerData.yonmaStat
            dan_text = '四麻  ' 
        else:
            stat = self.playerData.sanmaStat
            dan_text = '三麻  '
        dan_text += const.RANKS[stat['dan']]
        dan_text += ' ' + str(stat['pt'])
        dan_text += '/' + str(const.PT[stat['dan']]) + '龙玉'
        dan_text += '\n      雀力' + str(stat['rate'])
        ClientGUI.blit_text(surface, dan_text, [pos[0] + 0, pos[1] + 30], self.fontResources.simhei22)
        if stat['countGames'] == 0:
            return
        stat_text = '一位率\n二位率\n三位率\n四位率\n被飞率'
        ClientGUI.blit_text(surface, stat_text, [pos[0] + 0, pos[1] + 80], self.fontResources.simhei18)
        stat_text = '{:7.2%}'.format(stat['rate1']) + '\n' \
            + '{:7.2%}'.format(stat['rate2']) + '\n' \
            + '{:7.2%}'.format(stat['rate3']) + '\n' \
            + '{:7.2%}'.format(stat['rate4']) + '\n' \
            + '{:7.2%}'.format(stat['rateTobi'])
        ClientGUI.blit_text(surface, stat_text, [pos[0] + 60, pos[1] + 81], self.fontResources.consolas18)
        stat_text = '对战数\n和了率\n放铳率\n副露率\n立直率'
        ClientGUI.blit_text(surface, stat_text, [pos[0] + 180, pos[1] + 80], self.fontResources.simhei18)
        stat_text = '{:6n}'.format(stat['countGames']) + '\n' \
            + '{:7.2%}'.format(stat['rateAgari']) + '\n' \
            + '{:7.2%}'.format(stat['rateHouju']) + '\n' \
            + '{:7.2%}'.format(stat['rateFuro']) + '\n' \
            + '{:7.2%}'.format(stat['rateReach'])
        ClientGUI.blit_text(surface, stat_text, [pos[0] + 240, pos[1] + 81], self.fontResources.consolas18)
    
    def _blit_monthly_stats(self, surface, num_players, pos):
        game_count_text = '本月战绩：' + str(self.monthlyStats.gameCount[0]) + ' + ' + str(self.monthlyStats.gameCount[1]) + ' + ' + str(self.monthlyStats.gameCount[2])
        if num_players == 4:
            game_count_text += ' + ' + str(self.monthlyStats.gameCount[3])
        game_count_text += ' = ' + str(self.monthlyStats.totalGameCount) + '战'
        ClientGUI.blit_text(surface, game_count_text, pos, self.fontResources.simhei22)
        stats_table_text = ['总计得点', '平均得点', '总计顺位', '平均顺位', '综合', '一位率', '连对率', '末位率', '雀力']
        if num_players == 4:
            totalPosition = self.monthlyStats.gameCount[0] * 30 + self.monthlyStats.gameCount[1] * 10 \
                + self.monthlyStats.gameCount[2] * (-10) + self.monthlyStats.gameCount[3] * (-30)
            avgPosition = (self.monthlyStats.gameCount[0] * 1 + self.monthlyStats.gameCount[1] * 2 \
                + self.monthlyStats.gameCount[2] * 3 + self.monthlyStats.gameCount[3] * 4) / self.monthlyStats.totalGameCount
            lastRate = self.monthlyStats.gameCount[3] / self.monthlyStats.totalGameCount
        else:
            totalPosition = self.monthlyStats.gameCount[0] * 30 + self.monthlyStats.gameCount[2] * (-30)
            avgPosition = (self.monthlyStats.gameCount[0] * 1 + self.monthlyStats.gameCount[1] * 2 \
                + self.monthlyStats.gameCount[2] * 3) / self.monthlyStats.totalGameCount
            lastRate = self.monthlyStats.gameCount[2] / self.monthlyStats.totalGameCount
        stats_table_data = [
            '{:+7.1f}'.format(self.monthlyStats.totalScore),
            '{:+7.1f}'.format(self.monthlyStats.totalScore / self.monthlyStats.totalGameCount),
            '{:+7n}'.format(totalPosition),
            '{:7.2f}'.format(avgPosition),
            '{:7n}'.format(self.monthlyStats.totalScoreRanking + self.monthlyStats.avgScoreRanking\
                 + self.monthlyStats.totalPositionRanking + self.monthlyStats.avgPositionRanking),
            '{:7.2%}'.format(self.monthlyStats.gameCount[0] / self.monthlyStats.totalGameCount),
            '{:7.2%}'.format((self.monthlyStats.gameCount[0] + self.monthlyStats.gameCount[1]) / self.monthlyStats.totalGameCount) \
                if num_players == 4 else '    ---',
            '{:7.2%}'.format(lastRate),
            '{:7.2f}'.format(self.playerData.yonmaStat['rate'] if num_players == 4 else self.playerData.sanmaStat['rate'])
            ]
        def format_or_none(ranking):
            if ranking == 0:
                return '   ---'
            else:
                return '{:6n}'.format(ranking)
        stats_table_ranking = [format_or_none(self.monthlyStats.totalScoreRanking), format_or_none(self.monthlyStats.avgScoreRanking), \
            format_or_none(self.monthlyStats.totalPositionRanking), format_or_none(self.monthlyStats.avgPositionRanking), \
            format_or_none(self.monthlyStats.overallRanking), format_or_none(self.monthlyStats.topRateRanking), \
            format_or_none(self.monthlyStats.topTwoRateRanking), format_or_none(self.monthlyStats.lastRateRanking), \
            format_or_none(self.monthlyStats.rateRanking)]
        for j in range(1):
            for i in range(9):
                disp_pos = [pos[0] + j * 260, pos[1] + i * 20 + 40]
                ClientGUI.blit_text(surface, stats_table_text[j * 5 + i], disp_pos, self.fontResources.simhei18)
                disp_pos = [pos[0] + j * 260 + 87, pos[1] + i * 20 + 41]
                ClientGUI.blit_text(surface, stats_table_data[j * 5 + i], disp_pos, self.fontResources.consolas18)
                disp_pos = [pos[0] + j * 260 + 165, pos[1] + i * 20 + 41]
                ClientGUI.blit_text(surface, stats_table_ranking[j * 5 + i], disp_pos, self.fontResources.consolas18)
                disp_pos = [pos[0] + j * 260 + 228, pos[1] + i * 20 + 40]
                ClientGUI.blit_text(surface, '位', disp_pos, self.fontResources.simhei18)


    def isRequirementSatisfied(self, rulecode):
        if not (rulecode & 1):
            return True
        if rulecode & 0x10:
            stat = self.playerData.sanmaStat
        else:
            stat = self.playerData.yonmaStat
        if (rulecode & 0xa0) == 0xa0:
            if self.playerData.expire and stat['dan'] >= 16 and stat['rate'] >= 2000.0:
                return True
            return False
        elif (rulecode & 0x20) > 0:
            if stat['dan'] >= 13 and stat['rate'] >= 1800.0:
                return True
            return False
        elif (rulecode & 0x80) > 0:
            if (stat['dan'] >= 9 or self.playerData.expireDays >= 60) and not (stat['dan'] >= 16 and stat['rate'] >= 2000.0):
                return True
            return False
        else:
            if not (stat['dan'] >= 13 and stat['rate'] >= 1800.0):
                return True
            return False

    def storeLog(self, log):
        # string -> bool
        # store log identifier permanently
        try:
            with open('data/log.txt', 'a') as f:
                f.write(self.gameInfo.tableInfo.getLobbyString() + ' ' + self.gameInfo.tableInfo.getRuleString() + ' ' + log)
                f.write('\n')
            return True
        except:
            logger.warning('log store in file failed')

    def storeTempLog(self, log):
        # store log identifier temporarily, so that Haifu can be downloaded after disconnection and reconnection
        try:
            with open('data/temp_log.txt', 'w') as f:
                f.write(log)
        except:
            logger.warning('log store in temp file failed')


    def storeGpid(self, gpid):
        # string -> bool
        try:
            with open('data/gpid.txt', 'w') as f:
                f.write(gpid)
            # self.gameInfo.gpid = ''
            return True
        except:
            logger.warning('GPID store in file failed')
            return False
    def readTempLog(self):
        # -> string
        log = ''
        try:
            with open('data/temp_log.txt', 'r') as f:
                log = f.read()
        except:
            logger.info('No log file found')
        return log

    def readGpid(self):
        # -> string
        gpid = ''
        try:
            with open('data/gpid.txt', 'r') as f:
                gpid = f.read()
        except:
            logger.info('No gpid file found')
        return gpid
    @classmethod
    def downloadHaifu(cls, log, tw, method=0):
        # string -> int -> bool
        # if method == 0, use find.cgi to download gz file; else use mjlog2xml_.cgi to download xml text
        try:
            if method == 0:
                haifuText = HaifuDownloader.fetch_haifu_text(log)
                if len(haifuText) >= 19 and 'mjloggm' in haifuText:
                    # Create target Directory if don't exist
                    if not os.path.exists('log'):
                        os.mkdir('log')
                        logger.info("Directory " + 'log' + " Created ")
                    with open('log/' + log + '&tw=' + str(tw) + '.mjlog', 'w') as f:
                        f.write(haifuText)
                    return True
            else:
                haifuContent = HaifuDownloader.fetch_haifu_file(log)
                if len(haifuContent) >= 2 and haifuContent[:2] == b'\x1f\x8b':
                    # Create target Directory if don't exist
                    if not os.path.exists('log'):
                        os.mkdir('log')
                        logger.info("Directory " + 'log' + " Created ")
                    with open('log/' + log + '&tw=' + str(tw) + '.mjlog', 'wb') as f:
                        f.write(haifuContent)
                    return True
        except Exception as e:
            logger.warning('download haifu failed! ' + log)
            print(e)
            return False

    def pushMessage(self, message):
        message['_timestamp'] = time.time()
        self.messageQueue.put(message)
    
    def on_close(self):
        sp = GameMsgSprite('您已掉线，请按鼠标中键重连')
        self.gamemsg_group.add(sp)

    def decodeAndDisplay(self, message):
        logger.info('gui: msg rcvd')
        if self.actionTimestamp != 0.0:
            self.rtt = int((message['_timestamp'] - self.actionTimestamp) * 1000)
            self.actionTimestamp = 0.0

        tag = message['tag']
        if tag == 'HELO':
            '''example: 
            {"tag":"HELO",
            "uname":"%53%42",
            "PF4":"14,370,1865.42,1289.0,144,124,133,120,37,5276,1243,692,1869,898",
            "PF3":"17,490,2176.99,4421.0,545,550,459,0,109,13734,4005,1801,3222,3041","expire":"20200609","expiredays":"10",
            "ratingscale":"PF3=1.000000&PF4=1.000000&PF01C=0.582222&PF02C=0.501632&PF03C=0.414869&PF11C=0.823386&PF12C=0.709416&PF13C=0.586714&PF23C=0.378722&PF33C=0.535594&PF1C00=8.000000",
            "rr":"PF3=262,0&PF4=0,0&PF01C=0,0&PF02C=0,0&PF03C=0,0&PF11C=0,0&PF12C=0,0&PF13C=0,0&PF23C=0,0&PF33C=0,0&PF1C00=0,0"}
            '''
            self.lobbyData = utils.LobbyData()
            self.state = 1
            if 'expire' in message:
                logger.info('尊贵的会员，欢迎登录！')
                logger.info('友情提醒：您的会员将在' + message['expire'] + '到期，请及时续费')
            logger.info('昵称：' + unquote(message['uname']))
            if 'PF4' in message:
                logger.info('四麻战绩：' + message['PF4'])
            if 'PF3' in message:
                logger.info('三麻战绩：' + message['PF3'])
            self.playerData = utils.PlayerData(message)
            logger.info('和了率：' + str(self.playerData.yonmaStat['countAgari'] / self.playerData.yonmaStat['countKyoku']) if self.playerData.yonmaStat['countKyoku'] > 0 else 'NAN')


            if 'nintei' in message:
                self.displayNinteiInfo(unquote(message['nintei']))
        elif tag == 'LN':
            self.lobbyData.decode(message)
            pass
        elif tag == 'RANKING':
            if 'v2' in message:
                self.monthlyStats = utils.MonthlyStats(message)

        elif tag == 'CHAT':
            pass
        elif tag == 'REJOIN':
            try:
                tenhou_client.send(self.client.ws, {'tag': 'JOIN', 't': message['t']})
            except:
                pass
        elif tag == 'GO':
            self.gameInfo = GameInfo()
            self.gameInfo.tableInfo.rule = int(message['type'])
            self.gameInfo.tableInfo.lobby = int(message['lobby'])
            if 'gpid' in message:
                self.storeGpid(message['gpid'])
            self.pxr(0)
            self.client.gok()
            self.state = 3
            if self.gameInfo.tableInfo.isSanma():
                self.controlButtonSpriteGroup.getSpriteById('no_chi').visible = False
                self.controlButtonSpriteGroup.getSpriteById('no_pon').visible = False
            else:
                self.controlButtonSpriteGroup.getSpriteById('no_chi').visible = True
                self.controlButtonSpriteGroup.getSpriteById('no_pon').visible = True
            self.ruleSelectionButtonSpriteGroup.getSpriteById('join').choose(0)
            self.ruleSelectionButtonSpriteGroup.setEnabled(True)
            self.myHandTileSpriteGroup = MyHandTileSpriteGroup()
        elif tag == 'UN':
            # 可能是开局玩家信息，也可能是有人重连了
            # 目前根据有没有'dan'属性来判断是开局还是重连
            if 'dan' in message:
                # 有dan，是开局（或自己重连）
                dans = message['dan'].split(',')
                rates = message['rate'].split(',')
                for i in range(4):
                    p = self.gameInfo.tableInfo.players[i]
                    p['name'] = unquote(message['n' + str(i)])
                    p['dan'] = int(dans[i])
                    p['rate'] = float(rates[i])
                    if p['name'] != '':
                        self.gameInfo.playerExist[i] = True
                        print(p['name'], str(p['dan'] - 9) + '段', 'R'+str(p['rate']))
            else:
                # 没dan，是对手重连
                for i in range(4):
                    if 'n' + str(i) in message:
                        self.gameInfo.online[i] = True
                        print(unquote(message['n' + str(i)]), '重连了')
        elif tag == 'TAIKYOKU':
            self.gameInfo.initialOya = int(message['oya'])
            if 'log' in message:
                self.gameInfo.log = message['log']
                self.storeLog(message['log'])
                self.storeTempLog(message['log'])
            #self.client.ready()
            self.soundResources.sound['winlose'].play()
            self.displayGameStartInfo()
            self.waitingForReady = 1
            self.setTimer(10, False)
        elif tag == 'INIT':
            self.remainingOvertime = const.OVERTIME[1] if self.gameInfo.tableInfo.isFast() else const.OVERTIME[0]
            seeds = message['seed'].split(',')
            self.gameInfo.kyokuInfo = KyokuInfo()
            self.gameInfo.gameControlInfo = GameControlInfo()
            self.controlButtonSpriteGroup.deselectAll()
            self.popUpWindow = None
            info = self.gameInfo.kyokuInfo
            if self.gameInfo.tableInfo.isSanma():
                info.init_sanma()
            info.kyoku = int(seeds[0])
            info.honba = int(seeds[1])
            info.kyoutaku = int(seeds[2])
            info.doraIndicators = []
            for i in range(5, len(seeds)):
                info.doraIndicators.append(int(seeds[i]))
                info.reveal_tile(int(seeds[i]))
            info.hands = [[], [], [], []]
            for i in range(4):
                if i == 0:
                    hai = message['hai'].split(',')
                    for j in range(len(hai)):
                        info.hands[i].append(int(hai[j]))
                        info.reveal_tile(int(hai[j]))
                else:
                    if not self.gameInfo.playerExist[i]:
                        continue
                    for j in range(13):
                        info.hands[i].append(-1) # 对手的手牌都是牌背
            info.hands[0].sort() # 理牌
            self.updateMachi()
            self.myHandTileSpriteGroup.init(info.hands[0])
            info.furos = [[], [], [], []]
            info.rivers = [[], [], [], []]
            ten = message['ten'].split(',')
            info.ten = [0, 0, 0, 0]
            info.remaining = self.gameInfo.tableInfo.isSanma() and 55 or 70
            for i in range(4):
                info.ten[i] = int(ten[i])

            info.oya = int(message['oya'])
            info.whosTurn = info.oya
            info.playerState = 0
        elif tag == 'REINIT':
            # 重连之后会收到：
            # recv: {"tag":"GO","type":"25","lobby":"1717","gpid":"967297C0-57844F69"}
            # recv: {"tag":"UN","n0":"%4E%6F%4E%61%6D%65","n1":"%4E%6F%4E%61%6D%65","n2":"","n3":"%E7%8B%97%E7%8C%AB","dan":"0,0,0,2","rate":"1500.00,1500.00,1500.00,1502.64","sx":"M,M,C,M"}
            # recv: {"tag":"SAIKAI","ba":"0,0","oya":"3","sc":"350,0,350,0,0,0,350,0"}
            # recv: {"tag":"REINIT","seed":"0,0,0,0,5,72","ten":"350,350,0,350","oya":"3","hai":"33,37,43,59,68,80,93,95,102,116,119,128,135","m1":"31520,30752","kawa0":"41,79,89","kawa1":"64,32,67","kawa3":"112,34,131,38"}
            message['tag'] = 'INIT'
            self.decodeAndDisplay(message)
            info = self.gameInfo.kyokuInfo
            for i in range(4):
                # 取得牌河信息
                if 'kawa' + str(i) in message:
                    river = message['kawa' + str(i)].split(',')
                    rot = False
                    for tilestr in river:
                        info.remaining -= 1 # 重连之后的reinit消息表示的状态 好像必定是有人摸牌前 因此 牌河里每有一张牌 说明之前牌山被摸掉了一张牌
                        if tilestr == '255':
                            # 255表示下一张牌要横过来（应该是这样，是伪宣言牌 而不是真·立直宣言牌）
                            rot = True
                            info.reached[i] = True
                            continue
                        if rot:
                            discardInfo = 4
                        else:
                            discardInfo = 0
                        info.rivers[i].append([int(tilestr), discardInfo])
                        info.reveal_tile(int(tilestr))
                        rot = False
                    if rot:
                        # 如果牌河最后是255 说明宣言牌被副露掉了 下一张牌要横过来 (没遇到过这种情况，只是猜测
                        self.gameInfo.gameControlInfo.rotateNextTile[i] = True
                # 取得副露信息
                if 'm' + str(i) in message:
                    furostrs = message['m' + str(i)].split(',')
                    for furostr in furostrs:
                        furo = utils.decodeFuro(int(furostr))
                        info.furos[i].insert(0, furo)
                        for tilecode in furo.tilecodes:
                            info.reveal_tile(tilecode)
                        # 把被副露的那张牌加到被副露那家的牌河的头上
                        info.rivers[utils.relativeToAbsolute(furo.fromWhoRelative, i)].insert(0, [furo.tilecodes[furo.whichTileIsClaimed], 2])
                        if not furo.isKita:
                            info.hands[i] = info.hands[i][:-3]
                        if furo.isKita or furo.isKan:
                            # 如果是拔北或杠，则牌山也被多摸掉了一张牌
                            info.remaining -= 1
            self.popUpWindow = None
        elif tag == 'SAIKAI':
            self.displayGameResumeInfo(message)
        elif tag[0] in 'TUVW' and (len(tag) == 1 or tag[1] in '0123456789'):
            # 摸牌
            # self.soundResources.sound['draw'].play()
            if settings.FORCE_DELAY:
                self.busy = 10
            info = self.gameInfo.kyokuInfo
            who = ord(tag[0]) - ord('T')
            if len(tag) == 1:
                hai = -1
            else:
                hai = int(tag[1:])
                info.reveal_tile(hai)
            info.hands[who].append(hai) # 放入手牌
            info.playerState = 1 # 该玩家状态为摸了牌
            info.whosTurn = who # 该玩家的回合
            info.remaining -= 1 # 残牌-1
            # print('Player', who, self.gameInfo.tableInfo.getPlayerByIndex(who)['name'], '摸', utils.tilecodeToString2(hai))

            if who == 0:
                #self.client.discard(hai)
                self.setTimer(const.TIME[1] if self.gameInfo.tableInfo.isFast() else const.TIME[0])
                self.myHandTileSpriteGroup.tsumoTile(hai)
                self.gameInfo.gameControlInfo.canDiscard = True
                self.myHandTileSpriteGroup.setCanDiscard(True)
                self.updateTenpaiInfo()
                self.updateKanInfo()
                if 't' in message:
                    # 如果有按钮出现
                    # TODO: ask for human player's action
                    self.soundResources.sound['button'].play()
                    suggestion = int(message['t'])
                    self.gameInfo.gameControlInfo.suggestion = suggestion
                    self.gameInfo.gameControlInfo.suggestedTile = -1
                    if suggestion & 16:
                        # 自摸
                        if self.controlButtonSpriteGroup.getSpriteById('auto_agari').selected:
                            self.tsumo()
                        else:
                            self.textButtonSpriteGroup.getSpriteById('tsumo').visible = True
                    if suggestion & 32:
                        # 立直
                        self.textButtonSpriteGroup.getSpriteById('reach').visible = True
                        pass
                    if suggestion & 64:
                        # 99
                        self.textButtonSpriteGroup.getSpriteById('99').visible = True
                        pass
                    if suggestion & 128:
                        # 拔北
                        self.textButtonSpriteGroup.getSpriteById('kita').visible = True
                        pass

                # 询问是否加杠和暗杠
                for i in range(len(self.gameInfo.gameControlInfo.kanSuggestions)):
                    kanSuggestion = self.gameInfo.gameControlInfo.kanSuggestions[i]
                    btn = self.textButtonSpriteGroup.getSpriteById('self_kan' + str(i))
                    btn.updateTile(kanSuggestion[1])
                    btn.visible = True
                if (self.gameInfo.kyokuInfo.reached[0] or self.controlButtonSpriteGroup.getSpriteById('auto_discard').selected) and self.gameInfo.gameControlInfo.suggestion == 0 and len(self.gameInfo.gameControlInfo.kanSuggestions) == 0:
                    if settings.AUTO_ACTION_DELAY:
                        self.autoActionTimer = threading.Timer(settings.AUTO_ACTION_DELAY, self.discard, args=[hai])
                        self.autoActionTimer.start()
                    else:
                        self.discard(hai)
                
        elif (tag[0] in 'DEFG' or tag[0] in 'defg') and tag[1] in '0123456789':
            if settings.FORCE_DELAY:
                self.busy = 10
            if tag[0] in 'DEFG':
                tsumogiri = 0
                who = ord(tag[0]) - ord('D')
            else:
                tsumogiri = 1
                who = ord(tag[0]) - ord('d')
            #channel = self.soundResources.channels[who]
            #logger.debug(channel)
            #channel.play(self.soundResources.sound['discard'])
            self.soundResources.sound['discard'].play()

            hai = int(tag[1:])
            info = self.gameInfo.kyokuInfo
            if who == 0 and info.playerState == 1:
                # 如果自己切牌无论手模切都会收到大写D 因此要客户端自己判断手模切
                if hai == info.hands[0][-1]:
                    tsumogiri = 1
            reachDeclare = 0
            if self.gameInfo.gameControlInfo.rotateNextTile[who]:
                self.gameInfo.gameControlInfo.rotateNextTile[who] = False
                reachDeclare = 4
            discardInfo = tsumogiri | reachDeclare
            info.rivers[who].append([hai, discardInfo])
            if who == 0:
                self.myHandTileSpriteGroup.removeTile(hai)
                self.myHandTileSpriteGroup.sort()
                # 在接收到服务器的自己出牌的信息后，再把手牌变红 不然还没出去就变红看起来有点难受。。
                self.myHandTileSpriteGroup.setCanDiscard(False)
                info.hands[who].remove(hai)
                self.updateMachi()
            else:
                info.hands[who].pop(-1)
            info.playerState = 2 # 该玩家的状态为切了牌尚未通过
            # 加入到所有玩家的暂时通过的牌中 讲道理不应该加入切牌家的 但加入了也没啥后果 反正都永久通过了
            for i in range(4):
                info.temporarilyPassedTiles[i].append(hai)
                info.numNotPassedTiles[i], info.numNotPassedSujis[i] = info.calc_not_passed_tiles_and_sujis(i)
            # 如果不是自己切牌，则reveal这张牌（reveal里包含重新计算通过的牌和筋），否则只重新计算
            if who != 0:
                info.reveal_tile(hai)
            else:
                for i in range(4):
                    info.numNotPassedTiles[i], info.numNotPassedSujis[i] = info.calc_not_passed_tiles_and_sujis(i)
            if tsumogiri & 1 == 0:
                # 如果是手切的，则暂时通过的牌清空
                info.temporarilyPassedTiles[who] = []
                info.numNotPassedTiles[who], info.numNotPassedSujis[who] = info.calc_not_passed_tiles_and_sujis(who)
            if 't' in message:
                # 如果有按钮出现
                suggestion = int(message['t'])
                no_suggestion = 0
                if self.controlButtonSpriteGroup.getSpriteById('no_naki').selected:
                    no_suggestion |= 7
                if self.controlButtonSpriteGroup.getSpriteById('no_chi').selected:
                    no_suggestion |= 4
                if self.controlButtonSpriteGroup.getSpriteById('no_pon').selected:
                    no_suggestion |= 3
                if self.controlButtonSpriteGroup.getSpriteById('no_ron').selected:
                    no_suggestion |= 8
                
                remaining_suggestion = suggestion & (~no_suggestion)
                if remaining_suggestion == 0:
                    self.passTile()
                else:
                    self.soundResources.sound['button'].play()
                    self.textButtonSpriteGroup.getSpriteById('pass').visible = True
                    self.setTimer(const.TIME[1] if self.gameInfo.tableInfo.isFast() else const.TIME[0])

                    self.gameInfo.gameControlInfo.suggestion = suggestion
                    self.gameInfo.gameControlInfo.suggestedTile = hai
                    self.gameInfo.gameControlInfo.selectedTiles = []
                    self.processFuroSelection()
                    
                    if suggestion & 1:
                        # 碰
                        #self.textButtonSpriteGroup.getSpriteById('pon').visible = True
                        pass
                    if suggestion & 2:
                        # 大明杠
                        self.textButtonSpriteGroup.getSpriteById('kan').visible = True
                        pass
                    if suggestion & 4:
                        # 吃
                        #self.textButtonSpriteGroup.getSpriteById('chi').visible = True
                        pass
                    if suggestion & 8:
                        # 荣
                        if self.controlButtonSpriteGroup.getSpriteById('auto_agari').selected:
                            self.textButtonSpriteGroup.getSpriteById('pass').visible = False
                            self.ron()
                        else:
                            self.textButtonSpriteGroup.getSpriteById('ron').visible = True
                        pass
            # print('Player', who, self.gameInfo.tableInfo.getPlayerByIndex(who)['name'], ['手切', '摸切'][tsumogiri], utils.tilecodeToString2(hai))
            # print('手牌', list(map(utils.tilecodeToString2, info.hands[who])))
            # print('牌河', list(map(lambda tileAndInfo : (['', '摸切', '被副露', '摸切被副露'][tileAndInfo[1] % 4]) + ('立直' if tileAndInfo[1] & 4 else '') +  utils.tilecodeToString2(tileAndInfo[0]), (info.rivers[who]))))
        elif tag == 'N':
            # 副露
            who = int(message['who'])
            m = int(message['m'])
            furo = utils.decodeFuro(m)
            # 更新kyokuInfo里的副露信息
            # 实战无法根据数据包判断对手的手摸拔/杠
            info = self.gameInfo.kyokuInfo
            info.whosTurn = who
            if furo.isKan == 2: # 加杠
                info.playerState = 4 # 状态为加杠尚未通过
                # 加杠不会产生新的副露，只是修改了原先的副露
                for i in range(len(info.furos[who])):
                    origClaimedTile = info.furos[who][i].tilecodes[info.furos[who][i].whichTileIsClaimed]
                    claimedTile = furo.tilecodes[furo.whichTileIsClaimed]
                    if origClaimedTile == claimedTile:
                        # 找到了原先的副露
                        origTsumogiri = info.furos[who][i].isTsumogiri
                        # 新副露里还没分析手模切，所以要把老副露里的手模切复制到新副露里
                        info.furos[who][i] = furo
                        info.furos[who][i].isTsumogiri = origTsumogiri
                        break
                # 把加杠的那张牌加入到临时通过的牌中（当然现在尚未通过，不过马上就通过了 就算没通过，也没事，因为这小局已经结束了
                for i in range(4):
                    info.temporarilyPassedTiles[i].append(furo.tilecodes[3])
            else:
                if furo.isKan == 1 and furo.fromWhoRelative == 0: # 暗杠
                    info.playerState = 3 # 状态为副露后
                    pass
                elif furo.isKita:
                    info.playerState = 4 # 状态为拔北尚未通过
                    # 把拔北的那张牌加入到临时通过的牌中
                    for i in range(4):
                        if i != who: # 自己拔北不振听，所以不能算做他的通过了的牌
                            info.temporarilyPassedTiles[i].append(furo.tilecodes[0])
                else:
                    info.playerState = 3 # 状态为副露后
                    fromWhoAbsolute = utils.relativeToAbsolute(furo.fromWhoRelative, who)
                    [hai, tsumogiri] = info.rivers[fromWhoAbsolute][-1] # 副露的牌 必定是被副露家刚切的牌
                    if hai != furo.tilecodes[furo.whichTileIsClaimed]:
                        logger.error('ERROR: 副露的牌不是刚切的牌')
                    furo.isTsumogiri = tsumogiri
                    info.rivers[fromWhoAbsolute][-1][1] |= 2 # 设置牌河中的牌为'被副露'
                    if tsumogiri & 4:
                        # 有人的立直宣言牌被副露掉了
                        self.gameInfo.gameControlInfo.rotateNextTile[fromWhoAbsolute] = True
                
                info.furos[who].append(furo) # 加入此玩家的副露列表
                if self.controlButtonSpriteGroup.getSpriteById('no_ron').selected:
                    no_suggestion |= 8
            
            # 从手牌中移除副露的牌
            if who == 0:
                for i in range(4):
                    for j in range(len(info.hands[who])):
                        if info.hands[who][j] in furo.tilecodes:
                            info.hands[who].pop(j)
                            break
                for tilecode in furo.tilecodes:
                    self.myHandTileSpriteGroup.removeTile(tilecode)
                self.myHandTileSpriteGroup.sort()
                # 自己副露之后就能切牌了(开杠、拔北除外) 并且需要更新切啥听啥的信息
                if info.playerState == 3:
                    self.gameInfo.gameControlInfo.canDiscard = True
                    self.myHandTileSpriteGroup.setCanDiscard(True)
                    self.updateTenpaiInfo()
                    self.setTimer(const.TIME[1] if self.gameInfo.tableInfo.isFast() else const.TIME[0])
            else:
                # 从对手的暗牌里移除
                self._removeHandByFuro(info.hands[who], furo)
                # 添加到出现的牌
                for tile in furo.tilecodes:
                    info.reveal_tile(tile)
            self.displayCall(who, furo.getFuroTypeString())
            self.soundResources.sound[furo.getFuroTypeString2()].play()
            # 如果自己没在立直，则把手牌enable（如果有副露按钮，手牌会（部分）disable）
            if not info.reached[0]:
                self.myHandTileSpriteGroup.setEnabled(True)
            # 并且重置suggestion 隐藏所有按钮 因为可能是自己想吃被别人碰或杠了
            self.gameInfo.gameControlInfo.suggestion = 0
            self.gameInfo.gameControlInfo.suggestedTile = -1
            print('Player', who, self.gameInfo.tableInfo.getPlayerByIndex(who)['name'], furo.getFuroTypeString(), ['自己', '下家', '对家', '上家'][furo.fromWhoRelative])
            # print(furo.isTsumogiri == 1 and '被副露的牌是摸切的' or '被副露的牌是手切的')
            print(list(map(utils.tilecodeToString2, furo.tilecodes)))
            # print('副露后手牌', list(map(utils.tilecodeToString2, sorted(info.hands[who]))))
            print('他/她的所有副露：')
            for f in info.furos[who]:
                print(list(map(utils.tilecodeToString2, f.tilecodes)))

            if 't' in message:
                suggestion = int(message['t'])
                no_suggestion = 0
                remaining_suggestion = suggestion & (~no_suggestion)
                if remaining_suggestion == 0:
                    self.passTile()
                else:
                    self.soundResources.sound['button'].play()
                    self.textButtonSpriteGroup.getSpriteById('pass').visible = True
                    self.gameInfo.gameControlInfo.suggestion = suggestion
                    if suggestion & 8:
                        # 荣
                        if self.controlButtonSpriteGroup.getSpriteById('auto_agari').selected:
                            self.textButtonSpriteGroup.getSpriteById('pass').visible = False
                            self.ron()
                        else:
                            self.setTimer(const.TIME[1] if self.gameInfo.tableInfo.isFast() else const.TIME[0])
                            self.textButtonSpriteGroup.getSpriteById('ron').visible = True
                        pass
                    else:
                        logger.warning('Unreachable')

        elif tag == 'DORA':
            hai = int(message['hai'])
            self.gameInfo.kyokuInfo.doraIndicators.append(hai)
            print('新dora指示牌', utils.tilecodeToString2(hai))
            self.gameInfo.kyokuInfo.reveal_tile(hai)
        elif tag == 'REACH':
            who = int(message['who'])
            step = int(message['step'])
            info = self.gameInfo.kyokuInfo
            if step == 1:
                print('Player', who, self.gameInfo.tableInfo.getPlayerByIndex(who)['name'], '立直')
                if who == 0:
                    # 自己立直了 按下立直按钮后，canDiscard会变成false 此时收到了服务器确认消息 把canDiscard设回true
                    self.setTimer(const.TIME[1] if self.gameInfo.tableInfo.isFast() else const.TIME[0])
                    self.gameInfo.gameControlInfo.canDiscard = True
                    # TODO: 仅enable切了可以听牌的手牌 disable其他手牌
                    for tile in self.gameInfo.kyokuInfo.hands[0]:
                        if tile // 4 not in self.gameInfo.kyokuInfo.discardToMachi:
                            self.myHandTileSpriteGroup.setEnabled(False, tile)
                self.gameInfo.gameControlInfo.rotateNextTile[who] = True
                self.soundResources.sound['reach'].play()
                self.displayCall(who, 'reach')
            else:
                info.reached[who] = True
                ten = message['ten'].split(',')
                for i in range(4):
                    info.ten[i] = int(ten[i])
                info.kyoutaku += 1
                if who == 0:
                    # 自己立直成功了，把自己手牌disable
                    self.myHandTileSpriteGroup.setEnabled(False)
        elif tag == 'AGARI':
            who = int(message['who'])
            fromWho = int(message['fromWho'])
            print('Player', who, self.gameInfo.tableInfo.getPlayerByIndex(who)['name'], '和了')
            if fromWho == who:
                self.displayCall(who, 'tsumo')
                self.soundResources.sound['tsumo'].play()
                print('自摸')
            else:
                self.displayCall(who, 'ron')
                self.soundResources.sound['ron'].play()
                print('Player', fromWho, self.gameInfo.tableInfo.getPlayerByIndex(fromWho)['name'], '放铳')
            if 'paoWho' in message:
                paoWho = int(message['paoWho'])
                print('Player', paoWho, self.gameInfo.tableInfo.getPlayerByIndex(paoWho)['name'], '包牌')
            for key in message:
                print("attributes: ", key, "=", message[key])
            
            # 显示和牌信息
            self.gameInfo.gameControlInfo.canDiscard = False
            self.myHandTileSpriteGroup.setEnabled(False)
            self.gameInfo.gameControlInfo.suggestion = 0
            self.gameInfo.gameControlInfo.suggestedTile = -1
            self.textButtonSpriteGroup.setInvisible()
            self.gameInfo.kyokuInfo.playerState = 0

            if who != 0:
                hand = list(map(int, message['hai'].split(',')))
                hand.remove(int(message['machi']))
                if fromWho == who:
                    hand.append(int(message['machi']))
                self.gameInfo.kyokuInfo.hands[who] = hand
            self.gameInfo.kyokuInfo.agariInfo.append(message)
            if 'owari' in message:
                self.gameInfo.kyokuInfo.owariInfo = message['owari']
                self.processOwari()
            else:
                self.waitingForReady = 1
                self.setTimer(10, False)
        elif tag == 'RYUUKYOKU':
            print('流局')
            for key in message:
                print("attributes: ", key, "=", message[key])
            #TODO 显示信息、ask for NEXTREADY
            #self.displayRyukyokuInfo(message)
            self.myHandTileSpriteGroup.setEnabled(False)
            for player in range(1, 4):
                if 'hai' + str(player) in message:
                    self.gameInfo.kyokuInfo.hands[player] = list(map(int, message['hai' + str(player)].split(',')))
            self.gameInfo.kyokuInfo.ryukyokuInfo = message
            self.gameInfo.kyokuInfo.playerState = 0
            if 'owari' in message:
                self.gameInfo.kyokuInfo.owariInfo = message['owari']
                self.processOwari()
            else:
                self.waitingForReady = 1
                self.setTimer(5, False)
        elif tag == 'BYE':
            # 'who' 掉线了
            who = int(message['who'])
            self.gameInfo.online[who] = False
            print(self.gameInfo.tableInfo.players[who]['name'], '掉线了')
        elif tag == 'FURITEN':
            if 'show' in message:
                if message['show'] == '0':
                    self.gameInfo.kyokuInfo.furiten = False
                    print('解除振听')
                else:
                    # TODO 显示振听
                    self.gameInfo.kyokuInfo.furiten = True
                    print('振听')
        elif tag == 'PROF':
            # TODO
            pass
        else:
            logger.error("Unexpected tag")

    def _removeHandByFuro(self, hand, furo):
        # 根据副露信息来移除对手手牌
        def popn(l, n):
            for _ in range(n):
                l.pop(-1)
        if furo.isKan == 2:
            # 加杠
            hand.pop(-1)
        elif furo.isChi or furo.isPon:
            popn(hand, 2)
        elif furo.isKita:
            hand.pop(-1)
        elif furo.isKan == 1:
            if furo.fromWhoRelative == 0:
                popn(hand, 4)
            else:
                popn(hand, 3)
        else:
            logger.error('未知的副露类型')

    def processOwari(self):
        self.stopTimer()
        self.storeGpid('')
        self.client.disconnect()
        self.state = 0
        self.nextFunction = self.displayGameEndInfo
        
        log = self.gameInfo.log
        if not log:
            log = self.readTempLog()
        if log:
            downloadHaifuThread = DownloadHaifuThread(self.gameInfo.log, (4 - self.gameInfo.initialOya) % 4)
            self.gameInfo.log = ''
            self.storeTempLog('')
            timer = threading.Timer(15, downloadHaifuThread.run)
            timer.start()

    def login(self, name, sx='F', gpid=None):
        success = self.client.login(name, sx, gpid)
        if success:
            self.state = 1
            return True
        return False
    def gotoLobby(self, lobby):
        self.client.gotoLobby(lobby)
        while self.client.lobby != lobby:
            time.sleep(0.1)
        rulecode = self.ruleSelectionButtonSpriteGroup.getRulecode()
        if rulecode & 1 and lobby == 0000:
            self.pxr(rulecode)
    def autoLogin(self):
        self.dismissWindow()
        self.client.init()
        self.state = 0
        self.login(settings.ID)
        self.gotoLobby(settings.LOBBY)
    def pxr(self, rulecode):
        # 设置要查看的月间战绩的规则 0为不查看
        if rulecode != tenhou_client.PXR:
            tenhou_client.PXR = rulecode & (~0x40)
            self.client.pxr()
    def join(self):
        self.ruleSelectionButtonSpriteGroup.setEnabled(False)
        self.state = 2
        self.client.join(settings.LOBBY, self.ruleSelectionButtonSpriteGroup.getRulecode())
    def cancelJoin(self):
        self.client.cancelJoin()
        self.state = 1
        self.ruleSelectionButtonSpriteGroup.setEnabled(True)
    def ready(self):
        self.stopTimer()
        self.client.ready()
        
    def chi(self, tilecode0, tilecode1):
        self.stopTimer()
        self.textButtonSpriteGroup.setInvisible()
        # 暂时把手牌disable 等收到服务器的确认副露消息后，会重新enable的
        self.myHandTileSpriteGroup.setEnabled(False)
        self.gameInfo.gameControlInfo.selectedTiles = []
        self.client.chi(tilecode0, tilecode1)
    def pon(self, tilecode0, tilecode1):
        self.stopTimer()
        self.textButtonSpriteGroup.setInvisible()
        self.myHandTileSpriteGroup.setEnabled(False)
        self.gameInfo.gameControlInfo.selectedTiles = []
        self.client.pon(tilecode0, tilecode1)
    def daiminkan(self):
        self.stopTimer()
        self.textButtonSpriteGroup.setInvisible()
        self.myHandTileSpriteGroup.setEnabled(False)
        self.gameInfo.gameControlInfo.selectedTiles = []
        self.client.daiminkan()
    def ankan(self, tilecode):
        self.stopTimer()
        self.canDiscard = False
        self.actionTimestamp = time.time()
        self.client.ankan(tilecode)
    def kakan(self, tilecode):
        self.stopTimer()
        self.canDiscard = False
        self.actionTimestamp = time.time()
        self.client.kakan(tilecode)
    def kita(self):
        self.stopTimer()
        self.canDiscard = False
        self.actionTimestamp = time.time()
        self.client.kita()
    def ron(self):
        self.stopTimer()
        self.canDiscard = False
        self.client.ron()
    def tsumo(self):
        self.stopTimer()
        self.canDiscard = False
        self.actionTimestamp = time.time()
        self.client.tsumo()
    def ninenine(self):
        self.stopTimer()
        self.canDiscard = False
        self.actionTimestamp = time.time()
        self.client.ninenine()
    def reach(self):
        self.stopTimer()
        self.canDiscard = False
        self.actionTimestamp = time.time()
        self.client.reach()
    def passTile(self):
        self.stopTimer()
        # 如果自己没在立直，则把手牌enable（如果有副露按钮，手牌会（部分）disable）
        if not self.gameInfo.kyokuInfo.reached[0]:
            self.myHandTileSpriteGroup.setEnabled(True)
        self.textButtonSpriteGroup.setInvisible()
        self.myHandTileSpriteGroup.deselectAll()
        self.gameInfo.gameControlInfo.suggestion = 0
        self.gameInfo.gameControlInfo.suggestedTile = -1
        self.client.passTile()
    def discard(self, tilecode):
        self.stopTimer()
        if self.autoActionTimer:
            self.autoActionTimer.cancel()
        if self.remainingTime == (const.TIME[1] if self.gameInfo.tableInfo.isFast() else const.TIME[0]):
            self.remainingOvertime += 1
            logger.debug('+1s')
            if self.remainingOvertime > (const.OVERTIME[1] if self.gameInfo.tableInfo.isFast() else const.OVERTIME[0]):
                self.remainingOvertime = const.OVERTIME[1] if self.gameInfo.tableInfo.isFast() else const.OVERTIME[0]
        self.gameInfo.gameControlInfo.canDiscard = False
        self.textButtonSpriteGroup.setInvisible()
        self.gameInfo.gameControlInfo.suggestion = 0
        self.gameInfo.gameControlInfo.suggestedTile = -1
        self.actionTimestamp = time.time()
        self.client.discard(tilecode)

    def processFuroSelection(self):
        hand = self.gameInfo.kyokuInfo.hands[0]
        hai = self.gameInfo.gameControlInfo.suggestedTile
        selected = self.gameInfo.gameControlInfo.selectedTiles
        chi_candidates, chi_ways = furo_select.chi_tile_choices(hand, hai, selected)
        pon_candidates, pon_ways = furo_select.pon_tile_choices(hand, hai, selected)
        furo_candidates = set() # 只有这个是set，其他都是list。。有点不统一。。
        furo_ways = 0
        if self.gameInfo.gameControlInfo.suggestion & 4:
            furo_candidates = set(chi_candidates).union(furo_candidates)
            furo_ways += chi_ways
        if self.gameInfo.gameControlInfo.suggestion & 1:
            furo_candidates = set(pon_candidates).union(furo_candidates)
            furo_ways += pon_ways
        self.myHandTileSpriteGroup.setEnabledByList(furo_candidates.union(set(selected)))
        if len(selected) >= 1 and furo_ways == 1:
            if chi_ways == 1 and self.gameInfo.tableInfo.isYonma():
                if len(selected) == 2:
                    self.chi(selected[0], selected[1])
                elif len(selected) == 1:
                    self.chi(selected[0], chi_candidates[0])
                else:
                    logger.error('Cannot chi using selected tiles')
            elif pon_ways == 1:
                if len(selected) == 2:
                    self.pon(selected[0], selected[1])
                elif len(selected) == 1:
                    self.pon(selected[0], pon_candidates[0])
            else:
                logger.error('unreachable')
    
    def updateMachi(self):
        # 更新kyokuinfo里的当前在听啥的信息
        ac = AgariChecker.getInstance()
        myhand_34 = utils.tilecodesTo34(self.gameInfo.kyokuInfo.hands[0])
        self.gameInfo.kyokuInfo.machi = ac.get_machi(myhand_34)
        logger.info('听' + str(list(map(lambda tile34: utils.tilecodeToString2(tile34 << 2), self.gameInfo.kyokuInfo.machi))))
        
    def updateTenpaiInfo(self):
        # 更新kyokuinfo里的切啥听啥的信息
        ac = AgariChecker.getInstance()
        myhand_34 = utils.tilecodesTo34(self.gameInfo.kyokuInfo.hands[0])
        self.gameInfo.kyokuInfo.discardToMachi = ac.get_tenpai_info(myhand_34)
        for choice in self.gameInfo.kyokuInfo.discardToMachi:
            logger.info('切' + utils.tilecodeToString2(choice << 2) + '听' + str(list(map(lambda tile34: utils.tilecodeToString2(tile34 << 2), self.gameInfo.kyokuInfo.discardToMachi[choice]))))

    def updateKanInfo(self):
        # 更新gamecontrolinfo里的可以加杠、暗杠哪些牌的信息
        # （为什么听牌信息放在kyokuinfo里，可杠牌信息放在gamecontrolinfo里？我自己也不知道 不想通通放一个类里，就搞了一些小类，但这些类的分类方式就很模糊）
        info = self.gameInfo.kyokuInfo
        gci = self.gameInfo.gameControlInfo
        # 先重置
        gci.kanSuggestions = []
        # 如果海底了 不能杠
        if info.remaining == 0:
            return
        # 判断是否可以加杠。找碰，再找对应手牌
        for furo in info.furos[0]:
            if furo.isPon:
                tile34 = furo.tilecodes[0] // 4
                for tile in info.hands[0]:
                    if tile // 4 == tile34:
                        # 找到了可以加杠的牌
                        gci.kanSuggestions.append([5, tile])
        # 判断是否可以暗杠
        hand34 = utils.tilecodesTo34(info.hands[0])
        for i in range(34):
            if hand34[i] == 4:
                # 找到了杠材
                if info.reached[0]:
                    # 如果自己已经立直
                    ac = AgariChecker.getInstance()
                    hand34[i] = 0 # 暂时设为0枚 假装已经开了杠
                    machiAfterKan = ac.get_machi(hand34)
                    machiAfterKan_set = set(machiAfterKan)
                    origMachiSet = set(info.machi)
                    if machiAfterKan_set.issubset(origMachiSet) and machiAfterKan_set.issuperset(origMachiSet):
                        # 开杠不改变听牌，可以杠
                        gci.kanSuggestions.append([4, i << 2])
                    hand34[i] = 4 # 设回4枚
                else:
                    # 如果自己没立直 随便杠
                    gci.kanSuggestions.append([4, i << 2])


    def processMouseEvents(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            print(event.button)
            if event.button == 2:
                if self.client.ws.sock and self.client.ws.sock.connected:
                    # self.client.logout()
                    if settings.MIDDLE_CLICK_DISCONNECT:
                        self.client.disconnect()
                else:
                    sp = GameMsgSprite('重连中')
                    self.gamemsg_group.add(sp)
                    self.gameInfo = None
                    success = self.client.init()
                    if not success:
                        #sp = GameMsgSprite('重连失败')
                        return
                    self.state = 0 # 0: unauthenticated 1: authenticated, idle 2: joining 3: playing
                    gpid = ''
                    if self.gameInfo:
                        gpid = self.gameInfo.gpid
                    if gpid == '':
                        gpid = self.readGpid()
                    success = self.client.login(settings.ID, 'F', gpid)
                    if not success:
                        return
            elif event.button == 1:
                if self.state == 3:
                    self.textButtonSpriteGroup.onMouseDown(event.button, event.pos)
                    self.controlButtonSpriteGroup.onMouseDown(event.button, event.pos)
                    self.myHandTileSpriteGroup.onMouseDown(event.button, event.pos)
                elif self.state == 1 or self.state == 2:
                    self.ruleSelectionButtonSpriteGroup.onMouseDown(event.button, event.pos)
            elif event.button == 3:
                # 右键
                if self.state == 3:
                    # 正在牌桌上
                    if len(self.gameInfo.kyokuInfo.agariInfo) == 2:
                        self.gameInfo.kyokuInfo.agariInfo.pop(0)
                        return
                    elif self.waitingForReady == 1:
                        self.ready()
                        self.waitingForReady = 2
                    elif self.gameInfo.gameControlInfo.canDiscard:
                    #elif self.gameInfo.kyokuInfo.whosTurn == 0 and self.gameInfo.kyokuInfo.playerState == 1:
                        # 自己摸了牌，右键摸切
                        # self.discard(self.gameInfo.kyokuInfo.hands[0][-1])
                        # kyokuinfo的hand可能没排序 改成切屏幕显示的最右边的牌
                        self.discard(self.myHandTileSpriteGroup.sprites[-1].tilecode)
                    elif self.gameInfo.gameControlInfo.suggestion & 7 and not self.gameInfo.gameControlInfo.suggestion & 8:
                        self.passTile()
                if self.nextFunction:
                    tempFunction = self.nextFunction
                    self.nextFunction = None
                    tempFunction()
                    logger.debug('next function called')
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                if self.state == 3:
                    sp = self.textButtonSpriteGroup.onMouseUp(event.button, event.pos)
                    if sp:
                        self.textButtonSpriteGroup.setInvisible()
                        if sp.id == 'pass':
                            self.passTile()
                        elif sp.id == 'reach':
                            self.reach()
                        elif sp.id == 'tsumo':
                            self.tsumo()
                        elif sp.id == 'ron':
                            self.ron()
                        elif sp.id == '99':
                            self.ninenine()
                        elif sp.id == 'kita':
                            self.kita()
                        elif sp.id == 'pon':
                            hand = self.gameInfo.kyokuInfo.hands[0]
                            hai = self.gameInfo.gameControlInfo.suggestedTile
                            pon_candidates, pon_ways = furo_select.pon_tile_choices(hand, hai)
                            if pon_ways == 1:
                                self.pon(pon_candidates[0], pon_candidates[1])
                            
                        elif sp.id == 'chi':
                            hand = self.gameInfo.kyokuInfo.hands[0]
                            hai = self.gameInfo.gameControlInfo.suggestedTile
                            chi_candidates, chi_ways = furo_select.chi_tile_choices(hand, hai)
                            if chi_ways == 1:
                                self.chi(chi_candidates[0], chi_candidates[1])
                        elif sp.id == 'kan':
                            # 现在只能大明杠
                            self.daiminkan()
                        elif sp.id[:8] == 'self_kan':
                            index = int(sp.id[8:])
                            kanSuggestion = self.gameInfo.gameControlInfo.kanSuggestions[index]
                            if kanSuggestion[0] == 5:
                                self.kakan(kanSuggestion[1])
                            else:
                                self.ankan(kanSuggestion[1])
                        else:
                            logger.error('Unexpected button id')
                        
                        self.gameInfo.gameControlInfo.suggestion = 0
                        self.gameInfo.gameControlInfo.suggestedTile = -1
                    
                    sp = self.controlButtonSpriteGroup.onMouseUp(event.button, event.pos)
                    if sp:
                        logger.debug('control button clicked')

                    sp = self.myHandTileSpriteGroup.onMouseUp(event.button, event.pos)
                    if sp:
                        if self.gameInfo.gameControlInfo.suggestion & 7:
                            # 选择副露用的牌
                            tilecode = sp.tilecode
                            selected = self.gameInfo.gameControlInfo.selectedTiles
                            if tilecode in selected:
                                selected.remove(tilecode)
                                sp.deselect()
                            else:
                                selected.append(tilecode)
                                sp.select()
                            self.processFuroSelection()
                        # 切牌
                        if self.gameInfo.gameControlInfo.canDiscard:
                            self.discard(sp.tilecode)
                            # 暂时不把手牌变红 不然看起来难受
                            # self.myHandTileSpriteGroup.setCanDiscard(False)
                elif self.state == 1 or self.state == 2:
                    sp = self.ruleSelectionButtonSpriteGroup.onMouseUp(event.button, event.pos)
                    if sp:
                        if sp.id == 'join':
                            if sp.choice == 1:
                                if self.isRequirementSatisfied(self.ruleSelectionButtonSpriteGroup.getRulecode()) or settings.LOBBY != 0000:
                                    self.join()
                                else:
                                    sp.choose(0)
                            elif sp.choice == 0:
                                self.cancelJoin()
                        elif sp.id == 'exit':
                            if self.state == 2:
                                self.cancelJoin()
                            self.client.logout()
                            self.client.disconnect()
                            pygame.event.post(pygame.event.Event(pygame.QUIT, {}))
                        else:
                            if sp.id != 'speed':
                                self.monthlyStats = None
                                rulecode = self.ruleSelectionButtonSpriteGroup.getRulecode()
                                if rulecode & 1 and settings.LOBBY == 0000:
                                    self.pxr(rulecode)
                                else:
                                    self.pxr(0)

        elif event.type == pygame.MOUSEMOTION:
            pass
            #self.myHandTileSpriteGroup.onMouseMotion(event.pos)
    
    def run_test(self):
        # 此函数用于测试gui
        g = TextButtonSpriteGroup()
        running = True
        self.displayBackground()
        g.getSpriteById('self_kan1').updateTile(124)
        g.getSpriteById('self_kan1').visible = True
        b = TextButtonSprite('☑□', 'check')
        b.visible = True
        g.add(b)
        g.draw(self.screen)
        cbg = ControlButtonSpriteGroup()
        cbg.draw(self.screen)

        self.myHandTileSpriteGroup.init([3,9,52,124])
        self.myHandTileSpriteGroup.tsumoTile(95)
        self.myHandTileSpriteGroup.setCanDiscard(True)
        self.myHandTileSpriteGroup.draw(self.screen)

        self.displayNinteiInfo(unquote("%E8%AA%8D%E5%AE%9A%E6%AE%B5%E4%BD%8D%2F%E7%B4%9A%E4%BD%8D    :    %E3%82%B5%E3%83%B3%E3%83%9E %EF%BC%96%E7%B4%9A%0A%0A%E4%BA%8C%E9%9A%8E%E5%A0%82%E7%BE%8E%E6%A8%B9 %E6%AE%BF%0A%0A%E8%B2%B4%E6%AE%BF%E3%81%AF%E5%A4%A9%E9%B3%B3%E3%81%AB%E3%81%8A%E3%81%84%E3%81%A6%E5%8D%93%E8%B6%8A%E3%81%97%E3%81%9F%E6%8A%80%E8%83%BD%E3%82%92%E9%81%BA%E6%86%BE%E3%81%AA%E3%81%8F%E7%99%BA%E6%8F%AE%E3%81%95%E3%82%8C%E5%84%AA%E7%A7%80%E3%81%AA%0A%E6%88%90%E7%B8%BE%E3%82%92%E3%81%8A%E3%81%95%E3%82%81%E3%82%89%E3%82%8C%E3%81%BE%E3%81%97%E3%81%9F%E3%80%82%E4%BB%8A%E5%BE%8C%E3%82%82%E3%81%95%E3%82%89%E3%81%AA%E3%82%8B%E9%9B%80%E5%8A%9B%E5%90%91%E4%B8%8A%E3%81%AB%E7%B2%BE%E9%80%B2%E3%81%95%E3%82%8C%0A%E3%81%BE%E3%81%99%E3%82%88%E3%81%86%E3%81%93%E3%81%93%E3%81%AB%E6%AE%B5%E4%BD%8D%2F%E7%B4%9A%E4%BD%8D%E3%82%92%E8%AA%8D%E5%AE%9A%E3%81%97%E6%A0%84%E8%AA%89%E3%82%92%E7%A7%B0%E3%81%88%E3%81%BE%E3%81%99%E3%80%82%0A%0A2020%E5%B9%B406%E6%9C%8801%E6%97%A5%0A%E5%A4%A9%E9%B3%B3%E3%82%B5%E3%83%B3%E3%83%9E%E6%BC%81%E6%A5%AD%E5%8D%94%E4%BC%9A%0A"))
        disp_pos = [(1024 - 600) // 2, (740 - 450) // 2]
        self.screen.blit(self.popUpWindow, disp_pos)
        pygame.display.flip()
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    pygame.quit()

    def run(self):
        self.client = tenhou_client.TenhouClient()
        tenhou_client.client = self.client
        self.client.registerProcessFunc(clientGUI.pushMessage)
        self.client.registerOnCloseFunc(clientGUI.on_close)
        success = self.client.init()
        if not success:
            pygame.quit()
            return
        self.state = 0 # 0: unauthenticated 1: authenticated, idle 2: joining 3: playing
        gpid = self.readGpid()
        success = self.login(settings.ID, 'F', gpid)
        if not success:
            print('LOGIN Not Success')
            pygame.quit()
            return
        lobby = settings.LOBBY
        self.gotoLobby(lobby)
        '''
        self.client.join(lobby, 16) # 17:3ban dong 1:4ban dong
        self.state = 2
        '''
        clock = pygame.time.Clock()
        pygame.key.set_repeat(500, 30)
        running = True
        while running:
            if not self.busy:
                if not self.messageQueue.empty():
                    m = self.messageQueue.get()
                    self.decodeAndDisplay(m)
                    try:
                        # self.decodeAndDisplay(m)
                        pass
                    except Exception as e:
                        logger.error(str(e))
            else:
                self.busy -= 1
            self.display()
            mouse_pos = pygame.mouse.get_pos()
            adjusted_mouse_pos = (mouse_pos[0], mouse_pos[1] - 2) # 坐标不准 所以要调整一下
            self.controlButtonSpriteGroup.onMouseMotion(adjusted_mouse_pos)
            sp = self.myHandTileSpriteGroup.onMouseMotion(adjusted_mouse_pos)
            if sp and sp.enabled and sp.canDiscard and ((sp.tilecode >> 2) in self.gameInfo.kyokuInfo.discardToMachi):
                if settings.DISP_MACHI:
                    self.displayMachi(self.gameInfo.kyokuInfo.discardToMachi[sp.tilecode >> 2], sp.tilecode >> 2)
            if self.gameInfo:
                rect = pygame.Rect((1024 - 6 * self.TILE_WIDTHS[0]) // 2, (740 - 6 * self.TILE_HEIGHT_EFF[1]) // 2, \
                    6 * self.TILE_WIDTHS[0], 6 * self.TILE_HEIGHT_EFF[1])
                if rect.collidepoint(adjusted_mouse_pos):
                    self.gameInfo.gameControlInfo.displayScoreDiff = True
                else:
                    self.gameInfo.gameControlInfo.displayScoreDiff = False

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    if self.client.ws.sock and self.client.ws.sock.connected:
                        self.client.disconnect()
                    pygame.quit()
                else:
                    if hasattr(event, 'pos'):
                        event.pos = (event.pos[0], event.pos[1] - 2)
                        self.processMouseEvents(event)
            clock.tick(30)


class CallTextSprite(pygame.sprite.Sprite):

    def __init__(self, who, calltext):
        # Call the parent class (Sprite) constructor
        pygame.sprite.Sprite.__init__(self)
        self.who = who
        self.calltext = calltext
        # Create an image of the block, and fill it with a color.
        # This could also be an image loaded from the disk.
        self.fontResources = FontResources.getInstance()
        self.call_font = self.fontResources.simheif48

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
    
class GameMsgSprite(pygame.sprite.Sprite):
    def __init__(self, text):
        # Call the parent class (Sprite) constructor
        pygame.sprite.Sprite.__init__(self)
        self.text = text
        # Create an image of the block, and fill it with a color.
        # This could also be an image loaded from the disk.
        self.fontResources = FontResources.getInstance()
        self.call_font = self.fontResources.simheif48

        self.orig_image, self.rect = self.call_font.render(text, THECOLORS['white'])

        # Fetch the rectangle object that has the dimensions of the image
        # Update the position of this object by setting the values of rect.x and rect.y
        # self.rect = self.image.get_rect()
        self.alpha = 255
        # self.image.set_alpha(self.alpha)
        self.image = self.orig_image.copy()
        self.image.fill((255,255,255,self.alpha), None, pygame.BLEND_RGBA_MULT)

        self.rect.center = (512, 380)

    def update(self, *args):
        # self.rect.x += 2
        self.rect.y -= 2
        if self.alpha > 4:
            self.alpha -= 4
        else:
            self.kill()
        self.image = self.orig_image.copy()
        self.image.fill((255,255,255,self.alpha), None, pygame.BLEND_RGBA_MULT)
        # self.image = self.call_font.render(self.calltext, True, THECOLORS['white'])

class ButtonSpriteBase(pygame.sprite.Sprite):
    # 按钮基类
    def __init__(self):
        super().__init__()
        self.visible = True
        self.enabled = True
        self.isDown = False
        self.hover = False
    def onMouseDown(self):
        self.isDown = True
    def onMouseUp(self):
        # return whether is clicked
        if self.isDown and self.enabled:
            self.onClick()
            return True
        return False
    def onClick(self):
        # print(utils.tilecodeToString2(self.tilecode) + ' clicked')
        pass
    def onMouseHover(self):
        # print(utils.tilecodeToString2(self.tilecode))
        self.hover = True
        pass
    def onMouseLeave(self):
        self.hover = False
        self.isDown = False

class TextButtonSprite(ButtonSpriteBase):
    # 吃碰大明杠立直自摸pass等按钮
    def __init__(self, text, id, pos = (0, 0)):
        super().__init__()
        self.imageResources = ImageResources.getInstance()
        self.orig_image = self.imageResources.img_button
        self.rect = self.orig_image.get_rect()
        self.rect.topleft = pos
        self.text = text
        self.id = id
        self.fontResources = FontResources.getInstance()
        self.font = self.fontResources.simheif28
        self.text_image, text_rect = self.font.render(text, THECOLORS['white'])
        self.image = self.orig_image.copy()
        self.image.blit(self.text_image, [(80 - text_rect.width) / 2, (40 - text_rect.height) / 2])
        self.visible = False # 吃碰立直等按钮 一开始是不可见的
    def onClick(self):
        super().onClick()
        print('button clicked')

class KanButtonSprite(TextButtonSprite):
    # 暗杠、加杠按钮 由于可能有多种杠法 要选择杠哪个 所以要单独搞一个类
    def __init__(self, id, pos = (0, 0)):
        super().__init__('杠  ', id, pos)
        self.tile_font = self.fontResources.symbolf32
        self.image_with_kan = self.image.copy() # 已经blit了'杠'、还没blit麻将牌的image
    def updateTile(self, tilecode):
        self.text_image2, text_rect2 = self.tile_font.render('    ' + utils.tilecodeToUnicodeString(tilecode), THECOLORS['white'])
        self.image = self.image_with_kan.copy()
        self.image.blit(self.text_image2, [(80 - text_rect2.width) / 2, (40 - text_rect2.height) / 2 + 1])

class ControlButtonSprite(ButtonSpriteBase):
    # 自动和 鸣无等按钮
    def __init__(self, text, id, pos = (0, 0), selected = False):
        super().__init__()
        self.text = text
        self.id = id
        self.pos = pos
        self.selected = selected
        self.fontResources = FontResources.getInstance()
        self.font1 = self.fontResources.symbolf22
        self.font2 = self.fontResources.simheif20
        self.uncheck_image, self.text_rect1_uncheck = self.font1.render('□ ', THECOLORS['white'])
        self.check_image, self.text_rect1_check = self.font1.render('☑ ', THECOLORS['white'])
        self.text_image, self.text_rect2 = self.font2.render('' + text, THECOLORS['white'])

        # create original image when checked
        h1 = self.text_rect1_check.h
        h2 = self.text_rect2.h
        h = max(h1, h2)
        w = self.text_rect1_check.w + self.text_rect2.w
        self.orig_image_check = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
        self.orig_image_check.blit(self.check_image, (2, (h - h1 + 1) // 2 + 1))
        self.orig_image_check.blit(self.text_image, (self.text_rect1_check.w + 2, (h - h2 + 1) // 2 + 1))
        self.rect = pygame.Rect(self.pos, (self.orig_image_check.get_width(), self.orig_image_check.get_height()))
        # create original image when unchecked
        h1 = self.text_rect1_uncheck.h
        h2 = self.text_rect2.h
        h = max(h1, h2)
        w = self.text_rect1_uncheck.w + self.text_rect2.w
        self.orig_image_uncheck = pygame.Surface((w + 2, h + 2),  pygame.SRCALPHA)
        self.orig_image_uncheck.blit(self.uncheck_image, (1, (h - h1 + 1) // 2 + 1))
        self.orig_image_uncheck.blit(self.text_image, (self.text_rect1_uncheck.w + 1, (h - h2 + 1) // 2 + 1))

        if selected:
            self.select()
        else:
            self.deselect()
    '''
    def _join_images(self):
        self.image = self.check_image
        if self.selected:
            h1 = self.text_rect1_check.h
            h2 = self.text_rect2.h
            h = max(h1, h2)
            w = self.text_rect1_check.w + self.text_rect2.w
            self.orig_image = pygame.Surface((w, h), pygame.SRCALPHA)
            self.orig_image.blit(self.check_image, (0, (h - h1 + 1) // 2))
            self.orig_image.blit(self.text_image, (self.text_rect1_check.w, (h - h2 + 1) // 2))
            self.set_alpha(self.alpha)
            self.rect = pygame.Rect(self.pos, (w, h))
        else:
            h1 = self.text_rect1_uncheck.h
            h2 = self.text_rect2.h
            h = max(h1, h2)
            w = self.text_rect1_uncheck.w + self.text_rect2.w
            self.orig_image = pygame.Surface((w, h),  pygame.SRCALPHA)
            self.orig_image.blit(self.uncheck_image, (0, (h - h1 + 1) // 2))
            self.orig_image.blit(self.text_image, (self.text_rect1_uncheck.w, (h - h2 + 1) // 2))
            self.set_alpha(self.alpha)
            self.rect = pygame.Rect(self.pos, (w, h))
    '''
    def onClick(self):
        super().onClick()
        if self.selected:
            self.deselect()
        else:
            self.select()
    def select(self):
        self.selected = True
        self.orig_image = self.orig_image_check
        self.set_alpha(255)
    def deselect(self):
        self.selected = False
        self.orig_image = self.orig_image_uncheck
        self.set_alpha(127)
    def set_alpha(self, alpha):
        # self.rect.x += 2
        # self.rect.y += 2
        self.alpha = alpha
        self.image = self.orig_image.copy()
        self.image.fill((255,255,255,alpha), None, pygame.BLEND_RGBA_MULT)
    def onMouseHover(self):
        super().onMouseHover()
        self.image = self.orig_image.copy()
        self.image.fill((255,255,255,self.alpha), None, pygame.BLEND_RGBA_MULT)
        self.image.fill((255,255,255,32), None, pygame.BLEND_RGBA_ADD)
        #logger.debug('control button: on mouse hover')
        #self.image.fill((255,255,255,self.alpha), None, pygame.BLEND_RGBA_MULT)
    def onMouseLeave(self):
        super().onMouseLeave()
        self.image = self.orig_image.copy()
        self.image.fill((255,255,255,self.alpha), None, pygame.BLEND_RGBA_MULT)
        #self.image.fill((255,255,255,self.alpha), None, pygame.BLEND_RGBA_MULT)
    

class HandTileSprite(ButtonSpriteBase):
    def __init__(self, tilecode, pos):
        super().__init__()
        self.imageResources = ImageResources.getInstance()
        self.TILE_WIDTH = self.imageResources.TILE_WIDTH
        self.TILE_HEIGHT = self.imageResources.TILE_HEIGHT
        self.tilecode = tilecode

        #img_rect = pygame.Rect(self.TILE_WIDTH * num, self.TILE_HEIGHT * suit, self.TILE_WIDTH, self.TILE_HEIGHT)
        #self.image = pygame.Surface(img_rect.size).
        #self.image.blit(self.imageResources.img_mytiles, (0, 0), img_rect)
        self.rect = pygame.Rect(pos[0], pos[1], self.TILE_WIDTH, self.TILE_HEIGHT)
        self.rect.topleft = pos
        self.orig_pos = pos
        self.canDiscard = False
        self.selected = False
    def select(self):
        if not self.selected:
            self.selected = True
            self.rect.top = self.orig_pos[1] - self.TILE_HEIGHT // 10
    def deselect(self):
        if self.selected:
            self.selected = False
            self.rect.top = self.orig_pos[1]

class SwitchButtonSprite(ButtonSpriteBase):
    # 每按一下，都会变成下一个选项的按钮 例如“般上特疯”循环
    def __init__(self, texts, id, pos = (0, 0), default = 0):
        super().__init__()
        self.imageResources = ImageResources.getInstance()
        self.orig_image = self.imageResources.img_button
        self.rect = self.orig_image.get_rect()
        self.rect.topleft = pos
        self.texts = texts
        self.num_choices = len(texts)
        self.id = id
        self.choice = default
        self.fontResources = FontResources.getInstance()
        self.font = self.fontResources.simheif28
        self.text_image, text_rect = self.font.render(texts[self.choice], THECOLORS['white'])
        self.image = self.orig_image.copy()
        self.image.blit(self.text_image, [(80 - text_rect.width) / 2, (40 - text_rect.height) / 2])
    def choose(self, choice):
        self.choice = choice
        self.text_image, text_rect = self.font.render(self.texts[self.choice], THECOLORS['white'])
        self.image = self.orig_image.copy()
        self.image.blit(self.text_image, [(80 - text_rect.width) / 2, (40 - text_rect.height) / 2])
    def next_choice(self):
        self.choose((self.choice + 1) % self.num_choices)
    def onClick(self):
        super().onClick()
        self.next_choice()


class ButtonSpriteGroup:
    def __init__(self):
        self.sprites = []
    def onMouseDown(self, button, pos):
        # 返回被鼠标按下的精灵
        # 以后可以改成自定义事件 而不是返回精灵
        event_sp = None
        if button == 1:
            for sp in self.sprites:
                if sp.visible and sp.rect.collidepoint(pos):
                    sp.onMouseDown()
                    event_sp = sp
        return event_sp
    def onMouseUp(self, button, pos):
        # 返回被鼠标单击的精灵
        event_sp = None
        if button == 1:
            for sp in self.sprites:
                if sp.visible and sp.rect.collidepoint(pos):
                    if sp.onMouseUp():
                        event_sp = sp
        return event_sp
    def onMouseMotion(self, pos):
        # 返回鼠标悬停的精灵
        event_sp = None
        for sp in self.sprites:
            if sp.visible and sp.rect.collidepoint(pos):
                sp.onMouseHover()
                event_sp = sp
            else:
                sp.onMouseLeave()
        return event_sp

class TextButtonSpriteGroup(ButtonSpriteGroup):
    def __init__(self):
        super().__init__()
        self.add(TextButtonSprite('跳过', 'pass', (720, 585)))
        self.add(TextButtonSprite('立直', 'reach', (520, 585)))
        self.add(TextButtonSprite('自摸', 'tsumo', (620, 585)))
        self.add(TextButtonSprite('荣', 'ron', (620, 585)))
        self.add(TextButtonSprite('拔北', 'kita', (720, 585)))
        self.add(TextButtonSprite('吃', 'chi', (220, 585)))
        self.add(TextButtonSprite('碰', 'pon', (320, 585)))
        self.add(TextButtonSprite('杠', 'kan', (420, 585)))
        self.add(TextButtonSprite('流局', '99', (120, 585)))
        self.add(KanButtonSprite('self_kan0', (220, 585)))
        self.add(KanButtonSprite('self_kan1', (320, 585)))
        self.add(KanButtonSprite('self_kan2', (420, 585))) # 不管暗杠还是加杠都需要4张牌，手牌14张（含副露），同时最多只能有3种杠法，3个按钮足够
    def add(self, sprite):
        self.sprites.append(sprite)
    def draw(self, surface):
        for sp in self.sprites:
            if sp.visible:
                surface.blit(sp.image, sp.rect.topleft)
    def getSpriteById(self, id):
        # get sprite by id
        for sp in self.sprites:
            if sp.id == id:
                return sp
        return None
    def setInvisible(self):
        for sp in self.sprites:
            sp.visible = False
    
class ControlButtonSpriteGroup(ButtonSpriteGroup):
    def __init__(self):
        super().__init__()
        self.add(ControlButtonSprite('自动和', 'auto_agari', (500, 738)))
        self.add(ControlButtonSprite('不鸣牌', 'no_naki', (600, 738)))
        self.add(ControlButtonSprite('不吃', 'no_chi', (800, 738)))
        self.add(ControlButtonSprite('不碰杠', 'no_pon', (700, 738)))
        self.add(ControlButtonSprite('摸切', 'auto_discard', (20, 738)))
        self.add(ControlButtonSprite('不荣', 'no_ron', (100, 738)))
        self.getSpriteById('auto_discard').visible = False
        self.getSpriteById('no_ron').visible = False
    def add(self, sprite):
        self.sprites.append(sprite)
    def draw(self, surface):
        for sp in self.sprites:
            if sp.visible:
                surface.blit(sp.image, sp.rect.topleft)
    def getSpriteById(self, id):
        # get sprite by id
        for sp in self.sprites:
            if sp.id == id:
                return sp
        return None
    def deselectAll(self):
        for sp in self.sprites:
            sp.deselect()
    def onMouseUp(self, button, pos):
        # 返回被鼠标单击的精灵
        event_sp = None
        if button == 1:
            for sp in self.sprites:
                if sp.visible and sp.rect.collidepoint(pos):
                    if sp.onMouseUp():
                        event_sp = sp
                        if sp.id == 'no_naki':
                            if sp.selected:
                                self.getSpriteById('no_chi').select()
                                self.getSpriteById('no_pon').select()
                            else:
                                self.getSpriteById('no_chi').deselect()
                                self.getSpriteById('no_pon').deselect()
                        elif sp.id == 'no_chi':
                            if sp.selected and self.getSpriteById('no_pon').selected:
                                self.getSpriteById('no_naki').select()
                            elif not sp.selected:
                                self.getSpriteById('no_naki').deselect()
                        elif sp.id == 'no_pon':
                            if sp.selected and self.getSpriteById('no_chi').selected:
                                self.getSpriteById('no_naki').select()
                            elif not sp.selected:
                                self.getSpriteById('no_naki').deselect()
        return event_sp

class MyHandTileSpriteGroup(ButtonSpriteGroup):
    def __init__(self):
        super().__init__()
        self.imageResources = ImageResources.getInstance()
        self.TILE_WIDTH = self.imageResources.TILE_WIDTH
        self.TILE_HEIGHT = self.imageResources.TILE_HEIGHT
        self.img_mytiles = self.imageResources.img_mytiles
        self.black_surf = self.imageResources.mytile_black_surf
        self.green_surf = self.imageResources.mytile_green_surf
        self.red_surf = self.imageResources.mytile_red_surf
        self.disp_pos = [200, 660]
        self.tsumoTileOffset = 4
    def init(self, tilecodes):
        self.sprites = []
        for tilecode in tilecodes:
            n = len(self.sprites)
            sp = HandTileSprite(tilecode, [self.disp_pos[0] + n * self.TILE_WIDTH, self.disp_pos[1]])
            self.sprites.append(sp)
    def sort(self):
        self.sprites.sort(key = lambda sp: sp.tilecode)
        for i in range(len(self.sprites)):
            self.sprites[i].rect.topleft = [self.disp_pos[0] + i * self.TILE_WIDTH, self.disp_pos[1]]
    def tsumoTile(self, tilecode):
        # 名字不用drawTile的原因是draw有画的意思 有歧义
        n = len(self.sprites)
        sp = HandTileSprite(tilecode, [self.disp_pos[0] + n * self.TILE_WIDTH + self.tsumoTileOffset, self.disp_pos[1]])
        self.sprites.append(sp)
    def removeTile(self, tilecode):
        for i in range(len(self.sprites)):
            if self.sprites[i].tilecode == tilecode:
                self.sprites.pop(i)
                return
    def setCanDiscard(self, canDiscard):
        for sp in self.sprites:
            sp.canDiscard = canDiscard
    def setEnabled(self, enabled, tilecode = -1):
        for sp in self.sprites:
            if tilecode == -1 or tilecode == sp.tilecode:
                sp.enabled = enabled
    def setEnabledByList(self, tilecodes):
        for sp in self.sprites:
            if sp.tilecode in tilecodes:
                sp.enabled = True
            else:
                sp.enabled = False
    def deselectAll(self):
        for sp in self.sprites:
            sp.deselect()
    def draw(self, surface):
        for sp in self.sprites:
            if sp.tilecode == -2:
                return
            num = utils.tilecodeToNum(sp.tilecode)
            if utils.isAka(sp.tilecode):
                num = 0
            suit = utils.tilecodeToSuit(sp.tilecode)
            surface.blit(self.img_mytiles, sp.rect.topleft, [self.TILE_WIDTH * num, self.TILE_HEIGHT * suit, self.TILE_WIDTH, self.TILE_HEIGHT])
            if not sp.enabled:
                surface.blit(self.black_surf, sp.rect.topleft)
            else:
                if sp.hover:
                    if sp.canDiscard:
                        # green
                        surface.blit(self.green_surf, sp.rect.topleft)
                    else:
                        #red
                        surface.blit(self.red_surf, sp.rect.topleft)

class RuleSelectionButtonSpriteGroup(ButtonSpriteGroup):
    def __init__(self):
        super().__init__()
        # self.add(SwitchButtonSprite(['人机', '真人'], 'human', [200, 400]))
        self.add(SwitchButtonSprite(['四麻', '三麻'], 'num_players', [112, 350]))
        self.add(SwitchButtonSprite(['人机', '茅屋', '丛林', '荒野', '龙脉'], 'level', [212, 350]))
        self.add(SwitchButtonSprite(['东风', '半庄'], 'length', [312, 350]))
        self.add(SwitchButtonSprite(['常速', '快速'], 'speed', [412, 350]))
        self.add(SwitchButtonSprite(['预约', '取消'], 'join', [650, 350]))
        self.add(TextButtonSprite('退出', 'exit', [900, 670]))
        self.getSpriteById('exit').visible = True
        
    def add(self, sprite):
        self.sprites.append(sprite)
    def draw(self, surface):
        for sp in self.sprites:
            if sp.visible:
                surface.blit(sp.image, sp.rect.topleft)
    def getSpriteById(self, id):
        # get sprite by id
        for sp in self.sprites:
            if sp.id == id:
                return sp
        return None
    def getRulecode(self):
        rule = 0
        for sp in self.sprites:
            if sp.id == 'human':
                if sp.choice == 1:
                    rule |= 1
            elif sp.id == 'num_players':
                if sp.choice == 1:
                    rule |= 0x10
            elif sp.id == 'level':
                level = sp.choice
                rule |= [0x0, 0x1, 0x81, 0x21, 0xa1][level]
            elif sp.id == 'length':
                if sp.choice == 1:
                    rule |= 0x08
            elif sp.id == 'speed':
                if sp.choice == 1:
                    rule |= 0x40
        return rule
    def setEnabled(self, enabled):
        for sp in self.sprites:
            if sp.id != 'join':
                sp.enabled = enabled
    


class DownloadHaifuThread(threading.Thread):
    def __init__(self, log, tw):
        super().__init__()
        self.log = log
        self.tw = tw
        self.failCount = 0
    def run(self):
        success = ClientGUI.downloadHaifu(self.log, self.tw, (self.failCount + 1) % 2)
        if success:
            logger.debug('download haifu success. Thread closing')
        else:
            self.failCount += 1
            logger.warning('download haifu failed. Retry downloading ' + ['xml text', 'gzip file'][(self.failCount + 1) % 2])
            if self.failCount <= 3:
                timer = threading.Timer(10, self.run)
                timer.start()
        


if __name__ == "__main__":
    setupLogging()
    pygame.init()
    pygame.freetype.init()
    clientGUI = ClientGUI()
    clientGUI.run()
    #clientGUI.run_test()
