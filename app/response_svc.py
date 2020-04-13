from aiohttp_jinja2 import template
import uuid

from app.objects.secondclass.c_fact import Fact
from app.objects.c_operation import Operation
from app.objects.c_source import Source
from app.utility.base_service import BaseService
from app.utility.event import Observer


BLUE_GROUP = 'blue'
BLUE_ADVERSARY = 'f61e3fc0-43d8-4b36-b5d3-710610b92974'
BLUE_OP_NAME = 'Auto-Collect'


class LinkCompletedObserver(Observer):

    def __init__(self, response_svc):
        Observer.__init__(self, 'link', 'completed')
        self.response_svc = response_svc

    async def handle(self, agent, pid):
        if agent.group == BLUE_GROUP:
            return
        await self.response_svc.respond_to_pid(pid, agent)


class ResponseService(BaseService):

    def __init__(self, services):
        self.log = self.add_service('response_svc', self)
        self.data_svc = services.get('data_svc')
        self.rest_svc = services.get('rest_svc')
        self.agents = []
        self.adversary = None
        self.abilities = []

        self.op = None
        LinkCompletedObserver.register(self)

    @template('response.html')
    async def splash(self, request):
        abilities = [a for a in await self.data_svc.locate('abilities') if await a.which_plugin() == 'response']
        adversaries = [a for a in await self.data_svc.locate('adversaries') if await a.which_plugin() == 'response']
        return dict(abilities=abilities, adversaries=adversaries)

    async def respond_to_pid(self, pid, agent):
        self.log.info(f"responding to pid: {pid} and agent: {agent}")
        await self.refresh_blue_agents_abilities()
        available_agents = [a for a in self.agents if a.host == agent.host]
        if not available_agents:
            self.log.info('No available blue agents to respond to red action')
            return
        facts = [Fact(trait='host.process.id', value=pid)]
        total_links = []

        for blue_agent in available_agents:
            for ability_id in self.abilities:
                self.log.info(f"tasking blue agent with ability {blue_agent.paw} ability_id: {ability_id}, pid {pid}")
                links = await self.rest_svc.task_agent_with_ability(blue_agent.paw, ability_id, facts)
                for link in links:
                    facts.extend(link.facts)
                total_links.extend(links)

        for l in total_links:
            l.pin = int(pid)

        if not self.op:
            source = await self.create_fact_source(facts)
            await self.create_operation(links=total_links, source=source)
            self.log.info('blue op created')
        else:
            await self.update_operation(total_links)
            self.log.info('blue op updated')

    async def refresh_blue_agents_abilities(self):
        self.agents = [agent for agent in await self.data_svc.locate('agents', match=dict(group='blue'))
                       if agent.group == 'blue']

        self.adversary = (await self.data_svc.locate('adversaries', match=dict(adversary_id=BLUE_ADVERSARY)))[0]

        self.abilities = []
        for a in self.adversary.atomic_ordering:
            if a.ability_id not in self.abilities:
                self.abilities.append(a.ability_id)

    async def create_fact_source(self, facts):
        source_id = str(uuid.uuid4())
        source_name = 'blue-pid-{}'.format(source_id)
        return Source(identifier=source_id, name=source_name, facts=facts)

    async def create_operation(self, links, source):
        planner = (await self.get_service('data_svc').locate('planners', match=dict(name='sequential')))[0]
        await self.get_service('data_svc').store(source)
        self.op = Operation(name=BLUE_OP_NAME, agents=self.agents, adversary=self.adversary,
                            source=source, access=self.Access.BLUE, planner=planner, state='running',
                            auto_close=False, jitter='1/4')
        self.op.set_start_details()
        self.log.info(f"Response Operation {self.op.id}:{self.op.name} Started")

    async def update_operation(self, links):
        for link in links:
            self.op.add_link(link)
        await self.get_service('data_svc').store(self.op)
