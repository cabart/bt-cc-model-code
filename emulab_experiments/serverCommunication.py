from geni.aggregate import FrameworkRegistry
from geni.aggregate.context import Context
from geni.aggregate.user import User

import geni.aggregate.protogeni as pg
import geni.aggregate.instageni as IG


import os

# for testing
import pprint

# does not work, since when started with sudo HOME usually is /root
#HOME = os.environ["HOME"]
#HOME = os.getenv("HOME")

def buildContext(username="cabart",publicKeyPath="/.ssh/id_ed25519.pub",HOME="/home/cabart"):
    framework = FrameworkRegistry.get("portal")()
    framework.cert = HOME + "/.ssl/encrypted.pem"
    framework.key = HOME + "/.ssl/password"

    user = User()
    user.name = username
    user.urn = "urn:publicid:IDN+emulab.net+user+" + username
    user.addKey(HOME + publicKeyPath)

    context = Context()
    context.addUser(user)
    context.cf = framework
    context.project = "cc-model-valid"

    return context


if __name__ == "__main__":
    # build default context
    print("build default context")
    context = buildContext()
    print("finished building")
    pprint.pprint(pg.UTAH_PG.getversion(context))
    #pprint.pprint(IG.GPO.getversion(context))
    print("done")