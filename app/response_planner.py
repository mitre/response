class LogicalPlanner:

    def __init__(self, operation, planning_svc, stopping_conditions=()):
        self.operation = operation
        self.planning_svc = planning_svc
        self.stopping_conditions = stopping_conditions
        self.stopping_condition_met = False
        self.processed_links = []
        self.handled_detections = []
        self.severity = 0

    async def execute(self, **kwargs):
        self.process_completed_links()
        links = await self.planning_svc.get_links(operation=self.operation,
                                                  stopping_conditions=self.stopping_conditions, planner=self)
        to_apply, detections_being_handled = self.select_links(links)
        for link in to_apply:
            await self.operation.apply(link)
        self.handled_detections.extend(list(detections_being_handled))

    def select_links(self, links):
        to_apply = []
        detections_being_handled = set()
        for link in links:
            if link.ability.tactic == 'detection':
                to_apply.append(link)
            elif any(uf not in self.handled_detections for uf in link.used) and link.ability.tactic in ['hunt', 'response']:
                to_apply.append(link)
                if link.ability.tactic == 'response':
                    detections_being_handled.update(link.used)
        return to_apply, detections_being_handled

    def process_completed_links(self):
        for l in [link for link in self.operation.chain if link not in self.processed_links]:
            for rel in l.relationships:
                if rel.trait == 'operation.severity.modifier' and l.relationships.length() > 1:
                    self.severity += rel.edge
            self.processed_links.append(l)
