# Galaxy

Galaxy2Singularity imports a galaxy workspace into a Galaxy instance that lives in a Singularity container. Galaxy writes and updates several files during startup, dataset import and workflow execution. Because Singularity containers cannot be changed by normal users after container creation, this behaviour of Galaxy is a problem. 
This document lists the changes made to a vanilla Galaxy Instance in the container such that a non-root user is able to execute the workflow in the Singularity container. Also the contents of the container are not modified during workflow execution. 

## Problem

* Changes in config/galaxy.ini for executing the workflow
    * Imported datasets shouldn't be saved inside the container
        ```
        file_path = /galaxy_tmp/database/files
        new_file_path = /galaxy_tmp/database/tmp
        ```
    * Change the job working directory
        ```
        job_working_directory = /galaxy_tmp/jobs_directory
        ```
    * Change location of integrated_tool_panel.xml (explanation below)
        ```
        integrated_tool_panel_config = /galaxy_tmp/integrated_tool_panel.xml
        ```
    * Change location of the database (explanation below)
        ```
        database_connection = sqlite:////galaxy_tmp/universe.sqlite?isolation_level=IMMEDIATE
        ```
    * deprecated: A normal (non-admin) user is created during the import step. This user will upload datasets to a library during workflow execution, but the default options do not allow this:
        ```
        user_library_import_dir = /galaxy_tmp/library/
        ```
    
    * A admin user is created during the import step. This user will upload datasets to the input library during workflow exection. The following option will allow admin users to upload files to the library from any location on the disc
        ```
        allow_path_paste = True
        (allow_library_path_paste in Galaxy release_17.05 and earlier)
        ```
    * These are changes that are maybe unnecessary, but the description in the configuration file indicates that they fit to the unusual use-case
        ```
        precache_dependencies = False
        ```

* Changes in config/galaxy.ini for importing the workflow
    * Set a master API key such that tools can be installed to Galaxy without defining an admin user. 
        ```
        master_api_key = changethis
        ``` 

* The file permissions for galaxy/database has to be set to 777 recursively. Otherwise the Galaxy throws weird errors depending on the actual file permissions. Usually permissions like 777 are very bad ...
but here it is needes such that a normal user can startup Galaxy although all contents of /galaxy/database in the container belong to root. From a security point of view it's no problem, because a user cannot alter files in the container and also the scripts in the container cannot harm the host system because the user inside the container is the same user as outside the container (e.g. same permissions).
    ```
    chmod -R 777 /galaxy/database
    ```

* Add bind points for input and output files during bootstrapping of the Singularity container.
    ```
    mkdir /input        # input files
    mkdir /output       # output files
    mkdir /galaxy_tmp   # temporary files for galaxy
    ```
   
    The python wrapper will bind a directory in /tmp/galaxy2singularity_xxxxx to /galaxy_tmp in the container. This ensures that two parallel executed containers do not write into the same directory. 
   
    These directories are used as bind points when starting Galaxy in the python wrapper:
    
    ```    
    singularity exec --bind <input_dir>:/input,<output_dir>:/output,<temp_dir>:/galaxy_tmp <container> <args>
    ```

* Galaxy should run in daemon mode because start and stop of Galaxy is handled via a script. Galaxy wants to create the two files paster.log and paster.pid in the main galaxy directory. Force Galaxy to create these two files outside of the container (e.g in /tmp or the /output directory)
    ```
    singularity exec <binds> <container> --log-file /output/paster.log --pid-file /output/paster.pid --daemon
    ```

* The wrapper has to copy two Galaxy files to the /input directory before pipeline execution. These are the only two files that are changed during workflow execution. Both files (outside the container) are deleted after workflow execution. The corresponding files in the container aren't changed such that the container is unaltered.

    * galaxy/integrated_tool_panel.xml
    
    This file is recreated during Galaxy startup. I did not find a configuration option that prevents this behaviour. Therefore this file is copied into the `/input` directory before starting Galaxy. The `/input` directory binds to a writable directory outside the container such that Galaxy can write to integrated_tool_panel.xml
    
    * galaxy/database/universe.sqlite
    
    It is necessary to create new histories for input and output data, import the input and running jobs. Because this changes the state of the database, Galaxy needs write access to it. The wrapper script copies the database to the `/input` directory and deletes the database after workflow execution.
