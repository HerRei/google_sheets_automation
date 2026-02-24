from setuptools import setup

APP = ['main.py']          # oder 'app.py', je nachdem, wie deine Hauptdatei heißt
DATA_FILES = ['client_secret.json', 'token.json']  # falls du noch weitere Dateien brauchst
OPTIONS = {
    'argv_emulation': True,           # sorgt dafür, dass sys.argv korrekt übergeben wird
    'packages': ['flask',
                 'google_auth_oauthlib',
                 'googleapiclient'],
    # falls du Templates oder static-Ordner nutzt, kannst du sie hier
    # ebenfalls per include_package_data oder package_data reinpacken
}

setup(
    app=APP,
    name='LieferProtokoll',            # der Name deiner App
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
