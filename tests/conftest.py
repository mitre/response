"""Shared fixtures for the response plugin test suite."""
import sys
import os
import types
import importlib
import importlib.util
import pytest

# Root of the cloned repo
REPO_ROOT = '/tmp/response-pytest'


# ---------------------------------------------------------------------------
# Lightweight stubs for Caldera framework objects that are not available in an
# isolated test environment.  We only model the attributes / methods that the
# response plugin actually uses so the tests stay focused on *plugin* logic.
# ---------------------------------------------------------------------------

class FakeFact:
    """Minimal stand-in for app.objects.secondclass.c_fact.Fact."""
    def __init__(self, trait=None, value=None):
        self.trait = trait
        self.value = value

    def __eq__(self, other):
        if not isinstance(other, FakeFact):
            return NotImplemented
        return self.trait == other.trait and self.value == other.value

    def __repr__(self):
        return f"FakeFact(trait={self.trait!r}, value={self.value!r})"


class FakeRelationship:
    """Minimal stand-in for app.objects.secondclass.c_relationship.Relationship."""
    def __init__(self, source=None, edge=None, target=None):
        self.source = source
        self.edge = edge
        self.target = target

    def __repr__(self):
        return (f"FakeRelationship(source={self.source!r}, "
                f"edge={self.edge!r}, target={self.target!r})")


class FakeMapper:
    """Represents a parser mapper configuration."""
    def __init__(self, source, edge, target):
        self.source = source
        self.edge = edge
        self.target = target


class FakeLink:
    """Minimal stand-in for a Link object."""
    def __init__(self, id=None, host=None, used=None, facts=None,
                 relationships=None, finish=None, pin=None, pid=0,
                 status=0, operation=None, executor=None):
        self.id = id or 'link-1'
        self.host = host or 'testhost'
        self.used = used or []
        self.facts = facts if facts is not None else []
        self.relationships = relationships if relationships is not None else []
        self.finish = finish
        self.pin = pin
        self.pid = pid
        self.status = status
        self.operation = operation
        self.executor = executor

    def can_ignore(self):
        return False

    def apply_id(self, host):
        self.id = f'{self.id}-{host}'


class FakeOperation:
    """Minimal stand-in for an Operation."""
    def __init__(self, relationships=None, source=None, chain=None):
        self._relationships = relationships or []
        self.source = source
        self.chain = chain or []

    async def all_relationships(self):
        return self._relationships

    async def is_finished(self):
        return False


class FakeAgent:
    """Minimal stand-in for an Agent."""
    def __init__(self, paw='abc', host='testhost', pid=1234, trusted=True, access=None):
        self.paw = paw
        self.host = host
        self.pid = pid
        self.trusted = trusted
        self.access = access


class FakeSource:
    """Minimal stand-in for a Source."""
    def __init__(self, id=None, name=None, facts=None):
        self.id = id
        self.name = name
        self.facts = facts or []


class FakeBaseParser:
    """Stub for app.utility.base_parser.BaseParser.

    Provides the helper methods that concrete parsers rely on (line,
    set_value, load_json) without pulling in the full Caldera framework.
    """
    def __init__(self, mappers=None, used_facts=None):
        self.mappers = mappers or []
        self.used_facts = used_facts or []

    @staticmethod
    def line(blob):
        return blob.splitlines()

    @staticmethod
    def set_value(mapper_field, match, _facts):
        return match

    @staticmethod
    def load_json(blob):
        import json
        return json.loads(blob)


# ---------------------------------------------------------------------------
# Monkey-patch framework modules so that ``import app.…`` / ``import plugins.…``
# resolve to our fakes.
# ---------------------------------------------------------------------------

def _ensure_module(dotted_name, attrs=None):
    """Create a stub module at *dotted_name* (and all parents) if absent."""
    parts = dotted_name.split('.')
    for i in range(len(parts)):
        partial = '.'.join(parts[:i + 1])
        if partial not in sys.modules:
            sys.modules[partial] = types.ModuleType(partial)
    mod = sys.modules[dotted_name]
    for k, v in (attrs or {}).items():
        setattr(mod, k, v)
    return mod


def _install_stubs():
    # app.objects.secondclass.c_fact
    _ensure_module('app', {'__path__': [os.path.join(REPO_ROOT, 'app')]})
    _ensure_module('app.objects')
    _ensure_module('app.objects.secondclass')
    _ensure_module('app.objects.secondclass.c_fact', {'Fact': FakeFact})
    _ensure_module('app.objects.secondclass.c_relationship', {'Relationship': FakeRelationship})
    class FakeResult:
        def __init__(self, id=None, output=None, pid=None, status=None):
            self.id = id
            self.output = output
            self.pid = pid
            self.status = status

    _ensure_module('app.objects.secondclass.c_result', {'Result': FakeResult})
    _ensure_module('app.objects.secondclass.c_link', {'LinkSchema': type('LinkSchema', (), {})})

    class FakeOperationCls:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.chain = getattr(self, 'chain', [])
            self.id = getattr(self, 'id', 'op-id')
            self.objective = None
        def add_link(self, link):
            self.chain.append(link)
        def set_start_details(self):
            pass
        async def is_finished(self):
            return False

    _ensure_module('app.objects.c_operation', {'Operation': FakeOperationCls})
    _ensure_module('app.objects.c_source', {'Source': FakeSource})
    _ensure_module('app.objects.interfaces')
    _ensure_module('app.objects.interfaces.i_object',
                   {'FirstClassObjectInterface': type('FirstClassObjectInterface', (), {})})
    _ensure_module('app.utility')

    # BaseObject stub
    class _BaseObject:
        def __init__(self):
            pass
        def retrieve(self, collection, unique):
            for item in collection:
                if getattr(item, 'unique', None) == unique:
                    return item
            return None

    _ensure_module('app.utility.base_object', {'BaseObject': _BaseObject})

    # BaseService stub used by response_svc
    class _Access:
        RED = 'red'
        BLUE = 'blue'
        HIDDEN = 'hidden'

    class _BaseService(_BaseObject):
        Access = _Access
        services = {}

        @classmethod
        def add_service(cls, name, svc):
            cls.services[name] = svc
            import logging
            return logging.getLogger(name)

        @classmethod
        def get_service(cls, name):
            return cls.services.get(name)

        @staticmethod
        def decode_bytes(b):
            if isinstance(b, bytes):
                return b.decode()
            return b

        @staticmethod
        def encode_string(s):
            if isinstance(s, str):
                return s.encode()
            return s

        @classmethod
        def get_config(cls, name=None, prop=None):
            return None

        @classmethod
        def set_config(cls, name=None, prop=None, value=None):
            pass

    _ensure_module('app.utility.base_service', {'BaseService': _BaseService})

    # BaseWorld stub used by hook.py
    class _BaseWorld(_BaseService):
        @staticmethod
        def strip_yml(path):
            return [{}]

        @staticmethod
        def apply_config(name, cfg):
            pass

    _ensure_module('app.utility.base_world', {'BaseWorld': _BaseWorld})

    # BaseParser stub
    _ensure_module('app.utility.base_parser', {'BaseParser': FakeBaseParser})

    # marshmallow — try real one first
    try:
        import marshmallow  # noqa: F401
    except ImportError:
        ma = _ensure_module('marshmallow')
        ma.Schema = type('Schema', (), {})
        ma.fields = types.ModuleType('marshmallow.fields')
        sys.modules['marshmallow.fields'] = ma.fields
        for fld in ('Integer', 'String', 'List', 'Dict', 'Nested'):
            setattr(ma.fields, fld, lambda *a, **kw: None)
        ma.post_load = lambda **kw: (lambda fn: fn)

    # plugins.response paths
    _ensure_module('plugins')
    _ensure_module('plugins.response')
    _ensure_module('plugins.response.app')
    _ensure_module('plugins.response.app.requirements')

    # aiohttp / jinja stubs
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        aio = _ensure_module('aiohttp')
        aio.web = types.ModuleType('aiohttp.web')
        sys.modules['aiohttp.web'] = aio.web
        aio.web.json_response = lambda x: x

    try:
        import aiohttp_jinja2  # noqa: F401
    except ImportError:
        aj = _ensure_module('aiohttp_jinja2')
        aj.template = lambda name: (lambda fn: fn)


_install_stubs()

# ---------------------------------------------------------------------------
# Load real plugin modules from file paths using importlib
# ---------------------------------------------------------------------------

def _load_from_file(module_name, file_path):
    """Load a module from an absolute file path and register it in sys.modules."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Sub-packages need __path__ set so child imports work
def _ensure_package(dotted_name, dir_path):
    """Register a directory as a Python package in sys.modules."""
    mod = sys.modules.get(dotted_name)
    if mod is None:
        mod = types.ModuleType(dotted_name)
        sys.modules[dotted_name] = mod
    mod.__path__ = [dir_path]
    mod.__package__ = dotted_name
    return mod


# Make app and its sub-packages real packages that point to the repo
_app_mod = sys.modules['app']
_app_mod.__path__ = [os.path.join(REPO_ROOT, 'app')]
_app_mod.__package__ = 'app'

_ensure_package('app.parsers', os.path.join(REPO_ROOT, 'app', 'parsers'))
_ensure_package('app.requirements', os.path.join(REPO_ROOT, 'app', 'requirements'))

# Load base_requirement into the plugins path too
_load_from_file(
    'plugins.response.app.requirements.base_requirement',
    os.path.join(REPO_ROOT, 'app', 'requirements', 'base_requirement.py'),
)

# Load the actual parsers
for _parser_name in ('basic_strip', 'childprocess', 'ecs_sysmon', 'key_value',
                      'ports', 'processguids', 'process', 'sysmon'):
    _load_from_file(
        f'app.parsers.{_parser_name}',
        os.path.join(REPO_ROOT, 'app', 'parsers', f'{_parser_name}.py'),
    )

# Load requirements
for _req_name in ('base_requirement', 'basic', 'has_property', 'source_fact'):
    _mod_name = f'app.requirements.{_req_name}'
    _plugin_mod_name = f'plugins.response.app.requirements.{_req_name}'
    _fpath = os.path.join(REPO_ROOT, 'app', 'requirements', f'{_req_name}.py')
    _load_from_file(_mod_name, _fpath)
    # Also register under plugin path so intra-plugin imports work
    sys.modules[_plugin_mod_name] = sys.modules[_mod_name]

# Load ProcessNode and ProcessTree
_load_from_file(
    'plugins.response.app.c_processnode',
    os.path.join(REPO_ROOT, 'app', 'c_processnode.py'),
)
sys.modules['app.c_processnode'] = sys.modules['plugins.response.app.c_processnode']

_load_from_file(
    'plugins.response.app.c_processtree',
    os.path.join(REPO_ROOT, 'app', 'c_processtree.py'),
)
sys.modules['app.c_processtree'] = sys.modules['plugins.response.app.c_processtree']

# Load response_svc (needs plugins.response.app.c_processtree)
_load_from_file(
    'app.response_svc',
    os.path.join(REPO_ROOT, 'app', 'response_svc.py'),
)
sys.modules['plugins.response.app.response_svc'] = sys.modules['app.response_svc']

# Load hook
_load_from_file('hook', os.path.join(REPO_ROOT, 'hook.py'))


# ---------------------------------------------------------------------------
# Reusable pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_fact():
    return FakeFact


@pytest.fixture
def fake_relationship():
    return FakeRelationship


@pytest.fixture
def fake_mapper():
    return FakeMapper


@pytest.fixture
def fake_link():
    return FakeLink


@pytest.fixture
def fake_operation():
    return FakeOperation


@pytest.fixture
def fake_agent():
    return FakeAgent


@pytest.fixture
def fake_source():
    return FakeSource


@pytest.fixture
def make_parser():
    """Factory fixture: returns a parser instance with mappers / used_facts."""
    def _make(parser_cls, mappers=None, used_facts=None):
        p = parser_cls.__new__(parser_cls)
        FakeBaseParser.__init__(p, mappers=mappers or [], used_facts=used_facts or [])
        return p
    return _make
