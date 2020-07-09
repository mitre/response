import json

from app.objects.secondclass.c_fact import Fact
from app.objects.secondclass.c_relationship import Relationship
from app.utility.base_parser import BaseParser


class Parser(BaseParser):
    """
    This parser extracts information from sysmon events that
     have been transformed via the Elastic Common Schema (ECS)
    JSON documents (REF: https://www.elastic.co/guide/en/ecs/current/ecs-field-reference.html).
    """

    def parse(self, blob):
        relationships = []
        for event in json.loads(blob):
            for mp in self.mappers:
                match = self.parse_options[mp.target.split('.').pop()](event)
                if match:
                    guid = self.parse_process_guid(event)
                    relationships.append(Relationship(source=Fact(mp.source, guid),
                                                      edge=mp.edge,
                                                      target=Fact(mp.target, match)))
        return relationships

    @property
    def parse_options(self):
        return dict(
            eventid=self.parse_eventid,
            recordid=self.parse_recordid,
            user=self.parse_user,
            guid=self.parse_process_guid,
            pid=self.parse_pid,
        )

    @staticmethod
    def parse_process_guid(event):
        return event['_source']['process']['entity_id']

    @staticmethod
    def parse_eventid(event):
        return event['_source']['winlog']['event_id']

    @staticmethod
    def parse_recordid(event):
        return event['_source']['winlog']['record_id']

    @staticmethod
    def parse_user(event):
        return "%s\\%s" % (event['_source']['user']['domain'], event['_source']['user']['name'])

    @staticmethod
    def parse_pid(event):
        return event['_source']['process']['pid']
