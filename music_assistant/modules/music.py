#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import asyncio
import os
from utils import run_periodic, run_async_background_task, LOGGER, try_parse_int, try_supported
import aiohttp
from difflib import SequenceMatcher as Matcher
from models import MediaType, Track, Artist, Album, Playlist, Radio
from typing import List
import toolz
import operator


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODULES_PATH = os.path.join(BASE_DIR, "musicproviders" )

class Music():
    ''' several helpers around the musicproviders '''
    
    def __init__(self, mass):
        self.sync_running = False
        self.mass = mass
        self.providers = {}
        # dynamically load musicprovider modules
        self.load_music_providers()
        # schedule sync task
        mass.event_loop.create_task(self.sync_music_providers())

    async def item(self, item_id, media_type:MediaType, provider='database', lazy=True):
        ''' get single music item by id and media type'''
        if media_type == MediaType.Artist:
            return await self.artist(item_id, provider, lazy=lazy)
        elif media_type == MediaType.Album:
            return await self.album(item_id, provider, lazy=lazy)
        elif media_type == MediaType.Track:
            return await self.track(item_id, provider, lazy=lazy)
        elif media_type == MediaType.Playlist:
            return await self.playlist(item_id, provider)
        elif media_type == MediaType.Radio:
            return await self.radio(item_id, provider)
        else:
            return None

    async def library_artists(self, limit=0, offset=0, orderby='name', provider_filter=None) -> List[Artist]:
        ''' return all library artists, optionally filtered by provider '''
        return await self.mass.db.library_artists(provider=provider_filter, limit=limit, offset=offset, orderby=orderby)

    async def library_albums(self, limit=0, offset=0, orderby='name', provider_filter=None) -> List[Album]:
        ''' return all library albums, optionally filtered by provider '''
        return await self.mass.db.library_albums(provider=provider_filter, limit=limit, offset=offset, orderby=orderby)

    async def library_tracks(self, limit=0, offset=0, orderby='name', provider_filter=None) -> List[Track]:
        ''' return all library tracks, optionally filtered by provider '''
        return await self.mass.db.library_tracks(provider=provider_filter, limit=limit, offset=offset, orderby=orderby)

    async def playlists(self, limit=0, offset=0, orderby='name', provider_filter=None) -> List[Playlist]:
        ''' return all library playlists, optionally filtered by provider '''
        return await self.mass.db.playlists(provider=provider_filter, limit=limit, offset=offset, orderby=orderby)

    async def radios(self, limit=0, offset=0, orderby='name', provider_filter=None) -> List[Playlist]:
        ''' return all library radios, optionally filtered by provider '''
        return await self.mass.db.radios(provider=provider_filter, limit=limit, offset=offset, orderby=orderby)

    async def library_items(self, media_type:MediaType, limit=0, offset=0, orderby='name', provider_filter=None) -> List[object]:
        ''' get multiple music items in library'''
        if media_type == MediaType.Artist:
            return await self.library_artists(limit=limit, offset=offset, orderby=orderby, provider_filter=provider_filter)
        elif media_type == MediaType.Album:
            return await self.library_albums(limit=limit, offset=offset, orderby=orderby, provider_filter=provider_filter)
        elif media_type == MediaType.Track:
            return await self.library_tracks(limit=limit, offset=offset, orderby=orderby, provider_filter=provider_filter)
        elif media_type == MediaType.Playlist:
            return await self.playlists(limit=limit, offset=offset, orderby=orderby, provider_filter=provider_filter)
        elif media_type == MediaType.Radio:
            return await self.radios(limit=limit, offset=offset, orderby=orderby, provider_filter=provider_filter)

    async def artist(self, item_id, provider='database', lazy=True) -> Artist:
        ''' get artist by id '''
        if not provider or provider == 'database':
            return await self.mass.db.artist(item_id)
        return await self.providers[provider].artist(item_id, lazy=lazy)

    async def album(self, item_id, provider='database', lazy=True) -> Album:
        ''' get album by id '''
        if not provider or provider == 'database':
            return await self.mass.db.album(item_id)
        return await self.providers[provider].album(item_id, lazy=lazy)

    async def track(self, item_id, provider='database', lazy=True) -> Track:
        ''' get track by id '''
        if not provider or provider == 'database':
            return await self.mass.db.track(item_id)
        return await self.providers[provider].track(item_id, lazy=lazy)

    async def playlist(self, item_id, provider='database') -> Playlist:
        ''' get playlist by id '''
        if not provider or provider == 'database':
            return await self.mass.db.playlist(item_id)
        return await self.providers[provider].playlist(item_id)

    async def radio(self, item_id, provider='database') -> Radio:
        ''' get radio by id '''
        if not provider or provider == 'database':
            return await self.mass.db.radio(item_id)
        return await self.providers[provider].radio(item_id)

    async def playlist_by_name(self, name) -> Playlist:
        ''' get playlist by name '''
        for playlist in await self.playlists():
            if playlist.name == name:
                return playlist
        return None

    async def radio_by_name(self, name) -> Radio:
        ''' get radio by name '''
        for radio in await self.radios():
            if radio.name == name:
                return radio
        return None
    
    async def artist_toptracks(self, artist_id, provider='database') -> List[Track]:
        ''' get top tracks for given artist '''
        artist = await self.artist(artist_id, provider)
        # always append database tracks
        items = await self.mass.db.artist_tracks(artist.item_id)
        for prov_mapping in artist.provider_ids:
            prov_id = prov_mapping['provider']
            prov_item_id = prov_mapping['item_id']
            prov_obj = self.providers[prov_id]
            items += await prov_obj.artist_toptracks(prov_item_id)
        items = list(toolz.unique(items, key=operator.attrgetter('item_id')))
        items.sort(key=lambda x: x.name, reverse=False)
        return items

    async def artist_albums(self, artist_id, provider='database') -> List[Album]:
        ''' get (all) albums for given artist '''
        artist = await self.artist(artist_id, provider)
        # always append database tracks
        items = await self.mass.db.artist_albums(artist.item_id)
        for prov_mapping in artist.provider_ids:
            prov_id = prov_mapping['provider']
            prov_item_id = prov_mapping['item_id']
            prov_obj = self.providers[prov_id]
            items += await prov_obj.artist_albums(prov_item_id)
        items = list(toolz.unique(items, key=operator.attrgetter('item_id')))
        items.sort(key=lambda x: x.name, reverse=False)
        return items

    async def album_tracks(self, album_id, provider='database') -> List[Track]:
        ''' get the album tracks for given album '''
        items = []
        album = await self.album(album_id, provider)
        for prov_mapping in album.provider_ids:
            prov_id = prov_mapping['provider']
            prov_item_id = prov_mapping['item_id']
            prov_obj = self.providers[prov_id]
            items += await prov_obj.album_tracks(prov_item_id)
        items = list(toolz.unique(items, key=operator.attrgetter('item_id')))
        items = sorted(items, key=operator.attrgetter('disc_number'), reverse=False)
        items = sorted(items, key=operator.attrgetter('track_number'), reverse=False)
        return items

    async def playlist_tracks(self, playlist_id, provider='database', offset=0, limit=50) -> List[Track]:
        ''' get the tracks for given playlist '''
        playlist = None
        if not provider or provider == 'database':
            playlist = await self.mass.db.playlist(playlist_id)
        if playlist and playlist.is_editable:
            # database synced playlist, return tracks from db...
            return await self.mass.db.playlist_tracks(
                    playlist.item_id, offset=offset, limit=limit)
        else:
            # return playlist tracks from provider
            playlist = await self.playlist(playlist_id, provider)
            prov = playlist.provider_ids[0]
            return await self.providers[prov['provider']].playlist_tracks(
                    prov['item_id'], offset=offset, limit=limit)

    async def search(self, searchquery, media_types:List[MediaType], limit=10, online=False) -> dict:
        ''' search database or providers '''
        # get results from database
        result = await self.mass.db.search(searchquery, media_types, limit)
        if online:
            # include results from music providers
            for prov in self.providers.values():
                prov_results = await prov.search(searchquery, media_types, limit)
                for item_type, items in prov_results.items():
                    result[item_type] += items
            # filter out duplicates
            for item_type, items in result.items():
                items = list(toolz.unique(items, key=operator.attrgetter('item_id')))
        return result

    async def item_action(self, item_id, media_type, provider='database', action=None):
        ''' perform action on item (such as library add/remove) '''
        result = None
        item = await self.item(item_id, media_type, provider)
        if item and action in ['add', 'remove']:
            # remove or add item to the library
            for prov_mapping in result.provider_ids:
                prov_id = prov_mapping['provider']
                prov_item_id = prov_mapping['item_id']
                for prov in self.providers.values():
                    if prov.prov_id == prov_id:
                        if action == 'add':
                            result = await prov.add_library(prov_item_id, media_type)
                        elif action == 'remove':
                            result = await prov.remove_library(prov_item_id, media_type)
        return result
    
    async def add_playlist_tracks(self, playlist_id, tracks:List[Track]):
        ''' add tracks to playlist - make sure we dont add dupes '''
        # we can only edit playlists that are in the database (marked as editable)
        playlist = await self.playlist(playlist_id, 'database')
        if not playlist or not playlist.is_editable:
            LOGGER.warning("Playlist %s is not editable - skip addition of tracks" %(playlist.name))
            return False
        playlist_prov = playlist.provider_ids[0] # playlist can only have one provider (for now)
        cur_playlist_tracks = await self.mass.db.playlist_tracks(playlist_id, limit=0)
        # grab all (database) track ids in the playlist so we can check for duplicates
        cur_playlist_track_ids = [item.item_id for item in cur_playlist_tracks]
        track_ids_to_add = []
        for track in tracks:
            if not track.provider == 'database':
                # make sure we have a database track
                track = await self.track(track.item_id, track.provider, lazy=False)
            if track.item_id in cur_playlist_track_ids:
                LOGGER.warning("Track %s already in playlist %s - skip addition" %(track.name, playlist.name))
                continue
            # we can only add a track to a provider playlist if the track is available on that provider
            # exception is the file provider which does accept tracks from all providers in the m3u playlist
            # this should all be handled in the frontend but these checks are here just to be safe
            track_playlist_provs = [item['provider'] for item in track.provider_ids]
            if playlist_prov['provider'] in track_playlist_provs:
                # a track can contain multiple versions on the same provider
                # # simply sort by quality and just add the first one (assuming the track is still available)
                track_versions = sorted(track.provider_ids, key=operator.itemgetter('quality'), reverse=True)
                for track_version in track_versions:
                    if track_version['provider'] == playlist_prov['provider']:
                        track_ids_to_add.append(track_version['item_id'])
                        break
            elif playlist_prov['provider'] == 'file':
                # the file provider can handle uri's from all providers in the file so simply add the db id
                track_ids_to_add.append(track.item_id)
            else:
                LOGGER.warning("Track %s not available on provider %s - skip addition to playlist %s" %(track.name, playlist_prov['provider'], playlist.name))
                continue
        # actually add the tracks to the playlist on the provider
        await self.providers[playlist_prov['provider']].add_playlist_tracks(playlist_prov['item_id'], track_ids_to_add)
        # schedule sync
        self.mass.event_loop.create_task(self.sync_playlist_tracks(playlist.item_id, playlist_prov['provider'], playlist_prov['item_id']))

    @run_periodic(3600)
    async def sync_music_providers(self):
        ''' periodic sync of all music providers '''
        if self.sync_running:
            return
        self.sync_running = True
        for prov_id in self.providers.keys():
            # sync library artists
            await try_supported(self.sync_library_artists(prov_id))
            await try_supported(self.sync_library_albums(prov_id))
            await try_supported(self.sync_library_tracks(prov_id))
            await try_supported(self.sync_playlists(prov_id))
            await try_supported(self.sync_radios(prov_id))
        self.sync_running = False
        
    async def sync_library_artists(self, prov_id):
        ''' sync library artists for given provider'''
        music_provider = self.providers[prov_id]
        prev_items = await self.library_artists(provider_filter=prov_id)
        prev_db_ids = [item.item_id for item in prev_items]
        cur_items = await music_provider.get_library_artists()
        cur_db_ids = []
        for item in cur_items:
            db_item = await music_provider.artist(item.item_id, lazy=False)
            cur_db_ids.append(db_item.item_id)
            if not db_item.item_id in prev_db_ids:
                await self.mass.db.add_to_library(db_item.item_id, MediaType.Artist, prov_id)
        # process deletions
        for db_id in prev_db_ids:
            if db_id not in cur_db_ids:
                await self.mass.db.remove_from_library(db_id, MediaType.Artist, prov_id)
        LOGGER.info("Finished syncing Artists for provider %s" % prov_id)

    async def sync_library_albums(self, prov_id):
        ''' sync library albums for given provider'''
        music_provider = self.providers[prov_id]
        prev_items = await self.library_albums(provider_filter=prov_id)
        prev_db_ids = [item.item_id for item in prev_items]
        cur_items = await music_provider.get_library_albums()
        cur_db_ids = []
        for item in cur_items:
            db_item = await music_provider.album(item.item_id, lazy=False)
            cur_db_ids.append(db_item.item_id)
            # precache album tracks...
            for album_track in await music_provider.get_album_tracks(item.item_id):
                await music_provider.track(album_track.item_id)
            if not db_item.item_id in prev_db_ids:
                await self.mass.db.add_to_library(db_item.item_id, MediaType.Album, prov_id)
        # process deletions
        for db_id in prev_db_ids:
            if db_id not in cur_db_ids:
                await self.mass.db.remove_from_library(db_id, MediaType.Album, prov_id)
        LOGGER.info("Finished syncing Albums for provider %s" % prov_id)

    async def sync_library_tracks(self, prov_id):
        ''' sync library tracks for given provider'''
        music_provider = self.providers[prov_id]
        prev_items = await self.library_tracks(provider_filter=prov_id)
        prev_db_ids = [item.item_id for item in prev_items]
        cur_items = await music_provider.get_library_tracks()
        cur_db_ids = []
        for item in cur_items:
            db_item = await music_provider.track(item.item_id, lazy=False)
            cur_db_ids.append(db_item.item_id)
            if not db_item.item_id in prev_db_ids:
                await self.mass.db.add_to_library(db_item.item_id, MediaType.Track, prov_id)
        # process deletions
        for db_id in prev_db_ids:
            if db_id not in cur_db_ids:
                await self.mass.db.remove_from_library(db_id, MediaType.Track, prov_id)
        LOGGER.info("Finished syncing Tracks for provider %s" % prov_id)

    async def sync_playlists(self, prov_id):
        ''' sync library playlists for given provider'''
        music_provider = self.providers[prov_id]
        prev_items = await self.playlists(provider_filter=prov_id)
        prev_db_ids = [item.item_id for item in prev_items]
        cur_items = await music_provider.get_playlists()
        cur_db_ids = []
        for item in cur_items:
            # always add to db because playlist attributes could have changed
            db_id = await self.mass.db.add_playlist(item)
            cur_db_ids.append(db_id)
            if not db_id in prev_db_ids:
                await self.mass.db.add_to_library(db_id, MediaType.Playlist, prov_id)
            if item.is_editable:
                # precache/sync playlist tracks (user owned playlists only)
                asyncio.create_task( self.sync_playlist_tracks(db_id, prov_id, item.item_id) )
        # process playlist deletions
        for db_id in prev_db_ids:
            if db_id not in cur_db_ids:
                await self.mass.db.remove_from_library(db_id, MediaType.Playlist, prov_id)
        LOGGER.info("Finished syncing Playlists for provider %s" % prov_id)

    async def sync_playlist_tracks(self, db_playlist_id, prov_id, prov_playlist_id):
        ''' sync library playlists tracks for given provider'''
        music_provider = self.providers[prov_id]
        prev_items = await self.playlist_tracks(db_playlist_id)
        prev_db_ids = [item.item_id for item in prev_items]
        cur_items = await music_provider.get_playlist_tracks(prov_playlist_id, limit=0)
        cur_db_ids = []
        pos = 0
        for item in cur_items:
            # we need to do this the complicated way because the file provider can return tracks from other providers
            for prov_mapping in item.provider_ids:
                item_provider = prov_mapping['provider']
                prov_item_id = prov_mapping['item_id']
                db_item = await self.providers[item_provider].track(prov_item_id, lazy=False)
                cur_db_ids.append(db_item.item_id)
                if not db_item.item_id in prev_db_ids:
                    await self.mass.db.add_playlist_track(db_playlist_id, db_item.item_id, pos)
            pos += 1
        # process playlist track deletions
        for db_id in prev_db_ids:
            if db_id not in cur_db_ids:
                await self.mass.db.remove_playlist_track(db_playlist_id, db_id)
        LOGGER.info("Finished syncing Playlist %s tracks for provider %s" % (prov_playlist_id, prov_id))

    async def sync_radios(self, prov_id):
        ''' sync library radios for given provider'''
        music_provider = self.providers[prov_id]
        prev_items = await self.radios(provider_filter=prov_id)
        prev_db_ids = [item.item_id for item in prev_items]
        cur_items = await music_provider.get_radios()
        cur_db_ids = []
        for item in cur_items:
            db_id = await self.mass.db.get_database_id(prov_id, item.item_id, MediaType.Radio)
            if not db_id:
                db_id = await self.mass.db.add_radio(item)
            cur_db_ids.append(db_id)
            if not db_id in prev_db_ids:
                await self.mass.db.add_to_library(db_id, MediaType.Radio, prov_id)
        # process deletions
        for db_id in prev_db_ids:
            if db_id not in cur_db_ids:
                await self.mass.db.remove_from_library(db_id, MediaType.Radio, prov_id)
        LOGGER.info("Finished syncing Radios for provider %s" % prov_id)

    def load_music_providers(self):
        ''' dynamically load musicproviders '''
        for item in os.listdir(MODULES_PATH):
            if (os.path.isfile(os.path.join(MODULES_PATH, item)) and not item.startswith("_") and 
                    item.endswith('.py') and not item.startswith('.')):
                module_name = item.replace(".py","")
                LOGGER.debug("Loading musicprovider module %s" % module_name)
                try:
                    mod = __import__("modules.musicproviders." + module_name, fromlist=[''])
                    if not self.mass.config['musicproviders'].get(module_name):
                        self.mass.config['musicproviders'][module_name] = {}
                    self.mass.config['musicproviders'][module_name]['__desc__'] = mod.config_entries()
                    for key, def_value, desc in mod.config_entries():
                        if not key in self.mass.config['musicproviders'][module_name]:
                            self.mass.config['musicproviders'][module_name][key] = def_value
                    mod = mod.setup(self.mass)
                    if mod:
                        self.providers[mod.prov_id] = mod
                        cls_name = mod.__class__.__name__
                        LOGGER.info("Successfully initialized module %s" % cls_name)
                except Exception as exc:
                    LOGGER.exception("Error loading module %s: %s" %(module_name, exc))
