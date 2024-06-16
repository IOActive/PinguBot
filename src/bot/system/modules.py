
"""Functions for module management."""

# Do not add any imports to non-standard modules here.
import os
import site
import sys


def _config_modules_directory(root_directory):
    """Get the config modules directory."""
    config_dir = os.getenv('CONFIG_DIR_OVERRIDE')
    if not config_dir:
        config_dir = os.path.join(root_directory, 'src', 'config')

    return os.path.join(config_dir, 'modules')


def _patch_appengine_modules_for_bots():
    """Patch out App Engine reliant behaviour from bots."""
    if os.getenv('SERVER_SOFTWARE'):
        # Not applicable on App Engine.
        return

    # google.auth uses App Engine credentials based on importability of
    # google.appengine.api.app_identity.
    try:
        from google.auth import app_engine as auth_app_engine
        if auth_app_engine.app_identity:
            auth_app_engine.app_identity = None
    except ImportError:
        pass


def fix_module_search_paths(submodule_root=""):
    """Add directories that we must be able to import from to path."""
    root_directory = os.environ['ROOT_DIR']
    source_directory = os.path.join(root_directory, 'src')

    python_path = os.getenv('PYTHONPATH', '').split(os.pathsep)

    third_party_libraries_directory = os.path.join(root_directory,
                                                   'third_party')
    
    config_modules_directory = _config_modules_directory(root_directory)

    if (os.path.exists(config_modules_directory) and
            config_modules_directory not in sys.path):
        sys.path.insert(0, config_modules_directory)
        python_path.insert(0, config_modules_directory)

    if third_party_libraries_directory not in sys.path:
        sys.path.insert(0, third_party_libraries_directory)
        python_path.insert(0, third_party_libraries_directory)

    if source_directory not in sys.path:
        sys.path.insert(0, source_directory)
        python_path.insert(0, source_directory)

    os.environ['PYTHONPATH'] = os.pathsep.join(python_path)
