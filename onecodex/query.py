import logging

log = logging.getLogger(__name__)


def get(cls, uuid, **kwargs):
    instance = cls(uuid, **kwargs)
    return instance


def where(cls, **kwargs):
    return cls.instances(where=kwargs)
