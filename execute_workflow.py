# This script runs a workflow using the Galaxy API

import os
import sys
import argparse
import ConfigParser
import time
import tempfile
import urllib
import shutil
import logging as log
import subprocess
import errno
import distutils.util
from urlparse import urlparse
from bioblend.galaxy import GalaxyInstance
from bioblend.galaxy.config import ConfigClient
from bioblend.galaxy.workflows import WorkflowClient
from bioblend.galaxy.tools import ToolClient
from bioblend.galaxy.toolshed import ToolShedClient
from bioblend.galaxy.histories import HistoryClient
from bioblend.galaxy.libraries import LibraryClient
from bioblend.galaxy.datasets import DatasetClient
from g2s.create_logger import create_logger
from g2s.checks import *
from g2s.util import *
from g2s.GalaxyHandler import GalaxyHandler
from g2s.WorkflowHandler import WorkflowHandler
from g2s.ConfigHandler import ConfigHandler

# Parse the CL arguments
parser = argparse.ArgumentParser(description='Run Galaxy workflow using the Galaxy API.')
parser.add_argument("-c", "--config", type=str, required=True)
parser.add_argument("-l", "--log", type=str, required=False, default="execute_workflow.log")
parser.add_argument("-i", "--interactive", action='store_true')

args = parser.parse_args()
config_file = args.config
log_file = args.log
interactive_mode = args.interactive

# Create logger
logger = create_logger(log_file=log_file, log_level=log.DEBUG)
logger.info("Parsed command line arguments")

# Parse general configuration
config_handler = ConfigHandler(config_file)
config = config_handler.parse_config_file(config_file)
wf_id = config.get('General', 'workflow_id')
galaxy_url = config.get('General', 'galaxy_url')
container_file = config.get('General', 'container_file')

# Parse input/output/tmp directories
mount_input_dir = distutils.util.strtobool(config.get('Data', 'mount_input_directory'))
input_dir = config.get('Data', 'input_directory')
output_dir = config.get('Data', 'output_directory')
tmp_dir = config.get('Data', 'tmp_directory')

# Parse user information (user of Galaxy in Container for whom the workflow is installed)
user_mail = config.get('User', 'user_mail')
user_api_key = config.get('User', 'user_api_key')

# Is the path to the container file valid?
if not os.path.isfile(container_file):
    logger.error("Container does not exist: %s", container_file)
    exit(1)
if not os.access(container_file, os.R_OK):
    logger.error("Container exists, but is not readable: %s", container_file)


# Is the input_directory valid and does it contain all needed input files?
if mount_input_dir:
    if not os.path.isdir(input_dir):
        logger.error("Specified input_directory does not exist: %s", input_dir)
        exit(1)
    # Parse workflow input files
    workflow_input = config_handler.parse_workflow_input()
    if not workflow_input:
        logger.error("No workflow input specified")
        exit(1)

# Is the output_directory valid? If it does not exist, create it!
if not os.path.isdir(output_dir):
    logger.info("Specified output_directory does not exist, try to create it: %s", output_dir)
    try:
        os.makedirs(output_dir)
    except:
        logger.error("Cannot create specified output_directory: %s", output_dir)

# Is the tmp_directory valid? Try to create the temporary directory for this session. If that does not work, the temporary directory specifide is not valid.
try:
    tempfile.tempdir = tmp_dir
    session_tmp_dir = tempfile.mkdtemp(prefix="galaxy2singularity_")
except IOError as e:
    logger.error("Cannot write to the specified tmp_directory: %s", tmp_directory)
    exit(1)

# Copy the integrated tools panel and the universe.sqlite into the tmp directory
tmp_bind = session_tmp_dir + ":/galaxy_tmp"
subprocess.call(["singularity", "exec", "--bind", tmp_bind, container_file, "cp", "/galaxy/integrated_tool_panel.xml", "/galaxy/database/universe.sqlite", "/galaxy_tmp"])

# Start Galaxy in daemon mode with binds to input, output und temporary directories
if mount_input_dir:
    input_bind = input_dir + ":/input,"
else:
    input_bind = ""
output_bind = output_dir +":/output,"
bind_dirs = input_bind + output_bind + tmp_bind

# Start Galaxy in the container
galaxy_handler = GalaxyHandler(galaxy_url, user_api_key, container_file=container_file)
galaxy_handler.start_container_galaxy(binds=bind_dirs)
if not galaxy_handler.initialize():
    logger.error("Error during initialization of GalaxyHandler for source Galaxy")
    exit(1)

# Create WorkflowHandler for the workflow
workflow_handler = WorkflowHandler(galaxy_handler, wf_id) 

# If interactive mode is enabled, stop here and wait until the user exits the script
if interactive_mode:
    logger.info("Entering interactive mode")
    pressed_key = ''
    while(pressed_key != 'q'):
        pressed_key = raw_input("Press 'q' to leave the interactive mode:\n")
    logger.info("Leave interactive mode")
    galaxy_handler.shutdown_galaxy(bind_dirs, tmp_dir)
    exit(0)

# Create a new history where the workflow outputs are saved
output_history_id = galaxy_handler.create_history('Output History')

# Create a library for the input files
library_id, folder_id = galaxy_handler.create_folder('Input Library', user_mail)

# Iterate over the files in the input directory and upload them to Galaxy's data Library: 'Input Library'
galaxy_handler.upload_workflow_input(workflow_input, library_id, folder_id, mount_input_dir, input_dir)

# Invoke the workflow
workflow_handler.invoke_workflow(workflow_input, output_history_id)

# Export the output history to the output directory
galaxy_handler.export_output_history(output_history_id, output_dir)

# Copy the exection configuration file to the output directory
shutil.copy2(config_file, output_dir)

# Shutdown Galaxy
galaxy_handler.stop_container_galaxy(bind_dirs, tmp_dir)
