"""This file captures the models involved with permissions and action authorization within Noteable."""

import enum
from typing import List, Optional, Set

from pydantic import BaseModel


@enum.unique
class AccessLevel(enum.Enum):
    """Defines the access levels on a resource that control what actions are allowed.
    Note that this is different than Visibility which captures discoverability.
    """

    owner = "role:owner"
    contributor = "role:contributor"
    commenter = "role:commenter"
    viewer = "role:viewer"
    anonymous = "role:anonymous"
    executor = "role:executor"

    @classmethod
    def values(cls) -> Set[str]:
        """Returns all the avilable enum values possible"""
        return {x.value for x in cls}

    @classmethod
    def parse(cls, value) -> Optional["AccessLevel"]:
        """Converts the value to a typed enumeration if possible"""
        return AccessLevel(value) if value else None


class AccessLevelAction(enum.Enum):
    """Defines the enumeration of actions available on Noteable."""

    def _generate_next_value_(name, start, count, last_values):
        """Helper to enable initialization / enumeration"""
        return name

    # general actions
    create = enum.auto()
    read = enum.auto()
    update = enum.auto()
    delete = enum.auto()
    restore = enum.auto()

    # Space specific actions
    create_project = enum.auto()
    create_dataset = enum.auto()
    view_projects = enum.auto()
    view_datasets = enum.auto()
    modify_space_users = enum.auto()

    # Project specific actions
    modify_project_users = enum.auto()
    create_file = enum.auto()
    view_files = enum.auto()

    # NotebookFile specific actions
    modify_file_users = enum.auto()
    publish = enum.auto()
    edit_cell = enum.auto()
    execute_cell = enum.auto()
    connect_kernel = enum.auto()
    create_file_version = enum.auto()
    create_file_sandbox = enum.auto()
    create_parameterized_notebook = enum.auto()

    # NotebookFile comment actions
    view_comments = enum.auto()
    create_comment = enum.auto()
    resolve_comments = enum.auto()
    restore_comments = enum.auto()

    # NotebookFile metadata actions
    update_in_notebook_metadata = enum.auto()
    update_in_cell_metadata = enum.auto()

    # Dataset specific actions
    create_dataset_file = enum.auto()

    # Secrets privileges, attached to either a space or a project
    create_secret = enum.auto()
    view_secret = enum.auto()
    delete_secret = enum.auto()

    # Datasource privileges, attached to either a space or a project.
    create_datasource = enum.auto()
    view_datasource = enum.auto()
    delete_datasource = enum.auto()


class Visibility(enum.Enum):
    """Defines the visibility of a file for discoverability purposes.
    Note that this is different than AccessLevel which captures permissions.
    """

    def _generate_next_value_(name, start, count, last_values):
        """Helper to enable initialization / enumeration"""
        return name

    # the open visibility allows any logged-in user with access
    # to the organization the ability to be granted an implicit access level
    open = enum.auto()
    # the private visibility is the default visibility and does not
    # grant any implicit access level for a resource
    private = enum.auto()
    # public visibility allows any user to access the resource.
    # this includes anonymous users or users without a Noteable account.
    public = enum.auto()

    def is_private(self) -> bool:
        """Helper for asking if a resource is private or not."""
        return self is Visibility.private


class ResourceData(BaseModel):
    """The representation of a resouce's available actions."""

    # actions_allowed are all the possible actions for this object that are allowed
    actions_allowed: List[AccessLevelAction]
    # actions_denied are all the possible actions for this object that are not allowed
    actions_denied: List[AccessLevelAction]
    # the access level the user effectively had on the resource, implicit or explicit
    effective_access_level: Optional[AccessLevel] = None

    def can(self, action: AccessLevelAction) -> bool:
        """Mirroring the cancan library, the method returns if an action is allowed on the resource."""
        return action in self.actions_allowed
