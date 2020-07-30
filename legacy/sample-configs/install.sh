#!/bin/bash

########################################################################################################################
## Defaults
########################################################################################################################
PYTHON_DIR=/usr/bin
PYTHON_VERSION=3.7.8

INSTALL_ROOT=/opt
INSTALL_DIR=geneweaver
INSTALL_PATH=$INSTALL_ROOT/$INSTALL_DIR
INSTALL_USER=geneweaver
INSTALL_GROUP=geneweaver
VIRTUALENV_NAME=venv.geneweaver

GIT_SOURCE=false
GIT_BRANCH=master
GIT_WEB_SOURCE=https://bitbucket.org/geneweaver/py3-geneweaver-website.git
GIT_TOOLS_SOURCE=https://bitbucket.org/geneweaver/py3-geneweaver-tools.git

MODE=website
RUN_BASE_INSTALL=true

CELERY_RUN_DIR=/var/run/celery/
CELERY_LOG_DIR=/var/log/celery/

########################################################################################################################
## Usage and options/arguments
########################################################################################################################
function usage() {
  __USAGE="Usage: $(basename "$0") [options]

  Options:
    -m <mode>: The type of install to perform, must
    be one of [website|tools]
    (default=website)

    -p <path>: The base application directory to install
    modules into. (default=/opt/geneweaver)

    -u <user>: The unix user that will own and run the
    application (default=geneweaver)

    -g <group>: The unix group that owns the application
    directory (default=geneweaver)

    -e <name>: What to call the virtual environment(s)
    (default=venv.geneweaver)

    -s <git-url>: The git url of the source code
    (website default=https://bitbucket.org/geneweaver/py3-geneweaver-website.git)
    (tools default=https://bitbucket.org/geneweaver/py3-geneweaver-tools.git)

    -b <branch>: The git branch to use when checking
    out the source code. This can be changed later.
    (default=master)

    -x: If set, script will skip the os level installs,
    and user creation. It will only perform mode specific
    tasks.

    -h: Print this usage message and exit
  "

  echo "$__USAGE" >&2
  exit 1
}

function usage_post_install() {
  __NEXT="
  Before continuing, please fill out the geneweaver.cfg config file at:
    $CONFIG_FILE

  The [db] section MUST point to a running and connectable postgres database.

  Once the config is setup, you can run:
    sudo systemctl start $SERVICE_NAME
    sudo systemctl enable $SERVICE_NAME

  "

  __RABBITMQ_WEBSITE="
  Rabbitmq Server should be enabled and running.
  To check on the status of rabbitmq:
    sudo systemctl status rabbitmq-server

  This install created a 'geneweaver' user with password 'geneweaver' and granted
  it all permissions on a 'geneweaver' namespace. The celery url to connect to
  this looks like:
    amqp://geneweaver:geneweaver@localhost:5672/geneweaver

  To connect from a seperate server, specify the host
    amqp://geneweaver:geneweaver@<WEBSITE-SERVER>:5672/geneweaver

  "

  __RABBITMQ_WORKER="
  This script sets up RabbitMQ Server when installing in 'website' mode. When
  installed, it creates a 'geneweaver' user with password 'geneweaver' and grants
  it all permissions on a 'geneweaver' namespace. The url looks something like

    amqp://geneweaver:geneweaver@<WEBSITE-SERVER>:5672/geneweaver

  "

  __NGINX_STATUS="
  Nginx should be enabled and running, but we couldn't verify that it is.
  To check on the status of nginx:
    sudo systemctl status nginx

  Nginx configuration is available at:
    /etc/nginx/

  Once Ngxinx is setup and able to run, start and enable it with:
    sudo systemctl start nginx
    sudo systemctl enable nginx

  "

  __NGINX_NEXT="
  It's also a good idea to check the conents of:
    /etc/nginx/nginx.conf

  This is where you can setup https, and other nginx related functionality.

  "
  echo "$__NEXT"
  if [[ "$MODE" == "website" ]] ; then
    echo "$__RABBITMQ_WEBSITE"
    systemctl -q is-active nginx || echo "$__NGINX_STATUS"
    echo "$__NGINX_NEXT"
  else
    echo "$__RABBITMQ_WORKER"
  fi
}




while getopts ":m:p:u:g:v:e:s:b:xh" opt; do
  case ${opt} in
  m) MODE=$OPTARG ;;
  p) INSTALL_PATH=$OPTARG ;;
  u) INSTALL_USER=$OPTARG ;;
  g) INSTALL_GROUP=$OPTARG ;;
  v) PYTHON_VERSION=$OPTARG ;;
  e) VIRTUALENV_NAME=$OPTARG ;;
  s) GIT_SOURCE=$OPTARG ;;
  b) GIT_BRANCH=$OPTARG ;;
  x) RUN_BASE_INSTALL=false ;;
  h) usage ;;
  \?) echo "WARNING unused option included in call: $OPTARG" ;;
  esac
done


case $MODE in
website)
  if ! $GIT_SOURCE; then GIT_SOURCE=$GIT_WEB_SOURCE ; fi
  MODULE_DIR=website
  SERVICE_NAME=geneweaver
  CONFIG_PY="$INSTALL_PATH/$MODULE_DIR/src/config.py"
  ;;
tools)
  if ! $GIT_SOURCE; then GIT_SOURCE=$GIT_TOOLS_SOURCE ; fi
  MODULE_DIR=tools
  SERVICE_NAME=geneweaver-tools
  CONFIG_PY="$INSTALL_PATH/$MODULE_DIR/config.py"
  ;;
*)
  echo "Only 'website' and 'tools' modes are currently supported"
  exit 1
esac

CONFIG_FILE="$INSTALL_PATH/$MODULE_DIR/$MODULE_DIR.cfg"

########################################################################################################################
## Common Functions
########################################################################################################################
function install_python3() {
  if python3.7 --version | grep -q "Python $PYTHON_VERSION"; then
    echo "Python3.7 found: $(which python3.7). Skipping install."
  else
    # Requirements for compiling python3
    yum -y install gcc openssl-devel bzip2-devel libffi-devel wget

    wget -P /tmp/ "https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tgz"
    tar -xzf "/tmp/Python-$PYTHON_VERSION.tgz" --directory $PYTHON_DIR
    echo "Trying to cd to python dir"
    if cd "$PYTHON_DIR/Python-$PYTHON_VERSION/" ;
    then
      echo "Inside python dir: $(pwd)"
      rm "/tmp/Python-$PYTHON_VERSION.tgz"
      ./configure --enable-optimizations --prefix=/usr
      make altinstall
    else
      echo "There was a problem accessing the python installation directory"
      echo "Please check permissions on $PYTHON_DIR/Python-$PYTHON_VERSION/"
      exit
    fi
  fi
}

function install_os_deps() {
  yum -y install \
    boost \
    boost-devel \
    cairo \
    cairo-devel \
    git \
    graphviz \
    libffi \
    libffi-devel \
    libpqxx \
    libpqxx-devel \
    rabbitmq-server \
    ImageMagick \
    ImageMagick-devel \
    nginx
}

function clone_source() {
  CLONE_PATH="$INSTALL_PATH/$MODULE_DIR"
  mkdir -p "$INSTALL_PATH"
  if [ ! -d "$CLONE_PATH" ]; then
    git clone -b "$GIT_BRANCH" "$GIT_SOURCE" "$CLONE_PATH"
  else
    cd "$CLONE_PATH" || exit
    git checkout "$GIT_BRANCH"
    git pull
  fi
  chown "$INSTALL_USER":"$INSTALL_GROUP" "$CLONE_PATH" -R
  chmod g+w "$CLONE_PATH" -R
}

function add_system_user() {
  useradd "$INSTALL_USER" --system 2>/dev/null || true
}

function initialize_virtual_environment_pipenv() {
  REQS_FILE_PATH=$1
  VENV_PATH=$2
  su "$INSTALL_USER" <<EOF
cd "$VENV_PATH" || exit
python3.7 -m venv "$VIRTUALENV_NAME"
source "$VIRTUALENV_NAME/bin/activate"
pip3 install wheel
pip3 install -r $REQS_FILE_PATH
pipenv sync
EOF
}

function update_config_file_location() {
  sed -i "/^CONFIG_PATH\ =\ /c\CONFIG_PATH=\"$CONFIG_FILE\"" "$CONFIG_PY"
}

########################################################################################################################
## Web Specific Functions
########################################################################################################################
function initialize_website_config() {
  chown "$INSTALL_USER":"$INSTALL_GROUP" "$INSTALL_PATH" -R
  su "$INSTALL_USER" <<EOF
cd "$INSTALL_PATH/$MODULE_DIR" || exit
source "$VIRTUALENV_NAME/bin/activate"
pip install uwsgi
python -c 'from src.config import createConfig; createConfig()' || true
EOF
}

function setup_nginx() {
  mv /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup 2>/dev/null || true
  cp "$INSTALL_PATH/$MODULE_DIR/sample-configs/nginx.conf" /etc/nginx/nginx.conf
  # Update the location of the uswgi socket
  sed -i "s#unix:/srv/geneweaver/supervisord/uwsgi.sock;#unix:$INSTALL_PATH/$MODULE_DIR/uwsgi.sock;#" /etc/nginx/nginx.conf
  systemctl start nginx
}

function generate_uwsgi_file() {
  cat <<EOF >"$INSTALL_PATH/uwsgi.ini"
[uwsgi]

;; Change to the source directory prior to loading the application
chdir = $INSTALL_PATH/$MODULE_DIR/src
;; Virtual environment path. Comment out if not being used.
venv = $INSTALL_PATH/$MODULE_DIR/$VIRTUALENV_NAME
;; Name of the python script housing the application code
module = application
;; Create a master process
master = true
;; Number of worker processes to spawn
processes = 5
;; Number of threads per process
threads = 2
;; Location of the uWSGI UNIX socket nginx uses
socket = $INSTALL_PATH/$MODULE_DIR/uwsgi.sock
;; Modify socket permissions so nginx can read them
chmod-socket = 664
uid = nginx
gid = nginx
;; Clear environment on exit
vacuum = true
;; Ensure supervisor sends the correct kill signal
die-on-term = true
;; Allow uwsgi to rewrite script and path name variables
manage-script-name = true
;; Mounts application code to the root route
mount = /=application
;; Application name in application.py
callable = app
;; Request buffer size which needs to be increased for some admin page requests
buffer-size = 100000
;; Load the app a single time per worker to prevent concurrency issues from our
;; threaded DB pool
lazy-apps

EOF
}

function generate_systemd_file_website() {
  cat <<EOF >/etc/systemd/system/geneweaver.service
[Unit]
Description=uWSGI instance to serve geneweaver
After=network.target

[Service]
User=geneweaver
Group=nginx
StandardError=syslog
WorkingDirectory=$INSTALL_PATH/$MODULE_DIR/
Environment="PATH=$INSTALL_PATH/$MODULE_DIR/$VIRTUALENV_NAME/bin"
ExecStart=$INSTALL_PATH/$MODULE_DIR/$VIRTUALENV_NAME/bin/uwsgi --ini $INSTALL_PATH/uwsgi.ini

[Install]
WantedBy=multi-user.target
EOF
}

function setup_rabbitmq_server() {
  yum install rabbitmq-server
  systemctl start rabbitmq-server
  systemctl enable rabbitmq-server
  rabbitmqctl add_user geneweaver geneweaver
  rabbitmqctl add_vhost geneweaver
  rabbitmqctl set_permissions -p geneweaver geneweaver ".*" ".*" ".*"
}

########################################################################################################################
## Tool Specific Functions
########################################################################################################################
function install_tools_os_deps() {
  yum -y install \
    gcc \
    g++ \
    make
}

function initialize_celery() {
  mkdir -p $CELERY_LOG_DIR $CELERY_RUN_DIR
  chown "$INSTALL_USER":"$INSTALL_GROUP" $CELERY_LOG_DIR -R
  chown "$INSTALL_USER":"$INSTALL_GROUP" $CELERY_RUN_DIR -R
  su "$INSTALL_USER" <<EOF
cd $INSTALL_PATH && source "$MODULE_DIR/$VIRTUALENV_NAME/bin/activate"
python -c 'from tools.config import createConfig; createConfig()' || true
cd $INSTALL_PATH/tools/TOOLBOX && make && cd ../..
EOF
}

function generate_celery_config() {
  cat <<EOF >"$INSTALL_PATH/celery.cfg"
# Name of nodes to start
# here we have three nodes
CELERYD_NODES="w1 w2 w3"
# or we could have a single node:
# CELERYD_NODES="w1"

# Absolute or relative path to the 'celery' command:
CELERY_BIN="$INSTALL_PATH/$MODULE_DIR/$VIRTUALENV_NAME/bin/celery"

# App instance to use
CELERY_APP="tools.celeryapp"

# How to call manage.py
CELERYD_MULTI="multi"

# Extra command-line arguments to the worker
CELERYD_OPTS="--time-limit=300 --concurrency=8"

# - %n will be replaced with the first part of the nodename.
# - %I will be replaced with the current child process index
#   and is important when using the prefork pool to avoid race conditions.
CELERYD_PID_FILE="/var/run/celery/geneweaver/%n.pid"
CELERYD_LOG_FILE="/var/log/celery/geneweaver/%n%I.log"
CELERYD_LOG_LEVEL="INFO"

# you may wish to add these options for Celery Beat
CELERYBEAT_PID_FILE="$INSTALL_PATH/celery_beat.pid"
CELERYBEAT_LOG_FILE="$INSTALL_PATH/celery_beat.log"

EOF
}

function generate_systemd_file_tools() {
  cat <<EOF >/etc/systemd/system/geneweaver-tools.service
[Unit]
Description=Geneweaver Celery Service
After=network.target

[Service]
Type=forking
User=geneweaver
Group=geneweaver
EnvironmentFile=$INSTALL_PATH/celery.cfg
WorkingDirectory=$INSTALL_PATH
ExecStart=/bin/sh -c '\${CELERY_BIN} multi start \${CELERYD_NODES} \
  -A \${CELERY_APP} --pidfile=\${CELERYD_PID_FILE} \
  --logfile=\${CELERYD_LOG_FILE} --loglevel=\${CELERYD_LOG_LEVEL} \${CELERYD_OPTS}'
ExecStop=/bin/sh -c '\${CELERY_BIN} multi stopwait \${CELERYD_NODES} \
  --pidfile=\${CELERYD_PID_FILE}'
ExecReload=/bin/sh -c '\${CELERY_BIN} multi restart \${CELERYD_NODES} \
  -A \${CELERY_APP} --pidfile=\${CELERYD_PID_FILE} \
  --logfile=\${CELERYD_LOG_FILE} --loglevel=\${CELERYD_LOG_LEVEL} \${CELERYD_OPTS}'

[Install]
WantedBy=multi-user.target
EOF
}


########################################################################################################################
## The actual work of the script
########################################################################################################################
cd /tmp || ( echo "CRITICAL: Couldn't cd to /tmp" && exit )

echo "Working in $(pwd)"

if $RUN_BASE_INSTALL; then
  install_python3
  install_os_deps
  add_system_user
fi

clone_source
update_config_file_location
initialize_virtual_environment_pipenv "$INSTALL_PATH/$MODULE_DIR/requirements.txt" "$INSTALL_PATH/$MODULE_DIR"

case $MODE in
website)
  setup_rabbitmq_server
  initialize_website_config
  setup_nginx
  generate_uwsgi_file
  generate_systemd_file_website
  ;;
tools)
  initialize_celery
  generate_celery_config
  generate_systemd_file_tools
  ;;
esac

cd "$INSTALL_PATH" || echo "WARNING: Couldn't cd to $INSTALL_PATH."
echo "Currently working in: $(pwd)"

usage_post_install

exit 0
