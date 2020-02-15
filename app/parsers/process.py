from app.objects.secondclass.c_relationship import Relationship
from app.utility.base_parser import BaseParser


class Parser(BaseParser):

    UNAUTHORIZED = 'slack'

    def parse(self, blob):
        relationships = []
        for match in self.line(blob):
            for found in [name for name in self.UNAUTHORIZED if name in match.lower()]:
                for mp in self.mappers:
                    source = self.set_value(mp.source, found, self.used_facts)
                    target = self.set_value(mp.target, found, self.used_facts)
                    relationships.append(
                        Relationship(source=(mp.source, source),
                                     edge=mp.edge,
                                     target=(mp.target, target))
                    )
        return relationships
