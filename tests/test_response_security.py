import ast
import glob
import os
import re

import pytest
import yaml


PLUGIN_DIR = os.path.join(os.path.dirname(__file__), '..')
ABILITIES_DIR = os.path.join(PLUGIN_DIR, 'data', 'abilities')
PAYLOADS_DIR = os.path.join(PLUGIN_DIR, 'payloads')

REQUIRED_ABILITY_FIELDS = {'id', 'name', 'tactic', 'technique'}


class TestElasticatSecurity:
    """Tests that elasticat.py has timeout on all requests calls."""

    def _get_source(self):
        path = os.path.join(PAYLOADS_DIR, 'elasticat.py')
        with open(path) as f:
            return f.read()

    def test_elasticat_exists(self):
        path = os.path.join(PAYLOADS_DIR, 'elasticat.py')
        assert os.path.isfile(path), 'elasticat.py payload not found'

    def test_elasticat_is_valid_python(self):
        source = self._get_source()
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f'elasticat.py has syntax error: {e}')

    def test_elasticat_requests_have_timeout(self):
        source = self._get_source()
        tree = ast.parse(source)
        requests_methods = {'get', 'post', 'put', 'delete', 'patch', 'head'}
        missing = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                is_requests_call = False
                if isinstance(func, ast.Attribute) and func.attr in requests_methods:
                    if isinstance(func.value, ast.Name) and func.value.id == 'requests':
                        is_requests_call = True
                if is_requests_call:
                    keyword_names = [kw.arg for kw in node.keywords]
                    if 'timeout' not in keyword_names:
                        line = getattr(node, 'lineno', '?')
                        missing.append(f'line {line}: requests.{func.attr}()')
        if missing:
            pytest.fail(
                f'elasticat.py has requests calls without timeout: {"; ".join(missing)}'
            )

    def test_elasticat_no_verify_false(self):
        source = self._get_source()
        matches = re.findall(r'verify\s*=\s*False', source)
        if matches:
            pytest.fail(
                f'elasticat.py uses verify=False ({len(matches)} occurrence(s)). '
                'SSL verification should not be disabled.'
            )


class TestResponseAbilitiesYAML:
    """Tests that response abilities YAML files are valid."""

    @staticmethod
    def _collect_yaml_files():
        pattern = os.path.join(ABILITIES_DIR, '**', '*.yml')
        return glob.glob(pattern, recursive=True)

    def test_abilities_directory_exists(self):
        assert os.path.isdir(ABILITIES_DIR), 'abilities directory not found'

    def test_at_least_one_ability_exists(self):
        files = self._collect_yaml_files()
        assert len(files) > 0, 'No ability YAML files found'

    def test_all_abilities_are_parseable(self):
        for yml_file in self._collect_yaml_files():
            with open(yml_file) as f:
                try:
                    data = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    pytest.fail(f'Failed to parse {yml_file}: {e}')
                assert data is not None, f'{yml_file} is empty'

    def test_all_abilities_have_required_fields(self):
        for yml_file in self._collect_yaml_files():
            with open(yml_file) as f:
                data = yaml.safe_load(f)
            if not isinstance(data, list):
                data = [data]
            for ability in data:
                for field in REQUIRED_ABILITY_FIELDS:
                    assert field in ability, (
                        f'{yml_file}: ability missing required field "{field}"'
                    )

    def test_ability_ids_are_unique(self):
        seen_ids = {}
        for yml_file in self._collect_yaml_files():
            with open(yml_file) as f:
                data = yaml.safe_load(f)
            if not isinstance(data, list):
                data = [data]
            for ability in data:
                aid = ability.get('id')
                if aid in seen_ids:
                    pytest.fail(
                        f'Duplicate ability id {aid} in {yml_file} and {seen_ids[aid]}'
                    )
                seen_ids[aid] = yml_file


class TestResponseHook:
    """Tests that hook.py loads correctly."""

    def test_hook_module_loads(self):
        hook_path = os.path.join(PLUGIN_DIR, 'hook.py')
        assert os.path.isfile(hook_path), 'hook.py not found'
        tree = ast.parse(open(hook_path).read())
        top_level_names = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert 'enable' in top_level_names, 'hook.py must define an enable() function'

    def test_hook_has_name_and_description(self):
        hook_path = os.path.join(PLUGIN_DIR, 'hook.py')
        source = open(hook_path).read()
        tree = ast.parse(source)
        assigned_names = [
            node.targets[0].id
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
        ]
        assert 'name' in assigned_names, 'hook.py should assign a name variable'
        assert 'description' in assigned_names, 'hook.py should assign a description variable'
