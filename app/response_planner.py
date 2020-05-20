class LogicalPlanner:

    def __init__(self, operation, planning_svc, stopping_conditions=()):
        self.operation = operation
        self.planning_svc = planning_svc
        self.stopping_conditions = stopping_conditions
        self.stopping_condition_met = False
        self.state_machine = ['detection', 'hunt', 'response']
        self.next_bucket = 'detection'
        self.links_hunted = set()
        self.links_responded = set()
        self.severity = 0

    async def execute(self):
        await self.planning_svc.execute_planner(self)

    async def detection(self):
        await self.planning_svc.exhaust_bucket(self, ['detection'], self.operation)
        self.next_bucket = await self.planning_svc.default_next_bucket('detection', self.state_machine)

    async def hunt(self):
        await self._do_reactive_bucket(bucket='hunt', link_storage=self.links_hunted)
        self.next_bucket = await self.planning_svc.default_next_bucket('hunt', self.state_machine)

    async def response(self):
        await self._do_reactive_bucket(bucket='response', link_storage=self.links_responded)
        self.next_bucket = await self.planning_svc.default_next_bucket('response', self.state_machine)

    """ PRIVATE """

    async def _do_reactive_bucket(self, bucket, link_storage):
        links = self.planning_svc.get_links(planner=self, operation=self.operation, bucket=[bucket])
        links_to_apply = []
        links_being_addressed = set()
        for link in links:
            unaddressed_parents = self._get_unaddressed_parent_links(link)
            if len(unaddressed_parents):
                links_to_apply.append(link)
                links_being_addressed.update(unaddressed_parents)
        link_storage.update(list(links_being_addressed))
        await self._run_links(links_to_apply)

    def _get_unaddressed_parent_links(self, link):
        return [parent not in self.links_hunted for parent in self._get_parent_links(link)]

    def _get_parent_links(self, link):
        parent_links = []
        for fact in link.used:
            parent_links.extend(self._links_with_fact_as_relationship(fact))
        return parent_links

    def _links_with_fact_as_relationship(self, fact):
        links_with_fact = []
        for link in self.operation.chain:
            if any(self._fact_in_relationship(fact, rel) for rel in link.relationships):
                links_with_fact.append(link)
        return links_with_fact

    @staticmethod
    def _fact_in_relationship(fact, relationship):
        for f in [relationship.source, relationship.target]:
            if f.trait == fact.trait and f.value == fact.value:
                return True
        return False

    async def _run_links(self, links):
        link_ids = []
        for link in links:
            link_ids.append(await self.operation.apply(link))
        self.planning_svc.execute_links(self, self.operation, link_ids, True)






    # async def execute(self, **kwargs):
    #     links = await self.planning_svc.get_links(operation=self.operation,
    #                                               stopping_conditions=self.stopping_conditions, planner=self)
    #     to_apply, detections_being_handled = self.select_links(links)
    #     for link in to_apply:
    #         await self.operation.apply(link)
    #     self.handled_detection_and_response_links.extend(list(detections_being_handled))
    #
    # def select_links(self, links):
    #     to_apply = []
    #     detections_being_handled = set()
    #     for link in links:
    #         if link.ability.tactic == 'detection':
    #             to_apply.append(link)
    #         elif any(uf not in self.handled_detection_and_response_links for uf in link.used) and \
    #                 link.ability.tactic in ['hunt', 'response']:
    #             to_apply.append(link)
    #             if link.ability.tactic == 'response':
    #                 detections_being_handled.update(link.used)
    #     return to_apply, detections_being_handled
