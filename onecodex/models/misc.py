from onecodex.models import OneCodexBase


class Tags(OneCodexBase):
    _resource_path = '/api/v1/tags'


class Users(OneCodexBase):
    _resource_path = '/api/v1/users'


class Projects(OneCodexBase):
    _resource_path = '/api/v1/projects'


class Jobs(OneCodexBase):
    _resource_path = '/api/v1/jobs'
