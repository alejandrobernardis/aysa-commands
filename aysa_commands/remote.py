# Author: Alejandro M. Bernardis
# Email: alejandro.bernardis at gmail.com
# Created: 2019/10/21
# ~

import re
from pathlib import Path
from functools import lru_cache
from fabric import Connection
from aysa_commands import Command

DEVELOPMENT = 'development'
QUALITY = 'quality'
rx_item = re.compile(r'^[a-z](?:[\w_])+_\d{1,3}\s{2,}[a-z0-9](?:[\w.-]+)'
                     r'(?::\d{1,5})?/[a-z0-9](?:[\w.-/])*\s{2,}'
                     r'(?:[a-z][\w.-]*)\s', re.I)
rx_service = re.compile(r'^[a-z](?:[\w_])+$', re.I)
rx_login = re.compile(r'Login\sSucceeded$', re.I)


class _ConnectionCommand(Command):
    _stage = None
    _stages = (DEVELOPMENT, QUALITY)
    _connection_cache = None

    def s_close(self):
        if self._connection_cache is not None:
            self._connection_cache.close()
            self._connection_cache = None
            self._stage = None

    def s_connection(self, stage=None):
        if self._stage and stage != self._stage:
            self.s_close()
        if self._connection_cache is None:
            env = self.env_copy[stage]
            for x in ('path', 'tag'):
                env.pop(x, None)
            if env['user'].lower() == 'root':
                raise SystemExit('El usuario "root" no está permitido para '
                                 'ejecutar despliegues.')
            pkey = Path(env.pop('pkey', None)).expanduser()
            env['connect_kwargs'] = {'key_filename': str(pkey)}
            self._connection_cache = Connection(**env)
            self.logger.info('connection stage: %s, env: %s', stage, env)
            self._stage = stage
        return self._connection_cache

    def on_finish(self, *args, **kwargs):
        self.s_close()

    @property
    def cnx(self):
        if self._stage and self._connection_cache is None:
            self.s_connection(self._stage)
        return self._connection_cache

    def run(self, command, hide=False, **kwargs):
        self.logger.info('run command: %s, kwargs: %s', command, kwargs)
        return self.cnx.run(command, hide=hide, **kwargs)

    @lru_cache()
    def _norm_service(self, value, sep='_'):
        return sep.join(value.split(sep)[1:-1])

    def _list_to_str(self, values, sep=' '):
        return sep.join((x for x in values))

    def _list(self, cmd, filter_line=None, obj=None):
        response = self.run(cmd, hide=True)
        for line in response.stdout.splitlines():
            if filter_line and not filter_line.match(line):
                continue
            yield obj(line) if obj is not None else line

    def _list_environ(self, values, cnx=True):
        environs = [x for x in self._stages if values.get('--' + x, False)]
        for x in environs or (DEVELOPMENT,):
            if cnx is True:
                self.s_connection(x)
            stage = self.env[self._stage]
            self.output.head(x.upper(), stage.user, stage.host,
                             tmpl='[{}]: {}@{}', title=False)
            with self.cnx.cd('' if stage.user == '0x00' else stage.path):
                yield x
            self.output.blank()

    def _list_service(self, values=None, **kwargs):
        for x in self._list("docker-compose ps --services", rx_service):
            if values and x not in values:
                continue
            yield x

    def _list_image(self, values, **kwargs):
        for line in self._list("docker-compose images", rx_item):
            container, image, tag = line.split()[:3]
            if values and self._norm_service(container) not in values:
                continue
            yield '{}:{}'.format(image, tag)

    def _services(self, values):
        if isinstance(values, dict):
            values = values['service']
        return set([x for x in self._list_service(values)])

    def _images(self, values):
        if isinstance(values, dict):
            values = values['image']
        return set([x for x in self._list_image(values)])

    def _login(self):
        try:
            env = self.env.registry
            crd = env.credentials.split(':')
            cmd = 'docker login -u {} -p {} {}'.format(*crd, env.host)
            res = rx_login.match(self.run(cmd, hide=True).stdout) is not None
            self.logger.info('login registry: %s, username: %s, status: %s',
                             env.host, crd[0], res)
            return res
        except Exception as e:
            self.logger.error('login error: %s ', e)
            return False

    def _deploy(self, **kwargs):
        if self._login():
            self.run('docker-compose stop')
            services = self._services(kwargs)
            images = self._images(services)
            if services:
                srv = self._list_to_str(services)
                self.run('docker-compose rm -fsv {}'.format(srv))
            if images:
                srv = self._list_to_str(images)
                self.run('docker rmi -f {}'.format(srv))
            self.run('docker volume prune -f')
            if kwargs.pop('--update', False) is True:
                self.run('git reset --hard')
                self.run('git pull --rebase --stat')
            self.run('docker-compose up -d --remove-orphans')
        else:
            raise SystemExit('No se pudo establecer la sesión '
                             'con la `registry`.')

    def _run_cmd(self, cmd, values):
        self.run('{} {}'.format(cmd, self._list_to_str(values)))


class RemoteCommand(_ConnectionCommand):
    """
    Despliega las `imágenes` en los entornos de `DESARROLLO` y `QA/TESTING`.

    Usage:
        remote COMMAND [ARGS...]

    Comandos disponibles:
        config     Muestra la configuración del despliegue.
        down       Detiene y elimina los servicios en uno o más entornos.
        ls         Lista los servicios disponibles.
        prune      Purga los servicios en uno o más entornos.
        ps         Lista los servicios deplegados.
        restart    Detiene y elimina los servicios en uno o más entornos.
        start      Inicia los servicios en uno o más entornos.
        stop       Detiene los servicios en uno o más entornos.
        up         Crea e inicia los servicios en uno o más entornos.
        update     Actualiza el repositorio con la configuración del despliegue.
    """

    def up(self, **kwargs):
        """
        Crea e inicia los servicios en uno o más entornos.

        Usage:
            up [options] [SERVICE...]

        Opciones
            -d, --development    Entorno de `DESARROLLO`
            -q, --quality        Entorno de `QA/TESTING`
            -u, --update         Actualiza el repositorio con la
                                 configuración del despliegue.
            -y, --yes            Responde "SI" a todas las preguntas.
        """
        if self.yes(**kwargs):
            for _ in self._list_environ(kwargs):
                self._deploy(**kwargs)

    def down(self, **kwargs):
        """
        Crea e inicia los servicios en uno o más entornos.

        Usage:
            down [options]

        Opciones
            -d, --development    Entorno de `DESARROLLO`
            -q, --quality        Entorno de `QA/TESTING`
            -y, --yes            Responde "SI" a todas las preguntas.
        """
        if self.yes(**kwargs):
            for _ in self._list_environ(kwargs):
                self.run('docker-compose down -v --remove-orphans')

    def start(self, **kwargs):
        """
        Inicia los servicios en uno o más entornos.

        Usage:
            start [options] [SERVICE...]

        Opciones
            -d, --development    Entorno de `DESARROLLO`
            -q, --quality        Entorno de `QA/TESTING`
            -y, --yes            Responde "SI" a todas las preguntas.
        """
        if self.yes(**kwargs):
            for _ in self._list_environ(kwargs):
                self._run_cmd('docker-compose start', self._services(kwargs))

    def stop(self, **kwargs):
        """
        Detiene los servicios en uno o más entornos.

        Usage:
            stop [options] [SERVICE...]

        Opciones
            -d, --development    Entorno de `DESARROLLO`
            -q, --quality        Entorno de `QA/TESTING`
            -y, --yes            Responde "SI" a todas las preguntas.
        """
        if self.yes(**kwargs):
            for _ in self._list_environ(kwargs):
                self._run_cmd('docker-compose stop', self._services(kwargs))

    def restart(self, **kwargs):
        """
        Detiene los servicios en uno o más entornos.

        Usage:
            restart [options] [SERVICE...]

        Opciones
            -d, --development    Entorno de `DESARROLLO`
            -q, --quality        Entorno de `QA/TESTING`
            -y, --yes            Responde "SI" a todas las preguntas.
        """
        if self.yes(**kwargs):
            for _ in self._list_environ(kwargs):
                self._run_cmd('docker-compose restart', self._services(kwargs))

    def ls(self, **kwargs):
        """
        Lista los servicios disponibles.

        Usage:
            ls [options]

        Opciones
            -d, --development    Entorno de `DESARROLLO`
            -q, --quality        Entorno de `QA/TESTING`
        """
        for _ in self._list_environ(kwargs):
            for line in self._list_service():
                self.output.bullet(line, tab=1)

    def ps(self, **kwargs):
        """
        Lista los servicios deplegados.

        Usage:
            ps [options]

        Opciones
            -d, --development    Entorno de `DESARROLLO`
            -q, --quality        Entorno de `QA/TESTING`
        """
        for _ in self._list_environ(kwargs):
            self.run("docker-compose ps")

    def config(self, **kwargs):
        """
        Muestra la configuración del despliegue.

        Usage:
            config (--development|--quality)

        Opciones
            -d, --development    Entorno de `DESARROLLO`
            -q, --quality        Entorno de `QA/TESTING`
        """
        for _ in self._list_environ(kwargs):
            self.run("docker-compose config --resolve-image-digests")

    def prune(self, **kwargs):
        """
        Purga los servicios en uno o más entornos.

        Usage:
            prune [--yes] (--development|--quality)

        Opciones
            -d, --development    Entorno de `DESARROLLO`
            -q, --quality        Entorno de `QA/TESTING`
            -y, --yes            Responde "SI" a todas las preguntas.
        """
        message = '''
[PRECAUCIÓN]
  Se procederá a "PURGAR" el o los `entornos`,
  el siguiente proceso es "IRRÉVERSIBLE".
--
Desdea continuar?'''
        if self.yes(message, **kwargs):
            for _ in self._list_environ(kwargs):
                self.run('docker-compose down -v --rmi all --remove-orphans')
                self.run('docker volume prune -f')

    def update(self, **kwargs):
        """
        Actualiza el repositorio con la configuración del despliegue.

        Usage:
            update [options]

        Opciones
            -d, --development   Entorno de `DESARROLLO`
            -q, --quality       Entorno de `QA/TESTING`
            -y, --yes           Responde "SI" a todas las preguntas.
        """
        if self.yes(**kwargs):
            for _ in self._list_environ(kwargs):
                self.run('git reset --hard')
                self.run('git pull --rebase --stat')

    def cmd(self, **kwargs):
        """
        Ejecuta los comandos `docker`, `docker-compose` y `git` de forma remota.

        Usage:
            cmd [options] CMD...

        Opciones
            -d, --development    Entorno de `DESARROLLO`
            -q, --quality        Entorno de `QA/TESTING`
            -y, --yes            Responde "SI" a todas las preguntas.
        """
        for _ in self._list_environ(kwargs):
            cmd = kwargs['cmd']
            if len(cmd) == 1:
                cmd = cmd[0].split()
            if cmd[0] not in ('docker', 'docker-compose', 'git'):
                continue
            self.run(self._list_to_str(cmd))
