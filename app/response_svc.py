import asyncio
import json
import uuid
import yaml

from aiohttp import web
from aiohttp_jinja2 import template
from copy import deepcopy

from app.objects.secondclass.c_fact import Fact
from app.objects.c_operation import Operation
from app.objects.c_source import Source
from app.objects.secondclass.c_result import Result
from app.utility.base_service import BaseService


async def process_elasticsearch_result(data, services):
    operation = await services.get('app_svc').find_op_with_link(data['link_id'])
    if hasattr(operation, 'chain'):
        link = next(filter(lambda l: l.id == int(data['link_id']), operation.chain))
        if link.ability.executor == 'elasticsearch':
            await services.get('response_svc').process_elasticsearch_results(operation, link)


async def handle_link_completed(socket, path, services):
    data = json.loads(await socket.recv())
    paw = data['agent']['paw']
    data_svc = services.get('data_svc')

    await process_elasticsearch_result(data, services)

    agent = await data_svc.locate('agents', match=dict(paw=paw, access=data_svc.Access.RED))
    if agent:
        pid = data['pid']
        op_type = 'hidden' if BaseService.Access(data.get('access')) == BaseService.Access.HIDDEN else 'visible'
        return await services.get('response_svc').respond_to_pid(pid, agent[0], op_type)


class ResponseService(BaseService):

    def __init__(self, services):
        self.log = self.add_service('response_svc', self)
        self.data_svc = services.get('data_svc')
        self.rest_svc = services.get('rest_svc')
        self.agents = []
        self.adversary = None
        self.abilities = []
        self.search_time_range = 300000
        self.ops = dict()

    @template('response.html')
    async def splash(self, request):
        abilities = [a for a in await self.data_svc.locate('abilities') if await a.which_plugin() == 'response']
        adversaries = [a for a in await self.data_svc.locate('adversaries') if await a.which_plugin() == 'response']
        await self.apply_adversary_config()
        return dict(abilities=abilities, adversaries=adversaries, auto_response=self.adversary)

    async def update_responder(self, request):
        data = dict(await request.json())
        self.set_config(name='response', prop='adversary', value=data['adversary_id'])
        await self.apply_adversary_config()
        await self._save_configurations()
        return web.json_response('complete')

    @staticmethod
    async def register_handler(event_svc):
        await event_svc.observe_event(handle_link_completed, exchange='link', queue='completed')

    async def respond_to_pid(self, pid, red_agent, op_type):
        available_agents = await self.get_available_agents(red_agent)
        if not available_agents:
            return

        if op_type not in self.ops or await self.ops[op_type].is_finished():
            source = await self.create_fact_source()
            await self.create_operation(source=source, op_type=op_type)

        total_facts = []
        total_links = []

        for blue_agent in available_agents:
            agent_facts, agent_links = await self.run_abilities_on_agent(blue_agent, str(red_agent.pid), pid, op_type)
            total_facts.extend(agent_facts)
            total_links.extend(agent_links)

    async def process_elasticsearch_results(self, operation, link):
        file_svc = self.get_service('file_svc')
        contact_svc = self.get_service('contact_svc')
        link_output = BaseService.decode_bytes(file_svc.read_result_file(str(link.id)))
        loaded_output = json.loads(link_output)
        for result in loaded_output:

            # Add link
            new_link = deepcopy(link)
            new_link.facts = []
            new_link.relationships = []
            new_link.apply_id(new_link.host)
            operation.chain.append(new_link)
            await self.data_svc.store(operation)

            # Add result for new link
            new_result = Result(
                id=str(new_link.id),
                output=BaseService.encode_string(json.dumps(result, indent=4)),
                pid=str(link.pid),
                status=str(link.status)
            )
            await contact_svc._save(new_result)

    async def get_available_agents(self, agent_to_match):
        await self.refresh_blue_agents_abilities()
        available_agents = [a for a in self.agents if a.host == agent_to_match.host]

        if not available_agents:
            self.log.debug('No available blue agents to respond to red action')
            return []

        return available_agents

    async def refresh_blue_agents_abilities(self):
        self.agents = await self.data_svc.locate('agents', match=dict(access=self.Access.BLUE))
        await self.apply_adversary_config()

        self.abilities = []
        for a in self.adversary.atomic_ordering:
            if a not in self.abilities:
                self.abilities.append(a)

    async def run_abilities_on_agent(self, blue_agent, red_agent_pid, original_pid, op_type):
        facts = [Fact(trait='host.process.id', value=original_pid),
                 Fact(trait='sysmon.time.range', value=self.search_time_range)]
        links = []
        relationships = []
        for ability_id in self.abilities:
            ability_facts, ability_links, ability_relationships = await self.run_ability_on_agent(blue_agent, red_agent_pid, ability_id, facts, original_pid, relationships, op_type)
            links.extend(ability_links)
            facts.extend(ability_facts)
            relationships.extend(ability_relationships)
        return facts, links

    async def run_ability_on_agent(self, blue_agent, red_agent_pid, ability_id, agent_facts, original_pid, relationships, op_type):
        links = await self.rest_svc.task_agent_with_ability(paw=blue_agent.paw, ability_id=ability_id,
                                                            obfuscator='plain-text', facts=agent_facts)
        await self.save_to_operation(links, op_type)
        await self.wait_for_link_completion(links, blue_agent)
        ability_facts = []
        ability_relationships = []
        for link in links:
            ability_relationships.extend(link.relationships)
            link.pin = int(original_pid)
            unique_facts = link.facts[1:]
            ability_facts.extend(self._filter_ability_facts(unique_facts, relationships + ability_relationships,
                                                            red_agent_pid, original_pid))
        return ability_facts, links, ability_relationships

    @staticmethod
    async def wait_for_link_completion(links, agent):
        for link in links:
            while not link.finish or link.can_ignore():
                await asyncio.sleep(3)
                if not agent.trusted:
                    break

    @staticmethod
    async def create_fact_source():
        source_id = str(uuid.uuid4())
        source_name = 'blue-pid-{}'.format(source_id)
        return Source(id=source_id, name=source_name, facts=[])

    async def save_to_operation(self, links, op_type):
        await self.update_operation(links, op_type)
        await self.get_service('data_svc').store(self.ops[op_type])

    async def create_operation(self, source, op_type):
        planner = (await self.get_service('data_svc').locate('planners', match=dict(name='batch')))[0]
        await self.get_service('data_svc').store(source)
        blue_op_name = self.get_config(prop='op_name', name='response')
        access = self.Access.BLUE if op_type == 'visible' else self.Access.HIDDEN
        self.ops[op_type] = Operation(name=blue_op_name, agents=self.agents, adversary=self.adversary,
                                      source=source, access=access, planner=planner, state='running',
                                      auto_close=False, jitter='1/4')
        obj = await self.get_service('data_svc').locate('objectives', match=dict(name='default'))
        self.ops[op_type].objective = deepcopy(obj[0])
        self.ops[op_type].set_start_details()

    async def update_operation(self, links, op_type):
        for link in links:
            link.operation = self.ops[op_type].id
            self.ops[op_type].add_link(link)

    async def apply_adversary_config(self):
        blue_adversary = self.get_config(prop='adversary', name='response')
        self.adversary = (await self.data_svc.locate('adversaries', match=dict(adversary_id=blue_adversary)))[0]
        self.search_time_range = self.get_config(prop='search_time_range_msecs', name='response')

    async def _save_configurations(self):
        with open('plugins/response/conf/response.yml', 'w') as config:
            config.write(yaml.dump(self.get_config(name='response')))

    def _filter_ability_facts(self, unique_facts, relationships, red_pid, original_pid):
        ability_facts = []
        for fact in unique_facts:
            if fact.trait == 'host.process.guid':
                if self._is_child_guid(relationships, red_pid, original_pid, fact):
                    ability_facts.append(fact)
            elif fact.trait == 'host.process.parentguid':
                if self._is_red_agent_guid(relationships, red_pid, fact):
                    ability_facts.append(fact)
            else:
                ability_facts.append(fact)
        return ability_facts

    @staticmethod
    def _is_child_guid(relationships, red_pid, original_pid, fact):
        for r in relationships:
            if r.edge == 'has_parentid' and \
                    (r.target.value.strip() == red_pid or r.target.value.strip() == original_pid) \
                    and r.source.value == fact.value:
                return True
        return False

    @staticmethod
    def _is_red_agent_guid(relationships, red_pid, fact):
        red_guid = [r.target.value for r in relationships if r.source.value.strip() == red_pid].pop()
        return fact.value == red_guid
