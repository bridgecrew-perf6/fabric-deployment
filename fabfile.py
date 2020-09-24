import sys
from fabric import Connection, task
from contextlib import contextmanager
from pathlib import Path
import logging as logger
from functools import wraps
from invoke import Responder
import re
from fabric.config import Config
from posixpath import join
import environ
import time

# Read .env file
import os

env = environ.Env(
    # set casting, default value
    DEBUG=(bool, True),
)
environ.Env.read_env()

if sys.argv[0].split(os.sep)[-1] in ("fab", "fab-script.py"):
    # Ensure we import settings from the current dir
    try:
        env.list("HOSTS")[0]
    except (KeyError, ValueError):
        print("Aborting, no hosts defined.")
        raise ImportError

env.user = env('SSH_USER')
env.proj_name = env("PROJECT_NAME")
env.repo_path = "/home/%s/current/%s" % (env.user, env.proj_name)
env.repo_url = "git@github.com:Dehaat/%s.git" % env.proj_name

# env.proj_app = env('PROJECT_APP', env.proj_name)
# env.num_workers = env("NUM_WORKERS",
#                            "multiprocessing.cpu_count() * 2 + 1")
env.venv_home = env.str("VIRTUALENV_HOME", "/home/%s/venvs" % env.user)
env.venv_path = join(env.venv_home, env.proj_name)
time_stamp = time.strftime('%Y%m%d_%H%M%S')
deploy_dir = '/home/ubuntu/%s' % env.proj_name
cache_dir = '/tmp/cache'
main_release_dir = os.path.join(deploy_dir, 'releases')

release_dir = os.path.join(main_release_dir, 'release-' + time_stamp)
current_ver_dir = os.path.join(deploy_dir, 'current')
max_releases = 3

logger.basicConfig(level=logger.INFO)
logger.basicConfig(format='%(name)s --------- %(message)s')


@contextmanager
def connection(ctx):
    config = Config(overrides={"run": {'echo': True, 'warn': True}})
    with Connection(
            ctx.host,
            ctx.user,
            connect_kwargs=ctx.connect_kwargs,
            gateway=bastion_connection(),
            config=config,
            forward_agent=True,
    ) as conn:
        yield conn


@task
def prod(ctx):
    ctx.user = 'ubuntu'
    ctx.host = '13.127.83.212'
    ctx.connect_kwargs.key_filename = "/Users/deepakkhatri/Downloads/aeros-geo.pem"
    ctx.connect_kwargs.allow_agent = True


def bastion_connection():
    user = 'dkdocs'
    host = 'bastion.agrevolution.in'
    port = 272
    return Connection(user=user,
                      host=host,
                      port=port,
                      connect_kwargs={"key_filename": "/Users/deepakkhatri/.ssh/id_rsa", "allow_agent": True},
                      forward_agent=True
                      )


@contextmanager
def project(ctx):
    """
    Runs commands within the project's directory.
    """
    with connection(ctx) as conn:
        with conn.cd(current_ver_dir):
            yield conn


@task
def run(ctx, cmd):
    """
    Runs a Command to selected env i.e staging or prod
    """
    with connection(ctx) as conn:
        conn.run(cmd)


@contextmanager
def virtualenv(conn):
    """
    Runs commands within the project's virtualenv.
    """
    with conn.prefix("source %s/bin/activate" % env.venv_path):
        yield conn


@task
def setup(ctx):
    """
    Installs the base system and Python requirements for the entire server.
    """
    # install_system_requirements(ctx)
    setup_release(ctx)
    update_env(ctx)
    # install_python_requirements(ctx)
    cleanup_old_releases(ctx)


@task
def rollback(ctx):
    with connection(ctx) as conn:
        releases = conn.run('ls -xt {}'.format(main_release_dir)).stdout.split()
        if len(releases) < 2:
            logger.error("cannot rollback")
            quit(1)
        rollback_release_index = env.int('ROLLBACK_RELEASE', None)
        index = releases.index(rollback_release_index) if rollback_release_index else 1
        if not index:
            logger.error('cannot found rollback release')
            quit(1)

        last_release = releases[index]
        create_symlink(conn, last_release, current_ver_dir)


def install_system_requirements(ctx):
    with connection(ctx) as conn:
        os_type = conn.run('echo $OSTYPE')

        if os_type.stdout.strip() != 'linux-gnu':
            print('The underlying OS is not ubuntu, terminating the script')
            return

        # Install system requirements
        python_version = 3.7

        if conn.run('which python{}'.format(python_version)).exited == 0:
            print("Python{} is already installed".format(python_version))
        else:
            print('Python{} is not installed'.format(python_version))
            print('Installing Python$PYTHON_VERSION on the system'.format(python_version))
            conn.sudo('apt-get update -y -q')
            conn.sudo('apt-get install software-properties-common -y -q')
            conn.sudo('add-apt-repository ppa:deadsnakes/ppa')
            conn.sudo('apt install python{} -y -q'.format(python_version))
            py_path = conn.run('which python{}'.format(python_version)).stdout.strip()
            if py_path:
                print('python{} is successfully installed'.format(python_version))
            else:
                print('failed to install python{}'.format(python_version))

        # install system requirements
        print('installing system requirements')
        conn.sudo('apt install libgdal-dev libpq-dev python{}-dev gdal-bin -y -q'.format(python_version))

        # install virtual env
        conn.sudo('apt install virtualenv -y -q')
        conn.run('virtualenv --python=python{} {}'.format(python_version, env.venv_path))
        conn.run('source {}/bin/activate'.format(env.venv_path))

        # install gdal
        conn.sudo('apt-get update -y -q')
        conn.sudo('apt-get install g++ -y -q')
        with virtualenv(conn) as conn:
            conn.run('export CPLUS_INCLUDE_PATH=/usr/include/gdal')
            conn.run('export CPLUS_INCLUDE_PATH=/usr/include/gdal')
            conn.run('pip install "GDAL<=$(gdal-config --version)"')


def setup_release(ctx):
    with connection(ctx) as conn:
        if not exists(conn, deploy_dir):
            conn.run('mkdir -p ' + deploy_dir)

        if not exists(conn, main_release_dir):
            logger.info("Creating Main release dir ~/releases/")
            conn.run('mkdir -p ' + main_release_dir)
            conn.run('mkdir -p ' + release_dir)

        if exists(conn, cache_dir):
            # clean up cache dir if exists
            remove(conn, cache_dir)
        else:
            logger.info("Creating Git cache dir")
            conn.run('mkdir -p ' + cache_dir)
            logger.info("Cloning repo")
            clone_project(conn, cache_dir)

        with conn.cd(cache_dir):
            conn.run('cp -R . {}'.format(release_dir))

        with conn.cd(release_dir):
            install_python_requirements(conn)

        create_symlink(conn, release_dir, current_ver_dir)


def create_symlink(conn, source, dest):
    logger.info("Creating the Symlink")
    conn.run('ln -sTf %s %s' % (source, dest))


def clone_project(conn, path):
    """
       Clones git repo with env.proj_name
    """
    conn.run("git clone {} {}".format(env.repo_url, path))


def install_python_requirements(conn):
    with virtualenv(conn) as conn:
        conn.run('pip install -r requirements.txt')


def exists(conn, path):
    return conn.run("[ -d '{}' ]".format(path)).exited == 0


def update_env(ctx):
    pass


def cleanup_old_releases(ctx):
    with connection(ctx) as conn:
        releases = conn.run('ls -x {}'.format(main_release_dir)).stdout.split()
        valid = [x for x in releases if re.search(r'release-(\d+)', x).groups()]
        if len(valid) > max_releases:
            directories = list(
                map(lambda x: os.path.join(main_release_dir, x), list(set(valid) - set(valid[-max_releases:]))))
            if exists(current_ver_dir):
                current_release = conn.run('readlink {}'.format(current_ver_dir)).stdout.strip()
                if current_release in directories:
                    logger.warning('wont delete current release {} '.format(conn.host))
                    directories.remove(current_release)
            else:
                logger.info('No current release on host: {}', conn.host)
            if directories:
                for directory in directories:
                    remove(conn, directory)
            else:
                logger.info('no old releases {}'.format(conn.host))


@task
def rollback(ctx):
    with connection(ctx) as conn:
        releases = conn.run('ls -xt {}'.format(main_release_dir)).stdout.split()
        if len(releases) < 2:
            logger.error("cannot rollback")
            quit(1)
        rollback_release_index = env.int('ROLLBACK_RELEASE', None)
        index = releases.index(rollback_release_index) if rollback_release_index else 1
        if not index:
            logger.error('cannot found rollback release')
            quit(1)

        last_release = releases[index]
        create_symlink(conn, last_release, current_ver_dir)


def remove(conn, directory):
    conn.run('rm -rfv {}'.format(directory))
