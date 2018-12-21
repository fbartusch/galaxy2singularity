from setuptools import setup, find_packages

setup(
    name='GalaxyWF2Virt',
    version='0.2',
    description='Virtualize Galaxy workflows with containerization (Docker or Singularity) or with Virtual Machines.',
    long_description='This tool creates fresh Container with an installed Galaxy. The tool uses then Workflow descriptions to install all the publicly available tools the workflow uses in Galaxy. The tool can also provision a Galaxy instance running in an VM.',
    url='...',
    author='Felix Bartusch',
    author_email='felix.bartusch@uni-tuebingen.de',
    license='TODO',
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',
        # Indicate who your project is intended for
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering',
        'Scientific/Engineering :: Bio-Informatics',
        'Topic :: System :: Archiving',
        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
    packages=find_packages(),
    entry_points = {
        'console_scripts': ['g2v=g2v.__main__:main']
    },
    install_requires=[
        'bioblend==0.12.0',
        'docker'
    ],
    include_package_data=True,
    zip_safe=False)

