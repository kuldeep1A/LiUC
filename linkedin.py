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
        self.name = self.split_name(name)

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

    @staticmethod
    def split_name(name):
        """
        Takes a name (string) and returns a list of individual name-parts (dict).

        Some people have funny names. We assume the most important name are:
        first name, last name, and the name of right before the last name (if they have one)
        """
        parsed = re.split(' |-', name)

        if len(parsed) > 2:
            split_name = {'first': parsed[0], 'second': parsed[-2], 'last': parsed[-1]}
        else:
            split_name = {'first': parsed[0], 'second': '', 'last': parsed[-1]}

        return split_name

    def f_last(self):
        """rahulsharma"""
        names = set()
        names.add(self.name['first'][0] + self.name['last'])

        if self.name['second']:
            names.add(self.name['first'][0] + self.name['second'])

        return names

    def f_dot_last(self):
        """rahul.sharma"""
        names = set()
        names.add(self.name['first'][0] + '.' + self.name['last'])

        if self.name['second']:
            names.add(self.name['first'][0] + '.' + self.name['second'])

        return names

    def last_f(self):
        """sharmarahul"""
        names = set()
        names.add(self.name['last'] + self.name['first'][0])

        if self.name['second']:
            names.add(self.name['second'] + self.name['first'][0])

        return names

    def first_dot_last(self):
        """rahul.sharma"""
        names = set()
        names.add(self.name['first'] + '.' + self.name['last'])

        if self.name['second']:
            names.add(self.name['first'] + '.' + self.name['second'])

        return names

    def first_l(self):
        """rahuls"""
        names = set()
        names.add(self.name['first'] + self.name['last'][0])

        if self.name['second']:
            names.add(self.name['first'] + self.name['second'][0])

        return names

    def first(self):
        """rahul"""
        names = set()
        names.add(self.name['first'])

        return names


def parse_arguments():
    """
    Handle user-supplied arguments
    """
    desc = ('OSINT tool to generate lists of probable usernames from a'
            ' given company\'s LinkedIn page. This tool may break when'
            ' LinkedIn changes their site.')

    parser = argparse.ArgumentParser(description=desc)

    parser.add_argument('-u', '--username', type=str, action='store',
                        required=True,
                        help='A valid LinkedIn username.')
    parser.add_argument('-c', '--company', type=str, action='store',
                        required=True,
                        help='Company name exactly as typed in the compnay '
                             'linkedin profile page URL.')
    parser.add_argument('-p', '--password', type=str, action='store',
                        help='Specify your password in clear-text on the '
                             'command line. If not specified, will prompt and '
                             'obfuscate as you type.')
    parser.add_argument('-n', '--domain', type=str, action='store',
                        default='',
                        help='Append a domain name to username output. '
                             '[example: "-n uber.com" would output nikita@uber.com]')
    parser.add_argument('-d', '--depth', type=int, action='store',
                        default=False,
                        help='Search depth (how many loops of 25). If unset, '
                             'will try to grab them all.')
    parser.add_argument('-s', '--sleep', type=int, action='store', default=0,
                        help='Seconds to sleep between search loops.'
                             ' Defaults to 0.')
    parser.add_argument('-x', '--proxy', type=str, action='store',
                        default=False,
                        help='Proxy server to use.WARNING: WILL DISABLE SSL '
                             'VERIFICATION. [example: "-p https://localhost:8080"]')
    parser.add_argument('-k', '--keywords', type=str, action='store',
                        default=False,
                        help='Filter results by a a list of command separated '
                             'keywords. Will do a separate loop for each keyword, '
                             'potentially bypassing the 1,000 record limit. '
                             '[example: "-k \'sales,human resources,information '
                             'technology\']')
    parser.add_argument('-g', '--geoblast', default=False, action="store_true",
                        help='Attempts to bypass the 1,000 record search limit'
                             ' by running multiple searches split across geographic'
                             ' regions.')
    parser.add_argument('-o', '--output', default="li2u-output", action="store",
                        help='Output Directory, defaults to li2u-output')

    args = parser.parse_args()

    # Proxy argument is fed to requests as a dictionary, setting this now:
    args.proxy_dict = {"https": args.proxy}

    # If appending an email address, preparing this string now:
    if args.domain:
        args.domain = '@' + args.domain

        # Keywords are fed in as a list. Splitting comma-separated user input now:
    if args.keywords:
        args.keywords = args.keywords.split(',')

        # These two functions are not currently compatible, squashing this now:
    if args.keywords and args.geoblast:
        print("Sorry, keywords and geoblast are currently not compatible. Use one or the other.")
        sys.exit()

        # If password is not passed in the command line, prompt for it
    # in a more secure fashion (not shown on screen)
    args.password = args.password or getpass.getpass()

    return args


def login(args):
    """
    Creates a new authenticated session.

    Note that a mobile user agent is used. Parsing using the desktop results
    proved extremely difficult, as shared connections would be returned in
    a manner that was indistinguishable from the desired targets.

    The other header matters as well, otherwise advanced search functions
    (region and keyword) will not work.

    The function will check for common failure scenarios - the most common is
    logging in from a new location. Accounts using multi-factor auth are not
    yet supported and will produce an error.
    """
    session = requests.session()
    # The following are know errors that require the user to log in via the web
    login_problems = ['challenge', 'captcha', 'manage-account', 'add-email']

    # Special options below when using a proxy server. Helpful for debugging
    # the application in Burp Suite.
    if args.proxy:
        print("[!] Using a proxy, ignoring SSL errors. Don't get pwned.")
        session.verify = False
        urllib3.disable_warnings(category=urllib3.exceptions.InsecureRequestWarning)
        session.proxies.update(args.proxy_dict)

    # Our search and regex will work only with a mobile user agent and
    # the correct REST protocol specified below.
    mobile_agent = ('Mozilla/5.0 (Linux; U; Android 4.4.2; en-us; SCH-I535 '
                    'Build/KOT49H) AppleWebKit/534.30 (KHTML, like Gecko) '
                    'Version/4.0 Mobile Safari/534.30')
    session.headers.update({'User-Agent': mobile_agent,
                            'X-RestLi-Protocol-Version': '2.0.0'})

    # We wll grab an anonymous response to look for the CSRF token, which
    # is required for our logon attempt.
    anon_response = session.get('https://www.linkedin.com/login')
    login_csrf = re.findall(r'name="loginCsrfParm" value="(.*?)',
                            anon_response.text)
    if login_csrf:
        login_csrf = login_csrf[0]

    else:
        print("Having trouble loading login page... try the command again.")
        sys.exit()

    # Define the data we will POST for our login.
    auth_payload = {
        'session_key': args.username,
        'session_password': args.password,
        'isJsEnabled': 'false',
        'loginCsrfParam': login_csrf
    }

    # Perform the actual login. We disable redirects as we will use the 302
    # as an indicator of a successful logon.
    response = session.post('https://www.linkedin.com/checkpoint/lg/login-submit'
                            '?loginSubmitSource=GUEST_HOME',
                            data=auth_payload, allow_redirects=False)

    # Define a successful login by the 302 redirect to the 'feed' page. Try
    # to detect some other common logon failures and alert the user.
    if response.status_code in (302, 303):
        # Add CSRF token for all additional requests
        session = set_csrf_token(session)
        redirect = response.headers['Location']


def set_csrf_token(session):
    """Extract the required CSRF token.

    Some functions requires a CSRF token equal to the JSESSIONID.
    """
    csrf_token = session.cookies['JSESSIONID'].replace('"', '')
    session.headers.update({'Csrf-Token': csrf_token})
    return session
