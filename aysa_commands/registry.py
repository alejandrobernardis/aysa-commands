# Author: Alejandro M. Bernardis
# Email: alejandro.bernardis at gmail.com
# Created: 2019/10/18
# ~

from aysa_commands import Command
from aysa_commands._docker import Api, Image

WILDCARD = '*'


class _RegistryCommand(Command):
    _registry_api = None

    @property
    def api(self):
        if self._registry_api is None:
            self._registry_api = Api(**self.env.registry)
        return self._registry_api

    @property
    def namespace(self):
        return self.env.registry.namespace

    def _fix_image_name(self, value, namespace=None):
        value = value.strip()
        namespace = namespace or self.namespace
        return '{}/{}'.format(namespace, value) \
            if not value.startswith(namespace) else value

    def _fix_images_list(self, values, namespace=None):
        values = values.split(',') if isinstance(values, str) else values or []
        return [self._fix_image_name(x.strip(), namespace) for x in values]

    def _fix_tags_list(self, values):
        if not values or values == WILDCARD:
            return WILDCARD
        values = values.split(',') if not isinstance(values, list) else values
        return [x.strip() for x in values]

    def _list(self, filter_repos=None, filter_tags=None, **kwargs):
        filter_repos = self._fix_images_list(filter_repos)
        filter_tags = self._fix_tags_list(filter_tags)
        for x in self.api.catalog():
            if (self.namespace and not x.startswith(self.namespace)) \
                    or (filter_repos and x not in filter_repos):
                continue
            if filter_tags:
                for y in self.api.tags(x):
                    if filter_tags != WILDCARD and y not in filter_tags:
                        continue
                    yield Image('{}:{}'.format(x, y))
            else:
                yield Image(x)


class RegistryCommand(_RegistryCommand):
    """
    Lista las `imágenes` y administra los `tags` del `repositorio`.

    Usage:
        registry COMMAND [ARGS...]

    Comandos disponibles:
        ls     Lista los `tags` diponibles en el `repositorio`.
        tag    Crea un nuevo `tag` a partir de otro existente.
        rm     Elimina uno o mas `tags` existentes.
    """

    def ls(self, **kwargs):
        """
        Lista los `tags` existentes en el repositorio.

        Usage:
            ls [options] [IMAGE...]

        Opciones:
            -d, --detail                   Activa el modo `detail`.
            -m, --manifest                 Activa el modo `manifest`, éste imprime
                                           en pantalla el contenido del manifiesto,
                                           anulando al modo `detail`.
            -t tags, --filter-tags=tags    Lista de `tags` separados por comas,
                                           ex: "dev,rc,latest" [default: *]
        """
        tmpl = ' - {} = {}'
        detail = kwargs.get('--detail', False)
        manifest = kwargs.get('--manifest', False)
        env = self.env.registry
        self.output.head(env.host, env.namespace, tmpl='[REGISTRY]: {}/{}:',
                         title=False)
        for x in self._list(kwargs['image'], kwargs['--filter-tags']):
            self.output.bullet(x.repository, x.tag, tmpl='{}:{}')
            if detail or manifest:
                m = self.api.manifest(x.repository, x.tag, True, True)
                if detail and not manifest:
                    self.output.write('created', m.created, tmpl=tmpl)
                    d = self.api.digest(x.repository, x.tag)
                    self.output.write('digest', d, tmpl=tmpl)
                elif manifest:
                    self.output.json(m.history)

    def tag(self, **kwargs):
        """
        Crea un nuevo `tag` a partir de otro existente.

        Usage:
            tag SOURCE_IMAGE_TAG TARGET_TAG
        """
        src = Image(self._fix_image_name(kwargs['source_image_tag']))
        self.api.put_tag(src.repository, src.tag, kwargs['target_tag'])
        self.logger.info('tag repository: %s, tag: %s',
                         src.repository, src.tag)

    def rm(self, **kwargs):
        """
        Elimina un `tag` existente.

        Usage:
            rm [options] IMAGE_TAG [IMAGE_TAG...]

        Opciones:
            -y, --yes    Responde "SI" a todas las preguntas.
        """
        if self.yes(**kwargs):
            for x in kwargs['image_tag']:
                src = Image(self._fix_image_name(x))
                try:
                    self.api.delete_tag(src.repository, src.tag)
                    self.logger.info('rm repository: %s, tag: %s',
                                      src.repository, src.tag)
                except Exception as e:
                    self.logger.error('No se pudo eliminar la image "%s": %s',
                                      src.image_tag, e)


class ReleaseCommand(_RegistryCommand):
    """
    Crea las `imágenes` para los entornos de `QA/TESTING` y `PRODUCCIÓN`.

    Usage:
        release COMMAND [ARGS...]

    Comandos disponibles:
        quality       Crea las `imágenes` para el entorno de `QA/TESTING`.
        production    Crea las `imágenes` para el entorno de `PRODUCCIÓN`.
    """

    def _release(self, source_tag, target_tag, **kwargs):
        if self.yes(**kwargs):
            for x in self._list(kwargs['image'], source_tag):
                t = Image('{}:{}'.format(x.repository, target_tag))
                try:
                    rollback = '{}-rollback'.format(t.tag)
                    self.api.put_tag(t.repository, t.tag, rollback)
                    self.logger.info('release source: %s, target: %s',
                                     t.tag, rollback)
                except Exception as e:
                    self.logger.error('Rollback imagen "%s": %s',
                                      t.image_tag, e)
                self.api.put_tag(x.repository, x.tag, t.tag)
                self.logger.info('release source: %s, target: %s',
                                 x.tag, t.tag)

    def quality(self, **kwargs):
        """
        Crea las `imágenes` para el entorno de `QA/TESTING`.

        Usage:
            quality [options] [IMAGE...]

        Opciones:
            -y, --yes    Responde "SI" a todas las preguntas.
        """
        self._release('dev', 'rc', **kwargs)

    def production(self, **kwargs):
        """
        Crea las `imágenes` para el entorno de `PRODUCCIÓN`.

        Usage:
            production [options] [IMAGE...]

        Opciones:
            -y, --yes    Responde "SI" a todas las preguntas.
        """
        self._release('rc', 'latest', **kwargs)
