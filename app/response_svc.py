import asyncio
import json
import uuid

from aiohttp_jinja2 import template

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
        available_agents = await self.get_available_agents(agent)
        if not available_agents:
            return
        total_facts = []
        total_links = []

        for blue_agent in available_agents:
            agent_facts, agent_links = await self.run_abilities_on_agent(blue_agent, pid)
            total_facts.extend(agent_facts)
            total_links.extend(agent_links)

        await self.save_to_operation(total_facts, total_links)

    async def get_available_agents(self, agent_to_match):
        await self.refresh_blue_agents_abilities()
        available_agents = [a for a in self.agents if a.host == agent_to_match.host]

        if not available_agents:
            self.log.debug('No available blue agents to respond to red action')
            return []

        return available_agents

    async def refresh_blue_agents_abilities(self):
        self.agents = await self.data_svc.locate('agents', match=dict(access=self.Access.BLUE))
        self.adversary = (await self.data_svc.locate('adversaries', match=dict(adversary_id=BLUE_ADVERSARY)))[0]

        self.abilities = []
        for a in self.adversary.atomic_ordering:
            if a not in self.abilities:
                self.abilities.append(a)

    async def run_abilities_on_agent(self, blue_agent, original_pid):
        facts = [Fact(trait='host.process.id', value=original_pid)]
        links = []
        for ability_id in self.abilities:
            ability_facts, ability_links = await self.run_ability_on_agent(blue_agent, ability_id, facts, original_pid)
            links.extend(ability_links)
            facts.extend(ability_facts)
        return facts, links

    async def run_ability_on_agent(self, blue_agent, ability_id, agent_facts, original_pid):
        links = await self.rest_svc.task_agent_with_ability(blue_agent.paw, ability_id, agent_facts)
        await self.wait_for_link_completion(links, blue_agent)
        ability_facts = []
        for link in links:
            link.pin = int(original_pid)
            unique_facts = link.facts[1:]
            ability_facts.extend(unique_facts)
        return ability_facts, links

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
        return Source(id=source_id, name=source_name, facts=facts)

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
