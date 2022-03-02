# Code is loosely based on https://gitlab.flux.utah.edu/emulab/emulab-devel/-/tree/master/protogeni/tutorial and https://gitlab.flux.utah.edu/emulab/emulab-stable/-/tree/master/protogeni/test
# Goal is to make it object-oriented so it is easier and flexible to handle, and implement it so it works in python3

# Note: has to be run with sudo permissions

# More information about protogeni and especially the xmlrpc interface of it: http://www.protogeni.net/ProtoGeni/wiki/XMLRPCInterface

# General notes for implementer:
# after initialization only self.cred (user credentials) and self.sliceurn are known
# self.slice and self.sliver have always to be checked for (if not null or even better if they have expired)

# possible additions:
# - binding more users to a single slice
# - RenewSlice at sa (extend expiration date)
# - Check version 2 compatibility, also on server side
# - do_method and do_method_retry mix should be avoided
# - should ask user what to do if sliver already exists: take it or create new? (if new maybe have to wait until it is ready)

from getpass import getpass
import sys
import time
import os
import ssl
import re

# server connection libraries
from urllib.parse import urlsplit
import xmlrpc.client as xmlrpclib
import http.client as httplib

from cryptography import x509

# not supported anymore it seems
from cryptography.x509.oid import NameOID
from cryptography.x509.oid import ExtensionOID

import logging


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
        logging.info("Start emulab connection setup")

        # setup home path
        if home_loc is None:
            username = os.environ.get('SUDO_USER', os.environ.get('USERNAME'))
            self.HOME = os.path.expanduser(f'~{username}')
            logging.info("No home directory specified. '" + self.HOME + "' is used as home directory now")
            if self.HOME is None:
                raise InitializeError("Could not find a username variable in terminal, should specify a home directory")
        else:
            self.HOME = home_loc
            logging.info("Home directory: " + self.HOME)

        self.user = user
        self.certificate_loc = os.path.join(self.HOME,certificate_loc)
        self.password_loc = os.path.join(self.HOME, password_loc)
        self.experiment_name = experiment_name  # = slice name

        hostname = self.xmlrpc_server["ch"]
        self.domain = hostname[hostname.find('.')+1:]

        self.sliceurn = "urn:publicid:IDN+" + self.domain + "+slice+" + self.experiment_name

        # location of all certificates, encrypted and decrypted
        self.certificate_dir = os.path.dirname(self.certificate_loc)

        # load certificate
        # decrypt them and use that
        # TODO: loading does only work with .crt without key, maybe should look into this
        path = self.certificate_loc
        #path = os.path.join(self.HOME, ".ssl/emucert.crt")
        try:
            f = open(path)
            certdata = f.read()
            f.close()
        except IOError:
            logging.error("Reading of certificate failed. File may not exist?")
            logging.error("File path: ",path)
            raise InitializeError("Could not read certificate file. File may not exist")

        try:
            cert = x509.load_pem_x509_certificate(bytes(certdata,"utf-8"))
        except Exception:
            #raise InitializeError("Could not load certificate")
            logging.error("loading of certificate did not work")

        # passphrase
        if os.path.exists(self.password_loc):
            try:
                passphrase = open(self.password_loc).readline()
                if passphrase == "":
                    logging.info("empty password file, may cause problem")
                    self.password = getpass("Emulab password:")
                else:
                    self.password = passphrase[:-1]
            except IOError:
                logging.error("Error when reading password file")
                self.password = getpass("Emulab password:")
        else:
            logging.error("password file does not exist")
            self.password = getpass("Emulab password:")

        # get self credential, used for most calls at sa (slice authority)
        logging.debug("Getting credentials of user")
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

        logging.info("Successfully setup emulab connection!\n")


    def do_method(self, module, method, params, version=None):
        if module not in self.xmlrpc_server or module not in self.server_path:
            logging.error("Invalid call at: " + module + " in 'do_method' call")
            raise Exception("Invalid server module")
        else:
            addr = self.xmlrpc_server[module]
            path = self.server_path[module]

        uri = "https://" + addr + path + module
        
        if version:
            uri += "/" + version
        url = urlsplit(uri,"https")
        logging.debug("call at uri: " + uri + ", url: " + str(url) + ", method: " + method)

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
                    logging.debug("Try again in a few seonds")
                    time.sleep(5.0)
                    continue
                elif response.status != 200:
                    logging.error("connection error: " + str(response.status) + " " + str(response.reason))
                    return (-1, None)
                else:
                    response = xmlrpclib.loads(response.read())[0][0]
                    break
            except httplib.HTTPException:
                logging.error("http exception")
                return (-1, None)
            except xmlrpclib.Fault:
                e = sys.exc_info()[1]
                if e.faultCode == 503:
                    logging.debug("Retrying in a few seconds")
                    time.sleep(5.0)
                    continue
                else:
                    logging.error("xmlrpclib error")
                    return (-1, None)
            except ssl.CertificateError:
                e = sys.exc_info()[1]
                logging.error("Warning: possible certificate host name mismatch")
                logging.error("Consult: http://www.protogeni.net/trac/protogeni/wiki/HostNameMismatch")
                logging.error(e)
                return (-1, None)

        # If server call successfull
        # Parse the response
        if response["code"] and len(response["output"]):
            logging.debug(response["output"])
        
        rval = response["code"]

        # if there is a code != 0, then return error value
        if rval:
            if response["value"]:
                rval = response["value"]
                logging.warning("Error code at server: " + str(response["value"]))
        return (rval, response)
    

    def do_method_retry(self, suffix, method, params, version=None):
        count = 20
        rval, response = self.do_method(suffix, method, params, version)
        # code 14 means busy, maybe should also do this for code 16 (in progress)
        while count > 0 and response and response["code"] == 14: # code 14 means busy
            count -= 1
            logging.info("try again in a few seconds")
            time.sleep(5.0)
            rval, response = self.do_method(suffix, method, params, version)
        return (rval, response)


    def get_self_credential(self):
        rval, response = self.do_method_retry("sa", "GetCredential", {})
        if rval:
            logging.error("Could not get my credential")
            return None
        else:
            return response["value"]
    

    def getVersion(self):
        rval, response = self.do_method_retry("sa", "GetVersion", {})
        if rval:
            logging.error("Could not obtain API version")
            return None
        else:
            logging.debug("Server version:" + str(response["value"]))
            return response["value"]


    def lookupSlice(self):
        params = {}
        params["credential"] = self.cred
        params["type"] = "Slice"
        params["hrn"] = self.experiment_name # or params["urn"] = self.sliceurn

        rval, response = self.do_method_retry("sa", "Resolve", params)
        if rval:
            logging.warn("Slice does not exist yet or has expired")
            return False
        else:
            logging.debug("Slice already exists")
            #logging.debug(str(response["value"]))
            return True
    

    def createSlice(self, duration=4):
        """Create a new slice with slice name given in initialization (experiment_name)

        Attributes:
            duration -- time until experiation of slice/experiment given in hours 
        """

        # TODO maybe add option to increase expiration time
        # check if slice already exists
        if self.lookupSlice(): return True

        duration *= 60 * 60 # convert from hours to seconds
        validUntil = time.strftime("%Y%m%dT%H:%M:%S", time.gmtime(time.time() + duration))

        params = {}
        params["credential"] = self.cred
        params["type"] = "Slice"
        params["hrn"] = self.experiment_name
        params["expiration"] = validUntil

        rval, response = self.do_method_retry("sa", "Register", params)
        if rval:
            logging.error("Could not create slice:")
            logging.error(str(rval))
            logging.error(str(response))
            return False # or maybe raise exception
        else:
            self.slice = response["value"]
            logging.info("Slice successfully created")
            #logging.info("Slice created: " + str(myslice))
            return True
    

    def getSliceCredential(self):
        params = {}
        params["credentials"] = (self.cred,)
        params["type"] = "Slice"
        params["urn"] = self.sliceurn

        rval, response = self.do_method_retry("sa", "GetCredential", params)
        if rval:
            logging.error("Could not get slice credentials")
            return False
        else:
            logging.debug("Got slice credentials")
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
            logging.info("No specific rpsec given - using default rspec file")

            path = os.path.join(os.path.dirname(__file__), 'default.rspec')
            try:
                f = open(path)
                rspec = f.read()
                f.close()
            except IOError:
                logging.error("Reading of rspec failed. File may not exist?")
                logging.error("File path: ",path)
                return False

        logging.info("Starting sliver creation")

        params = {}
        params["credentials"] = (self.slice,)
        params["slice_urn"] = self.sliceurn
        params["rspec"] = rspec
        params["keys"] = self.keys

        rval, response = self.do_method_retry("cm", "CreateSliver", params)
        if rval:
            logging.error("Could not create sliver")
            return False
        else:
            logging.info("Sliver successfully created")
            self.sliver, self.manifest = response["value"]
            #print("sliver:",self.sliver,"\n\n\n")
            #print("manifest:",self.manifest,"\n\n")
            logging.info("Access nodes with: ssh -p 22 " + self.user + "@<node-name>." + self.experiment_name + ".emulab-net.emulab.net")
            logging.info("This does only work for exclusive/hardware node, VMs have to be accessed using a specific port, see manifest")
            return True


    def lookupSliver(self):
        params = {}
        params["credentials"] = (self.slice,)
        params["urn"] = self.sliceurn
        rval, response = self.do_method_retry("cm", "Resolve", params, version="2.0")
        if rval:
            logging.error("Could not resolve slice")
            return False
        else:
            if not "sliver_urn" in response["value"]:
                logging.error("no sliver found in this slice")
                return False
            else:
                logging.debug("Sliver found" + str(response["value"]["sliver_urn"]))
                #logging.debug("Manifest:" + str(response["value"]["manifest"]))
                self.sliverurn = response["value"]["sliver_urn"]
                self.manifest = response["value"]["manifest"]
                return True


    def getSliverCredential(self):
        params = {}
        params["credentials"] = (self.slice,)
        params["slice_urn"] = self.sliceurn

        rval, response = self.do_method_retry("cm", "GetSliver", params, version="2.0")
        if rval:
            logging.error("Could not get sliver credentials")
            return False
        else:
            logging.debug("Got sliver credentials")
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
            logging.error("Deleting sliver failed")
            return False
        else:
            logging.info("Ticket has been added for remaining time")
            self.ticket = response["value"]
            return True


    def sliverStatus(self):
        self.UpdateSliverInformation()

        params = {}
        params["slice_urn"] = self.sliceurn
        params["credentials"] = (self.sliver,)

        rval, response = self.do_method_retry("cm", "SliverStatus", params, version="2.0")
        if rval:
            logging.error("Could not get sliver status")
            return None
        else:
            return response["value"]
        

    def sliverWaitUntilReady(self, retries=50, interval=30):
        self.UpdateSliverInformation()

        ready = False
        count = 0
        logging.info("Waiting for hardware to start up... (large network setups may take a few minutes to get started up)")
        while not ready or count >= retries:
            count += 1
            status = self.sliverStatus()
            if status is None:
                logging.info("Sliver status unknown")
            else:
                #logging.debug(str(status))
                logging.debug("Current status of sliver:" + status["status"])
                if status["status"] == 'ready':
                    ready = True
                    break
            logging.info("Tried for " + str(count) + "/" + str(retries) + " times. Will try again in " + str(interval) + " seconds.")
            time.sleep(interval)

        return ready

        
    def startExperiment(self, duration=4, rspec=None):
        self.createSlice(duration)
        self.createSliver(rspec)

        if self.sliverWaitUntilReady():
            logging.debug("Experiment is ready")
            return True
        else:
            logging.debug("Experiment is not ready, timeout maybe too low or there was an error when starting up")
            return False


    def stopExperiment(self):
        # TODO: Should also delete slice, otherwise problems might come up for multiple successive experiments
        return self.deleteSliver()

    # Actually not needed, since exclusive VMs get their own address and are accessible through port 22
    def getVMPorts(self):
        self.UpdateSliverInformation()

        if self.manifest is None:
            logging.info("No sliver seems to exist")
            return None
        else:
            logging.debug("Find all ports...")
            #logging.info("in getAddresses() - Manifest:" + str(self.manifest)) 
            pattern = re.compile('port=\"[0-9]+\"')
            matches = pattern.findall(str(self.manifest))
            logging.debug("All ports found:" + str(matches))

            numberPattern = re.compile('[0-9]+')
            result = []
            for i in matches:
                num = (numberPattern.findall(i))[0]
                if num == '22':
                    continue
                else:
                    result.append(num)
            logging.debug("All VM ports:" + str(result))

            
            if len(result) == 0:
                logging.warn("No VM port found")
            elif len(result) > 1:
                logging.warn("Multiple VM ports found")
            else:
                logging.info("One VM port found:" + str(result[0]))
            return result



if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s:: %(levelname)s:: %(message)s',datefmt="%H:%M:%S", level=logging.INFO)

    try:
        #emuConn = emulabConnection("cabart","/home/cabart",".ssl/encrypted.pem",".ssl/password")
        emuConn = emulabConnection("cabart", certificate_loc=".ssl/encrypted.pem",password_loc=".ssl/password")
    except InitializeError as e:
        logging.error("Emulab initialization failed: " + str(e))
        logging.error("Connection could not get established, abort...")
        sys.exit(1)

    logging.info("Setting up has worked")

    #logging.info("Test for server version")
    #version = emuConn.getVersion()
    #logging.info("Version number:" + str(version))

    #logging.info("Test for credentials")
    #cred = emuConn.get_self_credential() 
    #if cred is None:
    #    logging.error("Could not get my credential")
    #else:
    #    logging.info("Did get credentials")
        #print(cred)

    logging.info("Test for slice creation")
    worked = emuConn.createSlice(duration=1)
    if worked:
        logging.info("Successfully created slice")
    else:
        logging.info("Could not create slice")

    logging.info("Test for sliver creation")
    worked = emuConn.createSliver()
    if worked:
        logging.info("Successfully created sliver")
    else:
        logging.info("Could not create sliver")


    logging.info("Wait for experiment to get ready")
    
    ready = emuConn.sliverWaitUntilReady()
    if ready:
        logging.info("experiment is now ready")
    else:
        logging.error("Sliver still not ready, maybe broken: abort")

    

    time.sleep(60)

    logging.info("Test for sliver deletion")
    worked = emuConn.deleteSliver()
    if worked:
        logging.info("Successfully deleted sliver")
    else:
        logging.info("Could not delete sliver")