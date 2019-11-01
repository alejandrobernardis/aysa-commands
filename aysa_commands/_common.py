# Author: Alejandro M. Bernardis
# Email: alejandro.bernardis at gmail.com
# Created: 2019/10/30
# ~

import sys
import json
import logging
from copy import deepcopy
from configparser import ConfigParser, ExtendedInterpolation
from docopt import docopt, DocoptExit
from importlib import import_module
from inspect import getdoc, isclass
from pathlib import Path

ENV_FILE = '~/.aysa/config.ini'
CONST_COMMAND = 'COMMAND'
CONST_ARGS = 'ARGS'


def docopt_helper(docstring, *args, **kwargs):
    try:
        docstring = doc_helper(docstring)
        return docopt(docstring, *args, **kwargs), docstring
    except DocoptExit:
        raise CommandExit(docstring)


def doc_helper(docstring):
    if not isinstance(docstring, str):
        docstring = getdoc(docstring)
    return ' \n{}\n '.format(docstring)


def env_helper(filename=None):
    filepath = Path(filename or ENV_FILE).expanduser()
    parser = ConfigObject(interpolation=ExtendedInterpolation())
    if parser.read(filepath, encoding='utf-8'):
        return parser, filepath
    raise CommandExit('Es necesario definir el archivo "~/.aysa/config.ini", '
                      'con las configuración de los diferentes "endpoints": '
                      '`registry`, `development` y `quality`.')


def is_yes(value):
    return str(value).lower() in ('true', 'yes', 'si', 'y', 's', '1')


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self


class ConfigObject(ConfigParser):
    def to_dict(self):
        result = {}
        for sk, sv in self.items():
            if sk == 'common':
                continue
            for svk, svv in sv.items():
                if sk not in result:
                    result[sk] = AttrDict()
                result[sk][svk] = svv
        return AttrDict(result)


class Printer:
    def __init__(self, output=None):
        self.output = output or sys.stdout

    def _parse(self, *values, sep=' ', end='\n', endx=None, **kwargs):
        tmpl = kwargs.pop('tmpl', None)
        value = tmpl.format(*values) if tmpl is not None \
            else sep.join([str(x) for x in values])
        if kwargs.pop('lower', False):
            value = value.lower()
        if kwargs.pop('upper', False):
            value = value.upper()
        if kwargs.pop('title', False):
            value = value.title()
        if endx is not None:
            end = '\n' * (endx or 1)
        if end and not value.endswith(end):
            end = '\n'
        tab = ' ' * kwargs.pop('tab', 0)
        return tab + value + end

    def done(self):
        self.flush('Done.', endx=3)

    def error(self, *message, **kwargs):
        kwargs['icon'] = '!'
        self.bullet(*message, **kwargs)

    def title(self, *message, **kwargs):
        kwargs['icon'] = '~'
        if 'tmpl' in kwargs:
            kwargs['title'] = False
        self.bullet(*message, **kwargs)

    def question(self, *message, **kwargs):
        kwargs['icon'] = '?'
        self.bullet(*message, **kwargs)

    def bullet(self, *message, icon='>', **kwargs):
        if 'tmpl' in kwargs:
            kwargs['tmpl'] = '{} ' + kwargs['tmpl']
        self.write(icon, *message, **kwargs)

    def rule(self, icon='-', maxsize=2):
        self.flush(icon * min(80, max(0, maxsize)))

    def blank(self):
        self.flush('')

    def head(self, *message, **kwargs):
        self.blank()
        self.title(*message, **kwargs)
        self.rule()

    def foot(self):
        self.blank()
        self.rule()
        self.done()

    def write(self, *values, **kwargs):
        value = self._parse(*values, **kwargs)
        if value:
            self.output.write(value)

    def flush(self, *values, **kwargs):
        if values:
            self.write(*values, **kwargs)
        self.output.flush()

    def json(self, value, indent=2):
        raw = json.dumps(value, indent=indent) \
              if isinstance(value, dict) else '-'
        self.output.write(raw + '\n')
        self.flush()


class Command:
    def __init__(self, command, options=None, **kwargs):
        self.command = command
        self.options = options or {}
        self.options.setdefault('options_first', True)

        # helpers
        self._env = None
        self._output = Printer()
        self._parent = kwargs.pop('parent', None)
        self._logger = kwargs.pop('logger', None)
        self.commands = kwargs.pop('commands', None)

        # event
        self.on_init(**kwargs)

    @property
    def top_level(self):
        value = None
        while 1:
            if self.parent is None:
                return self
            elif value is None:
                value = self.parent
            elif value.parent is not None:
                value = value.parent
            else:
                break
        return value

    @property
    def parent(self):
        return self._parent

    @property
    def output(self):
        return self._output

    @property
    def logger(self):
        if self._logger is not None:
            return self._logger
        else:
            self._logger = logging.getLogger(self.__class__.__name__)
        return self.top_level.logger

    @property
    def global_options(self):
        return self.top_level.options

    @property
    def env(self):
        return self.top_level._env

    @env.setter
    def env(self, value):
        self.top_level._env = value

    @property
    def env_copy(self):
        return deepcopy(self.env)

    @property
    def env_file(self):
        return self.global_options.get('--env', None)

    @property
    def debug(self):
        return self.global_options.get('--debug', False)

    @property
    def debug_output(self):
        return self.global_options.get('--debug-output', False)

    @property
    def verbose(self):
        return self.global_options.get('--verbose', False)

    def setup_logger(self, **kwargs):
        if self.debug:
            level = logging.DEBUG
        elif self.verbose:
            level = logging.INFO
        else:
            level = logging.ERROR

        root = logging.getLogger()

        if self.debug_output:
            file_formatter = logging.Formatter('%(asctime)s %(levelname)s '
                                               '%(filename)s %(lineno)d '
                                               '%(message)s')
            file_handler = logging.FileHandler(self.debug_output, 'w')
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG)
            root.addHandler(file_handler)
            level = logging.ERROR

        console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(level)
        root.addHandler(console_handler)
        root.setLevel(logging.DEBUG)

    def parse(self, argv=None, *args, **kwargs):
        opt, doc = docopt_helper(self, argv, *args, **self.options, **kwargs)
        cmd = opt.pop(CONST_COMMAND)
        arg = opt.pop(CONST_ARGS)
        self.options.update(opt)
        self.setup_logger()

        self.logger.info('parse cmd: %s, arg: %s, kwargs: %s',
                         argv, args, kwargs)
        self.logger.debug('parse options: %s', self.options)
        self.env_load()

        try:
            scmd = self.find_command(cmd)
            sdoc = doc_helper(scmd)
        except NoSuchCommand:
            raise CommandExit(doc)

        try:
            if isclass(scmd):
                sargs = arg[1:] if len(arg) > 1 else []
                scmd(cmd, parent=self).execute(arg[0], sargs, self.options)
            else:
                self.execute(scmd, arg, self.options, parent=self)
        except (NoSuchCommand, AttributeError, IndexError):
            raise CommandExit(sdoc)

    def execute(self, command, argv=None, global_args=None, **kwargs):
        self.logger.info('execute command: %s, argv: %s, global_args: %s, '
                         'kwargs: %s', command, argv, global_args, kwargs)
        if isinstance(command, str):
            command = self.find_command(command)

        opt, doc = docopt_helper(command, argv, options_first=True)
        opt = {k.lower(): v for k, v in opt.items()}
        command(**opt, global_args=global_args)

        self.on_finish()
        self.done()

    def find_command(self, command):
        try:
            cmd = getattr(self, 'commands')[command]
            if isinstance(cmd, str):
                mod, cls = cmd.rsplit('.', 1)
                return getattr(import_module(mod), cls)
            return cmd
        except Exception as e:
            self.logger.debug(e)
        try:
            return getattr(self, command)
        except Exception as e:
            self.logger.debug(e)
        raise NoSuchCommand(command)

    def __call__(self, argv=None, *args, **kwargs):
        return self.parse(argv, *args, **kwargs)

    def __str__(self):
        return self.command

    def __repr__(self):
        return '<{} Command="{}">'\
               .format(self.__class__.__name__, self.command)

    def input(self, message=None, recursive=False, default=None, values=None,
              cast=None):
        if not isinstance(message, str):
            message = 'Por favor, ingrese un valor'
        else:
            message = message.strip()
        if not message.endswith(':'):
            message += ': '
        if values or default:
            if not values:
                values = default
            message = '{} [{}]: '.format(message[:-2], str(values))
        value = input(message).strip()
        if default is not None and not value:
            return default
        if cast is not None:
            try:
                value = cast(value)
            except Exception:
                if recursive is True:
                    return self.input(message, recursive, default, cast)
                raise CommandExit('Valor incorrecto: ' + value)
        return value

    def yes(self, message=None, **kwargs):
        if kwargs and kwargs.get('--yes', False) is False:
            if message is None:
                message = 'Desea continuar?'
            return is_yes(self.input(message, default='N', values='N/y'))
        return True

    def env_load(self):
        env, _ = env_helper(self.env_file)
        self.env = env.to_dict()
        self.logger.info('env load: %s', self.env)

    def env_save(self, data=None):
        env, filepath = env_helper(self.env_file)
        env.read_dict(data or self.env)
        with filepath.open('w') as output:
            env.write(output)
            self.logger.info('env save: %s', env.to_dict())
        self.env_load()

    def done(self):
        self.output.done()
        sys.exit(0)

    def on_init(self, *args, **kwargs):
        pass

    def on_finish(self, *args, **kwargs):
        pass


class NoSuchCommand(Exception):
    def __init__(self, command):
        super().__init__("No such command: %s" % command)
        self.command = command


class CommandExit(SystemExit):
    def __init__(self, docstring):
        super().__init__(docstring)
        self.docstring = docstring
