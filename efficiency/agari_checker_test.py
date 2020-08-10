import mahjong.agari
import agari_checker
import random

ag = mahjong.agari.Agari()
ac = agari_checker.AgariChecker.getInstance()

def gen_random_hand(type = 0):
    hand = [0] * 34
    if type == 0:
        lower = 0
        upper = 33
    elif type == 1:
        lower = 18
        upper = 33
    else:
        lower = 9
        upper = 17
    for _ in range(14):
        rand = random.randint(lower, upper)
        while hand[rand] == 4:
            rand = random.randint(lower, upper)
        hand[rand] += 1
    return hand

agari_count = 0
fail_count = 0
for i in range(100000):
    if i < 30000:
        hand = gen_random_hand(0)
    elif i < 70000:
        hand = gen_random_hand(1)
    else:
        hand = gen_random_hand(2)
    my_judgment = ac.is_agari(hand)
    lib_judgment = ag.is_agari(hand)
    if my_judgment != lib_judgment:
        print(hand)
        print(my_judgment)
        print(lib_judgment)
        fail_count += 1
    if lib_judgment:
        agari_count += 1
print('agari count', agari_count)
print('fail count', fail_count)
