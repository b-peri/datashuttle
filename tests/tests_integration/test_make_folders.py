import datetime
import os
import re
import shutil
from os.path import join

import pytest
import test_utils
from base import BaseTest

from datashuttle.configs import canonical_folders
from datashuttle.configs.canonical_tags import tags


class TestMakeFolders(BaseTest):
    def test_generate_folders_default_ses(self, project):
        """
        Make a subject folders with full tree. Don't specify
        session name (it will default to no sessions).

        Check that the folder tree is created correctly. Pass
        a dict that indicates if each subfolder is used (to avoid
        circular testing from the project itself).
        """
        subs = ["00011", "sub-00002", "30303"]

        project.make_folders(subs)

        test_utils.check_folder_tree_is_correct(
            project,
            base_folder=test_utils.get_top_level_folder_path(project),
            subs=["sub-00011", "sub-00002", "sub-30303"],
            sessions=[],
            folder_used=test_utils.get_all_folders_used(),
        )

    def test_explicitly_session_list(self, project):
        """
        Perform an alternative test where the output is tested explicitly.
        This is some redundancy to ensure tests are working correctly and
        make explicit the expected folder tree.

        Note for new folders, this will have to be manually updated.
        This is highlighted in an assert in check_and_cd_folder()
        """
        subs = ["sub-001", "sub-002"]

        sessions = ["ses-00001", "50432"]

        project.make_folders(subs, sessions, "all")

        base_folder = test_utils.get_top_level_folder_path(project)

        for sub in subs:
            for ses in ["ses-00001", "ses-50432"]:
                test_utils.check_and_cd_folder(
                    join(base_folder, sub, ses, "ephys")
                )
                test_utils.check_and_cd_folder(
                    join(
                        base_folder,
                        sub,
                        ses,
                        "behav",
                    )
                )
                test_utils.check_and_cd_folder(
                    join(base_folder, sub, ses, "funcimg")
                )
                test_utils.check_and_cd_folder(
                    join(base_folder, sub, ses, "anat")
                )

    @pytest.mark.parametrize("behav", [True, False])
    @pytest.mark.parametrize("ephys", [True, False])
    @pytest.mark.parametrize("funcimg", [True, False])
    @pytest.mark.parametrize("anat", [True, False])
    def test_every_datatype_passed(self, project, behav, ephys, funcimg, anat):
        """
        Check every combination of data type used and ensure only the
        correct ones are made.

        NOTE: This test could be refactored to reduce code reuse.
        """
        datatypes_to_make = []
        if behav:
            datatypes_to_make.append("behav")
        if ephys:
            datatypes_to_make.append("ephys")
        if funcimg:
            datatypes_to_make.append("funcimg")
        if anat:
            datatypes_to_make.append("anat")

        # Make folder tree
        subs = ["sub-001", "sub-002"]
        sessions = ["ses-001", "ses-002"]

        project.make_folders(subs, sessions, datatypes_to_make)

        # Check folder tree is not made but all others are
        test_utils.check_folder_tree_is_correct(
            project,
            base_folder=test_utils.get_top_level_folder_path(project),
            subs=subs,
            sessions=sessions,
            folder_used={
                "behav": behav,
                "ephys": ephys,
                "funcimg": funcimg,
                "anat": anat,
            },
        )

    def test_custom_folder_names(self, project, monkeypatch):
        """
        Change folder names to custom (non-default) and
        ensure they are made correctly.
        """
        new_name_datafolders = canonical_folders.get_datatype_folders()
        new_name_datafolders["ephys"].name = "change_ephys"
        new_name_datafolders["behav"].name = "change_behav"
        new_name_datafolders["anat"].name = "change_anat"
        new_name_datafolders["funcimg"].name = "change_funcimg"

        def new_name_func():
            return new_name_datafolders

        monkeypatch.setattr(
            "datashuttle.configs.canonical_folders.get_datatype_folders",
            new_name_func,
        )

        # Make the folders
        sub = "sub-001"
        ses = "ses-001"

        project.make_folders(sub, ses, "all")

        # Check the correct folder names were made
        base_folder = test_utils.get_top_level_folder_path(project)

        test_utils.check_and_cd_folder(
            join(
                base_folder,
                sub,
                ses,
                "change_ephys",
            )
        )
        test_utils.check_and_cd_folder(
            join(base_folder, sub, ses, "change_behav")
        )
        test_utils.check_and_cd_folder(
            join(base_folder, sub, ses, "change_funcimg")
        )

        test_utils.check_and_cd_folder(
            join(base_folder, sub, ses, "change_anat")
        )

    @pytest.mark.parametrize(
        "files_to_test",
        [
            ["all"],
            ["ephys", "behav"],
            ["ephys", "behav", "anat"],
            ["ephys", "behav", "anat", "funcimg"],
            ["funcimg", "ephys"],
            ["funcimg"],
        ],
    )
    def test_datatypes_subsection(self, project, files_to_test):
        """
        Check that combinations of datatypes passed to make file folder
        make the correct combination of datatypes.

        Note this will fail when new top level folders are added, and should be
        updated.
        """
        sub = "sub-001"
        ses = "ses-001"
        project.make_folders(sub, ses, files_to_test)

        base_folder = test_utils.get_top_level_folder_path(project)

        # Check at the subject level
        test_utils.glob_basenames(
            join(base_folder, sub, "*"),
            exclude=ses,
        )

        # Check at the session level
        ses_file_names = test_utils.glob_basenames(
            join(base_folder, sub, ses, "*"),
            exclude=ses,
        )

        if files_to_test == ["all"]:
            assert ses_file_names == sorted(
                ["ephys", "behav", "funcimg", "anat"]
            )
        else:
            assert ses_file_names == sorted(files_to_test)

    def test_date_flags_in_session(self, project):
        """
        Check that @DATE@ is converted into current date
        in generated folder names
        """
        date, time_ = self.get_formatted_date_and_time()

        project.make_folders(
            ["sub-001", "sub-002"],
            [f"ses-001_{tags('date')}", f"002_{tags('date')}"],
            "ephys",
        )

        ses_names = test_utils.glob_basenames(
            join(test_utils.get_top_level_folder_path(project), "**", "ses-*"),
            recursive=True,
        )

        assert all([date in name for name in ses_names])
        assert all([tags("date") not in name for name in ses_names])

    def test_datetime_flag_in_session(self, project):
        """
        Check that @DATETIME@ is converted to datetime
        in generated folder names
        """
        date, time_ = self.get_formatted_date_and_time()

        project.make_folders(
            ["sub-001", "sub-002"],
            [f"ses-001_{tags('datetime')}", f"002_{tags('datetime')}"],
            "ephys",
        )

        ses_names = test_utils.glob_basenames(
            join(test_utils.get_top_level_folder_path(project), "**", "ses-*"),
            recursive=True,
        )

        # Convert the minutes to regexp as could change during test runtime
        regexp_time = r"\d{6}"
        datetime_regexp = f"datetime-{date}T{regexp_time}"

        assert all([re.search(datetime_regexp, name) for name in ses_names])
        assert all([tags("time") not in name for name in ses_names])

    # ----------------------------------------------------------------------------------------------------------
    # Test Make Folders in Different Top Level Folders
    # ----------------------------------------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "folder_name", canonical_folders.get_top_level_folders()
    )
    def test_all_top_level_folders(self, project, folder_name):
        """
        Check that when switching the top level folder (e.g. rawdata, derivatives)
        new folders are made in the correct folder. The code that underpins this
        is very simple (all the path for folder creation / transfer is determined
        only by project.cfg.top_level_folder. Therefore if these tests pass,
        any test that passes for rawdata (all other tests are for rawdata) should
        pass for all top-level folders.
        """
        project.cfg.top_level_folder = folder_name

        subs = ["sub-001", "sub-002"]
        sessions = ["ses-001", "ses-003"]

        project.make_folders(subs, sessions, "all")

        # Check folder tree is made in the desired top level folder
        test_utils.check_working_top_level_folder_only_exists(
            folder_name,
            project,
            project.cfg["local_path"] / folder_name,
            subs,
            sessions,
        )

    # ----------------------------------------------------------------------------------------------------------
    # Test get next subject / session numbers
    # ----------------------------------------------------------------------------------

    @pytest.mark.parametrize("return_with_prefix", [True, False])
    def test_get_next_sub_number(self, project, return_with_prefix):
        """
        Test that the next subject number is suggested correctly.
        This takes the union of subjects available in the local and
        central repository. As such test the case where either are
        empty, or when they have different subjects in.
        """
        # Create local folders, central is empty
        test_utils.make_local_folders_with_files_in(
            project, ["001", "002", "003"]
        )

        new_num = project.get_next_sub_number(return_with_prefix)

        assert new_num == "sub-004" if return_with_prefix else "004"

        # Upload to central, now local and central folders match
        project.upload_all()

        shutil.rmtree(project.cfg["local_path"] / "rawdata")

        new_num = project.get_next_sub_number(return_with_prefix)
        assert new_num == "sub-004" if return_with_prefix else "004"

        # Add large-sub num folders to local and check all are detected.
        project.make_folders(["004", "005"])

        new_num = project.get_next_sub_number(return_with_prefix)
        assert new_num == "sub-006" if return_with_prefix else "006"

        # check `local_path` option
        os.makedirs(project.cfg["central_path"] / "rawdata" / "sub-006")
        new_num = project.get_next_sub_number(
            return_with_prefix, local_only=False
        )
        assert new_num == "sub-007" if return_with_prefix else "007"

        new_num = project.get_next_sub_number(
            return_with_prefix, local_only=True
        )
        assert new_num == "sub-006" if return_with_prefix else "006"

    @pytest.mark.parametrize("return_with_prefix", [True, False])
    def test_get_next_ses_number(self, project, return_with_prefix):
        """
        Almost identical to test_get_next_sub_number() but with calls
        for searching sessions. This could be combined with
        above but reduces readability, so leave with some duplication.

        Note the main underlying function is tested in
        `test_get_max_sub_or_ses_num_and_value_length()`.

        TODO: note this is only tested by `local_filesystem`. I don't think
        it is required to be tested SSH but couldn't hurt, need to check.
        """
        sub = "sub-09"

        test_utils.make_local_folders_with_files_in(
            project, sub, ["001", "002", "003"]
        )

        # Test the next sub and ses number are correct
        new_num = project.get_next_sub_number(return_with_prefix)
        assert new_num == "sub-10" if return_with_prefix else "10"

        new_num = project.get_next_ses_number(sub, return_with_prefix)
        assert new_num == "ses-004" if return_with_prefix else "004"

        # Now upload the data, delete locally, and check the
        # suggested values are correct based on the `central` path.
        project.upload_all()

        shutil.rmtree(project.cfg["local_path"] / "rawdata")

        new_num = project.get_next_sub_number(return_with_prefix)
        assert new_num == "sub-10" if return_with_prefix else "10"

        new_num = project.get_next_ses_number(sub, return_with_prefix)
        assert new_num == "ses-004" if return_with_prefix else "004"

        # Now make a couple more sessions locally, and check
        # the next session is updated accordingly.
        project.make_folders(sub, ["004", "005"])

        new_num = project.get_next_ses_number(sub, return_with_prefix)
        assert new_num == "ses-006" if return_with_prefix else "006"

        # check `local_path` object
        os.makedirs(project.cfg["central_path"] / "rawdata" / sub / "ses-006")
        new_num = project.get_next_ses_number(
            sub, return_with_prefix, local_only=False
        )
        assert new_num == "ses-007" if return_with_prefix else "007"

        new_num = project.get_next_ses_number(
            sub, return_with_prefix, local_only=True
        )
        assert new_num == "ses-006" if return_with_prefix else "006"

    # ----------------------------------------------------------------------------------
    # Test Helpers
    # ----------------------------------------------------------------------------------

    def get_formatted_date_and_time(self):
        date = str(datetime.datetime.now().date())
        date = date.replace("-", "")
        time_ = datetime.datetime.now().time().strftime("%Hh%Mm")
        return date, time_
