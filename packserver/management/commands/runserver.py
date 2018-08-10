from __future__ import print_function

import atexit
import os
import psutil
import subprocess
import sys
import traceback
import time

from colored import fg, bg, attr, stylize
from concurrent.futures import ThreadPoolExecutor
from env_tools import load_env
from signal import SIGTERM

from django.contrib.staticfiles.management.commands.runserver import Command \
    as StaticfilesRunserverCommand

from django.core.management.base import CommandError
from django.core.servers import basehttp
from django.conf import settings

def log_local_message(message_format, *args):
    """
    Log a request so that it matches our local log format.
    """
    prefix = '{} {}'.format(stylize('INFO', fg(248)), stylize('request', fg(5)))

    if isinstance(message_format, str):
        message = message_format % args
        sys.stderr.write('{} {}\n'.format(prefix, stylize(message, fg(214))))


basehttp.WSGIRequestHandler.log_message = log_local_message


class Command(StaticfilesRunserverCommand):
    help = 'Starts a lightweight Web server for development with browser-sync reload and webpack.'

    def __init__(self, *args, **kwargs):
        self.cleanup_closing = False
        self.browsersync_process = None
        self.bsync_reload_process = None
        self.webpack_process = None

        super(Command, self).__init__(*args, **kwargs)

    @staticmethod
    def browsersync_exited_cb(future):
        if future.exception():
            print(traceback.format_exc())

            children = psutil.Process().children(recursive=True)

            for child in children:
                print(stylize('>>> Killing pid {}'.format(child.pid), fg(196)))

                child.send_signal(SIGTERM)

            print(stylize('>>> Exiting', fg(196)))

            # It would be nice to be able to raise a CommandError or use
            # sys.kill here but neither of those stop the runserver instance
            # since we're in a thread. This method is used in django as well.
            os._exit(1)

    @staticmethod
    def webpack_exited_cb(future):
        if future.exception():
            print(traceback.format_exc())

            children = psutil.Process().children(recursive=True)

            for child in children:
                print(stylize('>>> Killing pid {}'.format(child.pid), fg(196)))

                child.send_signal(SIGTERM)

            print(stylize('>>> Exiting', fg(196)))

            # It would be nice to be able to raise a CommandError or use
            # sys.kill here but neither of those stop the runserver instance
            # since we're in a thread. This method is used in django as well.
            os._exit(1)

    def kill_browsersync_process(self):
        if self.browsersync_process.returncode is not None:
            return

        self.cleanup_closing = True
        self.stdout.write(stylize('>>> Closing browsersync process', fg(196)))

        self.browsersync_process.terminate()

    def kill_webpack_process(self):
        if self.webpack_process.returncode is not None:
            return

        self.cleanup_closing = True
        self.stdout.write(stylize('>>> Closing webpack process', fg(196)))

        self.webpack_process.terminate()

    def start_webpack(self):
        self.stdout.write(stylize('>>> Starting webpack-serve', fg(135)))

        webpack_command = getattr(settings, 'WEBPACK_DEVELOP_COMMAND', 'webpack-serve')
        self.webpack_process = subprocess.Popen(
            webpack_command,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=self.stdout._out,
            stderr=self.stderr._out
        )

        if self.webpack_process.poll() is not None:
            raise CommandError('webpack failed to start')

        self.stdout.write(stylize('>>> webpack process on pid {0}'
                                  .format(self.webpack_process.pid), fg(135)))

        atexit.register(self.kill_webpack_process)

        self.webpack_process.wait()

        if self.webpack_process.returncode != 0 and not self.cleanup_closing:
            raise CommandError('webpack exited unexpectedly')

    def start_browsersync(self):
        self.stdout.write(stylize('>>> Starting browsersync', fg(135)))

        browsersync_command = getattr(settings, 'BROWSERSYNC_COMMAND', 'browsersync')
        self.browsersync_process = subprocess.Popen(
            browsersync_command,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=self.stdout._out,
            stderr=self.stderr._out
        )

        if self.browsersync_process.poll() is not None:
            raise CommandError('browsersync failed to start')

        self.stdout.write(stylize('>>> browsersync process on pid {0}'
                                  .format(self.browsersync_process.pid), fg(135)))

        atexit.register(self.kill_browsersync_process)

        self.browsersync_process.wait()

        if self.browsersync_process.returncode != 0 and not self.cleanup_closing:
            raise CommandError('browsersync exited unexpectedly')

    def bsync_request(self, **options):
        """
        Performs the browser-sync reload request.
        """

        bsync_cmd_line = 'browser-sync reload'
        bsync_port = getattr(settings, 'BSYNC_RELOAD_PORT', None)

        if bsync_port:
            try:
                int(bsync_port)
                bsync_command = '{} --port {}'.format(bsync_cmd_line, bsync_port)
            except ValueError:
                self.stdout.write(stylize('>>> Starting browser-sync reload request.', fg(51)))
                self.stdout.write(stylize('>>> BSYNC_RELOAD_PORT: {} --> failed to parse as an integer,'
                                          .format(bsync_port), fg(197)))
                self.stdout.write(stylize('>>> Browser-sync reload request complete.', fg(51)))
        else:
            bsync_command = bsync_cmd_line

        self.bsync_reload_process = subprocess.Popen(
            bsync_command,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=self.stdout,
            stderr=self.stderr
        )

        self.stdout.write(stylize('>>> Starting browser-sync reload request.', fg(51)))

        if self.bsync_reload_process.poll() is not None:
            raise CommandError('bsync failed to reload')

        self.stdout.write(stylize('>>> browser-sync process on pid {0}'
                                  .format(self.bsync_reload_process.pid), fg(226)))

        self.bsync_reload_process.wait()

        if self.bsync_reload_process.returncode == 0:
            self.stdout.write(stylize('>>> Browser-sync reload request complete', fg(51)))
        elif self.bsync_reload_process.returncode != 0 and not self.cleanup_closing:
            raise CommandError('browser-sync reload failed unexpectedly')

    def handle(self, *args, **options):
        try:
            env = load_env()
        except IOError:
            env = {}

        # XXX: In Django 1.8 this changes to:
        # if 'PORT' in env and not options.get('addrport'):
        #     options['addrport'] = env['PORT']

        if 'PORT' in env and not args:
            args = (env['PORT'],)

        # We're subclassing runserver, which spawns threads for its
        # autoreloader with RUN_MAIN set to true, we have to check for
        # this to avoid running browsersync twice.
        pool = ThreadPoolExecutor(max_workers=2)

        if not os.getenv('RUN_MAIN', False):
            browsersync_thread = pool.submit(self.start_browsersync)
            browsersync_thread.add_done_callback(self.browsersync_exited_cb)
            webpack_thread = pool.submit(self.start_webpack)
            webpack_thread.add_done_callback(self.webpack_exited_cb)
        else:
            pool.submit(self.bsync_request)

        return super(Command, self).handle(*args, **options)
