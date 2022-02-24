# bt-cc-model-code

Code for emulab experiments for congestion control algorithms.

## Setup

Clone the respository using:

> git clone --recurse-submodules git@github.com:cabart/bt-cc-model-code.git

or

> git clone git@github.com:cabart/bt-cc-model-code.git
> git submodule update --init --recursive

Afterwards run:

> ./setupEnvironment.sh

to finish the setup.

TODO: Test script if setup is working.

### Notes about setup

- Uses a python virtual environment located in 'env/'
- Uses geni-lib package located in 'geni-lib/'. This is a submodule and is directly cloned from https://gitlab.flux.utah.edu/emulab/geni-lib.git

The geni-lib package was installed in environment using the following command: '$> env/bin/python -m pip install -e ./geni-lib/'

## Documentation

Documentation located at: [Documentation](documentation)

## Running the experiment

See [Emulab experiment documentation](documentation/emulabExperiment.md#prerequisites) before running it the first time

> ./run.sh -v

## Additional notes about the repository

If python files are run by themselves they should be called like:

> ./env/bin/python \<python file\>

or depending on the file:

> sudo ./env/bin/python \<python file\>