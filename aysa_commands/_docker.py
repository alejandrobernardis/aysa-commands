# Author: Alejandro M. Bernardis
# Email: alejandro.bernardis at gmail.com
# Created: 2019/10/30
# ~

###############################################################################
# Docker Registry Documentation: https://docs.docker.com/registry/            #
###############################################################################
# TODO (0608156): implementar autenticación por token.
#                 https://docs.docker.com/registry/configuration/#auth
# TODO (0608156): implementar un paginador para el catálogo y tags dentro de
#                 la api

import re
import json
import requests
from requests.auth import HTTPBasicAuth

TAG_SEP = ':'
REPO_SEP = '/'
MANIFEST_VERSION = 'v2'
MEDIA_TYPES = {
    'v1': 'application/vnd.docker.distribution.manifest.v1+json',
    'v2': 'application/vnd.docker.distribution.manifest.v2+json',
    'v2f': 'application/vnd.docker.distribution.manifest.list.v2+json'
}

rx_schema = re.compile(r'(localhost|.*\.local(?:host)?(?::\d{1,5})?)$', re.I)
rx_registry = re.compile(r'^(localhost|[\w\-]+(\.[\w\-]+)+)(?::\d{1,5})?/',
                         re.I)
rx_repository = re.compile(r'^[a-z0-9]+(?:[/:._-][a-z0-9]+)*$')


def get_media_type(value=MANIFEST_VERSION, key='Accept', obj=True):
    value = MEDIA_TYPES[value if value in MEDIA_TYPES else MANIFEST_VERSION]
    return {key: value} if obj is True else value


def remove_registry(value):
    registry = get_registry(value)
    if registry is not None:
        value = value.replace(registry, '')
    return value


def get_tag(value):
    value = remove_registry(value)
    if TAG_SEP not in value:
        return None
    return value.rsplit(TAG_SEP, 1)[-1]


def get_repository(value):
    return remove_registry(value).rsplit(TAG_SEP, 1)[0]


def get_namespace(value):
    value = get_repository(value)
    if REPO_SEP not in value:
        return None
    return value.rsplit(REPO_SEP, 1)[0]


def get_image(value):
    return get_repository(value).rsplit(REPO_SEP, 1)[-1]


def get_registry(value):
    r = rx_registry.match(value)
    if r is not None:
        return r.group()
    return None


def get_parts(value):
    """
    Formato del string:
      - {url:port}/{namespace}/{repository}:{tag}
    """
    if not rx_repository.match(get_repository(value)):
        raise RegistryError('El endpoint "{}" está mal formateado.'
                            .format(value))
    return {
        'registry': get_registry(value),
        'repository': get_repository(value),
        'namespace': get_namespace(value),
        'image': get_image(value),
        'tag': get_tag(value),
    }


def validate_token(value, exclude='|#@'):
    return value and ''.join([x for x in value if x not in exclude]) == value


def scheme(endpoint):
    return 'http' if rx_schema.match(endpoint) else 'https'


class Registry:
    """
    Registry Client (simple)
    """
    def __init__(self, host, insecure=False, verify=True, credentials=None,
                 **kwargs):
        self.host = host
        self.insecure = insecure
        self.verify = verify if insecure is False else True
        self.scheme = scheme(host) if insecure is False else 'http'
        self.credentials = credentials

    def get_baseurl(self):
        return '{}://{}/v2'.format(self.scheme, self.host)

    def get_credentials(self, split=False):
        if split is True:
            return self.credentials.split(':')
        return self.credentials

    def session(self, headers=None, timeout=10):
        s = requests.Session()
        if self.credentials is not None:
            s.auth = HTTPBasicAuth(*self.get_credentials(True))
        s.headers.update(headers or {})
        s.headers['User-Agent'] = 'AySA-Command-Line-Tool'
        s.verify = self.verify
        s.timeout = timeout
        return s

    def request(self, method, *args, **kwargs):
        headers = kwargs.pop('headers', {})
        with self.session(headers) as req:
            response = req.request(method, *args, **kwargs)
            try:
                response.raise_for_status()
            except requests.HTTPError:
                data = response.json()
                if 'errors' in data:
                    error = data['errors'][0]
                    raise RegistryError('{code}: {message}'.format(**error))
            return response


class Entity:
    url = None
    url_template = None
    methods_supported = None

    def __init__(self, client):
        self.client = client

    def set_url(self, **kwargs):
        if self.url_template is None:
            raise RegistryError('Método "set_url" no está soportado '
                                'para la entidad: "{}".'
                                .format(self.__class__.__name__))
        self.url = self.url_template.format(**kwargs)

    def request(self, method, *args, **kwargs):
        method = method.upper()
        if self.methods_supported and method not in self.methods_supported:
            raise RegistryError('Método "{}" no soportado para "{}".'
                                .format(method, self.url))
        url = self.client.get_baseurl() + self.url
        response = self.client.request(method, url, *args, **kwargs)
        return response

    def json(self, method, *args, **kwargs):
        return self.request(method, *args, **kwargs).json()


class IterEntity(Entity):
    response_key = None
    response_data = None

    def __init__(self, client, prefix_filter=None):
        self.client = client
        self.prefix_filter = prefix_filter

    def get(self, *args, **kwargs):
        response_data = self.json('GET', *args, **kwargs)
        if self.response_key not in response_data:
            raise RegistryError('La clave "{}" no se encuentra dentro de la '
                                'respuesta.'.format(self.response_key))
        self.response_data = response_data[self.response_key]

    def __iter__(self):
        if self.response_data is None:
            self.get()

        for item in self.response_data:
            if self.prefix_filter and not item.startswith(self.prefix_filter):
                continue
            yield item


class Catalog(IterEntity):
    url = '/_catalog'
    methods_supported = 'GET'
    response_key = 'repositories'


class Tags(IterEntity):
    url_template = '/{name}/tags/list'
    methods_supported = 'GET'
    response_key = 'tags'

    def __init__(self, client, name, prefix_filter=None):
        super().__init__(client, prefix_filter)
        self.set_url(name=name)


class SlimManifest(Entity):
    url_template = '/{name}/manifests/{reference}'
    media_type = 'v2'
    methods_supported = 'GET,PUT,DELETE'

    def __init__(self, client, name, reference):
        super().__init__(client)
        self.set_url(name=name, reference=reference)

    def request(self, method, *args, **kwargs):
        headers = kwargs.pop('headers', {})
        media_type = get_media_type(self.media_type, obj=False)
        update = {'Accept': '*/*', 'Content-Type': media_type} \
            if method in ('PUT', 'DELETE') else {'Accept': media_type}
        headers.update(update)
        kwargs['headers'] = headers
        return super().request(method, *args, **kwargs)


class FatManifest(SlimManifest):
    media_type = 'v2f'
    methods_supported = 'GET'


class Api:
    def __init__(self, host, insecure=False, verify=True, credentials=None,
                 **kwargs):
        self.registry = Registry(host, insecure, verify, credentials)

    def catalog(self, prefix_filter=None):
        return Catalog(self.registry, prefix_filter)

    def tags(self, name, prefix_filter=None):
        return Tags(self.registry, name, prefix_filter)

    def put_tag(self, name, reference, target):
        return self.put_manifest(name, target, self.manifest(name, reference))

    def delete_tag(self, name, reference):
        return self.del_manifest(name, self.digest(name, reference))

    def digest(self, name, reference, **kwargs):
        r = self.get_manifest(name, reference)
        return r.headers.get('Docker-Content-Digest', None)

    def manifest(self, name, reference, fat=False, obj=False, **kwargs):
        r = self.get_manifest(name, reference, fat).json()
        return Manifest(r) if obj is True else r

    def get_manifest(self, name, reference, fat=False, **kwargs):
        return self._manifest(name, reference, fat)\
                   .request('GET', **kwargs)

    def put_manifest(self, name, reference, manifest, **kwargs):
        return self._manifest(name, reference)\
                   .request('PUT', json=manifest, **kwargs)

    def del_manifest(self, name, reference, **kwargs):
        return self._manifest(name, reference)\
                   .request('DELETE', **kwargs)

    def _manifest(self, name, reference, fat=False):
        args = (self.registry, name, reference)
        return SlimManifest(*args) if fat is False else FatManifest(*args)


class Image:
    registry = None
    repository = None
    namespace = None
    image = None
    tag = None

    def __init__(self, value):
        for k, v in get_parts(value).items():
            setattr(self, k, v)
        self.value = value

    @property
    def image_tag(self):
        return '{}:{}'.format(self.repository, self.tag)

    @property
    def full(self):
        return '{}{}'.format(self.registry or '', self.image_tag)

    def __str__(self):
        return '<{} Namespace="{}" Image="{}" Tag="{}">'\
               .format(self.registry or '',
                       self.namespace or '',
                       self.image or '',
                       self.tag or '')

    def __repr__(self):
        return self.image

    def __lt__(self, other):
        return self.image < other.image

    def __gt__(self, other):
        return self.image > other.image


class Manifest:
    def __init__(self, raw):
        self._raw = raw
        self._history = None

    @property
    def name(self):
        return self._raw.get('name', None)

    @property
    def tag(self):
        return self._raw.get('tag', None)

    @property
    def layers(self):
        return self._raw.get('fsLayers', self._raw.get('layers', None))

    @property
    def history(self):
        try:
            if self._history is None:
                raw = self._raw['history'][0]['v1Compatibility']
                self._history = json.loads(raw)
            return self._history
        except Exception:
            return {}

    @property
    def created(self):
        return self.history.get('created', None)

    @property
    def schema(self):
        return self._raw.get('schemaVersion', None)


class RegistryError(Exception):
    pass
