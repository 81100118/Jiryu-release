# -*- coding: utf-8 -*-
import datetime
import logging
import random
import socket
from threading import Thread
from time import sleep
from urllib.parse import quote

from decoder import TenhouDecoder

from settings_handler import settings

logger = logging.getLogger('tenhou')


class TenhouClient:
    socket = None
    game_is_continue = True
    looking_for_game = True
    keep_alive_thread = None
    reconnected_messages = None

    decoder = TenhouDecoder()

    _count_of_empty_messages = 0
    _rating_string = None

    def __init__(self):
        pass

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((settings.TENHOU_HOST, settings.TENHOU_PORT))

    def authenticate(self, id='NoName'):
        # TODO 返回值现在很混乱 以后要统一成tcp报文中的用户信息class
        self._send_message('<HELO name="{}" tid="f0" sx="M" />'.format(quote(id)))
        messages = self._get_multiple_messages()
        auth_message = messages[0]

        if not auth_message:
            logger.info("Auth message wasn't received")
            return None

        # we reconnected to the game
        if '<GO' in auth_message:
            logger.info('Successfully reconnected')
            self.reconnected_messages = messages

            selected_game_type = self.decoder.parse_go_tag(auth_message)
            # self._set_game_rules(selected_game_type)

            values = self.decoder.parse_names_and_ranks(messages[1])
            # self.table.set_players_names_and_ranks(values)

            return True

        uname_string, auth_string, rating_string, new_rank_message = self.decoder.parse_hello_string(auth_message)
        self._rating_string = rating_string
        if not auth_string:
            logger.info("We didn't obtain auth string")
            return None

        logger.info('Rating string is: {}'.format(rating_string))

        if new_rank_message:
            logger.info('Achieved a new rank! \n {}'.format(new_rank_message))

        auth_token = self.decoder.generate_auth_token(auth_string)

        self._send_message('<AUTH val="{}"/>'.format(auth_token))
        self._send_message(self._pxr_tag())

        # sometimes tenhou send an empty tag after authentication (in tournament mode)
        # and bot thinks that he was not auth
        # to prevent it lets wait a little bit
        # and lets read a group of tags
        continue_reading = True
        counter = 0
        authenticated = False
        while continue_reading:
            messages = self._get_multiple_messages()
            for message in messages:
                if '<LN' in message:
                    authenticated = True
                    continue_reading = False

            counter += 1
            # to avoid infinity loop
            if counter > 10:
                continue_reading = False

        if authenticated:
            self._send_keep_alive_ping()
            logger.info('Successfully authenticated')
            return uname_string
        else:
            logger.info('Failed to authenticate')
            return None

    def end_game(self, success=True):
        self.game_is_continue = False
        if success:
            self._send_message('<BYE />')

        if self.keep_alive_thread:
            self.keep_alive_thread.join()

        try:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
        except OSError:
            pass

        if success:
            logger.info('End of the game')
        else:
            logger.error('Game was ended without success')

    def _send_message(self, message):
        # tenhou requires an empty byte in the end of each sending message
        logger.debug('Send: {}'.format(message))
        message += '\0'
        self.socket.sendall(message.encode())

    def _read_message(self):
        message = self.socket.recv(2048)
        logger.debug('Get: {}'.format(message.decode('utf-8').replace('\x00', ' ')))
        return message.decode('utf-8')

    def _get_multiple_messages(self):
        # tenhou can send multiple messages in one request
        messages = self._read_message()
        messages = messages.split('\x00')
        # last message always is empty after split, so let's exclude it
        messages = messages[0:-1]

        return messages

    def _send_keep_alive_ping(self):
        def send_request():
            while self.game_is_continue:
                self._send_message('<Z />')

                # we can't use sleep(15), because we want to be able
                # end thread in the middle of running
                seconds_to_sleep = 15
                for _ in range(0, seconds_to_sleep * 2):
                    if self.game_is_continue:
                        sleep(0.5)

        self.keep_alive_thread = Thread(target=send_request)
        self.keep_alive_thread.start()

    def _pxr_tag(self):
        # I have no idea why we need to send it, but better to do it
        if settings.IS_TOURNAMENT:
            return '<PXR V="-1" />'

        if settings.USER_ID == 'NoName':
            return '<PXR V="1" />'
        else:
            return '<PXR V="9" />'

    def _build_game_type(self):
        # usual case, we specified game type to play
        if settings.GAME_TYPE is not None:
            return settings.GAME_TYPE

        # kyu lobby, hanchan ari-ari
        default_game_type = '9'

        if settings.LOBBY != '0':
            logger.error("We can't use dynamic game type and custom lobby. Default game type was set")
            return default_game_type

        if not self._rating_string:
            logger.error("For NoName dynamic game type is not available. Default game type was set")
            return default_game_type

        temp = self._rating_string.split(',')
        dan = int(temp[0])
        rate = float(temp[2])
        logger.info('Player has {} rank and {} rate'.format(TenhouDecoder.RANKS[dan], rate))

        game_type = default_game_type
        # dan lobby, we can play here from 1 kyu
        if dan >= 9:
            game_type = '137'

        # upperdan lobby, we can play here from 4 dan and with 1800+ rate
        if dan >= 13 and rate >= 1800:
            game_type = '41'

        # phoenix lobby, we can play here from 7 dan and with 2000+ rate
        if dan >= 16 and rate >= 2000:
            game_type = '169'

        return game_type
