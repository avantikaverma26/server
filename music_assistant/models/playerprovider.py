#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import asyncio
from enum import Enum
from typing import List
from music_assistant.utils import run_periodic, LOGGER
from music_assistant.constants import CONF_ENABLED
from music_assistant.models.player_queue import PlayerQueue
from music_assistant.models.media_types import Track
from music_assistant.models.player import Player


class PlayerProvider():
    ''' 
        Model for a Playerprovider
        Common methods usable for every provider
        Provider specific methods should be overriden in the provider specific implementation
    '''

    def __init__(self, mass):
        """[DO NOT OVERRIDE]"""
        self.prov_id = ''
        self.name = ''
        self.mass = mass
        self.cache = mass.cache
        self.player_config_entries = []

    async def setup(self, conf):
        """[SHOULD OVERRIDE] Setup the provider"""
        return False

    ### Common methods and properties ####

    @property
    def players(self):
        ''' return all players for this provider '''
        return [item for item in self.mass.players.players if item.player_provider == self.prov_id]

    async def get_player(self, player_id:str):
        ''' return player by id '''
        return await self.mass.players.get_player(player_id)

    async def add_player(self, player:Player):
        ''' register a new player '''
        return await self.mass.players.add_player(player)

    async def remove_player(self, player_id:str):
        ''' remove a player '''
        return await self.mass.players.remove_player(player_id)

    ### Provider specific implementation #####





