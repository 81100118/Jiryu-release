import utils

def pon_tile_choices(hand, target, selected = [], akaari = True):
    # 返回所有可能用来碰的牌 list， 以及有几种碰法（选不选赤算不同碰法）
    # hand: 手牌，136格式; target: 副露目标牌 136格式; selected: 已经选了的牌 136格式
    # 例如手牌是305567m, 副露目标牌为5m, 则返回055m、两种; 若已经选了0m，则返回55m、一种
    target_num = utils.tilecodeToNum(target)
    target_suit = utils.tilecodeToSuit(target)
    for stile in selected:
        snum = utils.tilecodeToNum(stile)
        ssuit = utils.tilecodeToSuit(stile)
        if snum != target_num or ssuit != target_suit:
            return [], 0
    if len(selected) == 2:
        return [], 1
    # 接下来只需考虑手牌里至多1枚的情况
    result_tilecodes = [] # 与target相同的手牌的tilecode
    # 康康手牌里有哪些牌与target相同
    for tile in hand:
        if tile in selected:
            # a tile can not be selected twice
            continue
        num = utils.tilecodeToNum(tile)
        suit = utils.tilecodeToSuit(tile)
        if suit == target_suit and num == target_num:
            result_tilecodes.append(tile)
    if len(selected) + len(result_tilecodes) < 2:
        # 不足两枚 没法碰
        return [], 0
    elif len(selected) + len(result_tilecodes) == 2:
        # 刚好两枚 不管有没有赤 都只有一种碰法
        return result_tilecodes, 1
    else:
        # 大于等于3枚 如果手牌里有红有黑 则有两种碰法 否则1种
        black_exist = False
        red_exist = False
        for tile in result_tilecodes:
            if akaari and utils.isAka(tile):
                red_exist = True
            else:
                black_exist = True
        if black_exist and red_exist:
            return result_tilecodes, 2
        else:
            return result_tilecodes, 1


def chi_tile_choices(hand, target, selected = [], akaari = True):
    # 返回所有可能用来吃的牌 list， 以及有几种吃法（选不选赤算不同吃法）
    # hand: 手牌，136格式; target: 副露目标牌 136格式; selected: 已经选了的牌 136格式
    # 例如手牌是3567m, 副露目标牌为4m, 则返回356m、2种; 若已经选了3m，则返回5m、1种
    num_choices = 0
    target_num = utils.tilecodeToNum(target)
    target_suit = utils.tilecodeToSuit(target)
    if target_suit == 3:
        # 字牌不能吃
        return [], 0
    candidate_nums = [] # 手牌里有的、target附近的num
    result_nums = [] # 真正能用来吃的手牌的num
    result_tilecodes = [] # 真正能用来吃的手牌的tilecode
    black_five_exist = False
    red_five_exist = False
    for tile in hand:
        if tile in selected:
            # a tile can not be selected twice
            continue
        num = utils.tilecodeToNum(tile)
        suit = utils.tilecodeToSuit(tile)
        if suit == target_suit and (num - target_num in [-2, -1, 1, 2]):
            candidate_nums.append(num)
            if num == 5:
                if akaari and utils.isAka(tile):
                    red_five_exist = True
                else:
                    black_five_exist = True
    if len(selected) == 0:
        if target_num - 2 in candidate_nums and target_num - 1 in candidate_nums:
            num_choices += 1
            result_nums.append(target_num - 2)
            result_nums.append(target_num - 1)
            if black_five_exist and red_five_exist and (target_num - 2 == 5 or target_num - 1 == 5):
                # if both red and black five exist in hand, we can choose from the two types of fives.
                # so there is an additional choice.
                num_choices += 1
        if target_num - 1 in candidate_nums and target_num + 1 in candidate_nums:
            num_choices += 1
            result_nums.append(target_num - 1)
            result_nums.append(target_num + 1)
            if black_five_exist and red_five_exist and (target_num - 1 == 5 or target_num + 1 == 5):
                num_choices += 1
        if target_num + 1 in candidate_nums and target_num + 2 in candidate_nums:
            num_choices += 1
            result_nums.append(target_num + 1)
            result_nums.append(target_num + 2)
            if black_five_exist and red_five_exist and (target_num + 1 == 5 or target_num + 2 == 5):
                num_choices += 1
        for tile in hand:
            if tile in selected:
                # a tile can not be selected twice
                continue
            num = utils.tilecodeToNum(tile)
            suit = utils.tilecodeToSuit(tile)
            if suit == target_suit and num in result_nums:
                result_tilecodes.append(tile)
        return result_tilecodes, num_choices
    elif len(selected) == 1:
        for tile in hand:
            if tile in selected:
                continue
            if utils.is_shuntsu([selected[0], target, tile]):
                result_tilecodes.append(tile)
                num = utils.tilecodeToNum(tile)
                if num not in result_nums:
                    result_nums.append(num)
                    if black_five_exist and red_five_exist and num == 5:
                        num_choices += 2
                    else:
                        num_choices += 1
        return result_tilecodes, num_choices
    elif len(selected) == 2:
        if utils.is_shuntsu([selected[0], selected[1], target]):
            return [], 1
        else:
            return [], 0
    else:
        return [], 0
