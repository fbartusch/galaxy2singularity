import json
import time
from g2s.GalaxyHandler import GalaxyHandler
from g2s.checks import *
from g2s.util import *

class WorkflowHandler():
    '''
    This class represents a Galaxy workflow that shall be imported into a Galaxy instance.
    '''

    def __init__(self, galaxy=None, wf_id=None, wf_file=None):
        if galaxy:
            # Needed if workflow is imported from another Galaxy instance
            # This is also the case if you want to execute a Galaxy workflow
            self.import_from_galaxy=True
            self.galaxy = galaxy      # A GalaxyHandler
            self.wf_id = wf_id
        else:
            # Needed if workflow is imported from .ga file
            self.import_from_galaxy=False
            self.wf_file = wf_file
        
        # Get the workflow description
        self.wf_description = self.get_wf_description()


    def get_wf_description(self):
        '''
        Get the workflow description of this Galaxy workflow.
        '''
        if self.import_from_galaxy:
            try:
                self.wf_description = galaxy.workflow_client.import_workflow_dict(self.wf_id)
            except:
                logger.error("Error while getting workflow_dict from Galaxy")
                return False
            return True
        else:
            # Check if the specified workflow .ga file exists
            if not check_file(self.wf_file):
                logger.error("Workflow file does not exist: %s", self.wf_file)
                return False
            with open(self.wf_file) as wf_file_handler:
                self.wf_description = json.load(wf_file_handler)
            return True

    
    def get_wf_name(self):
        '''
        Get the name of the workflow
        '''
        return self.wf_description['name']


    def install_wf_tools(self, dest_galaxy, tool_section_name=None):
        '''
        Install the tools used by the workflow in the corresponding Galaxy instance.
        '''
        logger.info("Install tools for the workflow %s", self.wf_description['name'])
        # Actual install routine
        steps = self.wf_description['steps']
        for index, step in steps.iteritems():
            logger.info("Install tool for workflow step %s:", index)
            # Ignore input steps
            if step['type'] == 'data_input':
                logger.info("Ignore: Data input step")
                continue
            # Ignore already installed tools
            if dest_galaxy.tool_client.get_tools(step['tool_id']) != []:
                logger.info("Ignore: Tool is already installed")
                continue
            # Install the tool with all dependencies
            repo = step['tool_shed_repository']
            tool_shed_url = 'http://' + repo['tool_shed']
            name = repo['name']
            owner = repo['owner']
            changeset_revision = repo['changeset_revision']
            dest_galaxy.toolshed_client.install_repository_revision(
                tool_shed_url = tool_shed_url,
                name = name,
                owner = owner,
                changeset_revision = changeset_revision,
                install_tool_dependencies = True,
                install_repository_dependencies = True,
                install_resolver_dependencies = True,
                new_tool_panel_section_label=tool_section_name)


    def import_workflow_to_galaxy(self, dest_galaxy):
        '''
        Import the workflow to the corresponding Galaxy instance
        '''
        # Import the workflow. No tools are installed.
        # Save the id of the imported workflow in the Galaxy instance
        try:
            import_result = dest_galaxy.workflow_client.import_workflow_dict(self.wf_description)
            self.imported_workflow_id = import_result['id']
            return True
        except:
            return False


    def create_execution_config():
        '''
        Create a configuration file used to execute the workflow.
        '''
        os.remove("./.tmp_import.ini")
        logger.info("Save workflow_id, user_api_key, user_password, and path to container_shasum file in a temporary config file")
        container_shasum_file = container_file.rsplit(".", 1)[0] + ".shasum"
        config.set('User', 'user_api_key', user_api_key_dest)
        config.set('General', 'workflow_id', import_result['id'])
        config.set('General', 'container_shasum_file', container_shasum_file)
        config.set('User', 'user_password', user_password)
        with open("./.tmp_import.ini", 'wb') as configfile:
            config.write(configfile)


    def prepare_runtime_params(self, workflow_input):
        '''
        Given a dictionary describing the workflow inputs, create the two dictionaries needed
        to invoke the workflow: inputs and runtime_params dictionary.
        inputs is a dict that maps workflow inputs to datasets and dataset collections:
         {'<input_index>': {'id': <encoded dataset ID>, 'src': '[ldda, ld, hda, hdca]'}} (e.g. {'2': {'id': '29beef4fadeed09f', 'src': 'hda'}})
        The input files itself have to be uploaded to Galaxy before, therefore the dataset_id in Galaxy is set in the workflow_input dictionary.
        '''
        wf_input={}
        runtime_params = dict()
        for step_uuid, step_param in workflow_input.iteritems():
            if step_param['step_type'] == 'data_input':
                wf_input[step_uuid] = {'id':step_param['dataset_id'][0]['id'] , 'src':'ld'}
            elif step_param['step_type'] == 'tool':
                # Remove the step_type from the step parameters and restore the dict structure from the keys:
                # e.g. '{x|y':'value}' -> {x:{y=value}}
                step_param.pop('step_type')
                runtime_params[step_uuid] = unflatten(step_param)
        return wf_input, runtime_params


    def invoke_workflow(self, workflow_input, output_history_id):
        '''
        Invoke the workflow with the specified input
        and save the resulting datasets in the output history.
        '''

        logger.info("Compute wf_input and runtime_params")
        # Prepare inputs for the invoke_workflow call
        wf_input, runtime_params = self.prepare_runtime_params(workflow_input)
        
        print wf_input
        print runtime_params

        # Invoke the workflow
        try:
            logger.info("Invoke Workflow")
            wf_invocation = self.galaxy.workflow_client.invoke_workflow(self.wf_id,
                inputs=wf_input,
                params=runtime_params,
                history_id=output_history_id,
                history_name=None,
                import_inputs_to_history=None,
                replacement_params=None,
                allow_tool_state_corrections=None)

            while True:
                history_status = self.galaxy.history_client.get_status(wf_invocation['history_id'])
                logger.info("Percent Complete: %s", str(history_status['percent_complete']))
                if history_status['percent_complete'] != 100 and history_status['state_details']['error'] < 1:
                    logger.info("Workflow is running ...")
                    time.sleep(10)
                else:
                    logger.info("No. Errors: " + str(history_status['state_details']['error']))
                    break
        except:
            logger.error("Error during workflow execution. Please see paster.log at in the output directory for more details.")





