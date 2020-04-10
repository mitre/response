from aiohttp_jinja2 import template
import uuid

from app.objects.secondclass.c_fact import Fact
from app.objects.c_operation import Operation
from app.objects.c_source import Source
from app.utility.base_service import BaseService
from app.utility.event import Observer


BLUE_GROUP = 'blue'
BLUE_ADVERSARY = 'f61e3fc0-43d8-4b36-b5d3-710610b92974'
BLUE_OP_NAME = 'Auto-Collect Response Data'


class LinkCompletedObserver(Observer):

    def __init__(self, response_svc):
        Observer.__init__(self, 'link', 'completed')
        self.response_svc = response_svc

    async def handle(self, agent, pid):
        if agent.group == BLUE_GROUP:
            return

        links, facts = await self.response_svc.respond_to_pid(pid, agent)
        await self.response_svc.create_operation(links, facts)


class ResponseService(BaseService):

    def __init__(self, services):
        self.log = self.add_service('response_svc', self)
        self.data_svc = services.get('data_svc')
        self.rest_svc = services.get('rest_svc')
        self.agents = []
        self.abilities = []

        LinkCompletedObserver.register(self)

    @template('response.html')
    async def splash(self, request):
        abilities = [a for a in await self.data_svc.locate('abilities') if await a.which_plugin() == 'response']
        adversaries = [a for a in await self.data_svc.locate('adversaries') if await a.which_plugin() == 'response']
        return dict(abilities=abilities, adversaries=adversaries)

    async def respond_to_pid(self, pid, agent):
        await self.refresh_blue_agents_abilities()
        facts = [Fact(trait='host.process.id', value=pid)]
        total_links = []

        for blue_agent in self.agents:
            for step in self.abilities:
                links = await self.rest_svc.task_agent_with_ability(blue_agent, step, facts)
                for link in links:
                    facts.extend(link.facts)
                total_links.extend(links)

        return total_links, facts

    async def refresh_blue_agents_abilities(self):
        blue_agents = await self.data_svc.locate('agents', match=dict(group='blue'))
        self.agents = [agent.paw for agent in blue_agents]

        blue_adversary = await self.data_svc.locate('adversaries', match=dict(adversary_id=BLUE_ADVERSARY))
        self.abilities = [a.ability_id for a in blue_adversary[0].atomic_ordering]

    async def create_operation(self, links, facts):
        access = dict(access=(self.rest_svc.Access.BLUE,))
        source_id = str(uuid.uuid4())
        source_name = 'blue-pid-{}'.format(source_id),
        source = Source(identifier=source_id, name=source_name, facts=facts)
        await self.get_service('data_svc').store(source)
        op = Operation(name=BLUE_OP_NAME, agents=self.agents, adversary=BLUE_ADVERSARY,
                       source=source, state='finished', access=access)
        await self.get_service('data_svc').store(op)
