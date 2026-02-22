"""
Shim to avoid shadowing the standard-library `profile` module.

When a local file named `profile.py` exists in the project root, an `import profile`
from third-party packages (for example, parts of torch) will load this file and
prevent the real library module from being imported. That breaks code that
expects stdlib's `profile` (which defines `run`, etc.).

This shim loads the real stdlib `profile.py` from the interpreter's stdlib
location, executes it under a private name, and re-exports its public
attributes so third-party imports work as expected.

Note: project-specific preference/profile helpers live in `user_profile.py` and
should be used instead of this module.
"""

import importlib.util
import sys
import os
import sysconfig

# Try to locate the stdlib's profile.py file
stdlib_dir = None
try:
    stdlib_dir = sysconfig.get_paths().get("stdlib")
except Exception:
    stdlib_dir = None

if not stdlib_dir:
    # Fallback: derive from the os module location
    stdlib_dir = os.path.dirname(os.__file__)

stdlib_profile_path = os.path.join(stdlib_dir, "profile.py")

if os.path.exists(stdlib_profile_path):
    spec = importlib.util.spec_from_file_location("_stdlib_profile", stdlib_profile_path)
    stdlib_profile = importlib.util.module_from_spec(spec)
    # Execute the stdlib profile module in its module object
    try:
        spec.loader.exec_module(stdlib_profile)
    except Exception:
        # If loading stdlib profile fails, expose a minimal fallback below
        stdlib_profile = None

    if stdlib_profile:
        # Re-export non-dunder attributes from stdlib.profile
        for _name in dir(stdlib_profile):
            if _name.startswith("__"):
                continue
            globals()[_name] = getattr(stdlib_profile, _name)
        __all__ = [n for n in dir(stdlib_profile) if not n.startswith("__")]
    else:
        # Minimal fallback: provide a `run` function that raises a clear error
        def run(*args, **kwargs):
            raise RuntimeError("Could not load the standard-library 'profile' module")

        __all__ = ["run"]
else:
    # If stdlib profile.py was not found (very unusual), provide a clear fallback
    def run(*args, **kwargs):
        raise RuntimeError("Standard-library 'profile.py' not found on this installation")

    __all__ = ["run"]
