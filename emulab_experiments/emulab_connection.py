# Code is loosely based on https://gitlab.flux.utah.edu/emulab/emulab-devel/-/tree/master/protogeni/tutorial and https://gitlab.flux.utah.edu/emulab/emulab-stable/-/tree/master/protogeni/test
# It was rewritten with the intention of making it object-oriented in order to be easier
# and more flexible to handle. Additionally it runs in Python 3 only

# Note: has to be run with sudo permissions

# More information about protogeni and especially the xmlrpc interface of it: http://www.protogeni.net/ProtoGeni/wiki/XMLRPCInterface

# General notes for implementer:
# after initialization only self.cred (user credentials) and self.sliceurn are known
# self.slice and self.sliver have always to be checked for (if not null or even better if they have expired)

from getpass import getpass
import sys
import time
import os
import ssl
import re
import traceback

# server connection libraries
from urllib.parse import urlsplit
import xmlrpc.client as xmlrpclib
import http.client as httplib

import logging

logger = logging.getLogger("root.emulab_connection")

class InitializeError(Exception):
    """Exception when initializing emulab connection class"""

    def __init__(self, message="error when initializing emulab connection"):
        super().__init__(message)


class emulabConnection:
    # emulab server
    xmlrpc_server = {"ch": "www.emulab.net", "sr": "www.emulab.net", "sa": "www.emulab.net", "cm": "www.emulab.net"}
    server_path = {"ch": ":12369/protogeni/xmlrpc/", "sr": ":12370/protogeni/pubxmlrpc/", "sa": ":12369/protogeni/xmlrpc/", "cm": ":12369/protogeni/xmlrpc/"}

    slice = None
    sliver = None
    manifest = None

    # all locations relative to home location, home location has to be an absolute path
    def __init__(self, user, home_loc=None, certificate_loc='.ssl/cloudlab.pem', password_loc='.ssl/password', experiment_name="emulab-experiment"):
        logger.info("Start emulab connection setup")

        # setup home path
        if home_loc is None:
            username = os.environ.get('SUDO_USER', os.environ.get('USERNAME'))
            self.HOME = os.path.expanduser(f'~{username}')
            logger.info("No home directory specified. '" + self.HOME + "' is used as home directory now")
            if self.HOME is None:
                raise InitializeError("Could not find a username variable in terminal, should specify a home directory")
        else:
            self.HOME = home_loc
            logger.info("Home directory: " + self.HOME)

        self.user = user
        self.certificate_loc = os.path.join(self.HOME,certificate_loc)
        self.password_loc = os.path.join(self.HOME, password_loc)
        self.experiment_name = experiment_name  # = slice name

        hostname = self.xmlrpc_server["ch"]
        self.domain = hostname[hostname.find('.')+1:]

        self.sliceurn = "urn:publicid:IDN+" + self.domain + "+slice+" + self.experiment_name

        # location of all certificates, encrypted and decrypted
        self.certificate_dir = os.path.dirname(self.certificate_loc)

        # passphrase
        if os.path.exists(self.password_loc):
            try:
                passphrase = open(self.password_loc).readline()
                if passphrase == "":
                    logger.info("empty password file, may cause problem")
                    self.password = getpass("Emulab password:")
                else:
                    self.password = passphrase[:-1]
            except IOError:
                logger.error("Error when reading password file")
                self.password = getpass("Emulab password:")
        else:
            logger.error("password file does not exist")
            self.password = getpass("Emulab password:")

        # get self credential, used for most calls at sa (slice authority)
        logger.debug("Getting credentials of user")
        cred = self.get_self_credential()
        if cred is None:
            raise InitializeError("Could not get self credential when setting up emulab connection")
        else:
            self.cred = cred

        # get SSH keys
        params = {"credential": self.cred}
        rval, response = self.do_method_retry("sa", "GetKeys", params)
        if rval:
            raise InitializeError("Could not get ssh keys")
        else:
            # TODO: maybe should check if there are any keys at all
            self.keys = response["value"]

        logger.info("Successfully setup emulab connection!\n")


    def do_method(self, module, method, params, version=None):
        if module not in self.xmlrpc_server or module not in self.server_path:
            logger.error("Invalid call at: " + module + " in 'do_method' call")
            raise Exception("Invalid server module")
        else:
            addr = self.xmlrpc_server[module]
            path = self.server_path[module]

        uri = "https://" + addr + path + module
        
        if version:
            uri += "/" + version
        url = urlsplit(uri,"https")
        logger.debug("call at uri: " + uri + ", url: " + str(url) + ", method: " + method)

        port = url.port
        
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        ctx.load_cert_chain(self.certificate_loc,password=self.password)
        
        # TODO: look into this in more detail
        # maybe should remove them if possible
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        # alternative: cacertificates

        server = httplib.HTTPSConnection(url.hostname, port, context=ctx)

        # Make the server call
        while True:
            try:
                server.request("POST", url.path, xmlrpclib.dumps((params,), method))
                response = server.getresponse()
                if response.status == 503:
                    logger.debug("Try again in a few seonds")
                    time.sleep(5.0)
                    continue
                elif response.status != 200:
                    logger.error("connection error: " + str(response.status) + " " + str(response.reason))
                    return (-1, None)
                else:
                    response = xmlrpclib.loads(response.read())[0][0]
                    break
            except httplib.HTTPException:
                logger.error("http exception")
                return (-1, None)
            except xmlrpclib.Fault:
                e = sys.exc_info()[1]
                if e.faultCode == 503:
                    logger.debug("Retrying in a few seconds")
                    time.sleep(5.0)
                    continue
                else:
                    logger.error("xmlrpclib error")
                    return (-1, None)
            except ssl.CertificateError:
                e = sys.exc_info()[1]
                logger.error("Warning: possible certificate host name mismatch")
                logger.error("Consult: http://www.protogeni.net/trac/protogeni/wiki/HostNameMismatch")
                logger.error(e)
                return (-1, None)
            except Exception as e:
                logger.error("Some error has occured during emulab server connection:" + str(traceback.format_exc()))

        # If server call successfull
        # Parse the response
        if response["code"] and len(response["output"]):
            logger.debug(response["output"])
        
        rval = response["code"]

        # if there is a code != 0, then return error value
        if rval:
            if response["value"]:
                rval = response["value"]
                logger.warning("Error code at server: " + str(response["value"]))
        return (rval, response)
    

    def do_method_retry(self, suffix, method, params, version=None):
        count = 20
        rval, response = self.do_method(suffix, method, params, version)
        # code 14 means busy, maybe should also do this for code 16 (in progress)
        while count > 0 and response and response["code"] == 14: # code 14 means busy
            count -= 1
            logger.info("Server is busy: Try again in a few seconds...")
            time.sleep(5.0)
            rval, response = self.do_method(suffix, method, params, version)
        return (rval, response)


    def get_self_credential(self):
        rval, response = self.do_method_retry("sa", "GetCredential", {})
        if rval:
            logger.error("Could not get my credential")
            return None
        else:
            return response["value"]
    

    def getVersion(self):
        rval, response = self.do_method_retry("sa", "GetVersion", {})
        if rval:
            logger.error("Could not obtain API version")
            return None
        else:
            logger.debug("Server version:" + str(response["value"]))
            return response["value"]


    def lookupSlice(self):
        params = {}
        params["credential"] = self.cred
        params["type"] = "Slice"
        params["hrn"] = self.experiment_name # or params["urn"] = self.sliceurn

        rval, response = self.do_method_retry("sa", "Resolve", params)
        if rval:
            logger.warning("Slice does not exist yet or has expired")
            return False
        else:
            logger.debug("Slice already exists")
            #logger.debug(str(response["value"]))
            return True
    

    def createSlice(self, duration=4):
        """Create a new slice with slice name given in initialization (experiment_name)

        Attributes:
            duration -- time until experiation of slice/experiment given in hours 
        """

        # check if slice already exists
        if self.lookupSlice(): return 2

        duration *= 60 * 60 # convert from hours to seconds
        validUntil = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + duration))

        params = {}
        params["credential"] = self.cred
        params["type"] = "Slice"
        params["hrn"] = self.experiment_name
        params["expiration"] = validUntil

        rval, response = self.do_method_retry("sa", "Register", params)
        if rval:
            logger.error("Could not create slice:")
            logger.error(str(rval))
            logger.error(str(response))
            return 1 # or maybe raise exception
        else:
            self.slice = response["value"]
            logger.info("Slice successfully created")
            #logger.info("Slice created: " + str(myslice))
            return 0


    def renewSlice(self, expiration:str):
        '''Takes the expiration time as string'''

        params = {}
        params["slice_urn"]   = self.sliceurn
        params["credentials"] = (self.slice,)
        params["expiration"] = expiration

        rval,response = self.do_method_retry("sa", "RenewSlice", params)
        if rval:
            logger.error("Could not renew slice at the SA")
            return False
        else:
            self.slice = response["value"]
            logger.debug("Slice has been renewed")
            return True

    def getSliceCredential(self):
        params = {}
        params["credentials"] = (self.cred,)
        params["type"] = "Slice"
        params["urn"] = self.sliceurn

        rval, response = self.do_method_retry("sa", "GetCredential", params)
        if rval:
            logger.error("Could not get slice credentials")
            return False
        else:
            logger.debug("Got slice credentials")
            self.slice = response["value"]
            return True

    def UpdateSliceInformation(self):
        # errors should only come up if slice does not exist anymore 
        if not self.lookupSlice():
            raise Exception("Slice does not exist")
        if not self.getSliceCredential():
            raise Exception("Could not get slice credentials")


    def createSliver(self,rspec=None):
        self.UpdateSliceInformation()

        if rspec is None:
            logger.info("No specific rpsec given - using default rspec file")

            path = os.path.join(os.path.dirname(__file__), 'default.rspec')
            try:
                f = open(path)
                rspec = f.read()
                f.close()
            except IOError:
                logger.error("Reading of rspec failed. File may not exist?")
                logger.error("File path: ",path)
                return False

        logger.info("Starting sliver creation")

        params = {}
        params["credentials"] = (self.slice,)
        params["slice_urn"] = self.sliceurn
        params["rspec"] = rspec
        params["keys"] = self.keys

        rval, response = self.do_method_retry("cm", "CreateSliver", params)
        if rval:
            logger.error("Could not create sliver")
            return False
        else:
            logger.info("Sliver successfully created")
            self.sliver, self.manifest = response["value"]
            #print("sliver:",self.sliver,"\n\n\n")
            #print("manifest:",self.manifest,"\n\n")
            logger.info("Access nodes with: ssh -p 22 " + self.user + "@<node-name>." + self.experiment_name + ".emulab-net.emulab.net")
            logger.info("This does only work for exclusive/hardware node, VMs have to be accessed using a specific port, see manifest")
            return True


    def lookupSliver(self):
        params = {}
        params["credentials"] = (self.slice,)
        params["urn"] = self.sliceurn
        rval, response = self.do_method_retry("cm", "Resolve", params, version="2.0")
        if rval:
            logger.error("Could not resolve slice")
            return False
        else:
            if not "sliver_urn" in response["value"]:
                logger.error("no sliver found in this slice")
                return False
            else:
                logger.debug("Sliver found" + str(response["value"]["sliver_urn"]))
                #logger.debug("Manifest:" + str(response["value"]["manifest"]))
                self.sliverurn = response["value"]["sliver_urn"]
                self.manifest = response["value"]["manifest"]
                return True


    def getSliverCredential(self):
        params = {}
        params["credentials"] = (self.slice,)
        params["slice_urn"] = self.sliceurn

        rval, response = self.do_method_retry("cm", "GetSliver", params, version="2.0")
        if rval:
            logger.error("Could not get sliver credentials")
            return False
        else:
            logger.debug("Got sliver credentials")
            self.sliver = response["value"]
            return True
    

    def UpdateSliverInformation(self):
        self.UpdateSliceInformation()
        # errors should only come up if slice does not exist anymore 
        if not self.lookupSliver():
            raise Exception("Sliver does not exist")
        if not self.getSliverCredential():
            raise Exception("Could not get Sliver credentials")


    def deleteSliver(self):
        self.UpdateSliverInformation()

        params = {}
        params["credentials"] = (self.sliver,)
        params["sliver_urn"] = self.sliverurn

        rval, response = self.do_method_retry("cm", "DeleteSliver", params, version="2.0")
        if rval:
            logger.error("Deleting sliver failed")
            return False
        else:
            logger.info("Ticket has been added for remaining time")
            self.ticket = response["value"]
            return True


    def restartSliver(self):
        self.UpdateSliverInformation()

        params = {}
        params["slice_urn"] = self.sliceurn
        params["credentials"] = (self.sliver,)

        rval, response = self.do_method_retry("cm", "RestartSliver", params, version="2.0")
        if rval:
            logger.error("Could not restart")
            return None
        else:
            return response["value"]



    def sliverStatus(self):
        '''
            Get current status of sliver 

            Returns:
                dictionary with keys: 'state', 'status' and 'details'
        '''
        self.UpdateSliverInformation()

        params = {}
        params["slice_urn"] = self.sliceurn
        params["credentials"] = (self.sliver,)

        rval, response = self.do_method_retry("cm", "SliverStatus", params, version="2.0")
        if rval:
            logger.error("Could not get sliver status")
            return None
        else:
            return response["value"]
        

    def sliverWaitUntilReady(self, retries=50, interval=30):
        '''
            Wait until sliver is ready. Poll every 'interval' seconds
            for up to 'retries' times

            Args:
                retries (int): number of retries
                interval (int): number of seconds before next retry

            Returns:
                True if sliver is ready, false otherwise (timeout)
        '''
        self.UpdateSliverInformation()

        ready = False
        count = 0
        logger.info("Waiting for hardware to start up... (large network setups may take a few minutes to get started up)")
        while not ready or count >= retries:
            count += 1
            status = self.sliverStatus()
            if status is None:
                logger.info("Sliver status unknown")
            else:
                logger.debug(f"Current status of sliver: {status['status']}")
                try:
                    for _,v in status["details"].items():
                        logger.debug(f"id:{v['client_id']}, status:{v['status']}, state:{v['state']}, error:{v['error']}")
                except:
                    logger.info("did not work")
                if status["status"] == 'ready':
                    ready = True
                    break
            logger.info(f"Tried for {count}/{retries} times. Will try again in {interval} seconds.")
            time.sleep(interval)

        return ready

        
    def startExperiment(self, duration=4, rspec=None):
        '''
            Start experiment hardware, needs to be called to
            request and startup all emulab resources

            Args:
                duration (int): duration of experiment in hours
                rspec (str | None): rpspec file of experiment
                    If rspec is None, the default rpec file will
                    be used (default.rspec).
            
            Returns:
                True if experiment is up and running, False otherwise
        '''

        ret = self.createSlice(duration)
        # check for expiration date, if it is smaller than duration extend it
        if ret == 0:
            logger.info("Creation successful")
        elif ret == 1:
            logger.info("Creation not successful")
        elif ret == 2:
            logger.info("Slice already exists, renew expiration date")
            self.UpdateSliceInformation()
            # get current slice expiration
            oldExpT = self.getSliceExpiration()
            # create new slice expiration
            newExpT = time.gmtime(time.time() + duration * 60 * 60)
            # check if old expiration time already exceeds new expiration time
            diff = time.mktime(newExpT) - time.mktime(oldExpT)

            logger.debug("old expiration time: " + str(oldExpT))
            logger.debug("new expiration time: " + str(newExpT))
            logger.debug("difference between old and new expiration time: " + str(diff))
            if diff > 0:
                logger.info("need to extend slice expiration time")
                worked = self.renewSlice(time.strftime("%Y-%m-%dT%H:%M:%SZ",newExpT))
                if not worked: logger.error("error occured when extending slice expiration time")
            else:
                logger.info("slice expiration time is longer than needed. Don't extend time")
            
        self.createSliver(rspec)

        # Use this code as a failsave when hardware does not work properly
        #if self.stopExperiment():
        #    logger.info("All done")
        #    sys.exit()

        if self.sliverWaitUntilReady():
            logger.debug("Experiment is ready")
            return True
        else:
            logger.debug("Experiment is not ready, timeout maybe too low or there was an error when starting up")
            return False


    def stopExperiment(self):
        return self.deleteSliver()

    # Actually not needed, since exclusive VMs get their own address and are accessible through port 22
    def getVMPorts(self):
        '''
            Get ports of all virtual machines in experiment. Unlike 'rawPC's
            non-exclusive VMs can not be accessed through port 22 but get assigned
            a different port which can be found in the manifest. (This is due to
            possibility of multiple VMs running on the same physical pc)

            As of now not very useful since no mapping between port and hostname is
            offered by this method

            Returns:
                list of all VM ports (except port 22)
        '''
        self.UpdateSliverInformation()

        if self.manifest is None:
            logger.info("No sliver seems to exist")
            return None
        else:
            logger.debug("Find all ports...")
            #logger.info("in getAddresses() - Manifest:" + str(self.manifest)) 
            pattern = re.compile('port=\"[0-9]+\"')
            matches = pattern.findall(str(self.manifest))
            logger.debug("All ports found:" + str(matches))

            numberPattern = re.compile('[0-9]+')
            result = []
            for i in matches:
                num = (numberPattern.findall(i))[0]
                if num == '22':
                    continue
                else:
                    result.append(num)
            logger.debug("All VM ports:" + str(result))

            
            if len(result) == 0:
                logger.warn("No VM port found")
            elif len(result) > 1:
                logger.warn("Multiple VM ports found")
            else:
                logger.info("One VM port found:" + str(result[0]))
            return result
    

    def getSliceExpiration(self):
        '''Returns struct_time object'''
        if self.slice is None:
            logger.error("No slice information available")
        else:
            try:
                pattern = re.compile("<expires>(.+)</expires>")
                expT = (pattern.findall(self.slice))[0]
                logger.info("Expiration time (GMT): " + expT)
                t = time.strptime(expT,"%Y-%m-%dT%H:%M:%SZ")
                return t
            except Exception as e:
                logger.error(str(e))
                return None


    def getManifest(self):
        if self.lookupSliver():
            return self.manifest
        else:
            return None
    

    def getPCs(self):
        if self.lookupSliver():
            manifest = self.manifest
            pcs = []
            for line in manifest.splitlines():
                output = re.match(r'.*hardware_type="(\S+)".* name="(\S+)"',line)
                if output is not None:
                    name = re.match(r'[^.]*',output.group(2))[0]
                    pcType = output.group(1)
                    pcs.append((name,pcType))
            return pcs
        else:
            return []


    def getPCTypes(self):
        pcs = self.getPCs()
        types = set()
        for name,pctype in pcs:
            if pctype != "pcvm":
                types.add(pctype)
        return types


if __name__ == "__main__":
    # Can be used for testing and debugging

    logger.basicConfig(format='%(asctime)s:: %(levelname)s:: %(message)s',datefmt="%H:%M:%S", level=logging.INFO)

    try:
        emuConn = emulabConnection("cabart", certificate_loc=".ssl/encrypted.pem",password_loc=".ssl/password")
    except InitializeError as e:
        logger.error("Emulab initialization failed: " + str(e))
        logger.error("Connection could not get established, abort...")
        sys.exit(1)

    logger.info("Setting up has worked")

    #logger.info("Test for server version")
    #version = emuConn.getVersion()
    #logger.info("Version number:" + str(version))

    #logger.info("Test for credentials")
    #cred = emuConn.get_self_credential() 
    #if cred is None:
    #    logger.error("Could not get my credential")
    #else:
    #    logger.info("Did get credentials")
        #print(cred)

    #logger.info("Test for slice creation")
    #worked = emuConn.createSlice(duration=1)
    #if worked:
    #    logger.info("Successfully created slice")
    #else:
    #    logger.info("Could not create slice")

    #logger.info("Test for sliver creation")
    #worked = emuConn.createSliver()
    #if worked:
    #    logger.info("Successfully created sliver")
    #else:
    #    logger.info("Could not create sliver")

    ready = emuConn.startExperiment()
    if ready:
        logger.info("experiment is now ready")
    else:
        logger.info("something went wrong")

    time.sleep(60)
    
    stopped = emuConn.stopExperiment()
    if stopped:
        logger.info("experiment has been stopped")
    else:
        logger.info("something went wrong")


    #logger.info("Wait for experiment to get ready")
    
    #ready = emuConn.sliverWaitUntilReady()
    #if ready:
    #    logger.info("experiment is now ready")
    #else:
    #    logger.error("Sliver still not ready, maybe broken: abort")

    

    #time.sleep(60)

    #logger.info("Test for sliver deletion")
    #worked = emuConn.deleteSliver()
    #if worked:
    #    logger.info("Successfully deleted sliver")
    #else:
    #    logger.info("Could not delete sliver")