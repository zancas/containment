# -*- coding: utf-8 -*-
"""Contains the activate command and helper methods.

Functions:
    activate: Activate the given project. If no project name is given, activate
        the current directory.
"""

import json
import os
import pathlib
import subprocess
import sys
import time

import docker

from .types import ProjectId

# COMMUNITY ACQUISITION
COMMUNITY_ROOT_PATH = pathlib.Path(os.getcwd())
PROJECT_NAME = COMMUNITY_ROOT_PATH.name
COMMUNITY = COMMUNITY_ROOT_PATH.joinpath(".containment")
BASE = COMMUNITY.joinpath("base")
COMMUNITY_OS_PACKAGES = COMMUNITY.joinpath("os_packages.json")

# PROFILE ACQUISITION
HOME = os.environ["HOME"]
PROFILE = pathlib.Path(HOME).joinpath(".containment")
PROJECTS_PATH = PROFILE.joinpath("projects")

# PROJECT ACQUISITION
PROJECT = PROJECTS_PATH.joinpath(PROJECT_NAME)
TAG = f"containment/{PROJECT_NAME}"
DOCKERFILE = PROJECT.joinpath("Dockerfile")
RUNFILE = PROJECT.joinpath("run_containment.sh")
ENTRYPOINTFILE = PROJECT.joinpath("entrypoint.sh")
PROJECT_OS_PACKAGES = PROJECT.joinpath("os_packages.json")
PROJECT_LANG_PACKAGES = PROJECT.joinpath("lang_packages.json")

# CONFIGURATION STRING VARIABLE VALUES
COMMUNITY_ROOTDIRNAME = COMMUNITY_ROOT_PATH.absolute().as_posix()
USER = os.environ["USER"]
SHELL = os.environ["SHELL"]
USERID = subprocess.getoutput("id -u")
DOCKERGID = subprocess.getoutput("grep docker /etc/group").split(':')[2]
PROFILE_OS_PACKAGES = ["vim", "tmux", "git"] # These are examples.

# CONFIGURATION STRINGS
PROJ_PLUGIN = \
f"""RUN     useradd -G docker --uid {USERID} --home /home/{USER} {USER}
RUN     echo {USER} ALL=\(ALL\) NOPASSWD: ALL >> /etc/sudoers
COPY    ./entrypoint.sh entrypoint.sh
RUN     chmod +x entrypoint.sh"""
ENTRYPOINT = f"""#! {SHELL}
cd {COMMUNITY_ROOTDIRNAME}
sudo sed -ie s/docker:x:[0-9]*:{USER}/docker:x:{DOCKERGID}:{USER}/g /etc/group
exec {SHELL}"""
RUNSCRIPT = \
f"""docker run -it \
               -v /var/run/docker.sock:/var/run/docker.sock \
               -v {HOME}:{HOME} \
               -v {COMMUNITY_ROOTDIRNAME}:{COMMUNITY_ROOTDIRNAME} \
               --entrypoint=/entrypoint.sh -u {USER}:{DOCKERGID} {TAG}:latest"""


EXTERNALBASIS = ("ubuntu@sha256:c8c275751219dadad8fa56b3ac41ca6cb22219ff117ca9"
                 "8fe82b42f24e1ba64e")
BASETEXT = f"""FROM    {EXTERNALBASIS}
RUN     apt-get update && apt-get install -y sudo docker.io"""

# docker config

client = docker.from_env()
dbuildapi = client.api.build

PKG_INSTALL_CMDS = {"debian":   "apt-get install -y",
                    "ubuntu":   "apt-get install -y",
                    "python3":  "`which pip3` install",
                    "python":   "`which pip` install"}


def _generate_OS_package_install_cmds(package_file):
    """
    take in a dict return a string of docker build RUN directives
    one RUN per package type
    one package type per JSON key
    """
    packages = ' '.join(json.load(package_file.open()))
    if packages:
        for packager in PKG_INSTALL_CMDS:
            if packager in EXTERNALBASIS:
                installer = PKG_INSTALL_CMDS[packager]
        return f'RUN    {installer} {packages}'
    else:
        return ''


def _generate_LANG_package_install_cmds(package_file):
    """
    """
    packages_dict = json.load(package_file.open())
    install_command = ''
    if packages_dict:
        for lang in packages_dict:
            if lang in PKG_INSTALL_CMDS:
                packages = ' '.join(packages_dict[lang])
                installer = PKG_INSTALL_CMDS[lang]
                install_command =\
                    install_command + f'RUN    {installer} {packages}\n'
        return install_command
    else:
        return ''


def pave_profile():
    """
    Usage:
      containment pave_profile
    """
    PROFILE.mkdir()
    json.dump(
        PROFILE_OS_PACKAGES,
        PROFILE.joinpath("os_packages.json").open(mode='w')
    )
    json.dump(
        {},
        PROFILE.joinpath("lang_packages.json").open(mode='w')
    )
    PROJECTS_PATH.mkdir()


def pave_project():
    """
    Usage:
      containment pave_project
    """
    print("Inside pave_project")
    PROJECT.mkdir()
    ENTRYPOINTFILE.write_text(ENTRYPOINT)
    RUNFILE.write_text(RUNSCRIPT)
    print("about to write to ", PROJECT_OS_PACKAGES.absolute().as_posix())
    PROJECT_OS_PACKAGES.write_text("[]")
    PROJECT_LANG_PACKAGES.write_text("{}")
    write_dockerfile()


def pave_community():
    """
    Usage:
      containment pave_community
    """
    print("pave_community is executing!!")
    COMMUNITY.mkdir()
    BASE.write_text(BASETEXT)
    COMMUNITY_OS_PACKAGES.write_text("[]")


def _assure_config():
    if not COMMUNITY.is_dir():
        pave_community()
    if not PROFILE.is_dir():
        pave_profile()
    if not PROJECT.is_dir():
        pave_project()


def write_dockerfile():
    """
    Usage:
      containment write_dockerfile  
    """
    docker_text = _assemble_dockerfile()
    DOCKERFILE.write_text(docker_text)


def _assemble_dockerfile():
    BASE_LAYER = BASE.read_text()
    COMMUNITY_OS_LAYER = _generate_OS_package_install_cmds(
        COMMUNITY.joinpath("os_packages.json")) 
    PROFILE_OS_LAYER = _generate_OS_package_install_cmds(
        PROFILE.joinpath("os_packages.json")) 
    PROJECT_OS_LAYER = _generate_OS_package_install_cmds(
        PROJECT.joinpath("os_packages.json")) 
    COMMUNITY_LANG_LAYER = _generate_LANG_package_install_cmds(
        COMMUNITY.joinpath("lang_packages.json")) 
    PROFILE_LANG_LAYER = _generate_LANG_package_install_cmds(
        PROFILE.joinpath("lang_packages.json")) 
    PROJECT_LANG_LAYER = _generate_LANG_package_install_cmds(
        PROJECT.joinpath("lang_packages.json")) 
    DOCKERTEXT = '\n'.join([BASE_LAYER,
                            COMMUNITY_OS_LAYER,
                            PROFILE_OS_LAYER,
                            PROJECT_OS_LAYER,
                            COMMUNITY_LANG_LAYER,
                            PROFILE_LANG_LAYER,
                            PROJECT_LANG_LAYER,
                            PROJ_PLUGIN])
    return DOCKERTEXT
        

def build():
    """
    Usage:
      containment build
    """
    build_actions = []
    for a in dbuildapi(PROJECT.absolute().as_posix(), tag=TAG):
        print(a)
        build_actions.append(a)


def run():
    """
    Usage:
      containment run
    """
    run_string = RUNFILE.read_text()
    run_command = run_string.split()
    chmod_string = "chmod +x " + RUNFILE.absolute().as_posix()
    chmod_run = subprocess.run(chmod_string.split())
    run_subprocess = subprocess.run(run_command,
                                    stdin=sys.stdin,
                                    stdout=sys.stdout,
                                    stderr=sys.stderr)
    

def activate():
    """
    Usage:
      containment activate
    """
    # This is derived from the clone
    _assure_config() 
    write_dockerfile()
    build()
    run()
