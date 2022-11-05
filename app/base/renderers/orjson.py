# source:
#   https://github.com/brianjbuck/drf_orjson_renderer/blob/master/drf_orjson_renderer
#   /renderers.py

# Didn't pip install because https://github.com/brianjbuck/drf_orjson_renderer/issues/20

import functools
import operator
from decimal import Decimal
from typing import Any, Optional

import orjson
from rest_framework.renderers import BaseRenderer
from rest_framework.settings import api_settings

__all__ = ['ORJSONRenderer']


class ORJSONRenderer(BaseRenderer):
    """
    Renderer which serializes to JSON.
    Uses the Rust-backed orjson library for serialization speed.
    """

    format: str = "json"
    html_media_type: str = "text/html"
    json_media_type: str = "application/json"
    media_type: str = json_media_type

    options = functools.reduce(
        operator.or_,
        api_settings.user_settings.get('ORJSON_RENDERER_OPTIONS', ()),
        orjson.OPT_SERIALIZE_NUMPY,
    )

    @staticmethod
    def default(obj: Any) -> Any:
        """
        When orjson doesn't recognize an object type for serialization it passes
        that object to this function which then converts the object to its
        native Python equivalent.
        :param obj: Object of any type to be converted.
        :return: native python object
        """
        if isinstance(obj, dict):
            return dict(obj)
        if isinstance(obj, list):
            return list(obj)
        if isinstance(obj, Decimal):
            return float(obj)
        if hasattr(obj, 'tolist'):
            return obj.tolist()
        if hasattr(obj, '__iter__'):
            return list(item for item in obj)
        return str(obj)

    def render(
        self,
        data: Any,
        media_type: Optional[str] = None,
        renderer_context: Any = None,
    ) -> bytes:
        """
        Serializes Python objects to JSON.
        :param data: The response data, as set by the Response() instantiation.
        :param media_type: If provided, this is the accepted media type, of the
                `Accept` HTTP header.
        :param renderer_context: If provided, this is a dictionary of contextual
                information provided by the view. By default this will include
                the following keys: view, request, response, args, kwargs
        :return: bytes() representation of the data encoded to UTF-8
        """
        if data is None:
            return b''
        renderer_context = renderer_context or {}
        if 'default_function' not in renderer_context:
            default = self.default
        else:
            default = renderer_context['default_function']
        options = self.options
        if media_type == self.html_media_type:
            options |= orjson.OPT_INDENT_2
        serialized: bytes = orjson.dumps(data, default=default, option=options)
        return serialized
