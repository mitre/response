from plugins.response.app.requirements.base_requirement import BaseRequirement


class Requirement(BaseRequirement):

    async def enforce(self, link, operation):
        """
        Given a link and the current operation, check if the link's used fact combination complies
        with the abilities enforcement mechanism
        :param link
        :param operation
        :return: True if it complies, False if it doesn't
        """
        relationships = operation.all_relationships()
        for uf in link.used:
            if self.enforcements['source'] == uf.trait:
                if any(uf.trait == source_fact.trait and uf.value == source_fact.value for
                       source_fact in operation.source.facts):
                    return True
        return False
