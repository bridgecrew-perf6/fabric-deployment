from pathlib import Path

import logging as logger
import os
import time

from click import Path
from dotenv import load_dotenv
from fabric import Connection as connection, task


@task
def deploy(ctx, env=None, branch=None):
    logger.basicConfig(level=logger.INFO)
    logger.basicConfig(format='%(name)s --------- %(message)s')

    if env is None or branch is None:
        logger.error("Env variable and branch name are required!, try to call it as follows : ")
        logger.error("fab deploy -e YOUR_ENV_FILE.env -b BRANCH_NAME")
        exit()
    time_stamp = time.strftime('%Y%m%d_%H%M%S')
    # Load the env files
    if os.path.exists(env):
        load_dotenv(dotenv_path=env, verbose=True)
        logger.info("The ENV file is successfully loaded")
    else:
        logger.error("The ENV is not found")
        exit()

    user = os.getenv("DS_USER")
    host = os.getenv("DS_HOST")
    deploy_dir = os.getenv("DS_DEPLOY_DIR")
    cache_dir = os.getenv("DS_CACHE_DIR")
    repo_url = os.getenv("DS_REPO_URL")
    main_release_dir = os.path.join(deploy_dir, os.getenv("DS_RELEASE_DIR"))

    release_dir = os.path.join(main_release_dir, 'release-' + time_stamp)
    current_ver_dir = os.path.join(deploy_dir, os.getenv('DS_CURRENT_DIR'))
    with connection(host=host, user=user) as c:
        # This is an example of how to add an env variable to the deploy server
        c.run('echo export %s >> ~/.bashrc ' % 'SAMPLE_ENV_VAR=VALUE')
        c.run('source ~/.bashrc')
        c.run('echo $SAMPLE_ENV_VAR')  # to verify if it's set or not!

        if not os.path.isdir(Path(deploy_dir)):
            c.run('mkdir -p ' + deploy_dir)

        if not os.path.isdir(Path(main_release_dir)):
            logger.info("Creating Main release dir /releases/")
            c.run('mkdir -p ' + main_release_dir)
            c.run('mkdir -p ' + release_dir)

            if not os.path.isdir(Path(cache_dir)):
                logger.info("Creating Git cache dir")
                logger.info("Cloning Flask_api")
                c.run('git clone -b %s %s %s' % (branch, repo_url, cache_dir), warn=True)

        with c.cd(cache_dir):
            logger.info("Pulling from Flask_api repo")
            c.run('git pull')
            logger.info("Checkout %s from Flask_api repo" % branch)
            c.run('git checkout %s' % branch)
            c.run('git pull')

        with c.cd(cache_dir):
            c.run('rsync -a  --exclude .git . %s' % release_dir)

        logger.info("Change recursively the owner-group of release directory")
        c.run('chgrp -R %s %s' % (user, release_dir))

        with c.cd(release_dir):
            c.run('virtualenv flask_api_virtualenv')
            with c.prefix('source flask_api_virtualenv/bin/activate'):
                c.run('pip3.6 install -r requirements.txt')
                c.run('deactivate')

        logger.info("Creating the Symlink")
        c.run('ln -sTf %s %s' % (release_dir, current_ver_dir))

        logger.info("Restarting nginx")
        c.run('sudo /bin/systemctl restart nginx')

        logger.info("Restarting uWSGi")
        c.run('sudo /bin/systemctl restart uwsgi')