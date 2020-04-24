from aiohttp_jinja2 import template
import asyncio
import json
import uuid

from app.objects.secondclass.c_fact import Fact
from app.objects.c_operation import Operation
from app.objects.c_source import Source
from app.utility.base_service import BaseService


BLUE_ADVERSARY = 'f61e3fc0-43d8-4b36-b5d3-710610b92974'
BLUE_OP_NAME = 'Auto-Collect'


async def handle_link_completed(socket, path, services):
    data = json.loads(await socket.recv())
    paw = data['agent']['paw']
    data_svc = services.get('data_svc')

    agent = await data_svc.locate('agents', match=dict(paw=paw, access=data_svc.Access.RED))
    if agent:
        pid = data['pid']
        return await services.get('response_svc').respond_to_pid(pid, agent[0])


class ResponseService(BaseService):

    def __init__(self, services):
        self.log = self.add_service('response_svc', self)
        self.data_svc = services.get('data_svc')
        self.rest_svc = services.get('rest_svc')
        self.agents = []
        self.adversary = None
        self.abilities = []
        self.op = None

    @template('response.html')
    async def splash(self, request):
        abilities = [a for a in await self.data_svc.locate('abilities') if await a.which_plugin() == 'response']
        adversaries = [a for a in await self.data_svc.locate('adversaries') if await a.which_plugin() == 'response']
        return dict(abilities=abilities, adversaries=adversaries)

    @staticmethod
    async def register_handler(event_svc):
        await event_svc.observe_event('link/completed', handle_link_completed)

    async def respond_to_pid(self, pid, agent):
        await self.refresh_blue_agents_abilities()
        available_agents = [a for a in self.agents if a.host == agent.host]
        if not available_agents:
            self.log.debug('No available blue agents to respond to red action')
            return
        facts = [Fact(trait='host.process.id', value=pid)]
        total_links = []

        for blue_agent in available_agents:
            agent_facts = facts.copy()
            for ability_id in self.abilities:
                links = await self.rest_svc.task_agent_with_ability(blue_agent.paw, ability_id, agent_facts)
                await self.wait_for_link_completion(links, agent)
                for link in links:
                    unique_facts = link.facts[1:]
                    agent_facts.extend(unique_facts)
                total_links.extend(links)
            facts.extend(agent_facts)

        for l in total_links:
            l.pin = int(pid)

        await self.save_to_operation(facts, total_links)

    async def refresh_blue_agents_abilities(self):
        self.agents = await self.data_svc.locate('agents', match=dict(access=self.Access.BLUE))
        self.adversary = (await self.data_svc.locate('adversaries', match=dict(adversary_id=BLUE_ADVERSARY)))[0]

        self.abilities = []
        for a in self.adversary.atomic_ordering:
            if a.ability_id not in self.abilities:
                self.abilities.append(a.ability_id)

    @staticmethod
    async def wait_for_link_completion(links, agent):
        for link in links:
            while not link.finish or link.can_ignore():
                await asyncio.sleep(3)
                if not agent.trusted:
                    break

    async def create_fact_source(self, facts):
        source_id = str(uuid.uuid4())
        source_name = 'blue-pid-{}'.format(source_id)
        return Source(identifier=source_id, name=source_name, facts=facts)

    async def save_to_operation(self, facts, links):
        if not self.op or await self.op.is_finished():
            source = await self.create_fact_source(facts)
            await self.create_operation(links=links, source=source)
        else:
            await self.update_operation(links)
        await self.get_service('data_svc').store(self.op)

    async def create_operation(self, links, source):
        planner = (await self.get_service('data_svc').locate('planners', match=dict(name='sequential')))[0]
        await self.get_service('data_svc').store(source)
        self.op = Operation(name=BLUE_OP_NAME, agents=self.agents, adversary=self.adversary,
                            source=source, access=self.Access.BLUE, planner=planner, state='running',
                            auto_close=False, jitter='1/4')
        self.op.set_start_details()
        await self.update_operation(links)

    async def update_operation(self, links):
        for link in links:
            link.operation = self.op.id
            self.op.add_link(link)
