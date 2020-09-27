import json
import logging

import yaml

logger = logging.getLogger()


class FileFormatError(Exception):
    """Custom exception when a file format not supported by the module passed by the client.
    """

    def __init__(self, path, msg=None):
        if not msg:
            msg = "The given config file format is not supported by this module: {0}".format(path)
        super(FileFormatError, self).__init__(msg)
        self.path = path
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class ConfigManager(object):
    default_source_file = 'config.yaml'
    cfg_path = None

    def __init__(self, config_file_path=default_source_file):
        """Create and initialize a ConfigManager object.
            parameters:
                config_file_path - Path of the configuration file.
        """

        self.cfg_path = config_file_path
        self.attribute_dict = None
        self.load_config()

    def __getattr__(self, attr):
        return self.attribute_dict[attr]

    def load_config(self):
        if self.cfg_path.endswith(".yaml"):
            self.load_yaml_file()
        elif self.cfg_path.endswith(".json"):
            self.load_json_file()
        else:
            logger.warning("The given config file format is not supported by this module: %s", self.cfg_path)
            raise FileFormatError(self.cfg_path)

    def load_yaml_file(self):
        try:
            entries = yaml.load(self.load_file_data(), Loader=yaml.FullLoader) if self.load_file_data() else None
            if entries:
                self.attribute_dict = AttributeDict(**entries)
        except yaml.YAMLError as exception:
            logger.warning("Error loading YAML file : %s", exception)
            raise

    def load_json_file(self):
        try:
            entries = json.loads(self.load_file_data()) if self.load_file_data() else None
            if entries:
                self.attribute_dict = AttributeDict(**entries)
        except ValueError as exception:
            logger.warning("Error loading Json file : %s", exception)
            raise

    def load_file_data(self):
        data = []
        try:
            with open(self.cfg_path, 'r') as config_file:
                data = config_file.read()
        except (OSError, IOError) as exception:
            logger.warning(
                "Error(%s) reading the file %s : %s", str(exception.errno), self.cfg_path, exception.strerror)
            raise
        return data


class AttributeDict(object):
    """
    A class to convert a nested Dictionary into an object with key-values
    accessibly using attribute notation (AttributeDict.attribute) instead of
    key notation (Dict["key"]). This class recursively sets Dicts to objects,
    allowing you to recurse down nested dicts (like: AttributeDict.attr.attr)
    """

    def __init__(self, **entries):
        self.add_entries(**entries)

    def add_entries(self, **entries):
        for key, value in entries.items():
            if type(value) is dict:
                self.__dict__[key] = AttributeDict(**value)
            else:
                self.__dict__[key] = value

    def __getitem__(self, key):
        """
        Provides dict-style access to attributes
        """
        return getattr(self, key)
