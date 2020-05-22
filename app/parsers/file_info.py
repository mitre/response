from app.objects.secondclass.c_fact import Fact
from app.objects.secondclass.c_relationship import Relationship
from app.utility.base_parser import BaseParser


class Parser(BaseParser):
    """
    Expects file hashes to be provided in the format:
    <hash> <filepath>

    Saves the following relationship
    - source: filepath
      edge: <has_hash>  -> this can be named anything
      target: hash
    """

    def parse(self, blob):
        relationships = []
        for match in self.line(blob.strip()):
            for mp in self.mappers:
                strings = match.strip.split('>')
                source = strings[1].strip()
                target = strings[0]
                relationships.append(
                    Relationship(source=Fact(mp.source, source),
                                 edge=mp.edge,
                                 target=Fact(mp.target, target))
                )
        return relationships
