import os
import shutil

import pytest
import test_utils
from base import BaseTest

from datashuttle import DataShuttle
from datashuttle.utils import validation
from datashuttle.utils.custom_exceptions import NeuroBlueprintError


class TestPersistentSettings(BaseTest):
    @pytest.mark.parametrize("unused_repeat", [1, 2])
    def test_persistent_settings(self, project, unused_repeat):
        """
        Test persistent settings functions by editing the
        persistent settings, checking they are changed and
        the program settings are changed accordingly.
        """
        settings = project._load_persistent_settings()

        assert len(settings) == 3
        assert settings["top_level_folder"] == "rawdata"

        # Update they persistent setting and check this is reflected
        # in a newly loading version of the settings
        project._update_persistent_setting("top_level_folder", "derivatives")

        settings_changed = project._load_persistent_settings()
        assert settings_changed["top_level_folder"] == "derivatives"

        # Re-load the project - this should now take top_level_folder
        # from the new persistent settings
        project_reload = DataShuttle(project.project_name)
        assert project_reload.cfg.top_level_folder == "derivatives"

        # Delete the persistent settings .yaml and check the next
        # time a project is loaded, it is initialized gracefully to the
        # default value.
        (
            project_reload._datashuttle_path / "persistent_settings.yaml"
        ).unlink()

        fresh_project = DataShuttle(project.project_name)

        assert fresh_project.cfg.top_level_folder == "rawdata"

    def test_persistent_settings_name_templates(self, project):
        """
        Test the 'name_templates' option that is stored in persistent
        settings and adds a regexp to validate subject and session
        names against.

        Here we test the mechanisms of getting and setting `name_templates`
        and then check that all validation are performing as expected when
        using them.
        """
        # Load name_templates and check defaults are as expected
        name_templates = project.get_name_templates()

        assert len(name_templates) == 3
        assert name_templates["on"] is False
        assert name_templates["sub"] is None
        assert name_templates["ses"] is None

        # Set some new settings and check they become persistent
        sub_regexp = "sub-\d_id-.?.?_random-.*"
        ses_regexp = "ses-\d\d_id-.?.?.?_random-.*"

        new_name_templates = {
            "on": True,
            "sub": sub_regexp,
            "ses": ses_regexp,
        }

        project.set_name_templates(new_name_templates)

        project_reload = DataShuttle(project.project_name)

        reload_name_templates = project_reload.get_name_templates()

        assert len(reload_name_templates) == 3
        assert reload_name_templates["on"] is True
        assert reload_name_templates["sub"] == sub_regexp
        assert reload_name_templates["ses"] == ses_regexp

        # Check the validation works correctly based on settings
        # when making sub / ses folders
        good_sub = "sub-2_id-ab_random-helloworld"
        bad_sub = "sub-3_id-abC_random-helloworld"
        good_ses = "ses-33_id-xyz_random-helloworld"
        bad_ses = "ses-33_id-xyz_ranDUM-helloworld"

        # Bad sub name
        with pytest.raises(NeuroBlueprintError) as e:
            project.make_folders(bad_sub)
        assert (
            str(e.value) == "The name: "
            "sub-3_id-abC_random-helloworld "
            "does not match the template: "
            "sub-\d_id-.?.?_random-.*"
        )

        # Good sub name (should not raise)
        project.make_folders(good_sub)

        # Bad ses name
        with pytest.raises(NeuroBlueprintError) as e:
            project.make_folders(good_sub, bad_ses)

        assert (
            str(e.value) == "The name: "
            "ses-33_id-xyz_ranDUM-helloworld "
            "does not match the template: "
            "ses-\\d\\d_id-.?.?.?_random-.*"
        )

        # Good ses name (should not raise)
        project.make_folders(good_sub, good_ses)

        # Now just test the other validation functions explicitly
        # here as well to avoid duplicate of test setup.

        # Test `validate_names_against_project()`
        with pytest.raises(NeuroBlueprintError) as e:
            validation.validate_names_against_project(
                project.cfg,
                [bad_sub],
                ses_names=None,
                local_only=True,
                error_or_warn="error",
                name_templates=reload_name_templates,
            )
        assert "does not match the template:" in str(e.value)

        bad_sub_path = project.cfg["local_path"] / "rawdata" / bad_sub
        os.makedirs(bad_sub_path)

        # Test `validate_project()`
        with pytest.raises(NeuroBlueprintError) as e:
            project.validate_project("error", local_only=True)
        shutil.rmtree(bad_sub_path)

        assert "sub-3_id-abC_random-helloworld" in str(e.value)

        # Turn it off the `name_template` option
        # and check a bad ses name does not raise
        reload_name_templates["on"] = False
        project.set_name_templates(reload_name_templates)

        project.make_folders(good_sub, "ses-02")

    def test_set_top_level_folder_is_persistent(self, project):
        """
        Test that set_top_level_folder sets the top
        level folder name persistently across sessions.
        """
        assert project.cfg.top_level_folder == "rawdata"

        project.set_top_level_folder("derivatives")

        assert project.cfg.top_level_folder == "derivatives"

        project_reload = DataShuttle(project.project_name)

        assert project_reload.cfg.top_level_folder == "derivatives"

        stdout = test_utils.run_cli(
            " get-top-level-folder", project.project_name
        )

        assert "derivatives" in stdout[0]
