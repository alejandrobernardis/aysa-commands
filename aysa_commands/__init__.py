# Author: Alejandro M. Bernardis
# Email: alejandro.bernardis at gmail.com
# Created: 2019/10/18
# ~

# version
SEGMENT = 'dev'
VERSION = (1, 0, 0, SEGMENT, 0)

# doc
__title__ = 'aysa-commands'
__summary__ = 'Marco de trabajo para el despliegue de contenedores.'
__uri__ = 'https://github.com/alejandrobernardis/aysa-commands/'
__issues__ = 'https://github.com/alejandrobernardis/aysa-commands/issues/'
__version__ = '.'.join([str(x) for x in VERSION])
__author__ = 'Alejandro M. BERNARDIS and individual contributors.'
__email__ = 'alejandro.bernardis@gmail.com'
__license__ = 'MTI License, Version 2.0'
__copyright__ = 'Copyright 2019-% {}'.format(__author__)

try:
    import sys

    if 'concurrency' in sys.modules:
        del sys.modules['concurrency']

    # import's
    from aysa_commands._common import Command

    # TopLevel
    class TopLevelCommand(Command):
        """
        AySA, Utilidad para la gestión de despliegues sobre `docker`.

        Usage:
            aysa [options] COMMAND [ARGS...]

        Opciones:
            -h, --help                              Muestra la `ayuda` del programa.
            -v, --version                           Muestra la `versión` del programa.
            -D, --debug                             Activa el modo `debug`.
            -V, --verbose                           Activa el modo `verbose`.
            -O filename, --debug-output=filename    Archivo de salida para el modo `debug`.
            -E filename, --env=filename             Archivo de configuración del entorno (`.ini`),
                                                    el mismo será buscado en la siguiente ruta
                                                    de no ser definido: `~/.aysa/config.ini`.

        Comandos disponibles:
            config      Lista y administra los valores de la configuración del entorno de trabajo
                        definidos por el archivo `~/.aysa/config.ini`.
            registry    Lista las `imágenes` y administra los `tags` del `repositorio`.
            release     Crea las `imágenes` para los entornos de `QA/TESTING` y `PRODUCCIÓN`.
            remote      Despliega las `imágenes` en los entornos de `DESARROLLO` y `QA/TESTING`.

        Actualización:
            upgrade     Actualiza los comandos disponibles.

        > Utilice `aysa COMMAND (-h|--help)` para ver la `ayuda` especifica del comando.
        """

        def __init__(self, command, options=None, **kwargs):
            # TODO (0608156): hacer un discovery de los comandos
            commands = kwargs.pop('commands', {
                'config': 'aysa_commands.config.ConfigCommand',
                'registry': 'aysa_commands.registry.RegistryCommand',
                'release': 'aysa_commands.registry.ReleaseCommand',
                'remote': 'aysa_commands.remote.RemoteCommand'
            })
            super().__init__(command, options, commands=commands, **kwargs)


    def main():
        TopLevelCommand('aysa_commands', {'version': __version__}).parse()

except Exception:
    pass
