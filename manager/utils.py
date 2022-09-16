import fnmatch
import glob
import os
import stat
import warnings
from pathlib import Path
from typing import Union

import appdirs
import paramiko
import yaml
from ftpsync.synchronizers import DownloadSynchronizer, UploadSynchronizer


def path_already_stars_with_base_dir(base_dir: Path, path_: Path):
    return path_.as_posix().startswith(base_dir.as_posix())


def message_user(message: str):
    """
    Temporary centralised way to message user.
    """
    print(message)


def make_dirs(paths: Union[str, list]):
    """
    For path or list of path, make them if do not already exist.
    """
    if isinstance(paths, str):
        paths = [paths]

    for path_ in paths:
        if not os.path.isdir(path_):
            os.makedirs(path_)
        else:
            warnings.warn(
                "The following directory was not made because it already exists"
                f" {path_}"
            )


def ensure_prefixes_on_list_of_names(names, prefix):
    """ """
    n_chars = len(prefix)
    return [
        prefix + name if name[:n_chars] != prefix else name for name in names
    ]


def get_user_appdir_path(project_name):
    """
    It is not possible to write to programfiles in windows from app without admin permissions
    However if admin permission given drag and drop dont work, and it is not good practice.
    Use appdirs module to get the AppData cross-platform and save / load all files form here .
    """
    base_path = Path(
        os.path.join(appdirs.user_data_dir("ProjectManagerSWC"), project_name)
    )

    if not os.path.isdir(base_path):
        os.makedirs(base_path)

    return base_path


def raise_error(message: str):
    """
    Temporary centralized way to raise and error
    """
    raise BaseException(message)


def process_names(names: Union[list, str], prefix: str):
    """
    Check a single or list of input session or subject names. First check the type is correct,
    next prepend the prefix sub- or ses- to entries that do not have the relevant prefix. Finally,
    check for duplicates.

    :param names: str or list containing sub or ses names (e.g. to make dirs)
    :param prefix: "sub" or "ses" - this defines the prefix checks.
    """
    if type(names) not in [str, list] or any(
        [not isinstance(ele, str) for ele in names]
    ):
        raise_error(
            "Ensure subject and session names are list of strings, or string"
        )
        return False

    if isinstance(names, str):
        names = [names]

    prefixed_names = ensure_prefixes_on_list_of_names(names, prefix)

    if len(prefixed_names) != len(set(prefixed_names)):
        raise_error(
            "Subject and session names but all be unqiue (i.e. there are no"
            " duplicates in list input)"
        )

    return prefixed_names


# ssh


def connect_client(
    client: paramiko.SSHClient,
    remote_host_id: str,
    remote_host_username: str,
    hostkeys: str,
    password: str = None,
    private_key_path: str = None,
):
    """
    Connect client to remote server using paramiko.
    Accept either password or path to private key, but not both.
    """
    try:
        client.get_host_keys().load(hostkeys)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.connect(
            remote_host_id,
            username=remote_host_username,
            password=password,
            key_filename=private_key_path,
            look_for_keys=True,
        )
    except Exception:
        raise_error(
            "Could not connect to server. Ensure that \n1) You are on SWC network"
            f" / VPN. \n2) The remote_host_id: {remote_host_id} is"
            " correct.\n3) The remote username:"
            f" {remote_host_username}, and password are correct."
        )


def setup_authorized_keys_over_client(client, key):
    """
    Append the public part of key to remote server ~/.ssh/authorized_keys.
    """
    client.exec_command("mkdir -p ~/.ssh/")
    client.exec_command(
        # double >> for concatenate
        f'echo "{key.get_name()} {key.get_base64()}" >> ~/.ssh/authorized_keys'
    )
    client.exec_command("chmod 644 ~/.ssh/authorized_keys")
    client.exec_command("chmod 700 ~/.ssh/")


def verify_ssh_remote_host(remote_host_id, hostkeys):
    """ """
    with paramiko.Transport(remote_host_id) as transport:
        transport.connect()
        key = transport.get_remote_server_key()

    message_user(
        "The host key is not cached for this server:"
        f" {remote_host_id}.\nYou have no guarantee that the server is"
        f" the computer you think it is.\nThe server's {key.get_name()} key"
        f" fingerprint is: {key.get_base64()}\nIf you trust this host, to connect"
        " and cache the host key, press y: "
    )
    input_ = input()

    if input_ == "y":
        client = paramiko.SSHClient()
        client.get_host_keys().add(remote_host_id, key.get_name(), key)
        client.get_host_keys().save(hostkeys)
        sucess = True
    else:
        message_user("Host not accepted. No connection made.")
        sucess = False

    return sucess


def generate_and_write_ssh_key(ssh_key_path):
    key = paramiko.RSAKey.generate(4096)
    key.write_private_key_file(ssh_key_path)


def get_list_of_directory_names_over_sftp(sftp, search_path, search_prefix):

    all_dirnames = []
    try:
        for file_or_dir in sftp.listdir_attr(search_path):
            if stat.S_ISDIR(file_or_dir.st_mode):
                if fnmatch.fnmatch(file_or_dir.filename, search_prefix):
                    all_dirnames.append(file_or_dir.filename)
    except FileNotFoundError:
        raise_error(f"No file found at {search_path}")

    return all_dirnames


def search_filesystem_path_for_directories(search_path_with_prefix: str):
    """
    Use glob to search the full search path (including prefix) with glob.
    Files are filtered out of results, returning directories only.
    """
    all_dirnames = []
    for file_or_dir in glob.glob(search_path_with_prefix):
        if os.path.isdir(file_or_dir):
            all_dirnames.append(os.path.basename(file_or_dir))
    return all_dirnames


def get_default_syncronizer_opts(preview: bool):
    """
    Retrieve the default options for upload and download. These
    are very important as define the behaviour of file transfer
    when there are conflicts (e.g. whether to delete remote
    file if it is not found on the local filesystem).

    Currently, all options are set so that no file is ever overwritten.
    If there is a remote directory that is older than the local directory, it will not
    be overwritten. The only 'overwrite' that occurs is if the remote
    or local directory has been deleted - by default this will not be replaced as
    pyftpsync metadata indicates the file has been deleted. Using the default
    'force' option will force file transfer, but also has other effects e.g.
    overwriting newer files with old, which we dont want. This option has been
    edited to permit a "restore" argumnent, which acts Force=False except
    in the case where the local / remote file has been deleted entirely, in which
    case it will be replaced.

    :param preview: run pyftpsync's "dry_run" option.
    """
    opts = {
        "help": False,
        "verbose": 5,
        "quiet": 0,
        "debug ": False,
        "case": "strict",
        "dry_run": preview,
        "progress": False,
        "no_color": True,
        "ftp_active": False,
        "migrate": False,
        "no_verify_host_keys": False,
        # "match": 3,
        # "exclude": 3,
        "prompt": False,
        "no_prompt": False,
        "no_keyring": True,
        "no_netrc": True,
        "store_password": False,
        "force": "restore",
        "resolve": "ask",
        "delete": False,
        "delete_unmatched": False,
        "create_dir": True,
        "report_problems": False,
    }

    return opts


def get_syncronizer(upload_or_download: str):
    """
    Convenience function to get the pyftpsync syncronizer
    """
    if upload_or_download == "upload":
        syncronizer = UploadSynchronizer

    elif upload_or_download == "download":
        syncronizer = DownloadSynchronizer

    return syncronizer
