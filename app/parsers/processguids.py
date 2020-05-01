import re

from app.objects.secondclass.c_relationship import Relationship
from app.utility.base_parser import BaseParser


class Parser(BaseParser):

    def parse(self, blob):
        relationships = []
        guids = re.findall(r'\bProcessGuid: {(.*)}', blob, re.IGNORECASE)
        for guid in guids:
            for mp in self.mappers:
                src_fact_value = [f.value for f in self.used_facts if f.trait == mp.source].pop()
                source = self.set_value(mp.source, src_fact_value, self.used_facts)
                target = self.set_value(mp.target, guid, self.used_facts)
                relationships.append(
                    Relationship(source=(mp.source, source),
                                 edge=mp.edge,
                                 target=(mp.target, target))
                )
        return relationships
