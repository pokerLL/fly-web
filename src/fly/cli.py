from io import StringIO
import sys
import importlib.util
import os
import contextlib

from fly.fly import Fly

DEBUG_MODE = True


def find_fly_instances():
    fly_instances = []
    filtered_filenames = [filename for filename in os.listdir(os.getcwd()) if filename.endswith(".py") and not filename.startswith("__")]
    if len(filtered_filenames) > 1:
        print("Warning: There should be one and only one Fly instance in the current directory.\n         If not, there may be unexpected errors.")
    for filename in filtered_filenames:
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = filename[:-3]
            module_spec = importlib.util.spec_from_file_location(module_name, os.path.join(os.getcwd(), filename))
            if module_spec is None:
                continue
            module = importlib.util.module_from_spec(module_spec)
            with contextlib.redirect_stdout(StringIO()) as out, contextlib.redirect_stderr(StringIO()) as err:
                try:
                    module_spec.loader.exec_module(module)
                except Exception as e:
                    # print(f"Error loading module {module_name}: {e}")
                    continue
            instances = [v for v in module.__dict__.values() if isinstance(v, Fly)]
            fly_instances.extend(instances)
    return fly_instances


def load_fly_instance(module_name, instance_name):
    module_spec = importlib.util.spec_from_file_location(module_name, os.path.join(os.getcwd(), f"{module_name}.py"))
    if module_spec is None:
        return None
    module = importlib.util.module_from_spec(module_spec)
    with contextlib.redirect_stdout(StringIO()) as out, contextlib.redirect_stderr(StringIO()) as err:
        try:
            module_spec.loader.exec_module(module)
        except Exception as e:
            # print(f"Error loading module {module_name}: {e}")
            return None
    return module.__dict__.get(instance_name, None)


def main():
    app_instance = None
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    # print(f"Command: {command}")

    if ":" in command:
        sys.argv.pop(1)
        module_name, instance_name = command.split(":", 1)
        app_instance = load_fly_instance(module_name, instance_name)
        if app_instance is None:
            print(f"Instance {instance_name} not found in module {module_name}.")
            sys.exit(1)

    if app_instance is None:
        fly_instances = find_fly_instances()
        if len(fly_instances) == 1:
            app_instance = fly_instances[0]
        else:
            print("Error: There should be one and only one Fly instance in the current directory.")
            sys.exit(1)

    app_instance.manage()


if __name__ == "__main__":
    main()
