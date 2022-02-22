"""Creates a network of n sender nodes, one receiver node and one virtual switch inbetween to connect them.

Instructions:
Click on any node in the topology and choose the `shell` menu item. When your shell window appears, use `ping` to test the link.

"""
#!/usr/bin/python3.8

# Heavily based on Simons code
# but aims for a clear distinction between config generation and experiment code

import sys
import yaml
import os
import pprint
import time

from generateRspec import *
from generateConfig import *
from serverCommunication import *
from emulabConnection import *

import geni.aggregate.protogeni as pg

def main(config_name):

    config = get_config(config_name)

    result_folder = 'results/'
    if not os.path.exists(result_folder):
        os.mkdir(result_folder)
        os.chown(result_folder, os.stat('.').st_uid, os.stat('.').st_gid)
    result_folder += config['name'] + '/'
    if not os.path.exists(result_folder):
        os.mkdir(result_folder)
        os.chown(result_folder, os.stat('.').st_uid, os.stat('.').st_gid)
    result_folder += 'emulab_experiments/'
    if not os.path.exists(result_folder):
        os.mkdir(result_folder)
        os.chown(result_folder, os.stat('.').st_uid, os.stat('.').st_gid)

    with open(config['emulab_parameters']['base_config'], 'r') as base_config_file:
        base_config = yaml.safe_load(base_config_file)

    # for now, only run one parameter combination
    print("Number of combinations:",len(config['param_combinations']))
    first = True
    for pc_map in config['param_combinations']:
        # create configuration file for experiment
        exp_config = config_edited_copy(base_config, custom=pc_map)
        exp_config = setup_configuration(exp_config)

        #print(exp_config)
        if first:
            first = False
            # do experiment

            emulab_config = get_emulab_config("emulab_experiments/emulab_config.yaml")
            emuServer = emulabConnection(emulab_config["username"],emulab_config["home"],emulab_config["certificate_location"],emulab_config["password_location"])

            # generate rspec file
            rspec = createUnboundRspec(exp_config)
            print(rspec.getDOM)

            # do serverCommunication setup by building context        
            #emulab_config = get_emulab_config("emulab_experiments/emulab_config.yaml")
            #context = buildContext(emulab_config)

            #from geni.util import loadContext
            #context = loadContext()

            sname = "test"
            #ans = pg.UTAH_PG.listresources(context,sname=sname)
            #ans = pg.UTAH_PG.listresources(context)
            #pprint.pprint(ans)

            #ans = pg.UTAH_PG.getversion(context)
            #pprint.pprint(ans)

            '''
            # start sliver
            sname = "emulab_experiment"
            ans = pg.UTAH_PG.createsliver(context,sname,rspec)
            pprint.pprint(ans)

            for i in range(15):
                time.sleep(60)
                print("-"*30)
                print("status report:")
                ans = pg.UTAH_PG.sliverstatus(context,sname)
                pprint.pprint(ans)

            print("-"*30)
            print("delete sliver")
            ans = pg.UTAH_PG.deletesliver(context,sname)
            pprint.pprint(ans)
            print("deleted sliver")'''
        else:
            continue


        #for i in range(config['experiment_parameters']['runs']):
        #    print("Run", i+1, "/", config['experiment_parameters']['runs'])
            #run_cc(exp_config, result_folder)
            #for dir_name, _, file_names in os.walk(result_folder):
            #    for file_name in file_names:
            #        os.chown(os.path.join(dir_name, file_name), os.stat('.').st_uid, os.stat('.').st_gid)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("Please provide a multi-experiment config file.")
