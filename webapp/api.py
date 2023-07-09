import json
import redis
import logging
import time
from flask import Flask, request, jsonify
from flask_restx import Resource, Api

#constants
UNPACK_REQUEST_LIST_KEY = "MARS:UNPACK:QUEUE" 
REDIS_RETRYS = 3

#globals
r = None
connected = False
conf = {}
logger = logging.getLogger("MARS")
logger.setLevel(logging.DEBUG)
api = Api()

post_parser = api.parser()
post_parser.add_argument('input',  required=True)
post_parser.add_argument('output',  required=False)

get_parser = api.parser()
get_parser.add_argument('input',  required=False)
get_parser.add_argument('output',  required=False)

def init_api(config):
    global conf
    conf = config
    return api

def reconnect():
    trials = 0
    global connected
    global r

    while (not connected and trials < REDIS_RETRYS):
        try: 
            r = redis.Redis(host='localhost', port=6379)
            r.ping()
            connected = True
        except (redis.exceptions.ConnectionError):
            connected = False
            logger.error ("connection error retry no {} ".format(trials))
            trials +=1
            time.sleep(1)
    return connected


@api.route('/ext')
class Unpack(Resource):
    @api.expect(get_parser)
    def get(self):
        global connected
        global r

        args = get_parser.parse_args()

        if not connected:
            connected = reconnect()

        status_code = 200
        data = {}
        if 'input' in args and args["input"] is not None:
            while connected:
                try:
                    for s in  r.lrange(UNPACK_REQUEST_LIST_KEY,0,-1):
                        v = json.loads(s)
                        if args["input"] == v["input"] :
                            data = v 
                    break
                except (redis.exceptions.ConnectionError):
                    logger.error("error lookup input request {} from queue {}".format(args["input"],UNPACK_REQUEST_LIST_KEY))
                    connected = reconnect()
    
            if not connected:
                logger.error("connection to redis failed")
                status_code = 404
        else:
            while connected:
                try:
                    s = "all items"
                    data = [json.loads(l) for l in r.lrange(UNPACK_REQUEST_LIST_KEY,0,-1)]
                    break
                except (redis.exceptions.ConnectionError):
                    logger.error("error lookup request {} from {} queue".format(s,UNPACK_REQUEST_LIST_KEY))
                    connected = reconnect()

            if not connected:
                logger.error("connection to redis failed")
                status_code = 404

        response = jsonify(data)
        response.status_code = status_code
        response.headers = {'Content-Type': 'application/json'}
        return response
    

    @api.expect(post_parser)
    def post(self):
        global connected
        global r
        args = post_parser.parse_args()

        if not connected:
            connected = reconnect()

        input = args["input"]
        output = args["output"] if "output" in args and args["output"] is not None else input
        data = {'input':input,'output':output}
        status_code = 201

        while connected:
            try:
                s = json.dumps(data)
                # write though a method that reconnect and retry if needed
                l = r.lpush(UNPACK_REQUEST_LIST_KEY, s)
                break 
            except (redis.exceptions.ConnectionError):
                logger.error("error writing request {} to {} queue".format(s,UNPACK_REQUEST_LIST_KEY))
                connected = reconnect()

        if not connected:
            logger.error("connection to redis failed")
            data["message"] = "error redis connection"
            status_code = 502

        headers = {'Content-Type': 'application/json'}
        response = jsonify(data)
        response.status_code = status_code
        response.headers = headers
        return response

