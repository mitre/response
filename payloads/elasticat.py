import argparse
import copy
import json
import os
import platform
import subprocess
import socket
import time
import traceback
from base64 import b64encode, b64decode

import requests


class OperationLoop:

    def __init__(self, server, es_host='http://127.0.0.1:9200', index_pattern='*',
                 result_size=10, group='blue', minutes_since=60):
        self.es_host = es_host
        self.index_pattern = index_pattern
        self.result_size = result_size
        self.minutes_since = minutes_since
        self._profile = dict(
            server=server,
            host=socket.gethostname(),
            platform=platform.system().lower(),
            executors=['elasticsearch'],
            pid=os.getpid(),
            group=group
        )

    def get_profile(self):
        return copy.copy(self._profile)

    @property
    def server(self):
        return self._profile['server']

    @property
    def paw(self):
        return self._profile.get('paw', 'unknown')

    def execute_lucene_query(self, lucene_query_string):
        query_string = 'event.created:[now-%im TO now] AND %s' % (self.minutes_since, lucene_query_string)
        body = dict(query=dict(query_string=dict(query=query_string)))
        resp = requests.post('%s/%s/_search' % (self.es_host, self.index_pattern),
                             params=dict(size=self.result_size),
                             json=body)
        resp.raise_for_status()
        return resp.json().get('hits', {}).get('hits', [])

    def start(self):
        while True:
            try:
                print('[*] Sending beacon for %s' % (self.paw,))
                beacon = self._send_beacon()
                sleep = self._handle_instructions(beacon)
                time.sleep(sleep)
            except Exception as e:
                print('[-] Operation loop error: %s' % e)
                traceback.print_exc()
                time.sleep(30)

    """ PRIVATE """

    def _handle_instructions(self, beacon):
        self._profile['paw'] = beacon['paw']
        for instruction in json.loads(beacon['instructions']):
            result, seconds = self._execute_instruction(json.loads(instruction))
            self._send_beacon(results=[result])
            time.sleep(seconds)
        else:
            self._send_beacon()
        return beacon['sleep']

    def _next_instructions(self, beacon):
        return json.loads(self._decode_bytes(beacon['instructions']))

    def _send_beacon(self, results=None):
        results = results if results else []
        beacon = self.get_profile()
        beacon['results'] = results
        body = self._encode_string(json.dumps(beacon))
        resp = requests.post('%s/beacon' % (self.server,), data=body)
        resp.raise_for_status()
        return json.loads(self._decode_bytes(resp.text))

    def _execute_instruction(self, i):
        print('[+] Running instruction: %s' % i['id'])
        query = self._decode_bytes(i['command'])
        results = self.execute_lucene_query(query)
        return dict(output=self._encode_string(json.dumps(results)), pid=os.getpid(), status=0, id=i['id']), i['sleep']

    @staticmethod
    def _decode_bytes(s):
        return b64decode(s).decode('utf-8', errors='ignore').replace('\n', '')

    @staticmethod
    def _encode_string(s):
        return str(b64encode(s.encode()), 'utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', default='http://127.0.0.1:8888', help='Base URL  Caldera server.')
    parser.add_argument('--es-host', default='http://127.0.0.1:9200', dest='es_host',
                        help='Base URL of ElasticSearch.')
    parser.add_argument('--index', default='*', help='ElasticSearch index pattern to search over.')
    parser.add_argument('--group', default='blue')
    parser.add_argument('--minutes-since', dest='minutes_since', default=60, type=int,
                        help='How many minutes back to search for events.')
    args = parser.parse_args()
    try:
        OperationLoop(args.server, es_host=args.es_host, index_pattern=args.index, group=args.group,
                      minutes_since=args.minutes_since).start()
    except Exception as e:
        print('[-] Caldera server not be accessible, or: %s' % e)
