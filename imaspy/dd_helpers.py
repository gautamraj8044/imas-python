"""Helper functions to build IDSDef.xml"""

import glob
import logging
import os
import re
import shutil
import subprocess
from distutils.version import StrictVersion as V
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZIP_DEFLATED, ZipFile

logger = logging.getLogger("imaspy")
logger.setLevel(logging.WARNING)


def prepare_data_dictionaries():
    """Build IMAS IDSDef.xml files for each tagged version in the DD repository
    1. Search for saxon or download it
    2. Clone the DD repository (ask for user/pass unless ssh key access is available)
    3. Generate IDSDef.xml and rename to IDSDef_${version}.xml
    4. Zip all these IDSDefs together and include in wheel
    """
    saxon_jar_path = get_saxon()
    repo = get_data_dictionary_repo()
    if repo:
        for tag in repo.tags:
            if V(str(tag)) > V("3.21.1"):
                logger.debug("Building data dictionary version %s", tag)
                build_data_dictionary(repo, tag, saxon_jar_path)

        logger.info("Creating zip file of DD versions")

        if os.path.isfile("data-dictionary/IDSDef.zip"):
            logger.warning("Overwriting data-dictionary/IDSDef.zip")

        with ZipFile(
            "data-dictionary/IDSDef.zip",
            mode="w",  # this needs w, since zip can have multiple same entries
            compression=ZIP_DEFLATED,
        ) as dd_zip:
            for filename in glob.glob("data-dictionary/[0-9]*.xml"):
                dd_zip.write(filename)


def get_saxon():
    """Search for saxon*.jar and return the path or download it.
    The DD build only works by having saxon9he.jar in the CLASSPATH (until 3.30.0).
    We will 'cheat' a little bit later by symlinking saxon9he.jar to any version
    of saxon we found.

    Check:
    1. CLASSPATH
    2. `which saxon`
    3. /usr/share/java/*
    4. or download it
    """

    local_saxon_path = os.getcwd() + "/saxon9he.jar"
    if os.path.exists(local_saxon_path):
        logger.debug("Something already at ./saxon9he.jar, not creating anew")
        return local_saxon_path

    saxon_jar_origin = Path(
        find_saxon_classpath()
        or find_saxon_bin()
        or find_saxon_jar()
        or download_saxon()
    )
    if not saxon_jar_origin.name == "saxon9he.jar":
        os.symlink(saxon_jar_origin, local_saxon_path)
        return local_saxon_path
    return str(saxon_jar_origin)


def find_saxon_jar():
    # This finds multiple versions on my system, but they are symlinked together.
    # take the shortest one.
    jars = [
        path
        for path in Path("/usr/share/java").rglob("*")
        if re.match("saxon(.*).jar", path.name, flags=re.IGNORECASE)
    ]

    if jars:
        saxon_jar_path = min(jars, key=lambda x: len(x.parts))
        return saxon_jar_path


def find_saxon_classpath():
    if "CLASSPATH" in os.environ:
        saxon_jar_path = re.search("[^:]*saxon[^:]*jar", os.environ["CLASSPATH"])
        if saxon_jar_path:
            return saxon_jar_path.group(0)


def find_saxon_bin():
    saxon_bin = shutil.which("saxon")
    if saxon_bin:
        with open(saxon_bin, "r") as file:
            for line in file:
                saxon_jar_path = re.search("[^ ]*saxon[^ ]*jar", line)
                if saxon_jar_path:
                    return saxon_jar_path.group(0)


def download_saxon():
    """Downloads a zipfile containing saxon9he.jar and extract it to the current dir.
    Return the full path to saxon9he.jar"""

    SAXON_PATH = (
        "https://iweb.dl.sourceforge.net/project/saxon/Saxon-HE/9.9/SaxonHE9-9-1-4J.zip"
    )

    resp = urlopen(SAXON_PATH)
    zipfile = ZipFile(BytesIO(resp.read()))
    path = zipfile.extract("saxon9he.jar")
    del zipfile
    return path


def get_data_dictionary_repo():
    try:
        import git  # Import git here, the user might not have it!
    except ModuleNotFoundError:
        logger.warning(
            "Could not find 'git' module, try 'pip install gitpython'. \
            Will not build Data Dictionaries!"
        )
        return False, False

        # We need the actual source code (for now) so grab it from ITER
    dd_repo_path = "data-dictionary"

    if "DD_DIRECTORY" in os.environ:
        logger.info("Found DD_DIRECTORY, copying")
        try:
            shutil.copytree(os.environ["DD_DIRECTORY"], dd_repo_path)
        except FileExistsError:
            pass
    else:
        logger.info("Trying to pull data dictionary git repo from ITER")

    # Set up a bare repo and fetch the access-layer repository in it
    os.makedirs(dd_repo_path, exist_ok=True)
    try:
        repo = git.Repo(dd_repo_path)
    except git.exc.InvalidGitRepositoryError:
        repo = git.Repo.init(dd_repo_path)
    logger.info("Set up local git repository {!s}".format(repo))

    try:
        origin = repo.remote()
    except ValueError:
        dd_repo_url = "ssh://git@git.iter.org/imas/data-dictionary.git"
        origin = repo.create_remote("origin", url=dd_repo_url)
    logger.info("Set up remote '{!s}' linking to '{!s}'".format(origin, origin.url))

    try:
        origin.fetch("--tags")
    except git.exc.GitCommandError:
        logger.warning("Could not fetch tags from %s", list(origin.urls))
    logger.info("Remote tags fetched")
    return repo


def build_data_dictionary(repo, tag, saxon_jar_path, rebuild=False):
    """Build a single version of the data dictionary given by the tag argument
    if the IDS does not already exist.

    In the data-dictionary repository sometimes IDSDef.xml is stored
    directly, in which case we do not call make.
    """
    if (
        os.path.exists("data-dictionary/{version}.xml".format(version=tag))
        and not rebuild
    ):
        return

    repo.git.checkout(tag, force=True)
    # this could cause issues if someone else has added or left IDSDef.xml
    # in this directory. However, we go through the tags in order
    # so 1.0.0 comes first, where git checks out IDSDef.xml
    if not os.path.exists("data-dictionary/IDSDef.xml"):
        try:
            subprocess.check_output(
                "make IDSDef.xml 2>/dev/null",
                cwd=os.getcwd() + "/data-dictionary",
                shell=True,
                env={"CLASSPATH": saxon_jar_path, "PATH": os.environ["PATH"]},
            )
        except subprocess.CalledProcessError:
            logger.warning("Error making DD version {version}", version=tag)
    # copy and delete original instead of move (to follow symlink)
    try:
        shutil.copy(
            "data-dictionary/IDSDef.xml",
            "data-dictionary/{version}.xml".format(version=tag),
            follow_symlinks=True,
        )
    except shutil.SameFileError:
        pass
    os.remove("data-dictionary/IDSDef.xml")
