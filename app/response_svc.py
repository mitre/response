from aiohttp_jinja2 import template
from aiohttp import web

from app.utility.base_service import BaseService
from app.objects.secondclass.c_fact import Fact


class ResponseService(BaseService):

    detection_traits = ['host.pid.unauthorized', 'file.malicious.hash', 'host.malicious.path']

    def __init__(self, services):
        self.log = self.add_service('response_svc', self)
        self.data_svc = services.get('data_svc')

    @staticmethod
    async def get_hosts(operation):
        hosts = []
        for agent in operation.agents:
            if agent.host not in hosts:
                hosts.append(agent.host)
        return web.Response(body=hosts)

    async def update_status(self, operation):
        hosts = {}
        lateral_mov = False
        for link in operation.chain:
            if link.relationships:
                if link.host not in hosts:
                    hosts[link.host] = []
                if link.tactic is 'detection':
                    for rel in link.relationships:
                        hosts[link.host].append(rel)
                        lateral_mov = self.is_lateral_mov(hosts, link.host, rel) if lateral_mov else lateral_mov
                else:
                    if not link.status:
                        for uf in link.used:
                            for rel in hosts[link.host]:
                                for node in [rel.source, rel.target]:
                                    if node[0] in self.__class__.detection_traits and uf.trait == node[0] and uf.value == node[1]:
                                        rel.score = 0
                        for rel in [rels for rels in link.relationships if not link.status]:
                            rel.score = 0
                            hosts[link.host].append(rel)
                            lateral_mov = self.is_lateral_mov(hosts, link.host, rel) if not lateral_mov else lateral_mov
        host_status = {}
        for host in hosts:
            status = 0
            for rel in hosts[host]:
                if rel.score != 0:
                    status = 1
            host_status[host] = status
        return {'lateral_mov' : lateral_mov, 'host_status' : host_status}

    async def is_lateral_mov(self, hosts, link_host, new_rel):
        for h in [host for host in hosts if host != link_host]:
            for existing_rel in hosts[h]:
                if new_rel.source == existing_rel.source or new_rel.target == existing_rel.target:
                    return True
        return False
