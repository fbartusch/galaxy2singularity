#! /usr/bin/env python

# Given a Galaxy workflow (.ga) files,
# create a config files that can be used to execute the encapsulated
# workflow by the execute_workflow.py script

import os
import sys
import argparse
import ConfigParser
import json
import copy
import collections
from pprint import pprint

def flatten_json_dict(d, parent_key='', sep='|'):
    '''
    Flattens a python dictionary. The keys are concatenated using 'sep' as seperator.
    This function takes also nested dicts/lists into account. These nested dicts/objects are usually represented as strings
    and parsed by the json module before the function recurs.
    '''
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        # Check if the value is a non empty string and it's a dictionary after decoding
        if isinstance(v, basestring) and v and any(i in v for i in ('{','[')) and isinstance(json.loads(v), collections.MutableMapping):
            items.extend(flatten_json_dict(json.loads(v), new_key, sep=sep).items())
        # Sometimes you do not need to decode a string because the value is a dict ... among others this is the case for runtime parameters
        elif isinstance(v, collections.MutableMapping):
            items.extend(flatten_json_dict(v, new_key, sep=sep).items())
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

def filter_runtime_params(param_dict):
    '''
    Filter runtime parameters for a workflow step from a parameter dictionary.
    This returns a list of runtime parameters. Each entry is of the form x|y|..,
    whereas x,y and other parts of the string represents the param dict that the Galaxy API (and therefore bioblend) expects.
    x|y|... will be translated to an dictionary of the form: {x: {y: ...}.
    '''
    # Flatten the parameter dictionary dictionary
    flattened_param_dict = flatten_json_dict(param_dict)
    # Get the runtime parameters
    return ["|".join(key.split('|')[0:-1]) for key, value in flattened_param_dict.iteritems() if value == 'RuntimeValue']


def get_input_connections(step_desc):
    '''
    Returns the names of the input_connections of a workflow step.
    These input_connections are runtime parameters. The input_connections are removed from the result of filter_input_params()
    because the user cannot change them
    '''
    return step_desc['input_connections'].keys()


def get_runtime_params(step_desc):
    '''
    Get all runtime parameters from the description of a workflow step, but exclude input_connections.
    Uses filter_runtime_params to get all runtime parameters and get_input_connections to get the input connections.
    '''
    param_dict = json.loads(step_desc['tool_state'])
    runtime_params = filter_runtime_params(param_dict)
    input_connections = get_input_connections(step_desc)
    return list(set(runtime_params) - set(input_connections)) 

# User has to specify
# - the config file that was used to import the workflow
# - the filename of the generated config file
# - the Galaxy workflow (.ga) file

# Parse the CL arguments
parser = argparse.ArgumentParser(description='Run Galaxy workflow using the Galaxy API.')
parser.add_argument("-i", "--import-config", type=str, required=True)
parser.add_argument("-w", "--workflow", type=str, required=True)
parser.add_argument("-d", "--output-dir", type=str, required=True)
parser.add_argument("-e", "--execute-config", type=str, required=True)

args = parser.parse_args()
import_config_file = args.import_config
workflow_file = args.workflow
output_dir = args.output_dir
execute_config_name = args.execute_config

# Parse the configuration file
import_config = ConfigParser.RawConfigParser(allow_no_value=True)
import_config.read(import_config_file)

# Create ConfigParser for the execute configuration
execute_config = ConfigParser.RawConfigParser()

# General section
execute_config.add_section('General')
execute_config.set('General', 'container_file', import_config.get('General', 'container_file'))
execute_config.set('General', 'container_shasum_file', import_config.get('General', 'container_shasum_file'))
execute_config.set('General', 'galaxy_url_dest', import_config.get('General', 'galaxy_url_dest'))
execute_config.set('General', 'workflow_id', import_config.get('General', 'workflow_id'))

# User section
execute_config.add_section('User')
# The user mail is needed for the execution because the execute script has to create a folder in /galaxy_tmp with the user mail as name
execute_config.set('User', 'user_mail', import_config.get('User', 'user_mail'))
execute_config.set('User', 'user_api_key', import_config.get('User', 'user_api_key'))
execute_config.set('User', 'user_password', import_config.get('User', 'user_password'))

# Data section
execute_config.add_section('Data')
execute_config.set('Data', 'input_directory', '# INSERT_PATH #')
execute_config.set('Data', 'output_directory', '# INSERT_PATH #')
execute_config.set('Data', 'tmp_directory', '/tmp')

# Process workflow .ga file
with open(workflow_file) as workflow_handler:
    # Open workflow .ga file
    workflow = json.load(workflow_handler)
    steps = workflow['steps']

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

        # Comments for this step (makes the config file more readable for the user)
        annotation_comment = '; Annotation: ' + step_annotation
        name_comment = '; Name: ' + step_name

        # Process step
        if step_desc['type'] == 'data_input':
            # Add section for this step
            execute_config.add_section(step_uuid)
            execute_config.set(step_uuid, '; Name',  step_name)
            execute_config.set(step_uuid, '; Annotation', step_annotation)
            execute_config.set(step_uuid, 'step_type', step_type)
            execute_config.set(step_uuid, 'filename', '# INSERT_FILENAME #')
            execute_config.set(step_uuid, 'galaxy_file_type', 'auto')
        else:
            # Check if there are any runtime parameters for this step
            # A user has to specify the runtime parameters if the wants to execute the workflow
            runtime_params = get_runtime_params(step_desc)

            # Write the runtime parameters to the execute config file
            if len(runtime_params) > 0:
                execute_config.add_section(step_uuid)
                execute_config.set(step_uuid, '; Name',  step_name)
                execute_config.set(step_uuid, '; Annotation', step_annotation)
                execute_config.set(step_uuid, 'step_type', step_type)
                # Add a line for each runtime parameter
                for param in runtime_params:
                    execute_config.set(step_uuid, param, '# INSERT VALUE')

# Create full output path
execute_config_path = os.path.join(output_dir, execute_config_name)

with open(execute_config_path, 'wb') as configfile:
    execute_config.write(configfile)
