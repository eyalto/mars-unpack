import os
import json
import logging
import threading
import munch
import redis
import time
from MarsUnpackRecording import unpack
# from flask_healthz import healthz, HealthError
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
#
# global
#semaphore = None

# health checks QAZ 
_ready = False
_connection_attempts = 0
#
logger = logging.getLogger("MARS")
#
#
# global conf
conf_filename = os.environ.get('MARSCONFIG') if 'MARSCONFIG' in os.environ else "config.json"
config = json.load(open(conf_filename)) if os.path.isfile(conf_filename) else default_config
conf = munch.munchify(config)

# healthchecks - TBD - 

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


def redis_consumer():
    connected = False
    
    while True:
        try: 
            if not connected:
                r = reconnect()
                connected = r is not None

            if connected:
                ## remove from request queue and insert to working queue
                s = r.brpoplpush(conf.redis.input_queue, conf.redis.working_queue)
                data  = munch.munchify(json.loads(s))
                # setup
                output_paths = unpack.setup(data.input, data.output)
                rc = unpack.unpack(data.input, output_paths, conf.unpack.parallel, conf.unpack.verbose)
                # add to success queue
                if rc == 0:
                    r.lpush(conf.redis.success_queue,s)
                else:
                    r.lpush(conf.redis.failed_queue, s)

        except (redis.exceptions.ConnectionError):
            logger.error("redis consumer connection error - sleeping before retry ")
            connected = False
            time.sleep(conf.redis.SLEEP_BETWEEN_ATTEMPTS)
        except Exception as e:
            logger.error("redis consumer unpacking error - moving to filed queue {}".format(s))
            logger.exception(e)
            r.lpush(conf.redis.failed_queue,s)


def main():
    
    try:
        redis_consumer()
    except Exception as e:
        logger.error(f"failed initilaizing api server - error {str(e)} - exiting.")


if __name__ == "__main__":
    main()