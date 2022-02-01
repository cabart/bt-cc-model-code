from geni.aggregate import FrameworkRegistry
from geni.aggregate.context import Context
from geni.aggregate.user import User

import geni.aggregate.protogeni as pg

import generateConfig

import os
import subprocess

# for testing
import pprint

# does not work, since when started with sudo HOME usually is /root
#HOME = os.environ["HOME"]
#HOME = os.getenv("HOME")

def buildContext(emulab_config):
    HOME = emulab_config["home"]
    username = emulab_config["username"]
    cert = os.path.join(HOME, emulab_config["certificate_location"])
    # correct directories for decrypted certificate and key
    # will be saved at the same place as the original certificate
    certDir = os.path.dirname(cert)
    keyPath = os.path.join(certDir,"dec.key")
    certPath = os.path.join(certDir,"emucert.crt")

    # check if both files exists already
    if (subprocess.call(["test","-e",keyPath]) or subprocess.call(["test","-e",certPath])):
        # preprocess certificate
        subprocess.call(["openssl","x509","-in",cert,"-out",certPath])
        # password options, at runtime or by using a password file
        if "password_location" in emulab_config:
            pwd = emulab_config["password_location"]
            subprocess.call(["openssl","rsa","-in",cert,"-passin","file:"+ os.path.join(HOME,pwd),"-out",keyPath])
        else:
            subprocess.call(["openssl","rsa","-in",cert,"-out",keyPath])
    else:
        # both files were already processed in an earlier run, no action necessary
        pass

    framework = FrameworkRegistry.get("portal")()
    framework.cert = certPath
    framework.key = keyPath

    user = User()
    user.name = username
    user.urn = "urn:publicid:IDN+emulab.net+user+" + username
    user.addKey(os.path.join(HOME, emulab_config["ssh_public_key_location"]))

    context = Context()
    context.addUser(user)
    context.cf = framework
    context.project = "cc-model-valid"

    return context


if __name__ == "__main__":
    # get emulab configuration file
    print("load configuration file...")
    emulab_config = generateConfig.get_emulab_config("emulab_config.yaml")
    print("loaded configuration file")
    # build default context
    print("build default context")
    context = buildContext(emulab_config)
    print("finished building")
    print("query server...")
    pprint.pprint(pg.UTAH_PG.getversion(context))
    #pprint.pprint(IG.GPO.getversion(context))
    print("done!")
