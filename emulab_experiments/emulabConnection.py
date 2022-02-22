# Code is loosely based on https://gitlab.flux.utah.edu/emulab/emulab-devel/-/tree/master/protogeni/tutorial and https://gitlab.flux.utah.edu/emulab/emulab-stable/-/tree/master/protogeni/test
# Goal is to make it object-oriented so it is easier and flexible to handle, and implement it so it works in python3

# Note: has to be run with sudo permissions

from getpass import getpass
import sys
import pwd
import getopt
import time
import os
import re
import xmlrpc
import traceback
import ssl

# server connection libraries
from urllib.parse import urlsplit, urlunsplit
from urllib.parse import urlparse
import xmlrpc.client as xmlrpclib
import http.client as httplib

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.x509.oid import ExtensionOID

# Todo: add logging
import logging

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


class InitializeError(Exception):
    """Exception when initializing emulab connection class"""

    def __init__(self, message="error when initializing emulab connection"):
        super().__init__(message)


class emulabConnection:
    # emulab server
    xmlrpc_server = {"ch": "www.emulab.net", "sr": "www.emulab.net", "sa": "www.emulab.net"}
    server_path = {"ch": ":12369/protogeni/xmlrpc/", "sr": ":12370/protogeni/pubxmlrpc/", "sa": ":12369/protogeni/xmlrpc/"}

    # all locations relative to home location, home location has to be an absolute path
    def __init__(self, user, home_loc, certificate_loc, password_loc, experiment_name="emulab-experiment"):
        logging.info("Start emulab connection setup")

        self.user = user
        self.HOME = home_loc
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
        cred = self.get_self_credential()
        if cred == -1:
            raise InitializeError("Could not get self credential when setting up emulab connection")
        else:
            self.cred = cred

        logging.info("Successfully setup emulab connection")


    def do_method(self, module, method, params, version=None):
        if module not in self.xmlrpc_server or module not in self.server_path:
            logging.error("Invalid call at:",module,"in do_method call")
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
        return (rval, response)
    

    def do_method_retry(self, suffix, method, params):
        count = 200
        rval, response = self.do_method(suffix, method, params)
        while count > 0 and response and response["code"] == 14:
            count -= 1
            logging.info("try again in a few seconds")
            time.sleep(5.0)
            rval, response = self.do_method(suffix, method, params)
        return (rval, response)

    def get_self_credential(self):
        params = {}
        rval, response = self.do_method_retry("sa", "GetCredential", params)
        if rval:
            logging.error("Could not get my credential")
            return -1
        else:
            return response["value"]
    
    def getVersion(self):
        rval, response = self.do_method("sa", "GetVersion", {})
        if rval:
            logging.error("Could not obtain API version")
            return -1
        else:
            logging.debug("Server version:" + str(response["value"]))
            return response["value"]

    def lookupSlice(self):
        
        params = {}
        params["credential"] = self.cred
        params["type"] = "Slice"
        params["hrn"] = self.experiment_name
        rval, response = self.do_method_retry("sa", "Resolve", params)
        if rval == 0:
            logging.info("Slice already exists")
            #logging.debug(str(response["value"]))
            return True
        else:
            logging.info("Slice does not exist yet")
            return False
    
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
            myslice = response["value"]
            logging.info("Slice successfully created")
            #logging.info("Slice created: " + str(myslice))
            return True



if __name__ == "__main__":
    try:
        emuConn = emulabConnection("cabart","/home/cabart",".ssl/encrypted.pem",".ssl/password")
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
    #if cred == -1:
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

