#!/usr/bin/env python
import zmq
from argparse import ArgumentParser
from time import sleep
import zlib
import pickle


from utils import *

from console_logger import *

SOCKET_ADDRESS = "tcp://localhost:5556"

def init_zmq():
	context = zmq.Context()
	socket = context.socket(zmq.REQ)
	socket.connect(SOCKET_ADDRESS)
	return socket

NODE_INFO = "node_info"
WALLET_INFO = "wallet_info"

def action_parser(action):
	if action == NODE_INFO:
		return NODE_INFO
	elif action == WALLET_INFO:
		return WALLET_INFO
	else:
		return None

def create_action(action, value):
	return {
		"action": action,
		"value": value
	}

def main():
	p = ArgumentParser()
	p.add_argument('--node_info', action='store_true')
	p.add_argument('--wallet_info', action='store_true')
	p.add_argument('--lock_status', action='store_true')
	p.add_argument('--set_lock_proportion', nargs=1, help="The amount as a proportion of your wallet to lock. 1 = 100%", type=float)

	args = p.parse_args()

	socket = init_zmq()

	if args.node_info:
		action = create_action("get_node_info", None)
		socket.send_json(action)
		sleep(0.5)
		state = socket.recv_json()
		print_node_info(state)
	elif args.wallet_info:
		action = create_action("get_wallet_info", None)
		socket.send_json(action)
		sleep(0.5)
		state = socket.recv_json()
		print_wallet_info(state)
	elif args.lock_status:
		action = create_action("get_lock_status", None)
		socket.send_json(action)
		sleep(0.5)
		state = socket.recv_json()
		print_status(state)
	elif args.set_lock_proportion:
		proportion = args.set_lock_proportion[0]
		if proportion > 1 and proportion < 0:
			return
		action = create_action("set_hedge_proportion", proportion)
		socket.send_json(action)
		sleep(0.5)
		state = socket.recv_json()
		print_success("New Lock Proportion: {}".format(str(state["hedge_proportion"] * 100) + " %"))
	else:
		print(args)
		print("noting")


	sleep(0.5)


if __name__ in "__main__":
	main()