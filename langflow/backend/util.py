import ast
import inspect
import re
import importlib

from langchain.agents.load_tools import *
from langchain.agents.load_tools import (
    _BASE_TOOLS,
    _LLM_TOOLS,
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
)
from typing import Optional


def build_template_from_function(name: str, type_to_loader_dict: dict):
    classes = [
        item.__annotations__["return"].__name__ for item in type_to_loader_dict.values()
    ]

    # Raise error if name is not in chains
    if name not in classes:
        raise ValueError(f"{name} not found")

    for _type, v in type_to_loader_dict.items():
        if v.__annotations__["return"].__name__ == name:
            _class = v.__annotations__["return"]

            docs = get_class_doc(_class)

            variables = {"_type": _type}
            for name, value in _class.__fields__.items():
                if name in ["callback_manager", "requests_wrapper"]:
                    continue
                variables[name] = {}
                for name_, value_ in value.__repr_args__():
                    if name_ == "default_factory":
                        try:
                            variables[name]["default"] = get_default_factory(
                                module=_class.__base__.__module__, function=value_
                            )
                        except Exception:
                            variables[name]["default"] = None
                    elif name_ not in ["name"]:
                        variables[name][name_] = value_

                variables[name]["placeholder"] = (
                    docs["Attributes"][name] if name in docs["Attributes"] else ""
                )

            return {
                "template": format_dict(variables),
                "description": docs["Description"],
                "base_classes": get_base_classes(_class),
            }


def build_template_from_class(name: str, type_to_cls_dict: dict):
    classes = [item.__name__ for item in type_to_cls_dict.values()]

    # Raise error if name is not in chains
    if name not in classes:
        raise ValueError(f"{name} not found.")

    for _type, v in type_to_cls_dict.items():
        if v.__name__ == name:
            _class = v

            docs = get_class_doc(_class)

            variables = {"_type": _type}
            for name, value in _class.__fields__.items():
                if name in ["callback_manager"]:
                    continue
                variables[name] = {}
                for name_, value_ in value.__repr_args__():
                    if name_ == "default_factory":
                        try:
                            variables[name]["default"] = get_default_factory(
                                module=_class.__base__.__module__, function=value_
                            )
                        except Exception:
                            variables[name]["default"] = None
                    elif name_ not in ["name"]:
                        variables[name][name_] = value_

                variables[name]["placeholder"] = (
                    docs["Attributes"][name] if name in docs["Attributes"] else ""
                )

            return {
                "template": format_dict(variables),
                "description": docs["Description"],
                "base_classes": get_base_classes(_class),
            }


def get_base_classes(cls):
    bases = cls.__bases__
    if not bases:
        return []
    else:
        result = []
        for base in bases:
            if any(type in base.__module__ for type in ["pydantic", "abc"]):
                continue
            result.append(base.__name__)
            result.extend(get_base_classes(base))
        return result


def get_default_factory(module: str, function: str):
    pattern = r"<function (\w+)>"

    if match := re.search(pattern, function):
        module = importlib.import_module(module)
        return getattr(module, match[1])()
    return None


def get_tools_dict(name: Optional[str] = None):
    """Get the tools dictionary."""
    tools = {
        **_BASE_TOOLS,
        **_LLM_TOOLS,
        **{k: v[0] for k, v in _EXTRA_LLM_TOOLS.items()},
        **{k: v[0] for k, v in _EXTRA_OPTIONAL_TOOLS.items()},
    }
    return tools[name] if name else tools


def get_tool_params(func, **kwargs):
    # Parse the function code into an abstract syntax tree
    tree = ast.parse(inspect.getsource(func))

    # Iterate over the statements in the abstract syntax tree
    for node in ast.walk(tree):
        # Find the first return statement
        if isinstance(node, ast.Return):
            tool = node.value
            if isinstance(tool, ast.Call):
                if tool.func.id == "Tool":
                    if tool.keywords:
                        tool_params = {}
                        for keyword in tool.keywords:
                            if keyword.arg == "name":
                                tool_params["name"] = ast.literal_eval(keyword.value)
                            elif keyword.arg == "description":
                                tool_params["description"] = ast.literal_eval(
                                    keyword.value
                                )
                        return tool_params
                    return {
                        "name": ast.literal_eval(tool.args[0]),
                        "description": ast.literal_eval(tool.args[2]),
                    }
                else:
                    # get the class object from the return statement
                    try:
                        class_obj = eval(
                            compile(ast.Expression(tool), "<string>", "eval")
                        )
                    except Exception:
                        return None

                    return {
                        "name": getattr(class_obj, "name"),
                        "description": getattr(class_obj, "description"),
                    }

    # Return None if no return statement was found
    return None


def get_class_doc(class_name):
    """
    Extracts information from the docstring of a given class.

    Args:
        class_name: the class to extract information from

    Returns:
        A dictionary containing the extracted information, with keys
        for 'Description', 'Parameters', 'Attributes', and 'Returns'.
    """
    # Get the class docstring
    docstring = class_name.__doc__

    # Parse the docstring to extract information
    lines = docstring.split("\n")
    data = {
        "Description": "",
        "Parameters": {},
        "Attributes": {},
        "Example": [],
        "Returns": {},
    }

    current_section = "Description"

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if (
            line.startswith(tuple(data.keys()))
            and len(line.split()) == 1
            and line.endswith(":")
        ):
            current_section = line[:-1]
            continue

        if current_section in ["Description", "Example"]:
            data[current_section] += line
        else:
            param, desc = line.split(":")
            data[current_section][param.strip()] = desc.strip()

    return data


def format_dict(d):
    """
    Formats a dictionary by removing certain keys and modifying the
    values of other keys.

    Args:
        d: the dictionary to format

    Returns:
        A new dictionary with the desired modifications applied.
    """

    # Process remaining keys
    for key, value in d.items():
        if key == "_type":
            continue

        # Set verbose to True
        if key == "verbose":
            value["default"] = True

        _type = value["type"]

        # Remove 'Optional' wrapper
        if "Optional" in _type:
            _type = _type.replace("Optional[", "")[:-1]

        # Check for list type
        if "List" in _type:
            _type = _type.replace("List[", "")[:-1]
            value["list"] = True
        else:
            value["list"] = False

        # Replace 'Mapping' with 'dict'
        if "Mapping" in _type:
            _type = _type.replace("Mapping", "dict")

        value["type"] = "Tool" if key == "allowed_tools" else _type

        # Show if required
        value["show"] = bool(
            (value["required"] and key not in ["input_variables"])
            or key
            in [
                "allowed_tools",
                # "Memory",
                "memory",
                "prefix",
                "examples",
                "temperature",
            ]
            or "api_key" in key
        )

        # Add multline
        value["multiline"] = key in ["suffix", "prefix", "template", "examples"]
        # Replace default value with actual value
        # if _type in ["str", "bool"]:
        #     value["value"] = value.get("default", "")
        #     if "default" in value:
        #         value.pop("default")
        if "default" in value:
            value["value"] = value["default"]
            value.pop("default")

    # Filter out keys that should not be shown
    return d
