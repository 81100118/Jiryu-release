from copy import deepcopy

class AgariChecker:
    instance = None
    @classmethod
    def getInstance(cls):
        if AgariChecker.instance == None:
            AgariChecker.instance = AgariChecker()
        return AgariChecker.instance
    def __init__(self):
        self.agari_patterns = [set(), set(), {2}, {0o111, 3}, set(), \
                set(), set(), set(), set(), set(),\
                set(), set(), set(), set(), set()]
        self.gen_pattern()
    def gen_pattern(self):
        agari_patterns = self.agari_patterns
        for pa in agari_patterns[2]:
            for pb in agari_patterns[3]:
                combine_results = combine(pa, pb)
                for c in combine_results:
                    agari_patterns[5].add(c)
        
        for pa in agari_patterns[5]:
            for pb in agari_patterns[3]:
                combine_results = combine(pa, pb)
                for c in combine_results:
                    agari_patterns[8].add(c)
        
        for pa in agari_patterns[8]:
            for pb in agari_patterns[3]:
                combine_results = combine(pa, pb)
                for c in combine_results:
                    agari_patterns[11].add(c)
        
        for pa in agari_patterns[11]:
            for pb in agari_patterns[3]:
                combine_results = combine(pa, pb)
                for c in combine_results:
                    agari_patterns[14].add(c)
        
        for pa in agari_patterns[3]:
            for pb in agari_patterns[3]:
                combine_results = combine(pa, pb)
                for c in combine_results:
                    agari_patterns[6].add(c)
        
        for pa in agari_patterns[6]:
            for pb in agari_patterns[3]:
                combine_results = combine(pa, pb)
                for c in combine_results:
                    agari_patterns[9].add(c)
        
        for pa in agari_patterns[9]:
            for pb in agari_patterns[3]:
                combine_results = combine(pa, pb)
                for c in combine_results:
                    agari_patterns[12].add(c)
    def is_agari(self, hand_34):
        if hand_34[0] * hand_34[8] * hand_34[9] * hand_34[17] * hand_34[18] *\
                hand_34[26] * hand_34[27] * hand_34[28] * hand_34[29] * hand_34[30] *\
                hand_34[31] * hand_34[32] * hand_34[33] == 2:
            return True
        may_be_seven_pairs = True
        may_be_common = True
        p = 0
        num_tiles_in_chunk = 0
        num_tiles = 0
        head_count = 0
        length = len(hand_34)
        agari_patterns = self.agari_patterns
        for i in range(length):
            digit = hand_34[i]
            if digit == 0 or i == 9 or i == 18 or i >= 27:
                if p != 0:
                    remainder = num_tiles_in_chunk % 3
                    if remainder == 1:
                        may_be_common = False
                    else:
                        if remainder == 2:
                            head_count += 1
                        if p not in agari_patterns[num_tiles_in_chunk]:
                            may_be_common = False
                    p = 0
                    num_tiles_in_chunk = 0
            if digit != 0:
                if digit != 2:
                    may_be_seven_pairs = False
                p <<= 3
                p += digit
                num_tiles_in_chunk += digit
                num_tiles += digit
                if not (may_be_common and head_count <= 1) and not may_be_seven_pairs:
                    return False
        if p != 0:
            remainder = num_tiles_in_chunk % 3
            if remainder == 1:
                may_be_common = False
            else:
                if remainder == 2:
                    head_count += 1
                if p not in agari_patterns[num_tiles_in_chunk]:
                    may_be_common = False
        return (may_be_common and head_count == 1) or (may_be_seven_pairs and num_tiles == 14)

    def get_machi(self, hand_34):
        # hand_34 is an array of length 34 which sums to 3n+1
        # returns a list of 听的牌的34码
        result = []
        h = deepcopy(hand_34)
        for j in range(len(h)):
            if h[j] < 4:
                h[j] += 1
                if self.is_agari(h):
                    result.append(j)
                h[j] -= 1
        return result

    def get_tenpai_info(self, hand_34):
        # hand_34 is an array of length 34 which sums to 3n+2
        # returns a dictionary. {切的牌的34码 : [听的牌的34码], ...}
        h = deepcopy(hand_34)
        result = {}
        for i in range(len(h)):
            if h[i] > 0:
                h[i] -= 1
                for j in range(len(h)):
                    if h[j] < 4:
                        h[j] += 1
                        if self.is_agari(h):
                            if i in result:
                                result[i].append(j)
                            else:
                                result[i] = [j]
                        h[j] -= 1
                h[i] += 1
        return result


def num_to_list(n):
    result = []
    while n > 0:
        result.insert(0, n & 7)
        n >>= 3
    return result

def list_to_num(l):
    result = 0
    for digit in l:
        result <<= 3
        result += digit
    return result

def check_valid(p):
    if len(p) > 9:
        return False
    for i in p:
        if i > 4:
            return False
    return True

def combine(pa, pb):
    pa_list = num_to_list(pa)
    pb_list = num_to_list(pb)
    la = len(pa_list)
    lb = len(pb_list)
    pa_extended = [0] * lb + pa_list + [0] * lb
    results = []
    for i in range(la + lb + 1):
        p_combined_list = combine_helper(pa_extended, pb_list, i)
        if check_valid(p_combined_list):
            results.append(list_to_num(p_combined_list))
    return results

def combine_helper(audend, addend, pos):
    result = deepcopy(audend)
    for i in range(len(addend)):
        result[pos + i] += addend[i]
    return trim(result)

def trim(l):
    # remove prefix and postfix 0s
    # must contain at least one non-zero element
    begin = 0
    while l[begin] == 0:
        begin += 1
    end = -1
    while l[end] == 0:
        end -= 1
    if end == -1:
        return l[begin:]
    return l[begin:(end + 1)]
    
    
def agari_speed_test():
    print('my')
    ac = AgariChecker.getInstance()
    print(ac.is_agari([0,0,0,3,2,4,1,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]))
    print(ac.is_agari([4,4,4,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]))
    print(ac.is_agari([1,1,1,0,0,0,0,0,0,1,1,1,0,0,0,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,2,0,0]))
    print(ac.is_agari([1,0,0,0,0,0,0,0,1,1,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1]))
    for _ in range(1000000):
        a = ac.is_agari([0,0,0,3,2,4,1,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
        a = ac.is_agari([4,4,4,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
        a = ac.is_agari([1,1,1,0,0,0,0,0,0,1,1,1,0,0,0,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,2,0,0])
    print('lib')
    import mahjong.agari as ma
    agari = ma.Agari()
    print(agari.is_agari([0,0,0,3,2,4,1,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]))
    print(agari.is_agari([4,4,4,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]))
    print(agari.is_agari([1,1,1,0,0,0,0,0,0,1,1,1,0,0,0,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,2,0,0]))
    print(agari.is_agari([1,0,0,0,0,0,0,0,1,1,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1]))
    for _ in range(100000):
        a = agari.is_agari([0,0,0,3,2,4,1,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
        a = agari.is_agari([4,4,4,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
        a = agari.is_agari([1,1,1,0,0,0,0,0,0,1,1,1,0,0,0,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,2,0,0])
    print('end')    

if __name__ == "__main__":
    ac = AgariChecker.getInstance()
    print(ac.get_tenpai_info([0,0,0,3,2,4,1,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]))
    print(ac.get_tenpai_info([4,4,4,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]))
    print(ac.get_tenpai_info([1,1,1,0,0,0,0,0,0,1,1,1,0,0,0,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,2,0,0]))
    print(ac.get_tenpai_info([1,0,0,0,0,0,0,0,1,1,0,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1]))
    print(ac.get_tenpai_info([4,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]))
    print(ac.get_tenpai_info([4,1,1,1,1,1,1,1,3,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]))
    print(ac.get_tenpai_info([3,2,0,0,1,1,0,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]))
    for _ in range(3000):
        _ = ac.get_tenpai_info([4,1,1,1,1,1,1,1,3,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
