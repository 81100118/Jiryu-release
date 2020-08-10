import pygame
from utils import *

pygame.init()

screen = pygame.display.set_mode([1024,600])
screen.fill([255,255,255])

jpgFileName = 'tiles.png'
imgRect = pygame.image.load(jpgFileName)
tilewidth = 75
tileheight = 113

def draw(hand):
    # hand is tilecode[13]
    xpos = 0
    ypos = 0
    for i in range(len(hand)):
        tile = hand[i]
        num = tilecodeToNum(tile)
        if isAka(tile):
            num = 0
        suit = tilecodeToSuit(tile)
        screen.blit(imgRect, [i * tilewidth, 0], [tilewidth * num, tileheight * suit, tilewidth, tileheight])


draw([0,1,4,6,22,33,34,52,68,99,100,123,126])

pygame.display.flip()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            pygame.quit()
