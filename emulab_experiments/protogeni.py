
# maybe needed for the protogeni approach
from urllib.parse import urlsplit, urlunsplit
from urllib.request import splitport
import xmlrpc.client as xmlrpclib
import http.client as httplib
import os
import getopt
import sys
import time
import traceback
import ssl
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import NameOID
from cryptography.x509.oid import ExtensionOID
