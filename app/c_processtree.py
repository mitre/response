import marshmallow as ma
from random import randint

from app.utility.base_object import BaseObject
from app.objects.interfaces.i_object import FirstClassObjectInterface
from plugins.response.app.c_processnode import ProcessNode, ProcessNodeSchema


class ProcessTreeSchema(ma.Schema):
    id = ma.fields.Integer()
    guid_to_processnode_map = ma.fields.Dict(keys=ma.fields.String(), values=ma.fields.Nested(ProcessNodeSchema()))

    @ma.post_load()
    def build_processtree(self, data, **_):
        return ProcessTree(**data)


class ProcessTree(FirstClassObjectInterface, BaseObject):

    schema = ProcessTreeSchema()

    @property
    def unique(self):
        return hash(self.id)

    def __init__(self, id=None, guid_to_processnode_map=None):
        super().__init__()
        self.id = id if id else randint(0, 999999)
        self.guid_to_processnode_map = guid_to_processnode_map if guid_to_processnode_map else dict()

    def add_processnode(self, guid, pid, link, parent_guid):
        processnode = ProcessNode(pid=pid, link=link, parent_guid=parent_guid)
        if guid in self.guid_to_processnode_map.keys():
            self.guid_to_processnode_map[guid].append(processnode)
        else:
            self.guid_to_processnode_map[pid] = [processnode]
        self.guid_to_processnode_map[parent_guid].add_child(guid, link)

    def store(self, ram):
        existing = self.retrieve(ram['processtree'], self.unique)
        if not existing:
            ram['processtree'].append(self)
            return self.retrieve(ram['processtree'], self.unique)
        return existing
