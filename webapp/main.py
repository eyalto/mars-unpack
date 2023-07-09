import os
import json
import logging
import threading
import munch
import redis
import time
from flask import Flask
from flask_healthz import healthz, HealthError
from api import init_api
from MarsUnpackRecording import unpack
#
#
default_config = {
    "api": {
        "port": 8001
    },
    "monitor": {
        "port": 5080
    },
    "log" : {
        "name": "MARS",
        "level": "DEBUG"
    },
    "unpack" : {
        "parallel": 8,
        "verbose" : False,
        "threads" : 1
    },
    "redis": {
        "host": "localhost",
        "port": 6379,
        "input_queue": "MARS:UNPACK:QUEUE" ,
        "working_queue": "MARS:UNPACK:WORK",
        "failed_queue": "MARS:UNPACK:FAILED" ,
        "success_queue": "MARS:UNPACK:DONE" ,
        "MAX_CUNCURRENT_WORKING_CONSUMERS": 3, 
        "CONNECTION_BACKOFF_ATTEMPTS": 5,
        "SLEEP_BETWEEN_ATTEMPTS": 2
    }
}
# configmap location 
default_config_path = "/etc/mars/config.json"

#
# global
#semaphore = None
#
HEALTHZ = {
    "live": f"{__name__}.liveness",
    "ready": f"{__name__}.readiness",
}
#
# global conf
conf_filename = os.environ.get('MARSCONFIG') if 'MARSCONFIG' in os.environ else default_config_path
config = json.load(open(conf_filename)) if os.path.isfile(conf_filename) else default_config
conf = munch.munchify(config)

# health checks
_ready = False
_connection_attempts = 0
#
logger = logging.getLogger(conf.log.name)

# healthchecks
def liveness():
    logger.info("liveness check")
    if _connection_attempts >= conf.redis.CONNECTION_BACKOFF_ATTEMPTS:
        raise HealthError("Can't connect to the redis")

def readiness():
    logger.info("readiness check")
    if not _ready:
        raise HealthError("Waiting for redis become ready")

# global api server
app = Flask(__name__)
app.register_blueprint(healthz, url_prefix="/healthz")
app.config['HEALTHZ']=HEALTHZ


def excepthook(args):
    global _liveliness
    _liveliness = False
    logger.error(f"Unhandled exception: type {str(args.exc_type)} thread {str(args.thread)}")
    logger.error(f"Unhandled exception: value {str(args.exc_value)}")
    logger.error(f"Unhandled exception: trace {str(args.exc_traceback)}")
    
def start_monitor_server():
    pass

def reconnect():
    connected = False
    trials = 0
    r = None

    while (not connected and trials < conf.redis.CONNECTION_BACKOFF_ATTEMPTS):
        try: 
            r = redis.Redis(host='localhost', port=6379)
            r.ping()
            connected = True
        except (redis.exceptions.ConnectionError):
            connected = False
            logger.error ("connection error retry no {} ".format(trials))
            trials +=1
            time.sleep(conf.redis.SLEEP_BETWEEN_ATTEMPTS)
    
    if not connected:
        r = None

    return r


def main():
    
    logger.info(f"main starting with following configuration: {json.dumps(conf,indent=2)}")
    threading.excepthook = excepthook
    # monitor
    try:
       start_monitor_server()
    except Exception as e: 
        logger.warning(f"error initializing prometheus metric serving client: exception msg {str(e)} - exiting.")
        exit(1)
    try:
        api=init_api(conf)
        api.init_app(app)
        app.run(host="0.0.0.0", port=conf.api.port)
    except Exception as e:
        logger.error(f"failed initilaizing api server - error {str(e)} - exiting.")


if __name__ == "__main__":
    main()