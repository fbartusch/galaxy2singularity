# galaxy2singularity

Galaxy2singularityimports your existing Galaxy workflow into a Singularity container. The container is able to run the whole workflow on its own.
This tool enables you to:

* Bring your data processing workflow to your data
* Share your workflow with others
* Archive your workflow

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

You need the following software:
 * Singularity 2.3.2
 * Python 2.7 with bioblend 0.9.0

### Installing

This project uses Singularity 2.3.1 to create and run Singularity containers. Just execute the code below to get the source code, compile it and install it at `/usr/local`

```
VERSION=2.3.2
wget https://github.com/singularityware/singularity/releases/download/$VERSION/singularity-$VERSION.tar.gz
tar xvf singularity-$VERSION.tar.gz
cd singularity-$VERSION
./configure --prefix=/usr/local
make
sudo make install
```

Install Python 2.7 and bioblend 0.9.0 by creating your own Python environment with conda or just install bioblend via pip.

Last but not least, clone this repo.

## Import a Galaxy workflow to a Singularity container

First you need to create a new Singularity container. The following command will create a 3GB Singularity container, install Centos 7.3 and Galaxy 17.01 into it.
This will take some time. You only have to do it once. The container behaves like a normal file for the file system, so you can copy it to another location and reuse it later.

```
sudo sh g2s/scripts/build_template_container.sh
```

Now you want to import a Galaxy workflow into the Galaxy in the container. You have two possibilities:

* Import the workflow from the workflow .ga file
* Import the workflow from a running Galaxy instance

### Import workflow from the workflow .ga file

Obviously you need a .ga file of the workflow to import. The repository contains two test workflows that should work out-of-the-box. The first one is the Galaxy101 workflow, the other is a NGS workflow that maps genomic data to a reference genome and calls SNPs and INDELs afterwards.

```
sudo python import_workflow.py --conf test/galaxy101/import_from_multiple_workflows.ini
```

Or to install the example NGS-workflow:

```
sudo python import_workflow.py --conf test/Map_Call_SNP_IND_Consensus/import_from_workflow.ini
```

### Import the workflow from a running Galaxy instance

If your workflow is accessible in a running Galaxy instance you can directly import it from there. In principle the script accesses the Galaxy API of the running instance, gets the details of the workflow and imports it. The import itself works like the 'Import workflow from the workflow .ga file'.

You have to specify some options in the config-file. The file `import_from_instance_template.ini` is suitable template. The additional options are:

* The IP of the Galaxy instance
* Your API key in the Galaxy instance
* The workflow ID of the workflow to import

```
sudo python import_workflow.py --conf import_from_instance.ini
```

## Execute workflow in the container

Now you have a container that contains Galaxy, the workflow and all dependencies.
If you want to run the workflow, you have to specify again some option in an execution config-file. A template is stored within the container at /g2s/workflows/<wf_name>/<wf_name>.ga.ini
This config-file contains following sections:

* General: Information about the container and the workflow to execute
* User: The Galaxy inside the container has one user that runs the workflow. The API-key is used by `execute_workflow.py` to access the Galaxy API. With the password you are can access Galaxy in your Browser and inspect the progress of the running workflow.
* Data: You can specify three directories that are mounted in the container during workflow execution. The `input_directory` contains the input data for the workflow. The `output_directory` will contain the workflows output datasets. A temporary directory is created in the `tmp_directory` during workflow execution.
* For each input step of the workflow you have to specify the corresponding file in your `input_directory`
* For each compute step of the workflow you have to specify so-called runtime parameters that are not specified in the workflow

The repository contains templates for the example workflows. You can use them, but you have to copy the `User` section from the preliminary config-file because the API-Key and the password is randomly generated each time a new template container is created.

To print the preliminary config-file just type.

```
singularity exec centos7-galaxy.img cat /g2s/workflows/Galaxy101/Galaxy-Workflow-galaxy101.ga.ini
```

Then replace the `User` section in `test/galaxy101/execute_galaxy101.ini` and execute the workflow.

```
python execute_workflow.py --conf test/galaxy101/execute_galaxy101.ini 
```

The script should start Galaxy, import the input data, invoke the workflow, and download the results into the specified output directory.

Analogous for the NGS-workflow:

```
singularity exec centos7-galaxy.img less /g2s/workflows/Map_Call_SNPIND_Consensus_\(annotated\)/Galaxy-Workflow-Map_Call_SNP_IND_Consensus_\(annotated\).ga.ini
python execute_workflow.py --conf test/Map_Call_SNP_IND_Consensus/execute_example_workflow.ini
```

## Execute the workflow in interactive mode

If you don't want to inspect the workflow and access the containerized Galaxy instance via the browser, you can use the `interactive` mode.

```
python execute_workflow.py --conf test/galaxy101/execute_galaxy101.ini --interactive
```

This will startup Galaxy, binds the input directory to the container, but does not upload data or invoke the workflow. You can sign in to Galaxy using the mail and password from the previous step. Just open `http://127.0.0.1:8080/` in your browser.

