import os
import sys
import argparse
import ConfigParser
import json
import copy
import collections
from pprint import pprint
from util import *
import logging
logger = logging.getLogger(__name__)

class ConfigHandler():
    '''
    This class handles config files used to import and execute
    Galaxy workflows that are containerized in Singularity containers.
    '''
    def __init__(self, config_file):
        '''
        Parse the import configuration file and return the import configuration.
        '''
        self.config_file = config_file
        self.config = self.parse_config_file(config_file)


    def parse_config_file(self, config_file):
        '''
        Parse a config file.
        This function first checks if the specified file exists and parses the file afterwards.
        '''
        # Check if specified configuration file exists
        logger.info("Check if specified configuration file exists")
        if not os.path.isfile(config_file):
            logger.error("Specified configuration file does not exist: %s", config_file)
            exit(1)

        # Parse the configuration file
        logger.info("Parse configuration file")
        try:
            config = ConfigParser.RawConfigParser()
            config.read(config_file)
        except:
            logger.error("Error during parsing specified configuration file: %s", config_file)
            exit(1)
        return config


    def flatten_json_dict(self, d, parent_key='', sep='|'):
        '''
        Flattens a python dictionary. The keys are concatenated using 'sep' as seperator.
        This function takes also nested dicts/lists into account. These nested dicts/objects are usually represented as strings
        and parsed by the json module before the function recurs.
        '''
        items = []
        for k, v in d.iteritems():
            new_key = parent_key + sep + k if parent_key else k
            # Check if the value is a non empty string and it's a dictionary after decoding
            if isinstance(v, basestring) and v and any(i in v for i in ('{','[')) and isinstance(json.loads(v), collections.MutableMapping):
                items.extend(self.flatten_json_dict(json.loads(v), new_key, sep=sep).items())
            # Sometimes you do not need to decode a string because the value is a dict ... among others this is the case for runtime parameters
            elif isinstance(v, collections.MutableMapping):
                items.extend(self.flatten_json_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)


    def unflatten(d, sep='|'):
        '''
        Unflatten a dictionary
        e.g. unflatten({'a' : 0, 'c|d' : 1)) -> {'a' : 0, 'c' : {'d' : 1}}
        '''
        resultDict = dict()
        for key, value in d.iteritems():
            parts = key.split(sep)
            d = resultDict
            for part in parts[:-1]:
                if part not in d:
                    d[part] = dict()
                d = d[part]
            d[parts[-1]] = value
        return resultDict


    def filter_runtime_params(self, param_dict):
        '''
        Filter runtime parameters for a workflow step from a parameter dictionary.
        This returns a list of runtime parameters. Each entry is of the form x|y|..,
        whereas x,y and other parts of the string represents the param dict that the Galaxy API (and therefore bioblend) expects.
        x|y|... will be translated to an dictionary of the form: {x: {y: ...}.
        '''
        # Flatten the parameter dictionary dictionary
        flattened_param_dict = self.flatten_json_dict(param_dict)
        # Get the runtime parameters
        return ["|".join(key.split('|')[0:-1]) for key, value in flattened_param_dict.iteritems() if value == 'RuntimeValue']


    def get_input_connections(self, step_desc):
        '''
        Returns the names of the input_connections of a workflow step.
        These input_connections are runtime parameters. The input_connections are removed from the result of filter_input_params()
        because the user cannot change them
        '''
        return step_desc['input_connections'].keys()


    def get_runtime_params(self, step_desc):
        '''
        Get all runtime parameters from the description of a workflow step, but exclude input_connections.
        Uses filter_runtime_params to get all runtime parameters and get_input_connections to get the input connections.
        '''
        param_dict = json.loads(step_desc['tool_state'])
        runtime_params = self.filter_runtime_params(param_dict)
        input_connections = self.get_input_connections(step_desc)
        return list(set(runtime_params) - set(input_connections))


    def create_exec_config(self, wf_handler, user_api_key, user_password):
        '''
        Create an execution configuration file for the given workflow. Adopt values from the import config like the container filename.
        The key aspect of the execution configuration file is to specifiy input files for the workflows and give a user the possibility to
        set (runtime) parameters of the workflow. 
        '''
        # Create ConfigParser for the execute configuration
        # This ConfigParser will be returned by this function
        execute_config = ConfigParser.RawConfigParser()

        # General section
        execute_config.add_section('General')
        execute_config.set('General', 'container_file', self.config.get('General', 'container_file'))
        execute_config.set('General', 'galaxy_url', self.config.get('General', 'galaxy_url_dest'))
        execute_config.set('General', 'workflow_id', wf_handler.imported_workflow_id)

        # User section
        execute_config.add_section('User')
        # The user mail is needed for the execution because the execute script has to create a folder in /galaxy_tmp with the user mail as name
        execute_config.set('User', 'user_mail', self.config.get('User', 'user_mail'))
        execute_config.set('User', 'user_api_key', user_api_key)
        execute_config.set('User', 'user_password', user_password)

        # Data section
        execute_config.add_section('Data')
        execute_config.set('Data', 'input_directory', '/input')
        execute_config.set('Data', 'output_directory', '/output')
        execute_config.set('Data', 'tmp_directory', '/tmp')
	execute_config.set('Data', 'mount_input_directory', 'True')

        steps = wf_handler.wf_description['steps']

        # Sort the steps by their ordered index such
        # that the corresponding parameters appear ordered in the config file
        ordered_index = steps.keys()
        ordered_index.sort(key=int)

        # Iterate over the workflow steps
        for index in ordered_index:
            step_desc = steps[index]

            # Basic step information
            step_annotation = step_desc['annotation']
            step_uuid = step_desc['uuid']
            step_name = step_desc['name']
            step_type = step_desc['type']

            # Check if step_uuid is None, this can be the case (for older workflow files?)
            if step_uuid == "None":
                step_section_name = str(step_desc['id'])
            else:
                step_section_name = step_uuid

            # Comments for this step (makes the config file more readable for the user)
            annotation_comment = '; Annotation: ' + step_annotation
            name_comment = '; Name: ' + step_name

            # Process step
            if step_desc['type'] == 'data_input':
                # Add section for this step
                execute_config.add_section(step_section_name)
                execute_config.set(step_section_name, '; Name',  step_name)
                execute_config.set(step_section_name, '; Annotation', step_annotation)
                execute_config.set(step_section_name, 'step_type', step_type)
                execute_config.set(step_section_name, 'filename', '# INSERT_FILENAME #')
                execute_config.set(step_section_name, 'galaxy_file_type', 'auto')
            else:
                # Check if there are any runtime parameters for this step
                # A user has to specify the runtime parameters if the wants to execute the workflow
                runtime_params = self.get_runtime_params(step_desc)


                # Write the runtime parameters to the execute config file
                if len(runtime_params) > 0:
                    execute_config.add_section(step_section_name)
                    execute_config.set(step_section_name, '; Name',  step_name)
                    execute_config.set(step_section_name, '; Annotation', step_annotation)
                    execute_config.set(step_section_name, 'step_type', step_type)
                    # Add a line for each runtime parameter
                    for param in runtime_params:
                        execute_config.set(step_section_name, param, '# INSERT VALUE')

        # Return the final execution config
        return execute_config


    def parse_workflow_input(self):
        '''
        Parse workflow input steps from the config file.
        This results in a dictionary, whereas a
        - key is the name of a Galaxy workflow input step (specified by either uuid or id)
        - value is a dictionary with two keys describing the path to the input file and the corresponding galaxy data type
        '''
        # Parse the import files
        workflow_input = {}
        input_dir = self.config.get('Data', 'input_directory')
        for section in self.config.sections():
            if section not in ["General", "User", "Data"]:
                workflow_input[section] = {}
                for (key, val) in self.config.items(section):
                    workflow_input[section][key] = val
        # Check that every input file is present in the input_directory
        for step, input  in workflow_input.iteritems():
            if input['step_type'] == 'data_input':
                input_file = input['filename']
                if os.path.isabs(input_file):
                    input_file_abs = input_file
                else:
                    input_file_abs = os.path.join(input_dir, input_file)
                if not os.path.isfile(input_file_abs):
                    # Just check if the input files are mounted to the container
                    logger.error("Input file for input step %s does not exist: %s", step, input_file_abs)
                    return None
            else:
                continue
        return workflow_input



    def dump_config_to_file(self, config, dest):
        '''
        Write a configuration object to file.
        config is a ConfigParser.RawConfigParser() object
        '''
        print "dump execute config to " + dest
        with open(dest, 'wb') as configfile:
            config.write(configfile)

