# -*- coding: utf-8 -*-
from urllib.parse import unquote

import re

class TenhouDecoder(object):
    RANKS = [
        u'雏鸡Ⅸ',
        u'雏鸡Ⅷ',
        u'雏鸡Ⅶ',
        u'雏鸡Ⅵ',
        u'雏鸡Ⅴ',
        u'雏鸡Ⅳ',
        u'雏鸡Ⅲ',
        u'雏鸡Ⅱ',
        u'雏鸡Ⅰ',
        u'狡狐Ⅳ',
        u'狡狐Ⅲ',
        u'狡狐Ⅱ',
        u'狡狐Ⅰ',
        u'迅犬Ⅲ',
        u'迅犬Ⅱ',
        u'迅犬Ⅰ',
        u'孤狼',
        u'猎豹',
        u'猛虎',
        u'巨象',
        u'地龙'
    ]

    def parse_hello_string(self, message):
        uname_string = ''
        rating_string = ''
        auth_message = ''
        new_rank_message = ''

        if 'auth=' in message:
            auth_message = self.get_attribute_content(message, 'auth')
            # for NoName we don't have rating attribute
            if 'PF4=' in message:
                rating_string = self.get_attribute_content(message, 'PF4')
            if 'uname=' in message:
                uname_string = unquote(self.get_attribute_content(message, 'uname'))

        if 'nintei' in message:
            new_rank_message = unquote(self.get_attribute_content(message, 'nintei'))

        return uname_string, auth_message, rating_string, new_rank_message

    def parse_initial_values(self, message):
        """
        Six element list:
            - Round number,
            - Number of honba sticks,
            - Number of riichi sticks,
            - First dice minus one,
            - Second dice minus one,
            - Dora indicator.
        """

        seed = self.get_attribute_content(message, 'seed').split(',')
        seed = [int(i) for i in seed]

        round_wind_number = seed[0]
        count_of_honba_sticks = seed[1]
        count_of_riichi_sticks = seed[2]
        dora_indicator = seed[5]
        dealer = int(self.get_attribute_content(message, 'oya'))

        scores = self.get_attribute_content(message, 'ten').split(',')
        scores = [int(i) for i in scores]

        return {
            'round_wind_number': round_wind_number,
            'count_of_honba_sticks': count_of_honba_sticks,
            'count_of_riichi_sticks': count_of_riichi_sticks,
            'dora_indicator': dora_indicator,
            'dealer': dealer,
            'scores': scores
        }

    def parse_initial_hand(self, message):
        tiles = self.get_attribute_content(message, 'hai')
        tiles = [int(i) for i in tiles.split(',')]
        return tiles

    def parse_final_scores_and_uma(self, message):
        data = self.get_attribute_content(message, 'owari')
        data = [float(i) for i in data.split(',')]

        # start at the beginning at take every second item (even)
        scores = data[::2]
        # start at second item and take every second item (odd)
        uma = data[1::2]

        return {'scores': scores, 'uma': uma}

    def parse_names_and_ranks(self, message):
        ranks = self.get_attribute_content(message, 'dan')
        ranks = [int(i) for i in ranks.split(',')]

        return [
            {'name': unquote(self.get_attribute_content(message, 'n0')), 'rank': TenhouDecoder.RANKS[ranks[0]]},
            {'name': unquote(self.get_attribute_content(message, 'n1')), 'rank': TenhouDecoder.RANKS[ranks[1]]},
            {'name': unquote(self.get_attribute_content(message, 'n2')), 'rank': TenhouDecoder.RANKS[ranks[2]]},
            {'name': unquote(self.get_attribute_content(message, 'n3')), 'rank': TenhouDecoder.RANKS[ranks[3]]},
        ]

    def parse_log_link(self, message):
        seat = int(self.get_attribute_content(message, 'oya'))
        seat = (4 - seat) % 4
        game_id = self.get_attribute_content(message, 'log')
        return game_id, seat

    def parse_tile(self, message):
        # tenhou format: <t23/>, <e23/>, <f23 t="4"/>, <f23/>, <g23/>
        result = re.match(r'^<[tefgEFGTUVWD]+\d*', message).group()
        return int(result[2:])

    def parse_dora_indicator(self, message):
        return int(self.get_attribute_content(message, 'hai'))

    def parse_who_called_riichi(self, message):
        return int(self.get_attribute_content(message, 'who'))

    def parse_go_tag(self, message):
        return int(self.get_attribute_content(message, 'type'))

    def generate_auth_token(self, auth_string):
        translation_table = [63006, 9570, 49216, 45888, 9822, 23121, 59830, 51114, 54831, 4189, 580, 5203, 42174, 59972,
                             55457, 59009, 59347, 64456, 8673, 52710, 49975, 2006, 62677, 3463, 17754, 5357]

        parts = auth_string.split('-')
        if len(parts) != 2:
            return False

        first_part = parts[0]
        second_part = parts[1]
        if len(first_part) != 8 or len(second_part) != 8:
            return False

        table_index = int('2' + first_part[2:8]) % (12 - int(first_part[7:8])) * 2

        a = translation_table[table_index] ^ int(second_part[0:4], 16)
        b = translation_table[table_index + 1] ^ int(second_part[4:8], 16)

        postfix = format(a, '2x') + format(b, '2x')

        result = first_part + '-' + postfix

        return result

    def get_attribute_content(self, message, attribute_name):
        result = re.findall(r'{}="([^"]*)"'.format(attribute_name), message)
        return result and result[0] or None

    def is_discarded_tile_message(self, message):
        if '<GO' in message:
            return False

        if '<FURITEN' in message:
            return False

        match_discard = re.match(r"^<[efgEFG]+\d*", message)
        if match_discard:
            return True

        return False

    def is_opened_set_message(self, message):
        return '<N who=' in message

    def get_enemy_seat(self, message):
        player_sign = message.lower()[1]
        if player_sign == 'e':
            player_seat = 1
        elif player_sign == 'f':
            player_seat = 2
        else:
            player_seat = 3

        return player_seat
