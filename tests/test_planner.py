from app.objects.c_ability import Ability
from app.objects.c_adversary import Adversary
from app.objects.c_agent import Agent
from app.utility.base_world import BaseWorld
from app.objects.secondclass.c_fact import Fact
from app.objects.secondclass.c_link import Link
from plugins.response.app.response_planner import LogicalPlanner
from app.objects.c_obfuscator import Obfuscator
from app.objects.c_operation import Operation
from app.objects.c_planner import Planner
from app.objects.secondclass.c_relationship import Relationship
from app.objects.secondclass.c_requirement import Requirement
from app.objects.c_source import Source
from tests.base.test_base import TestBase

class TestPlanner(TestBase):

    def setUp(self):
        self.initialize()
        BaseWorld.apply_config(name='default',
                               config={'app.contact.http': '0.0.0.0', 'plugins': ['sandcat', 'stockpile']})
        self.test_ab_detection = Ability(ability_id='10', tactic='detection', technique_id='1', technique='1',
                                    name='detection1',
                                    test='MQ==', description='detection1', cleanup='', executor='sh',
                                    platform='linux', parsers=[], requirements=[], privilege=None, variations=[])
        self.test_ab_hunt = Ability(ability_id='20', tactic='hunt', technique_id='2', technique='2', name='hunt1',
                                    test='I3todW50LnRoaXMuZmFjdH0=', description='hunt1', cleanup='', executor='sh',
                                    platform='linux', parsers=[], requirements=[], privilege=None, variations=[])
        self.test_relationship = Relationship(source='respond.this.fact')
        self.requirement_paw_provenance = Requirement(module='plugins.stockpile.app.requirements.paw_provenance',
                                                      relationships=[self.test_relationship])
        self.test_ab_response = Ability(ability_id='30', tactic='response', technique_id='3', technique='3',
                                        name='response1', test='I3tyZXNwb25kLnRoaXMuZmFjdH0=', description='response1',
                                        cleanup='', executor='sh', platform='linux', parsers=[],
                                        requirements=[self.requirement_paw_provenance],privilege=None, variations=[])
        self.ab_list = [self.test_ab_detection, self.test_ab_hunt, self.test_ab_response]
        self.agent1 = Agent(0, 0, 0, paw='agent1', platform='linux', executors=['sh'])
        self.agent2 = Agent(0, 0, 0, paw='agent2', platform='linux', executors=['sh'])
        self.adversary = Adversary(adversary_id='1', name='test', description='test adversary',
                                        phases={1: self.ab_list})
        self.source = Source(identifier='test', name='test', facts=[])
        self.planner_object = Planner(planner_id='1', name='response_planner', params=[],
                                      module='plugins.response.app.response_planner.py')
        self.run_async(self.data_svc.store(
            Obfuscator(name='plain-text',
                       description='Does no obfuscation to any command, instead running it in plain text',
                       module='plugins.stockpile.app.obfuscators.plain_text')))

    def test_execute_no_facts(self):
        operation = Operation(name='test_operation', agents=[self.agent1, self.agent2],
                                   adversary=self.adversary, source=self.source, planner=self.planner_object)
        response_planner = LogicalPlanner(operation, self.planning_svc)

        self.run_async(response_planner.execute(phase=1))
        self.assertEqual(2, len(operation.chain))
        self.assertEqual(operation.chain[0].ability.ability_id, '10')
        self.assertEqual(operation.chain[1].ability.ability_id, '10')

    def test_execute_hunt_fact(self):
        operation = Operation(name='test_operation', agents=[self.agent1, self.agent2],
                                   adversary=self.adversary, source=self.source, planner=self.planner_object)
        response_planner = LogicalPlanner(operation, self.planning_svc)

        fact1 = Fact(trait='hunt.this.fact', value='fact1', collected_by='some_random_agent')
        operation.source.facts.append(fact1)

        self.run_async(response_planner.execute(phase=1))
        self.assertEqual(4, len(operation.chain))
        link_ability_ids = []
        for link in operation.chain:
            link_ability_ids.append(link.ability.ability_id)
        self.assertEqual(2, link_ability_ids.count('10'))
        self.assertEqual(2, link_ability_ids.count('20'))

    def test_execute_detect_fact(self):
        operation = Operation(name='test_operation', agents=[self.agent1, self.agent2],
                                   adversary=self.adversary, source=self.source, planner=self.planner_object)
        response_planner = LogicalPlanner(operation, self.planning_svc)

        fact1 = Fact(trait='respond.this.fact', value='fact1', collected_by='agent1')
        link1 = Link(operation=operation, command='some_command', paw='agent1', ability=self.test_ab_detection)
        link1.facts.append(fact1)
        operation.chain.append(link1)

        self.run_async(response_planner.execute(phase=1))
        self.assertEqual(4, len(operation.chain))
        link_ability_ids = []
        for link in operation.chain:
            link_ability_ids.append(link.ability.ability_id)
        self.assertEqual(3, link_ability_ids.count('10'))
        self.assertEqual(1, link_ability_ids.count('30'))

    def test_execute_all_together(self):
        self.operation = Operation(name='test_operation', agents=[self.agent1, self.agent2],
                                   adversary=self.adversary, source=self.source, planner=self.planner_object)
        self.response_planner = LogicalPlanner(self.operation, self.planning_svc)

        fact1 = Fact(trait='hunt.this.fact', value='fact1', collected_by='some_random_agent')
        self.operation.source.facts.append(fact1)
        fact2 = Fact(trait='respond.this.fact', value='fact1', collected_by='agent1')
        link1 = Link(operation=self.operation, command='some_command', paw='agent1', ability=self.test_ab_detection)
        link1.facts.append(fact2)
        self.operation.chain.append(link1)

        self.run_async(self.response_planner.execute(phase=1))
        self.assertEqual(6, len(self.operation.chain))
        link_ability_ids = []
        for link in self.operation.chain:
            link_ability_ids.append(link.ability.ability_id)
        self.assertEqual(3, link_ability_ids.count('10'))
        self.assertEqual(2, link_ability_ids.count('20'))
        self.assertEqual(1, link_ability_ids.count('30'))
        