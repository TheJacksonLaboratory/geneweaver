# TODO: Should be deprecated with python2
from __future__ import print_function

import os
import configparser


## Just as a reminder: the configuration file (geneweaver.cfg) should NEVER be
## included in version control, especially if it has any usernames, passwords,
## or API keys.
rootpath="/srv/geneweaver/"
CONFIG_PATH = rootpath+'geneweaver.cfg'

## Global config object, sholudn't be accessed directly but using the helper
## functions found below.
CONFIG = None


def createConfig():
    """
    Generates a new configuration file in the current directory. The config
    file uses the common INI style which can be parsed with python's
    configparser module.

    :ret:
    """

    with open(CONFIG_PATH, 'w') as fl:
        print('## GeneWeaver Configuration File', file=fl)
        print('#', file=fl)
        print('', file=fl)
        print('[application]', file=fl)
        print('host = 127.0.0.1', file=fl)
        print('results = '+rootpath+'website-py/results', file=fl)
        print('secret = ' + os.urandom(32).encode('hex'), file=fl)
        print('help_url = http://geneweaver.org/help', file=fl)
        print('', file=fl)
        print('[celery]', file=fl)
        print('url = amqp://guest@localhost//', file=fl)
        print('backend = amqp', file=fl)
        print('', file=fl)
        print('[db]', file=fl)
        print('database = dbname', file=fl)
        print('user = user', file=fl)
        print('password = somepassword', file=fl)
        print('host = 127.0.0.1', file=fl)
        print('port = 5432', file=fl)
        print('', file=fl)
        print('[sphinx]', file=fl)
        print('host = 127.0.0.1', file=fl)
        print('port = 9312', file=fl)
        print('', file=fl)

def checkIntegrity():
    """
    Checks to make sure all the key-value pairs have values and fills in any
    missing spots so the app won't crash later.
    """

    sections = ['application', 'celery', 'db', 'sphinx']

    for sec in sections:
        for key, val in CONFIG.items(sec):
            if not val:
                val = '0'

                CONFIG.set(sec, key, val)

def loadConfig():
    """
    Attempts to load and parse a config file.
    """

    if not os.path.exists(CONFIG_PATH):
        createConfig()

        raise IOError(('Could not find a config file, so we made '
                       'one for you. Please fill it out.'))

    ## Assumes the config file info is correct. The app will throw exceptions
    ## later anyway if any of the parameters are wrong.
    CONFIG.read(CONFIG_PATH)

    checkIntegrity()

def get(section, option):
    """
    Returns the value of a section, key pair from the global config object.

    :ret str: some config value
    """

    return CONFIG.get(section, option)


def getInt(section, option):
    """
    Returns the value of a section, key pair from the global config object as
    an int.

    :ret str: some config value
    """

    return CONFIG.getint(section, option)

## This config module should be included prior to any others since other parts
## of the app may need to access its variables. The config will attempt to load
## and parse everything as soon as it's imported.
if not CONFIG:
    CONFIG = configparser.RawConfigParser(allow_no_value=True)
    loadConfig()

if __name__ == '__main__':
    loadConfig()
