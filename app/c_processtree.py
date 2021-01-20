import marshmallow as ma
from random import randint

from app.utility.base_object import BaseObject
from app.objects.interfaces.i_object import FirstClassObjectInterface
from plugins.response.app.c_processnode import ProcessNode, ProcessNodeSchema


class ProcessTreeSchema(ma.Schema):
    id = ma.fields.Integer()
    pid_to_guids_map = ma.fields.Dict(keys=ma.fields.String(),
                                      values=ma.fields.Dict(keys=ma.fields.Integer(),
                                                            values=ma.fields.List(ma.fields.String())))
    guid_to_processnode_map = ma.fields.Dict(keys=ma.fields.String(),
                                             values=ma.fields.Dict(keys=ma.fields.String(),
                                                                   values=ma.fields.Nested(ProcessNodeSchema())))

    @ma.post_load()
    def build_processtree(self, data, **_):
        return ProcessTree(**data)


class ProcessTree(FirstClassObjectInterface, BaseObject):

    schema = ProcessTreeSchema()

    @property
    def unique(self):
        return hash(self.id)

    def __init__(self, id=None, pid_to_guids_map=None, guid_to_processnode_map=None):
        super().__init__()
        self.id = id if id else randint(0, 999999)
        self.pid_to_guids_map = pid_to_guids_map if pid_to_guids_map else dict()
        self.guid_to_processnode_map = guid_to_processnode_map if guid_to_processnode_map else dict()

    def add_processnode(self, guid, pid, link, parent_guid):
        processnode = ProcessNode(pid=pid, link=link, parent_guid=parent_guid)

        if link.host not in self.guid_to_processnode_map:
            self.guid_to_processnode_map[link.host] = dict()

        if guid in self.guid_to_processnode_map[link.host]:
            self.guid_to_processnode_map[link.host][guid].append(processnode)
        else:
            self.guid_to_processnode_map[link.host][guid] = [processnode]

        if link.host not in self.pid_to_guids_map:
            self.pid_to_guids_map[link.host] = dict()

        if pid in self.pid_to_guids_map[link.host]:
            self.pid_to_guids_map[link.host][pid].append(guid)
        else:
            self.pid_to_guids_map[link.host][pid] = [guid]

        self.guid_to_processnode_map[link.host][parent_guid].add_child(guid, link)

    async def find_original_process_by_pid(self, pid, host):
        # TODO: caller needs to add check for multiple pids, verify which pid/link is intended
        original_guids = []
        if host in self.pid_to_guids_map and pid in self.pid_to_guids_map[host]:
            guids = self.pid_to_guids_map[host][pid]
            for guid in guids:
                original_guid = guid
                parent_guid = await self.find_parent_guid(guid, host)
                while parent_guid is not None:
                    original_guid = parent_guid
                    parent_guid = await self.find_parent_guid(guid, host)
                original_guids.append(original_guid)
        return await self.convert_guids_to_pids(original_guids, host)

    async def find_parent_guid(self, guid, host):
        if host in self.guid_to_processnode_map and guid in self.guid_to_processnode_map[host]:
            return self.guid_to_processnode_map[host][guid].parent_guid
        return None

    async def convert_guids_to_pids(self, guids, host):
        pids = []
        for guid in guids:
            for pid in self.pid_to_guids_map[host]:
                if guid in self.pid_to_guids_map[host][pid]:
                    pids.append(pid)
        return pids

    def store(self, ram):
        existing = self.retrieve(ram['processtrees'], self.unique)
        if not existing:
            ram['processtrees'].append(self)
            return self.retrieve(ram['processtrees'], self.unique)
        return existing
