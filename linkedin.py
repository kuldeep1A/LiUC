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


class NameMutator:

    def __init__(self, name):
        self.name = self.clean_name(name)

    @staticmethod
    def clean_name(name):
        """
        Removes common punctuation.

        LinkedIn's users tend to add credentials to their names to look special.
        This function is based on what I have seen in large searches, and attempts
        to remove them.
        """
        # Lower-case everything to make it easier to de-duplicate.
        name = name.lower()

        # Use case for tool is mostly standard English, try to standardize common non-English
        # characters.
        name = re.sub("[àáâãäå]", 'a', name)
        name = re.sub("[èéêë]", 'e', name)
        name = re.sub("[ìíîï]", 'i', name)
        name = re.sub("[òóôõö]", 'o', name)
        name = re.sub("[ùúûü]", 'u', name)
        name = re.sub("[ýÿ]", 'y', name)
        name = re.sub("[ß]", 'ss', name)
        name = re.sub("[ñ]", 'n', name)

        # Get rid of all things in parentheses. Lots of people put various credentials, etc
        name = re.sub(r'\([^()]*\)', '', name)

        # The lines below basically trash anything weird left over.
        # A lot of users have funny things in their names, like () or ''
        # People like to feel special, I guess.
        allowed_chars = re.compile('[^a-zA-Z -]')
        name = allowed_chars.sub('', name)

        # We get rid of common titles.
        titles = ['mr', 'miss', 'mrs', 'phd', 'prof', 'professor', 'md', 'dr', 'mba']
        pattern = "\\b(" + "|".join(titles) + ")\\b"
        name = re.sub(pattern, '', name)

        # The line below tries to consolidate white space between words
        # and get rid of leading/trailing spaces.
        name = re.sub(r'\s+', ' ', name).strip()

        return name





