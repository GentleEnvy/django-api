import inspect
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from drf_spectacular.drainage import error, get_view_method_names, isolate_view_method
from drf_spectacular.utils import OpenApiExample, OpenApiParameter
from rest_framework import serializers
from rest_framework.fields import empty
from rest_framework.serializers import Serializer
from rest_framework.settings import api_settings

__all__ = ['schema_serializer', 'extend_schema']


def schema_serializer(
    _name: str, **fields: serializers.Field
) -> Type[serializers.Serializer]:
    if not _name.endswith('Serializer'):
        _name += 'Serializer'
    # noinspection PyTypeChecker
    return type(_name, (serializers.Serializer,), fields)


_F = TypeVar('_F', bound=Callable[..., Any])


def _delete_none(f):
    def _decorator(*args, **kwargs):
        res = f(*args, **kwargs)
        if isinstance(res, dict):
            res = {k: v for k, v in res.items() if v is not None}
        return res

    return _decorator


# taken from drf_spectacular.utils.extend_schema
def extend_schema(
    operation_id: Optional[str] = None,
    parameters: Optional[List[OpenApiParameter]] = None,
    request: Any = empty,
    responses: Any = empty,
    auth: Optional[List[str]] = None,
    description: Optional[str] = None,
    summary: Optional[str] = None,
    deprecated: Optional[bool] = None,
    tags: Optional[List[str]] = None,
    filters: Optional[bool] = None,
    exclude: bool = False,
    operation: Optional[Dict] = None,
    methods: Optional[List[str]] = None,
    versions: Optional[List[str]] = None,
    examples: Optional[List[OpenApiExample]] = None,
    extensions: Optional[Dict[str, Any]] = None,
) -> Callable[[_F], _F]:
    """
    Decorator mainly for the "view" method kind. Partially or completely overrides
    what would be otherwise generated by drf-spectacular.

    :param operation_id: replaces the auto-generated operation_id. make sure there
        are no naming collisions.
    :param parameters: list of additional or replacement parameters added to the
        auto-discovered fields.
    :param responses: replaces the discovered Serializer. Takes a variety of
        inputs that can be used individually or combined

        - ``Serializer`` class
        - ``Serializer`` instance (e.g. ``Serializer(many=True)`` for listings)
        - basic types or instances of ``OpenApiTypes``
        - :class:`.OpenApiResponse` for bundling any of the other choices together with
            either a dedicated response description and/or examples.
        - :class:`.PolymorphicProxySerializer` for signaling that
            the operation may yield data from different serializers depending
            on the circumstances.
        - ``dict`` with status codes as keys and one of the above as values.
            Additionally in this case, it is also possible to provide a raw schema dict
            as value.
        - ``dict`` with tuples (status_code, media_type) as keys and one of the above
            as values. Additionally in this case, it is also possible to provide a raw
            schema dict as value.
    :param request: replaces the discovered ``Serializer``. Takes a variety of inputs

        - ``Serializer`` class/instance
        - basic types or instances of ``OpenApiTypes``
        - :class:`.PolymorphicProxySerializer` for signaling that the operation
            accepts a set of different types of objects.
        - ``dict`` with media_type as keys and one of the above as values.
        Additionally in
            this case, it is also possible to provide a raw schema dict as value.
    :param auth: replace discovered auth with explicit list of auth methods
    :param description: replaces discovered doc strings
    :param summary: an optional short summary of the description
    :param deprecated: mark operation as deprecated
    :param tags: override default list of tags
    :param filters: ignore list detection and forcefully enable/disable filter discovery
    :param exclude: set True to exclude operation from schema
    :param operation: manually override what auto-discovery would generate. you must
        provide a OpenAPI3-compliant dictionary that gets directly translated to YAML.
    :param methods: scope extend_schema to specific methods. matches all by default.
    :param versions: scope extend_schema to specific API version. matches all by
    default.
    :param examples: attach request/response examples to the operation
    :param extensions: specification extensions, e.g. ``x-badges``, ``x-code-samples``,
        etc.
    :return:
    """
    if methods is not None:
        methods = [method.upper() for method in methods]

    def decorator(f):
        BaseSchema = (
            getattr(f, 'schema', None)
            or getattr(f, 'kwargs', {}).get('schema', None)
            or getattr(getattr(f, 'cls', None), 'kwargs', {}).get('schema', None)
            or api_settings.DEFAULT_SCHEMA_CLASS
        )

        if not inspect.isclass(BaseSchema):
            BaseSchema = BaseSchema.__class__

        def is_in_scope(ext_schema):
            version, _ = ext_schema.view.determine_version(
                ext_schema.view.request, **ext_schema.view.kwargs
            )
            version_scope = versions is None or version in versions
            method_scope = methods is None or ext_schema.method in methods
            return method_scope and version_scope

        class ExtendedSchema(BaseSchema):
            view: Any
            method: str

            _method__status = {
                'GET': 200,
                'POST': 201,
                'PUT': 200,
                'PATCH': 200,
                'DELETE': 204,
                'HEAD': 200,
                'OPTIONS': 200,
                'TRACE': 200,
            }

            def get_operation(self, path, path_regex, path_prefix, method_, registry):
                setattr(self, 'method', method_.upper())
                if exclude and is_in_scope(self):
                    return None
                if operation is not None and is_in_scope(self):
                    return operation
                return super().get_operation(
                    path, path_regex, path_prefix, method_, registry
                )

            def get_operation_id(self):
                if operation_id and is_in_scope(self):
                    return operation_id
                return super().get_operation_id()

            def get_override_parameters(self):
                if parameters and is_in_scope(self):
                    return super().get_override_parameters() + parameters
                return super().get_override_parameters()

            def get_auth(self):
                if auth and is_in_scope(self):
                    return auth
                return super().get_auth()

            def get_examples(self):
                if examples and is_in_scope(self):
                    return super().get_examples() + examples
                return super().get_examples()

            def get_request_serializer(self):
                if request is not empty and is_in_scope(self):
                    return request
                return super().get_request_serializer()

            @_delete_none
            def get_response_serializers(self):
                super_responses = super().get_response_serializers()
                if responses is not empty and is_in_scope(self):
                    if isinstance(responses, dict):
                        if isinstance(super_responses, dict):
                            return super_responses | responses
                        if isinstance(super_responses, Serializer):
                            status = self._method__status[self.method]
                            return {status: super_responses} | responses
                    return responses
                return super_responses

            def get_description(self):
                if description and is_in_scope(self):
                    return description
                return super().get_description()

            def get_summary(self):
                if summary and is_in_scope(self):
                    return str(summary)
                return super().get_summary()

            def is_deprecated(self):
                if deprecated and is_in_scope(self):
                    return deprecated
                return super().is_deprecated()

            def get_tags(self):
                if tags is not None and is_in_scope(self):
                    return tags
                return super().get_tags()

            def get_extensions(self):
                if extensions and is_in_scope(self):
                    return extensions
                return super().get_extensions()

            def get_filter_backends(self):
                if filters is not None and is_in_scope(self):
                    return getattr(self.view, 'filter_backends', []) if filters else []
                return super().get_filter_backends()

        if inspect.isclass(f):
            if operation_id is not None or operation is not None:
                error(
                    f"using @extend_schema on viewset class {f.__name__} with "
                    f"parameters "
                    f"operation_id or operation will most likely result in a broken "
                    f"schema."
                )
            for view_method_name in get_view_method_names(view=f, schema=BaseSchema):
                if 'schema' not in getattr(getattr(f, view_method_name), 'kwargs', {}):
                    continue
                view_method = isolate_view_method(f, view_method_name)
                view_method.kwargs['schema'] = type(
                    'ExtendedMetaSchema',
                    (view_method.kwargs['schema'], ExtendedSchema),
                    {},
                )
            f.schema = ExtendedSchema()
            return f
        if callable(f) and hasattr(f, 'cls'):
            setattr(f.cls, 'kwargs', {'schema': ExtendedSchema})
            for method in f.cls.http_method_names:
                setattr(getattr(f.cls, method), 'kwargs', {'schema': ExtendedSchema})
            return f
        if callable(f):
            if not hasattr(f, 'kwargs'):
                f.kwargs = {}
            f.kwargs['schema'] = ExtendedSchema
            return f
        return f

    return decorator
