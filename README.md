# bt-cc-model-code

Code for emulab experiments for congestion control algorithms.

## Setup

Clone the respository using:

~~~bash
git clone --recurse-submodules git@github.com:cabart/bt-cc-model-code.git
~~~

or

~~~bash
git clone git@github.com:cabart/bt-cc-model-code.git
git submodule update --init --recursive
~~~

Afterwards run:

~~~bash
./setupEnvironment.sh
~~~

to finish the setup.

### Notes about setup

- Uses a Python virtual environment located in 'env/'
- Uses geni-lib package located in 'geni-lib/'. This is a submodule and is directly cloned from [geni-lib](https://gitlab.flux.utah.edu/emulab/geni-lib.git)

The geni-lib package was installed in environment using the following command:

~~~bash
env/bin/python -m pip install -e ./geni-lib/'
~~~

## Documentation

see [Documentation](documentation).

## Running the experiment

See [Emulab experiment documentation](documentation/emulab_experiment.md#prerequisites) before running it the first time

~~~bash
./run.sh
~~~

Run specific configuration:

~~~bash
./run.sh -c ./configs/<specific_config>.yaml
~~~

Get more information about experiment options:

~~~bash
./run.sh -h
~~~

## Create plots

Run the following:

~~~bash
sudo ./env/bin/python3 plot.py ./configs/<specific_config>.yaml
~~~

## Additional notes about the repository

If Python files are run by themselves they should be called like:

~~~bash
./env/bin/python <python file>
~~~

or depending on the file:

~~~bash
sudo ./env/bin/python <python file>
~~~
