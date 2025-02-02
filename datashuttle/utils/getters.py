from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
)

if TYPE_CHECKING:
    from pathlib import Path

    from datashuttle.configs.config_class import Configs

import warnings

from datashuttle.configs import canonical_folders
from datashuttle.utils import folders, utils
from datashuttle.utils.custom_exceptions import (
    ConfigError,
    NeuroBlueprintError,
)


def get_next_sub_or_ses_number(
    cfg: Configs,
    sub: Optional[str],
    search_str: str,
    local_only: bool = False,
    return_with_prefix: bool = True,
    default_num_value_digits: int = 3,
) -> str:
    """
    Suggest the next available subject or session number. This function will
    search the local repository, and the central repository, for all subject
    or session folders (subject or session depending on inputs).

    It will take the union of all folder names, find the relevant key-value
    pair values, and return the maximum value + 1 as the new number.

    A warning will be shown if the existing sub / session numbers are not
    consecutive.

    Parameters
    ----------
    cfg : Configs
        datashuttle configs class

    sub : Optional[str]
        subject name to search within if searching for sessions, otherwise None
        to search for subjects

    search_str : str
        the string to search for within the top-level or subject-level
        folder ("sub-*") or ("ses-*") are suggested, respectively.

    local_only : bool
        If `True, only get names from `local_path`, otherwise from
        `local_path` and `central_path`.

    return_with_prefix : bool
        If `True`, the next sub or ses value will include the prefix
        e.g. "sub-001", otherwise the value alone will be returned (e.g. "001")

    default_num_value_digits : int
        If no sub or ses exist in the project, the starting number is 1.
        Because the number of digits for the project is not accessible,
        the desired value can be entered here. e.g. if 3 (the default),
        if no subjects are found the subject returned will be "sub-001".

    Returns
    -------
    suggested_new_num : the new suggested sub / ses.
    """
    prefix: Literal["sub", "ses"]

    if sub:
        prefix = "ses"
    else:
        prefix = "sub"

    folder_names = folders.search_project_for_sub_or_ses_names(
        cfg, sub, search_str, local_only=local_only
    )

    all_folders = list(set(folder_names["local"] + folder_names["central"]))

    (
        max_existing_num,
        num_value_digits,
    ) = get_max_sub_or_ses_num_and_value_length(
        all_folders, prefix, default_num_value_digits
    )

    # calculate next sub number
    suggested_new_num = max_existing_num + 1
    format_suggested_new_num = str(suggested_new_num).zfill(num_value_digits)

    if return_with_prefix:
        format_suggested_new_num = f"{prefix}-{format_suggested_new_num}"

    return format_suggested_new_num


def get_max_sub_or_ses_num_and_value_length(
    all_folders: List[str],
    prefix: Literal["sub", "ses"],
    default_num_value_digits: Optional[int] = None,
) -> Tuple[int, int]:
    """
    Given a list of BIDS-style folder names, find the maximum subject or
    session value (sub or ses depending on `prefix`). Also, find the
    number of value digits across the project, so a new suggested number
    can be formatted consistency. If the list is empty, set the value
    to 0 and a default number of value digits.

    Parameters
    ----------

    all_folders : List[str]
        A list of BIDS-style formatted folder names.

    see `get_next_sub_or_ses_number()` for other arguments.

    Returns
    -------

    max_existing_num : int
        The largest number sub / ses value in the past list.

    num_value_digits : int
        The length of the value in all sub / ses values within the
        passed list. If these are not consistent, an error is raised.

    For example, if the project contains "sub-0001", "sub-0002" then
    the max_existing_num will be 2 and num_value_digits 4.

    """
    if len(all_folders) == 0:
        max_existing_num = 0
        assert isinstance(
            default_num_value_digits, int
        ), "`default_num_value_digits` must be int`"

        num_value_digits = default_num_value_digits
    else:
        all_values_str = utils.get_values_from_bids_formatted_name(
            all_folders,
            prefix,
            return_as_int=False,
        )

        # First get the length of bids-key value across the project
        # (e.g. sub-003 has three values).
        all_num_value_digits = [len(value) for value in all_values_str]

        if len(set(all_num_value_digits)) != 1:
            utils.raise_error(
                f"The number of value digits for the {prefix} level are not "
                f"consistent. Cannot suggest a {prefix} number.",
                NeuroBlueprintError,
            )
        num_value_digits = all_num_value_digits[0]

        # Then get the latest existing sub or ses number in the project.
        all_value_nums = sorted(
            [utils.sub_or_ses_value_to_int(value) for value in all_values_str]
        )

        if not utils.integers_are_consecutive(all_value_nums):
            warnings.warn(
                f"A subject number has been skipped, "
                f"currently used subject numbers are: {all_value_nums}",
            )

        max_existing_num = max(all_value_nums)

    return max_existing_num, num_value_digits


def get_existing_project_paths() -> List[Path]:
    """
    Return full path and names of datashuttle projects on
    this local machine. A project is determined by a project
    folder in the home / .datashuttle folder that contains a
    config.yaml file.
    """
    datashuttle_path = canonical_folders.get_datashuttle_path()

    all_folders, _ = folders.search_filesystem_path_for_folders(
        datashuttle_path / "*"
    )

    existing_project_paths = []
    for folder_name in all_folders:
        config_file = list(
            (datashuttle_path / folder_name).glob("config.yaml")
        )

        if len(config_file) > 1:
            utils.raise_error(
                f"There are two config files in project"
                f"{folder_name} at path {datashuttle_path}. There "
                f"should only ever be one config per project. ",
                ConfigError,
            )
        elif len(config_file) == 1:
            existing_project_paths.append(datashuttle_path / folder_name)

    return existing_project_paths


def get_all_sub_and_ses_names(cfg: Configs, local_only: bool) -> Dict:
    """
    Get a list of every subject and session name in the
    local and central project folders. Local and central names are combined
    into a single list, separately for subject and sessions.

    Note this only finds local sub and ses names on this
    machine. Other local machines are not searched.

    Parameters
    ----------

    cfg : Configs
        datashuttle Configs

    local_only : bool
        If `True, only get names from `local_path`, otherwise from
        `local_path` and `central_path`.
    """
    sub_folder_names = folders.search_project_for_sub_or_ses_names(
        cfg, None, "sub-*", local_only
    )

    if local_only:
        all_sub_folder_names = sub_folder_names["local"]
    else:
        all_sub_folder_names = (
            sub_folder_names["local"] + sub_folder_names["central"]
        )

    all_ses_folder_names = {}
    for sub in all_sub_folder_names:
        ses_folder_names = folders.search_project_for_sub_or_ses_names(
            cfg, sub, "ses-*", local_only
        )

        if local_only:
            all_ses_folder_names[sub] = ses_folder_names["local"]
        else:
            all_ses_folder_names[sub] = (
                ses_folder_names["local"] + ses_folder_names["central"]
            )

    return {"sub": all_sub_folder_names, "ses": all_ses_folder_names}
