# cc-de-models

1. Setup VM as described in mininetSetup.md.
2. Install all dependencies (either as root or using python venv since experiments must be run as root)
    - matplotlib, pandas, colour, pyroute2
    - TODO: write requirements file
3. Install all required system packages (apt-get):
    - texlive-latex-recommended
    - cm-super
    - dvipng

Install as root:
(Beware of the fact that python behaves different when run as sudo, may not find modules. If so use a python environment or install these modules globally)

> sudo python -m pip install \<library>
>
> sudo ./run_experiment.py configs/test_config.yml

OR use python venv:

> source /path/to/env/bin/activate
> python -m pip install \<library>
> sudo /path/to/env/bin/python3 run_experiment.py configs/test_config.yml

TODO: Maybe it is actually /path/to/env/bin. Test this!

## Running Code

tcpdump file is seemingly not saved correctly -> Error

## Code Review

- Why is the max_queue_size set as a property of the link and not as a part of the switch (respectively the network interface at the switch)?
Shouldn't it be enough to specify the queue size directly in tc-netem?
Same for qdisc (RED, drop-tail)

- In Emulab latency can be set directly at link. Disadvantage: May not be changed during experiment.