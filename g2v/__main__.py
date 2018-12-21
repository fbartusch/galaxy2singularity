from __future__ import absolute_import, division, print_function
import os
import argparse
import docker
import json
import urllib2
import time
from bioblend.galaxy import GalaxyInstance
from bioblend.galaxy.users import UserClient
from bioblend.galaxy import GalaxyInstance
from bioblend.galaxy.config import ConfigClient
from bioblend.galaxy.workflows import WorkflowClient
from bioblend.galaxy.tools import ToolClient
from bioblend.galaxy.toolshed import ToolShedClient
from bioblend.galaxy.libraries import LibraryClient
from bioblend.galaxy.roles import RolesClient
from bioblend.galaxy.histories import HistoryClient
from bioblend.galaxy.datasets import DatasetClient

def main():

    parser = argparse.ArgumentParser(description='Containerize Galaxy workflows with Docker or Singularity.')

    parser.add_argument('-d', '--debug',
                        help="Use verbose logging to debug.", 
                        default=False, action='store_true')

    parser.add_argument('-q', '--quiet',
                        help="Suppress printed output", 
                        default=False, action='store_true')

    parser.add_argument('-v', '--version',
                        help="Print version information",
                        default=False, action='store_true')
      
    # Run modes
    #  provision: Provision Galaxy instance (container or VM) with a workflow
    #  execute:   Execute Workflow in a virtualized Galaxy instance 
    subparsers = parser.add_subparsers(help="Actions", title="Actions", dest="command")
    create_parser = subparsers.add_parser("create")
    provision_parser = subparsers.add_parser("provision")
    execute_parser = subparsers.add_parser("execute")

    # Options
    # Provision  
    #parser.add_argument("-c", "--config", type=str, required=True)
    default_galaxy_version = '18.09'
    create_parser.add_argument("--log", help="Specifies logging file", type=str, required=False, default="galaxyWF2Virt.log")
    create_parser.add_argument('-v', '--version', help="Install the specified Galaxy version (default: " + default_galaxy_version + ")")
    create_parser.add_argument('-w', '--workflow', help="Workflow to import into container")
    # Only one of the following options allowed
    create_group = create_parser.add_mutually_exclusive_group()
    create_group.add_argument('-d', '--docker', action='store_true', help="Create a Docker container with installed Galaxy")
    create_group.add_argument('-s', '--singularity', action='store_true', help="Create a Singularity container with installed Galaxy")
    create_group.add_argument('--vm', action='store_true', help="Create a Virtual Machine (VM) with installed Galaxy")
    #  Execute

    # Parse command line arguments
    args = parser.parse_args();

    # Check for valid Galaxy version.
    #TODO List of versions are equal the list of releases from https://github.com/galaxyproject/galaxy
    valid_galaxy_versions = ['16.01','16.04','16.07','16.10','17.01','17.05','17.09','18.01','18.05','18.09']
    #TODO Check for a valid version

    #TODO Create logger
    #log_file = args.log
    #log = create_logger(log_file=log_file, log_level=log.DEBUG)
    #log.info("Parsed command line arguments")

    # Use the correct subcommand
    if args.command == "create":
        if args.docker:
            client = docker.from_env()

            client.images.pull('bgruening/galaxy-stable:17.09')
            client.images.list()

            # Move everything from here to the 'provision' part
            provision_env = {'GALAXY_CONFIG_ADMIN_USERS': 'admin@galaxy.org',
                             'GALAXY_CONFIG_MASTER_API_KEY': '83D4jaba7330aDKHkakjGa937'}

            cont = client.containers.run("bgruening/galaxy-stable:17.09", detach=True, ports={'80/tcp': 8080, '21/tcp': 8021, '22/tcp': 8022}, environment=provision_env)
            
            instance = GalaxyInstance(url='127.0.0.1:8080', key='83D4jaba7330aDKHkakjGa937')
            
            user_client = UserClient(instance)
            workflow_client = WorkflowClient(instance)
            tool_client = ToolClient(instance)
            toolshed_client = ToolShedClient(instance)
            library_client = LibraryClient(instance)
            roles_client = RolesClient(instance)
            history_client = HistoryClient(instance)
            dataset_client = DatasetClient(instance)

            # Wait until Galaxy instance started
            response = None
            t = 0
            while not response:
                try:
                    response = urllib2.urlopen('http://127.0.0.1:8080').getcode() # returns 200 if galaxy is up
                except:
                    if t > 600:
                        print("Galaxy is not up after 4 minutes. Probably something went wrong.")
                        exit(1)
                    else:
                        print(response)
                        print("Galaxy is not up yet ... waiting 10 seconds")
                        t = t + 10
                        time.sleep(10)
                        response = None
                        continue

            wf_file = "/mnt/data/own_projects/galaxy2singularity/test/galaxy101/Galaxy-Workflow-galaxy101.ga"
            #wf_file = "/mnt/data/own_projects/galaxy2singularity/test/galaxy101/Galaxy-Workflow-galaxy101_18.05.ga"

            with open(wf_file) as wf_file_handler:
                wf_description = json.load(wf_file_handler)

            steps = wf_description['steps']
            for index, step in steps.iteritems():
                print("Install tool for workflow step ", index)
                # Ignore input steps
                if step['type'] == 'data_input':
                    print("Ignore: Data input step")
                    continue
                # Ignore already installed tools.
                # Ignore, IFF the tool version is exactly the same as defined in the workflow description
                # TODO iterate over tool_details list
                tool_details = tool_client.get_tools(step['tool_id'])
                print(tool_details)
                if tool_details != [] and tool_details[0]['version'] == step['tool_version'] :
                    print("Ignore: Tool is already installed")
                    continue
                # Build-in tools (no repo instormation) cannot be installed in other versions
                if tool_details != [] and tool_details[0]['version'] != step['tool_version']:
                    try:
                        repo = step['tool_shed_repository']
                    except:
                        print("Error: Tool already installed, but in another version. Also no Toolshed information is available for this tool. Maybe you chose the wrong Galaxy version")
                        exit(1)
                #tool_shed_repository ...
                # Install the tool with all dependencies
                repo = step['tool_shed_repository']
                tool_shed_url = 'http://' + repo['tool_shed']
                name = repo['name']
                owner = repo['owner']
                changeset_revision = repo['changeset_revision']
                toolshed_client.install_repository_revision(
                    tool_shed_url = tool_shed_url,
                    name = name,
                    owner = owner,
                    changeset_revision = changeset_revision,
                    install_tool_dependencies = True,
                    install_repository_dependencies = True,
                    install_resolver_dependencies = True,
                    new_tool_panel_section_label="Imported Workflow")
            

            #TODO Create new user of the Galaxy instance. This user will be used to import the workflow.
            wf_user = user_client.create_local_user('wf_user', 'wf_user@test.org', 'password')
            print(wf_user)
            wf_user_api_key = user_client.create_user_apikey(wf_user['id'])


            #TODO Import workflow using the new workflow user
            wf_user_instance = GalaxyInstance(url='127.0.0.1:8080', key=wf_user_api_key)
            wf_user_workflow_client = WorkflowClient(wf_user_instance)

            import_result = wf_user_workflow_client.import_workflow_dict(wf_description)

            # Create new admin user in the container.
        elif args.singularity:
            exit(0)
    elif args.command  == "provision":
        print("Action: Provision")
    elif args.command == "execute":
        print("Action: Execute")
    else:
        print("Unknown Action")
    exit(1)
    
    # 

if __name__ == '__main__':
    main()
