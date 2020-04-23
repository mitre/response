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


class TestPlanner:

    @classmethod
    def setup_class(cls, loop, data_svc):
        BaseWorld.apply_config(name='default',
                               config={'app.contact.http': '0.0.0.0', 'plugins': ['sandcat', 'stockpile']})
        cls.test_ab_detection = Ability(ability_id='10', tactic='detection', technique_id='1', technique='1',
                                         name='detection1',
                                         test='MQ==', description='detection1', cleanup='', executor='sh',
                                         platform='linux', parsers=[], requirements=[], privilege=None, variations=[])
        cls.test_ab_hunt = Ability(ability_id='20', tactic='hunt', technique_id='2', technique='2', name='hunt1',
                                    test='I3todW50LnRoaXMuZmFjdH0=', description='hunt1', cleanup='', executor='sh',
                                    platform='linux', parsers=[], requirements=[], privilege=None, variations=[])
        cls.test_relationship = Relationship(source='respond.this.fact')
        cls.requirement_paw_provenance = Requirement(module='plugins.stockpile.app.requirements.paw_provenance',
                                                      relationships=[cls.test_relationship])
        cls.test_ab_response = Ability(ability_id='30', tactic='response', technique_id='3', technique='3',
                                        name='response1', test='I3tyZXNwb25kLnRoaXMuZmFjdH0=', description='response1',
                                        cleanup='', executor='sh', platform='linux', parsers=[],
                                        requirements=[cls.requirement_paw_provenance], privilege=None, variations=[])
        cls.ab_list = [cls.test_ab_detection, cls.test_ab_hunt, cls.test_ab_response]
        cls.agent1 = Agent(0, 0, 0, paw='agent1', platform='linux', executors=['sh'])
        cls.agent2 = Agent(0, 0, 0, paw='agent2', platform='linux', executors=['sh'])
        cls.adversary = Adversary(adversary_id='1', name='test', description='test adversary',
                                   atomic_ordering=cls.ab_list)
        cls.source = Source(identifier='test', name='test', facts=[])
        cls.planner_object = Planner(planner_id='1', name='response_planner', params=[],
                                      module='plugins.response.app.response_planner.py')
        loop.run_until_complete(data_svc.store(
            Obfuscator(name='plain-text',
                       description='Does no obfuscation to any command, instead running it in plain text',
                       module='plugins.stockpile.app.obfuscators.plain_text')))

    def test_execute_no_facts(self, loop, ):
        operation = Operation(name='test_operation', agents=[type(self).agent1, type(self).agent2],
                                   adversary=type(self).adversary, source=type(self).source, planner=type(self).planner_object)
        response_planner = LogicalPlanner(operation, type(self).planning_svc)

        loop.run_until_complete(response_planner.execute(phase=1))
        type(self).assertEqual(2, len(operation.chain))
        type(self).assertEqual(operation.chain[0].ability.ability_id, '10')
        type(self).assertEqual(operation.chain[1].ability.ability_id, '10')

    # def test_execute_hunt_fact(self):
    #     operation = Operation(name='test_operation', agents=[self.agent1, self.agent2],
    #                                adversary=self.adversary, source=self.source, planner=self.planner_object)
    #     response_planner = LogicalPlanner(operation, self.planning_svc)
    #
    #     fact1 = Fact(trait='hunt.this.fact', value='fact1', collected_by='some_random_agent')
    #     operation.source.facts.append(fact1)
    #
    #     self.run_async(response_planner.execute(phase=1))
    #     self.assertEqual(4, len(operation.chain))
    #     link_ability_ids = []
    #     for link in operation.chain:
    #         link_ability_ids.append(link.ability.ability_id)
    #     self.assertEqual(2, link_ability_ids.count('10'))
    #     self.assertEqual(2, link_ability_ids.count('20'))
    #
    # def test_execute_detect_fact(self):
    #     operation = Operation(name='test_operation', agents=[self.agent1, self.agent2],
    #                                adversary=self.adversary, source=self.source, planner=self.planner_object)
    #     response_planner = LogicalPlanner(operation, self.planning_svc)
    #
    #     fact1 = Fact(trait='respond.this.fact', value='fact1', collected_by='agent1')
    #     link1 = Link(operation=operation, command='some_command', paw='agent1', ability=self.test_ab_detection)
    #     link1.facts.append(fact1)
    #     operation.chain.append(link1)
    #
    #     self.run_async(response_planner.execute(phase=1))
    #     self.assertEqual(4, len(operation.chain))
    #     link_ability_ids = []
    #     for link in operation.chain:
    #         link_ability_ids.append(link.ability.ability_id)
    #     self.assertEqual(3, link_ability_ids.count('10'))
    #     self.assertEqual(1, link_ability_ids.count('30'))
    #
    # def test_execute_all_together(self):
    #     self.operation = Operation(name='test_operation', agents=[self.agent1, self.agent2],
    #                                adversary=self.adversary, source=self.source, planner=self.planner_object)
    #     self.response_planner = LogicalPlanner(self.operation, self.planning_svc)
    #
    #     fact1 = Fact(trait='hunt.this.fact', value='fact1', collected_by='some_random_agent')
    #     self.operation.source.facts.append(fact1)
    #     fact2 = Fact(trait='respond.this.fact', value='fact1', collected_by='agent1')
    #     link1 = Link(operation=self.operation, command='some_command', paw='agent1', ability=self.test_ab_detection)
    #     link1.facts.append(fact2)
    #     self.operation.chain.append(link1)
    #
    #     self.run_async(self.response_planner.execute(phase=1))
    #     self.assertEqual(6, len(self.operation.chain))
    #     link_ability_ids = []
    #     for link in self.operation.chain:
    #         link_ability_ids.append(link.ability.ability_id)
    #     self.assertEqual(3, link_ability_ids.count('10'))
    #     self.assertEqual(2, link_ability_ids.count('20'))
    #     self.assertEqual(1, link_ability_ids.count('30'))
