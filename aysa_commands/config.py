# Author: Alejandro M. Bernardis
# Email: alejandro.bernardis at gmail.com
# Created: 2019/10/21
# ~

from getpass import getpass
from aysa_commands._common import Command
CREDENTIALS = 'credentials'


class ConfigCommand(Command):
    """
    Lista y administra los valores de la configuración del entorno de trabajo
    definidos por el archivo `~/.aysa/config.ini`.

    Usage:
        config COMMAND [ARGS...]

    Comandos disponibles:
        ls        Lista todas las `variables` de configuración.
        update    Actualiza el valor de una nueva `variable` de configuración.
                  Para la variable `registry.credentials` NO es necesario
                  pasar el valor de la contraseña, éste es solicitado
                  posteriomente.
    """

    def ls(self, **kwargs):
        """
        Lista todas las `variables` de configuración.

        Usage:
            ls [SECTION...]
        """
        if not self.env:
            raise ValueError('La configuración del entorno está vacía.')
        sections_filter = kwargs['section']
        self.output.blank()
        for s, sv in self.env.items():
            if sections_filter and s not in sections_filter:
                continue
            self.output.title(s, tmpl='[{}]:', upper=True)
            for k, v in sv.items():
                if k == CREDENTIALS and v:
                    v = '{}:******'.format(v.split(':')[0])
                self.output.write(k, v, tmpl='{} = "{}"', tab=2)
            self.output.blank()

    def update(self, **kwargs):
        """
        Actualiza el valor de una nueva `variable` de configuración.
        Para la variable `registry.credentials` NO es necesario pasar
        el valor de la contraseña, éste es solicitado posteriomente.

        Usage:
            update SECTION_VARIABLE VALUE
        """
        section, sep, variable = kwargs['section_variable'].partition('.')
        self.logger.info('update section: %s, variable: %s',
                         section, variable)
        if not sep or not variable:
            raise ValueError('La definición de la sección "{}" y variable '
                             '"{}" es incorrecta, recuerda que debes '
                             'expresarla separando la sección de la variable '
                             'con un punto (.), ex: "<sección>.<variable>"'
                             .format(section, variable))
        new_value = kwargs['value']
        self.logger.info('update value: %s', new_value)
        if variable == CREDENTIALS:
            password = getpass()
            if new_value and password:
                new_value = '{}:{}'.format(new_value, password)
                self.logger.info('update password')
        try:
            self.env[section][variable] = new_value
            self.env_save()
            self.logger.info('update done')
        except KeyError:
            raise KeyError('La sección y/o variable "{}.{}" no están '
                           'soportadas por la acutal versión del '
                           'archivo de configuración.'
                           .format(section, variable))
