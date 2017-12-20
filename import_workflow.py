import os
import sys
import argparse
import urllib
import time
import subprocess
import string
import random
import json
import shutil
import ConfigParser
import logging as log
from urlparse import urlparse
from bioblend.galaxy import GalaxyInstance
from bioblend.galaxy.config import ConfigClient
from bioblend.galaxy.workflows import WorkflowClient
from bioblend.galaxy.tools import ToolClient
from bioblend.galaxy.toolshed import ToolShedClient
from bioblend.galaxy.libraries import LibraryClient
from bioblend.galaxy.roles import RolesClient
from g2s.create_logger import create_logger
from g2s.checks import *
from g2s.util import *
from g2s.GalaxyHandler import GalaxyHandler
from g2s.WorkflowHandler import WorkflowHandler
from g2s.ConfigHandler import ConfigHandler

# Parse CL arguments
parser = argparse.ArgumentParser(description='Export Galaxy workflow into another Galaxy instance.')
parser.add_argument("-c", "--config", type=str, required=True)
parser.add_argument("-l", "--log", type=str, required=False, default="import_workflow.log")

args = parser.parse_args()
config_file = args.config
log_file = args.log

# Create logger
logger = create_logger(log_file=log_file, log_level=log.DEBUG)
logger.info("Parsed command line arguments")

# Parse the config file
config_handler = ConfigHandler(config_file)
config = config_handler.parse_config_file(config_file)
container_file = config.get('General', 'container_file')
galaxy_url_dest = config.get('General', 'galaxy_url_dest')
master_api_key_dest = config.get('General', 'master_api_key_dest')

# The tool section name is optional. If it's missing or the value is set to none the tools are installed to the default tool section
try:
    tool_section_name = config.get('General', 'tool_section_name')
    if tool_section_name.lower() == 'none':
        tool_section_name = None
except:
    # Value is not specified in the config file
    tool_section_name = None

# Handle specified workflows to import
# Check if user specified workflow .ga-files.
# If that does not exist, try to get information about the Source Galaxy instance
try:
    logger.info("Try to parse specified workflow filenames")
    wf_files = json.loads(config.get('General', 'workflow_files'))
    import_from_galaxy = False
    logger.info("Parsed workflow filenames: %s", wf_files)
    logger.info("Check if workflow files exist")
    for wf_file in wf_files:
        if not check_file(wf_file):
            logger.error("Specified workflow file does not exist: %s", wf_file)
            exit(1)
except ConfigParser.NoOptionError as e:
    logger.info("No workflow files specified. Try to parse Source Galaxy information")
    wf_files = None
    import_from_galaxy = True
    try:
        wf_ids = json.loads(config.get('General', 'workflow_ids'))
        galaxy_url_source = config.get('General', 'galaxy_url_source')
        api_key_source = config.get('General', 'api_key_source')
        logger.info("Parsed Source Galaxy information")
    except:
        logger.error("Neither specified workflow file nor Source Galaxy information")
        exit(1)

# Parse user information
user_name = config.get('User', 'user_name')
user_mail= config.get('User', 'user_mail')
# Create random password. The password is not required later because the stored API key is used.
user_password = ''.join(random.SystemRandom().choice(string.letters + string.digits) for _ in range(6))

# Check if specified container file is valid
logger.info("Check if specified container file exists ...")
if not check_file(container_file):
    logger.error("Specified container file does not exist: %s", container_file)
    exit(1)

# Swap to Galaxy import config
# Usually the Galaxy import config should be in place, but maybe someone is running this script
# after a succesful import and therefore the Galaxy execute config is installed
logger.info("Replace Container Galaxy configuration file with the configuration that enables the workflow import")
subprocess.call(["sudo", "singularity", "exec", "-w", container_file, "/bin/sh", "/g2s/scripts/swap_to_galaxy_import_config.sh"])

# Create GalaxyHandlers for the containerized Galaxy (and eventually the source Galaxy)
dest_handler = GalaxyHandler(galaxy_url_dest, master_api_key_dest, container_file=container_file)

# Startup Galaxy in the container
logger.info("Start Galaxy in container as daemon")
dest_handler.start_container_galaxy(writable=True)
logger.info("Galaxy in the container is up")
logger.info("Initialize GalaxyHandler")
if not dest_handler.initialize():
    logger.error("Error during initialization of GalaxyHandler for Container Galaxy.")
    exit(1)


# Create GalaxyHandler for source Galaxy
if import_from_galaxy:
    source_handler = GalaxyHandler(galaxy_url_source, api_key_source)
    if not source_handler.initialize():
        logger.error("Error during initialization of GalaxyHandler for source Galaxy")
        exit(1)


# Check if the workflows to import are accessible
wf_handlers = []
if import_from_galaxy:
    for wf_id in wf_ids:
        # Create a WorkflowHandler
        logger.log("Create WorkflowHandler for workflow: %s", wf_id)
        wf_handler = WorkflowHandler(source_galaxy=source_handler, wf_id=wf_id)
        wf_handlers.append(wf_handler)
        logger.log("Try to get the workflow description from source Galaxy")
        if not wf_handler.get_wf_description():
            logger.error("Can't get workflow description from source Galaxy")
            exit(1)
else:
    for wf_file in wf_files:
        # Create a WorkflowHandler
        logger.info("Create WorkflowHandler for workflow: %s", wf_file)
        wf_handler = WorkflowHandler(wf_file=wf_file)
        wf_handlers.append(wf_handler)
        logger.info("Try to read workflow description from file")
        if not wf_handler.get_wf_description():
            logger.error("Can't read workflow description from file")
            exit(1)

# Create new user in Galaxy
# TODO option for making the user admin?
logger.info("Create new user in Container Galaxy instance")
user_id, user_api_key = dest_handler.create_user(user_name, user_mail, user_password)

# Now create a new GalaxyHandler for the new user
logger.info("Create new GalaxyHandler for newly created user")
user_dest_handler = GalaxyHandler(galaxy_url_dest, user_api_key)
if not user_dest_handler.initialize():
    logger.error("Cannot initialize GalaxyHandler for newly created user")
    exit(1)

# Import the workflows
for wf_handler in wf_handlers:
    # Install tools with master API-key GalaxyHandler
    wf_handler.install_wf_tools(dest_handler, tool_section_name="Imported Workflows")
    # Import workflow as 'normal' user
    wf_handler.import_workflow_to_galaxy(user_dest_handler)

# Create input library
logger.info("Create Galaxy data library for input data")
if not dest_handler.create_input_library("Input Library", user_id):
    logger.error("Cannot create Galaxy data library")    

# stop galaxy daemon
logger.info("Try to stop Galaxy daemon")
dest_handler.stop_container_galaxy(sudo=True)
time.sleep(10)

# For each workflow, place the .ga file in the container,
# generate a configuration file for later execution and place it also in the container
# Create the temporary directory
tmp_dir = '/tmp/.g2s/'
logger.info("Create temporary directory: %s", tmp_dir)
if not os.path.exists(tmp_dir):
    try:
        os.makedirs(tmp_dir)
    except:
        logger.error("Cannot create temporary directory: %s", tmp_dir)
        exit(0)

for wf_handler in wf_handlers:
    # Get the workflow name and create a name for the subdirectory in the container
    wf_name = wf_handler.get_wf_name()
    wf_subdir_name = format_filename(wf_name)

    # If we import from a Galaxy instance, we have to
    # create a workflow file first from the workflow description
    # Do this in /tmp such that the file is accessible from inside the container
    if import_from_galaxy:
        wf_file = '.Galaxy-Workflow-' + wf_subdir_name + '.ga'
        wf_file = os.path.join(tmp_dir, wf_file)
        logger.info("Dump workflow dict to workflow file: %s", wf_file)
        with open(wf_file, 'w') as fp:
            json.dump(wf_description, fp, sort_keys=True, indent=4)
            time.sleep(1)
    else:
        # User specified the absolute path in the import config already
        wf_file = wf_handler.wf_file
        # Copy the file to the temporary directory such that it's visible to the container
        tmp_wf_file = os.path.join(tmp_dir, os.path.split(wf_file)[1])
        shutil.copyfile(wf_file, tmp_wf_file)
        wf_file = tmp_wf_file
    
    # Generate the execution configuration file
    logger.info("Create execute config file for workflow: %s", wf_name)
    wf_exec_config = config_handler.create_exec_config(wf_handler, user_api_key, user_password)
    if import_from_galaxy:
        wf_exec_config_file = wf_subdir_name + '.ini'
    else:
        # Name the config file in the same way as the workflow file
        wf_exec_config_file = os.path.basename(wf_file) + '.ini'
    wf_exec_config_file = os.path.join(tmp_dir, wf_exec_config_file)
    config_handler.dump_config_to_file(wf_exec_config, wf_exec_config_file)
    time.sleep(1)

    # For each workflow to import, create a subdirectory in the container
    # and place the workflow file as well as a sample execution configuration in that subdirectory
    # This does not work if the workflow file and the config are in the user's home directory, because it's not mounted to the container. Use copy instead.
    subprocess.call(["sudo", "singularity", "exec", "-w",  container_file, "/g2s/scripts/create_workflow_dir.sh", wf_subdir_name, wf_file, wf_exec_config_file])
    time.sleep(5)

    # TODO write a script that copies the execution configuration of a workflow to the current directory (retrieave the encapsulated information in the container)
    # TODO change metadata of the container such that one can see what workflows are available in the container
    # Take a look onto https://schema.datacite.org/meta/kernel-4.1/

# Remove the temporary directory
logger.info("Remove temporary directory: %s", tmp_dir)
try:
    shutil.rmtree(tmp_dir)
except:
    logger.error("Cannot remove temporary directory: %s", tmp_dir)

# Add the new user to the admin_users in the execute config file
# The new user has to be in admin_users during execution because he is then able to upload files to Galaxy's data library directly from any disc location (here: /input in the container).
# Otherwise one has to tweek the structure of the input bind point such that input directory bindsto /input/<user_mail> in the container
# See: https://galaxyproject.org/data-libraries/#administration -> Import configuration, User folder
# By adding the user to admin_users we don't have to create the <user_mail> subdirectory and the integration with the provided data much easier
logger.info("Add admin_user in container Galaxy")
subprocess.call(["sudo", "singularity", "exec", "-w", container_file, "/g2s/scripts/add_admin_user.sh", user_mail])

time.sleep(5)

# Replace the 'import' version with the 'execute' version
# The 'execute' version enables Galaxy to run inside the container without modifying any file inside the container
logger.info("Replace Container Galaxy configuration file with the configuration that enables the workflow execution")
subprocess.call(["sudo", "singularity", "exec", "-w", container_file, "/bin/sh", "/g2s/scripts/swap_to_galaxy_execute_config.sh"])

time.sleep(5)

logger.info("Workflow import succeeded")
