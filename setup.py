from setuptools import setup

APP = ['Sheet/main.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': True,
    'packages': ['flask',
                 'google_auth_oauthlib',
                 'googleapiclient'],
}

setup(
    app=APP,
    name='GoogleSheetsAutomation',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
