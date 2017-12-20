import os
import time
import subprocess
import logging
import urllib
import shutil
from g2s.checks import check_url
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

from bioblend import ConnectionError
logger = logging.getLogger(__name__)

#TODO make class GalaxyHandler that stores also clients that are needed to access workflows, user, ....
#store also url, api-key, container_filename, ....

class GalaxyHandler:
    '''
    This class represents a Galaxy instance and provides functions to interact with that instance.
    '''
    def __init__(self, url, api_key, container_file=None):
        self.url = url
        self.api_key = api_key
        self.container_file = container_file
       
        # Bioblend GalaxyInstance
        self.instance = None
        # Bioblend Clients
        self.user_client = None
        self.config_client = None
        self.workflow_client = None
        self.tool_client = None
        self.toolshed_client = None
        self.library_client = None
        self.roles_client = None
        self.history_client = None
        self.dataset_client = None

    def start_container_galaxy(self, writable=False, binds=None):
        '''
        Run a containerized Galaxy instance.
        '''
        with open(os.devnull, 'w') as FNULL:
            if writable:
                subprocess.call(["sudo", "singularity", "exec", "-w", self.container_file, "sh", "/galaxy/run.sh", "--daemon"], stdout=FNULL)
            elif binds:
                subprocess.call(["singularity", "exec", "--bind", binds, self.container_file, "sh", "/galaxy/run.sh","--log-file", "/output/paster.log", "--pid-file", " /output/paster.pid", "--daemon"], stdout=FNULL, stderr=subprocess.STDOUT)
            else:
                subprocess.call(["singularity", "exec", self.container_file, "sh", "/galaxy/run.sh", "--daemon"], stdout=FNULL)
    
            # Wait until the Galaxy instance is available but do not wait longer than 1 minute
            response = None
            t = 0
            while not response:
                try:
                    response = urllib.urlopen(self.url).getcode() # returns 200 if galaxy is up
                except:
                    if t > 60:
                        logger.error("Galaxy is not up after 1 minute. Something went wrong. Maybe the container is corrupted. Try to open a shell in writable mode in the container and start Galaxy from the shell")
                        exit(1)
                    else:
                        # Wait 5s until Galaxy is up
                        logger.info("Galaxy is not up ... wait 5 seconds and try again")
                        t = t + 5
                        time.sleep(5)
                        response = None
                        continue
            self.instance_running = True
        return


    def stop_container_galaxy(self, sudo=False, bind_dirs=None, tmp_dir=None):
        '''
        Stop a running containerized Galaxy instance.
        Remove an existing temporary directory
        '''
        with open(os.devnull, 'w') as FNULL:
            if sudo:
                # We use sudo only for importing workflows, so no binds.
                subprocess.call(["sudo", "singularity", "exec", "-w", self.container_file, "sh", "/galaxy/run.sh", "--stop-daemon"], stdout=FNULL, stderr=subprocess.STDOUT)
                self.instance_running = False
                time.sleep(5)
            else:
                # We this only for workflow execution
                subprocess.call(["singularity", "exec", "--bind", bind_dirs, self.container_file, "sh", "/galaxy/run.sh", "--log-file", "/output/paster.log", "--pid-file", " /output/paster.pid", "--stop-daemon"], stdout=FNULL, stderr=subprocess.STDOUT)
                self.instance_running = False
                time.sleep(5)

        # Remove temporary directories
        if tmp_dir:
            logger.info("Remove temporary directory: %s", tmp_dir)
            shutil.rmtree(tmp_dir)
        
        return

    
    def create_galaxy_instance(self, check_admin=False):
        '''
        Create a bioblend GalaxyInstance.
        If check_admin = True, check if the user is admin of the galaxy instance. If not, return None.
        Returns False if an error occurs.
        '''
        # Check if the URL is valid
        if not check_url(self.url):
            logger.error("URL to galaxy instance is not a valid URL: %s", self.url)
            return False
        # Try to create a bioblend Galaxy instance
        try:
            self.instance = GalaxyInstance(url=self.url, key=self.api_key)
        except:
            logger.error("Cannot create Galaxy instance.") 
            return False
        return True


    def create_clients(self):
        '''
        Create bioblend clients for the Galaxy instance.
        '''
        # Create first client and check if the API works
        self.config_client = ConfigClient(self.instance)
        try:
            self.config_client.get_version()
            self.config_client.get_config()
        except:
            logger.error("Provided API-key does not work.")
            return False
        try:
            self.user_client = UserClient(self.instance)
            self.workflow_client = WorkflowClient(self.instance)
            self.tool_client = ToolClient(self.instance)
            self.toolshed_client = ToolShedClient(self.instance)
            self.library_client = LibraryClient(self.instance)
            self.roles_client = RolesClient(self.instance)
            self.history_client = HistoryClient(self.instance)
            self.dataset_client = DatasetClient(self.instance)
        except:
            logger.error("Error initializing other bioblend clients.")
            return False
        return True


    def initialize(self):
        '''
        Initialize bioblend GalaxyInstance, clients, and check if the API works.
        Returns False if something went wrong.
        '''
        if not self.create_galaxy_instance():
            logger.error("Cannot create bioblend GalaxyInstance for the GalaxyHandler")
            return False
        if not self.create_clients():
            logger.error("Cannot create bioblend clients for the GalaxyHandler")
            return False
        return True


    def create_user(self, name, mail, password):
        '''
        Create a new Galaxy user for an specific Galaxy instance.
        Return the user_id and an api-key.
        '''
        try:
            new_user = self.user_client.create_local_user(name, mail, password)
        except ConnectionError as e:
            # User already exists
            if "already exists" in e.body:
                new_user = self.user_client.get_users(f_email=mail)[0]
        new_user_id = new_user['id']

        # Create API key for that user
        new_user_api_key = self.user_client.create_user_apikey(new_user_id)
        
        return (new_user_id, new_user_api_key)


    def create_input_library(self, name, user):
        '''
        Create a dataset library for this instance.
        '''
        try:
            # Create the library
            new_library = self.library_client.create_library(name, description=None, synopsis=None)
            logger.info("new_library ok")
            # Get the role of the user
            user_role_id = self.roles_client.get_roles()[0]['id']
            logger.info("user_role_id ok")
            # Set permissions for that library
            # The following settings will enable the upload of input data by the user to this libary
            self.library_client.set_library_permissions(library_id=new_library['id'], access_in=user_role_id, modify_in=user_role_id, add_in=user_role_id, manage_in=user_role_id)
            return True
        except:
            logger.error("Cannot create Galaxy data library")
            return False


    def create_history(self, name):
        '''
        Create a history and return the history id
        '''
        history_dict = self.history_client.create_history(name)
        return history_dict['id']


    def create_folder(self, library_name, user_mail):
        '''
        Create a folder for the files in a library.
        This is used to store files for the a Galaxy library.
        Return a tuple containing the library id and the folder id.
        '''
        # Assume that there is just one library with this name
        library = self.library_client.get_libraries(library_id=None, name=library_name, deleted=False)[0]
        folder = self.library_client.create_folder(library['id'], user_mail)
        return library['id'], folder[0]['id']


    def upload_workflow_input(self, workflow_input, library_id, folder_id, mount_input_dir=True, input_dir=None):
        '''
        Upload the input data for a workflow to Galaxy.
        The files are uploaded from the filesystem to a folder of an Galaxy library.
        The files are not duplicated, because just symbolic links will be created.
        If a user provides his own data, the files are 'uploaded' from the /input directory,
        which is just a mount point for a directory outside the container.
        If a user wants to use test data provided with the container, mount_input_dir is False
        and the directory inside the container has to be specified.
        '''
        for step_uuid, step_param in workflow_input.iteritems():
            if step_param['step_type'] == 'data_input':
                if mount_input_dir:
                    # Input data is mounted in the container
                    path = os.path.join('/input', step_param['filename'])
                else:
                    # input_dir exists inside the container (e.g. workflow test data)
                    path = os.path.join(input_dir, step_param['filename'])
                logger.info("Next upload: " + path)
                workflow_input[step_uuid]['dataset_id'] = self.library_client.upload_from_galaxy_filesystem(library_id, path, folder_id=folder_id, file_type=step_param['galaxy_file_type'], link_data_only='link_to_files')   


    def export_output_history(self, history_id, output_dir):
        '''
        Export all datasets of a history to the output directory.
        '''
        # Get a list of all datasets in the output history
        history_datasets = self.history_client.show_history(history_id, contents=True, deleted=None, visible=None, details=None, types=None)
        
        # Iterate over the datasets of the history and download each dataset that has 'ok' state (e.g. the tool completed)
        for dataset in history_datasets:
            # Check the dataset status, e.g. if the corresponding task completed. Do not download input datasets!
            if dataset['state'] == 'ok':
                logger.info("Download dataset %s, state: %s", dataset['name'], dataset['state'])
                self.dataset_client.download_dataset(dataset['id'], file_path=output_dir, use_default_filename=True, wait_for_completion=False, maxwait=12000)
            else:
                logger.info("Do not download dataset %s, state: %s", dataset['name'], dataset['state'])
