#!/usr/bin/env python

from datetime import datetime
from elasticsearch import Elasticsearch
import json
import screepsapi
from settings import getSettings
import six
import time
import os
import services.screeps as screeps_service
import sys
from elasticsearch import helpers

MAXPAGES = 200
es_settings_dir = os.path.join(os.path.dirname(__file__), 'mappings')

class ScreepsMemoryStats():

    ELASTICSEARCH_HOST = 'elasticsearch' if 'ELASTICSEARCH' in os.environ else 'localhost'
    es = Elasticsearch([ELASTICSEARCH_HOST])

    def __init__(self, u=None, p=None, ptr=False, host=None, secure=True):
        self.user = u
        self.password = p
        self.ptr = ptr
        self.processed_ticks = {}

    def getScreepsAPI(self):
        if not self.__api:
            settings = getSettings()
            self.__api = screepsapi.API(u=settings['screeps_username'],p=settings['screeps_password'],ptr=settings['screeps_ptr'], host=settings["host"], secure=settings["secure"])
        return self.__api
    __api = False

    def run_forever(self):
        lastrun = False
        while True:
            api = self.getScreepsAPI()
            try:
                shard_data = api.shard_info()['shards']
                shards = [x['name'] for x in shard_data]
                if len(shards) < 1:
                    shards = ['shard0']
            except:
                shards = ['shard0']

            for shard in shards:
                self.collectMemoryStats(shard)

                # Market data changes much more rarely so process it less often.
                if not lastrun or lastrun >= 20:
                    self.collectMarketHistory(shard)
                    lastrun = 1
                    # don't pause before next run as market collection adds its own
                    # delays
                    continue

            lastrun += 1
            time.sleep(65)

    def collectMarketHistory(self, shard):
        screeps = self.getScreepsAPI()
        page = None
        failures = 0

        while True:

            market_history = screeps.market_history(page, shard)

            if 'list' not in market_history:
                return

            for item in market_history['list']:
                if '_id' not in item:
                    continue

                item['id'] = item['_id']
                item['shard'] = shard
                del item['_id']
                if item['type'] == 'market.fee':
                    if 'extendOrder' in item['market']:
                        item['addAmount'] = item['market']['extendOrder']['addAmount']
                    elif 'order' in item['market']:
                        item['orderType'] = item['market']['order']['type']
                        item['resourceType'] = item['market']['order']['resourceType']
                        item['price'] = item['market']['order']['price']
                        item['totalAmount'] = item['market']['order']['totalAmount']
                        if 'roomName' in item['market']['order']:
                            item['roomName'] = item['market']['order']['roomName']
                    else:
                        continue
                    if self.saveFee(item):
                        failures = 0
                    else:
                        failures += 1
                else:
                    item['resourceType'] = item['market']['resourceType']
                    item['price'] = item['market']['price']
                    item['totalAmount'] = item['market']['amount']
                    if 'roomName' in item['market']:
                        item['roomName'] = item['market']['roomName']

                    if 'targetRoomName' in item['market']:
                        item['targetRoomName'] = item['market']['targetRoomName']
                        user = screeps_service.getRoomOwner(item['targetRoomName'])
                        if user:
                            item['player'] = user
                            alliance = screeps_service.getAllianceFromUser(user)
                            if alliance:
                                item['alliance'] = alliance

                    if 'npc' in item['market']:
                        item['npc'] = item['market']['npc']
                    else:
                        item['npc'] = False

                    if self.saveOrder(item):
                        failures = 0
                    else:
                        failures += 1

            if failures >= 10:
                print('Too many already captured records')
                return

            if 'hasMore' not in market_history:
                print('hasMore not present')
                return

            if not market_history['hasMore']:
                print('hasMore is false')
                return

            page = int(market_history['page']) + 1
            if page >= MAXPAGES:
                return


    def saveFee(self, order):
        date_index = time.strftime("%Y_%m")
        indexname = 'screeps-market-fees_' + date_index

        if not self.es.indices.exists(indexname):
            with open('%s/fees.json' % (es_settings_dir,), 'r') as settings_file:
                settings=settings_file.read()
            self.es.indices.create(index=indexname, ignore=400, body=settings)

        order = self.clean(order)
        if self.es.exists(index=indexname, doc_type="fees", id=order['id']):
            return False
        else:
            order['timestamp'] = order['date']
            self.es.index(index=indexname,
                          doc_type="fees",
                          body=order)
            print("Saving order (fee) %s" % (order['id'],))
            return True

    def saveOrder(self, order):
        date_index = time.strftime("%Y_%m")
        indexname = 'screeps-market-orders_' + date_index
        if not self.es.indices.exists(indexname):
            with open('%s/orders.json' % (es_settings_dir,), 'r') as settings_file:
                settings=settings_file.read()
            self.es.indices.create(index=indexname, ignore=400, body=settings)

        order = self.clean(order)
        if self.es.exists(index=indexname, doc_type="orders", id=order['id']):
            return False
        else:
            order['timestamp'] = order['date']
            self.es.index(index=indexname,
                          doc_type="orders",
                          body=order)
            print("Saving order (deal) %s" % (order['id'],))
            return True


    def collectMemoryStats(self, shard):
        screeps = self.getScreepsAPI()
        stats = screeps.memory(path='___screeps_stats', shard=shard)
        if 'data' not in stats:
            return False

        if shard not in self.processed_ticks:
            self.processed_ticks[shard] = []

        # stats[tick][group][subgroup][data]
        # stats[4233][rooms][W43S94] = {}
        date_index = time.strftime("%Y_%m")
        confirm_queue =[]
        data_by_indices = {}
        for tick,tick_index in stats['data'].items():
            if int(tick) in self.processed_ticks[shard]:
                continue

            # Is tick_index a list of segments or the data itself?
            if isinstance(tick_index, list):
                rawstring = ''
                for segment_id in tick_index:
                    segment = screeps.get_segment(segment=int(segment_id))
                    if 'data' in segment and len(segment['data']) > 1:
                        rawstring = segment['data']
                    else:
                        # Segment may not be ready yet - try again next run.
                        return
                try:
                    tickstats = json.loads(rawstring)
                except:
                    continue
            else:
                tickstats = tick_index

            self.processed_ticks[shard].append(int(tick))
            if len(self.processed_ticks[shard]) > 100:
                self.processed_ticks[shard].pop(0)
            for group, groupstats in tickstats.items():
                indexname = 'screeps-stats-' + group + '_' + date_index
                docs = data_by_indices.get(indexname, [])
                if not isinstance(groupstats, dict):
                    continue

                if 'subgroups' in groupstats:
                    for subgroup, statdata in groupstats.items():
                        if subgroup == 'subgroups':
                            continue

                        statdata[group] = subgroup
                        savedata = self.clean(statdata)
                        savedata['tick'] = int(tick)
                        savedata['timestamp'] = tickstats['time']
                        savedata['shard'] = shard
                        docs.append({
                            "_index": indexname,
                            "_type": "stats",
                            "_source": savedata
                        })
                        #self.es.index(index=indexname, doc_type="stats", body=savedata)
                else:
                    savedata = self.clean(groupstats)
                    savedata['tick'] = int(tick)
                    savedata['timestamp'] = tickstats['time']
                    savedata['shard'] = shard
                    docs.append({
                        "_index": indexname,
                        "_type": "stats",
                        "_source": savedata
                    })
                    #self.es.index(index=indexname, doc_type="stats", body=savedata)
                data_by_indices[indexname] = docs
            for (indexname, docs) in data_by_indices.items():
                helpers.bulk(self.es, docs)
            confirm_queue.append(tick)

        self.confirm(confirm_queue, shard)

    def confirm(self, ticks, shard):
        javascript_clear = 'Stats.removeTick(' + json.dumps(ticks, separators=(',',':')) + ');'
        sconn = self.getScreepsAPI()
        sconn.console(javascript_clear, shard)

    def clean(self, datadict):
        newdict = {}
        for key, value in datadict.items():
            if key == 'tick':
                newdict[key] = int(value)
            else:
                try:
                    newdict[key] = float(value)
                except:
                    newdict[key] = value
        return datadict


if __name__ == "__main__":
    settings = getSettings()
    screepsconsole = ScreepsMemoryStats(u=settings['screeps_username'], p=settings['screeps_password'], ptr=settings['screeps_ptr'])
    screepsconsole.run_forever()
