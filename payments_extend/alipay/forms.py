import binascii
import collections
import hashlib
import json
import copy
from urllib.parse import quote_plus, urlencode

from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import redirect
from django.utils.translation import pgettext_lazy

from payments import BasicProvider
import requests

from .exceptions import MissingParameter
from .exceptions import ParameterValueError
from .exceptions import TkoenAuthorizationError

# maybe, I need to implement a django form?
