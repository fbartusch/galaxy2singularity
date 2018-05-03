# Build a singularity container that contains a Galaxy instance

# Create empty container
singularity create --size 3572 $PWD/centos7-galaxy.img

# Bootstrap the container
singularity bootstrap $PWD/centos7-galaxy.img g2s/singularity_def_files/Singularity



