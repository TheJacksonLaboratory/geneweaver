import configparser
import os

# Just as a reminder: the configuration file should NEVER be included in
# version control, especially if it has any usernames, passwords, or API keys.
CONFIG_PATH = '/srv/geneweaver/tools.cfg'
# CONFIG_PATH = '/srv/www/geneweaver/tools.cfg'

# Global config object, shouldn't be accessed directly but using the helper
# functions found below.
CONFIG = None

def create_config():
    """
    Generates a new configuration file in the current directory. The config
    file uses the common INI style which can be parsed with python's
    ConfigParser module.
    """

    with open(CONFIG_PATH, 'w') as fl:
        print('## GeneWeaver Toolset Configuration File', file=fl)
        print('#', file=fl)
        print('', file=fl)
        print('[tools]', file=fl)
        print('results = /opt/geneweaver/results', file=fl)
        print('tool_dir = /opt/geneweaver/tools', file=fl)
        print('', file=fl)
        print('[celery]', file=fl)
        print('backend = amqp', file=fl)
        print('url = amqp://geneweaver:geneweaver@localhost:5672/geneweaver', file=fl)
        print('', file=fl)
        print('[db]', file=fl)
        print('database = dbname', file=fl)
        print('user = user', file=fl)
        print('password = somepassword', file=fl)
        print('host = 127.0.0.1', file=fl)
        print('port = 5432', file=fl)
        print('', file=fl)

def check_integrity():
    """
    Checks to make sure all the key-value pairs have values and fills in any
    missing spots so the app won't crash later.
    """

    sections = ['tools', 'db']

    for sec in sections:
        for key, val in CONFIG.items(sec):
            if not val:
                val = '0'

                CONFIG.set(sec, key, val)

def load_config():
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

def get_int(section, option):
    """
    Returns the value of a section, key pair from the global config object as
    an int.

    :ret str: some config value
    """

    return CONFIG.getint(section, option)


# TODO: Get rid of these once nothing depends on them
# Non-PEP8 function alias for historical purposes
createConfig = create_config
checkIntegrity = check_integrity
loadConfig = load_config
getInt = get_int

# This config module should be included prior to any others since other parts
# of the app may need to access its variables. The config will attempt to load
# and parse everything as soon as it's imported.
if not CONFIG:
    CONFIG = configparser.RawConfigParser(allow_no_value=True)
    load_config()

if __name__ == '__main__':
    load_config()
