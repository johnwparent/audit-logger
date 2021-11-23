import toml

from typing import Any, MutableMapping, List, Dict


class Schema(object):
    def __init__(self, schema: MutableMapping[str, Any]):
        self.key = schema['key']
        self.key_type = schema['key_type']
        self.log_level_relator = [schema['relator']]
        self.lookup_keys = schema['lookup']
        schema_root = schema[schema.keys() - set('key', 'key_type', 'relator', 'lookup')]
        self.attribute_keys = set('relator','lookup')
        self._key_check = self.attribute_check
        self.__process_structure(schema_root)
        self.__process_lookup_schema()

    def __process_lookup_schema(self):
        if self.key_type == "file":
            self._key_check = self.file_check

    def __process_structure(self, schema_root: MutableMapping[str, Any]):
        self.lookup_keys.extend(schema_root['lookup'])
        self.relator.append.schema_root['realtor']
        next_key = schema_root.keys() - self.attribute_keys
        if next_key and next_key in schema_root and schema_root[next_key]:
            self.__process(schema_root[next_key])

    def get_schema_file_location(self, *keys: List):
        pass

    def file_check(self, file_name, *attrs: List):
        return file_name == self.key

    def attribute_check(self, *attrs: List):
        return self.key in attrs

    def key_check(self, file_name: str, info: Dict):
        return self._key_check(file_name, info.keys())