import os
import sys
import re
import time
import argparse
import getpass
import json
import urllib.parse
import requests
import urllib3


# The dictionary below is a best-effort attempt to spread a search load
# across sets of geographic locations. This can bypass the 1000 result
# search limit as we are now allowed 1000 per geo set.
# developer.linkedin.com/docs/v1/companies/targeting-company-shares#additionalcodes
GEO_REGIONS = {
    'r0': 'us:0',
    'r1': 'ca:0',
    'r2': 'gb:0',
    'r3': 'au:0|nz:0',
    'r4': 'cn:0|hk:0',
    'r5': 'jp:0|kr:0|my:0|np:0|ph:0|sg:0|lk:0|tw:0|th:0|vn:0',
    'r6': 'in:0',
    'r7': 'at:0|be:0|bg:0|hr:0|cz:0|dk:0|fi:0',
    'r8': 'fr:0|de:0',
    'r9': 'gr:0|hu:0|ie:0|it:0|lt:0|nl:0|no:0|pl:0|pt:0',
    'r10': 'ro:0|ru:0|rs:0|sk:0|es:0|se:0|ch:0|tr:0|ua:0',
    'r11': ('ar:0|bo:0|br:0|cl:0|co:0|cr:0|do:0|ec:0|gt:0|mx:0|pa:0|pe:0'
            '|pr:0|tt:0|uy:0|ve:0'),
    'r12': 'af:0|bh:0|il:0|jo:0|kw:0|pk:0|qa:0|sa:0|ae:0'}

