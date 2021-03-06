# cc-de-models

Additional notes on how to run simon's mininet experiments code.

1. Setup VM as described in *mininetSetup.md*
2. Install all dependencies (either as root or using python venv since experiments must be run as root)
    - matplotlib, pandas, colour, pyroute2
3. Install all required system packages (apt-get):
    ~~- texlive-latex-recommended~~
    - texlive-latex-extra
    - cm-super
    - dvipng

Install as root:
(Beware of the fact that Python behaves different when run as sudo, may not find modules. If so, use a Python environment or install these modules globally)

> sudo python -m pip install \<library>
>
> sudo ./run_experiment.py configs/test_config.yml

OR use python venv:

> source /path/to/env/bin/activate
> python -m pip install \<library>
> sudo /path/to/env/bin/python3 run_experiment.py configs/test_config.yml
