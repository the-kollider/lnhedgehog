from os import get_inheritable
from kollider_api_client.ws import KolliderWsClient
from kollider_api_client.rest import KolliderRestClient
from utils import *
from console_logger import *
from lnd_client import LndClient
from kollider_msgs import OpenOrder, Position, TradableSymbol, Ticker
from time import sleep
from threading import Lock
import json
from math import floor
import uuid
from pprint import pprint
import threading

import zmq

SATOSHI_MULTIPLIER = 100000000

SOCKET_ADDRESS = "tcp://*:5556"

class HedgerState(object):
	position_quantity = 0
	ask_open_order_quantity = 0
	bid_open_order_quantity = 0
	target_quantity = 0
	target_value = 0
	is_locking = False
	lock_price = None
	side = None
	predicted_funding_payment = 0

	def to_dict(self):
		return {
			"position_quantity": self.position_quantity,
			"bid_open_order_quantity": self.bid_open_order_quantity,
			"ask_open_order_quantity": self.ask_open_order_quantity,
			"target_quantity": self.target_quantity,
			"target_value": self.target_value,
			"is_locking": self.is_locking,
			"lock_price": self.lock_price,
			"side": self.side,
			"predicted_funding_payment": self.predicted_funding_payment
		}

class Wallet(object):

	def __init__(self):
		self.channel_balance = 0
		self.nchain_balance = 0
		self.kollider_balance = 0

	def update_channel_balance(self, balance):
		self.channel_balance = balance

	def update_onchain_balance(self, balance):
		self.onchain_balance = balance

	def update_kollider_balance(self, balance):
		self.kollider_balance = balance

	def to_dict(self):
		return {
			"channel_balance": self.channel_balance,
			"onchain_balance": self.onchain_balance,
			"kollider_balance": self.kollider_balance
		}

	def total_ln_balance(self):
		return self.channel_balance + self.kollider_balance


class HedgerEngine(KolliderWsClient):
	def __init__(self, lnd_client):
		# Orders that are currently open on the Kollider platform.
		self.open_orders = {}
		# Positions that are currently open on the Kollider platform.
		self.positions = {}
		self.current_index_price = 0
		self.current_mark_price = 0
		self.target_fiat_currency = "USD"
		self.target_symbol = "BTCUSD.PERP"
		self.target_index_symbol = ".BTCUSD"
		self.ws_is_open = False
		self.contracts = {}

		self.hedge_value = 0
		self.hedge_proportion = 0
		self.hedge_side = None
		self.target_leverage = 100

		# Last hedge state.
		self.last_state = None

		# Summary of the connected node.
		self.node_info = None

		# Order type that is used to make trades on Kollider.
		self.order_type = "Market"

		self.wallet = Wallet()

		self.lnd_client = lnd_client

		self.last_ticker = Ticker()

		self.received_tradable_symbols = False

		# Average hourly funding rates for each symbol. Used
		# as an prediction of the next funding rate.
		self.average_hourly_funding_rates = {}

		self.is_locked = True

	def to_dict(self):
		average_funding = self.average_hourly_funding_rates.get(self.target_symbol)
		average_funding = average_funding if average_funding else 0
		return {
			"node_info": self.node_info,
			"wallet": self.wallet.to_dict(),
			"current_index_price": self.current_index_price,
			"current_mark_price": self.current_mark_price,
			"last_state": self.last_state.to_dict(),
			"target_fiat_currency": self.target_fiat_currency,
			"target_symbol": self.target_index_symbol,
			"target_index_symbol": self.target_index_symbol,
			"hedge_value": self.hedge_value,
			"hedge_proportion": self.hedge_proportion,
			"average_hourly_funding_rate": average_funding 
		}

	def set_params(self, **args):
		self.hedge_proportion = args.get("hedge_proportion") if args.get("hedge_proportion") else 0
		self.hedge_side = args.get("hedge_side") if args.get("hedge_side") else None
		self.target_fiat_currency = args.get("target_fiat_currency") if args.get("target_fiat_currency") else None
		self.target_symbol = args.get("target_symbol") if args.get("target_symbol") else None
		self.target_index_price = args.get("target_index_symbol") if args.get("target_index_symbol") else None
		self.target_leverage = args.get("target_leverage") if args.get("target_leverage") else None
		self.order_type = args.get("order_type") if args.get("order_type") else "Market"

	def on_open(self, event):
		self.auth()
		self.sub_index_price([self.target_index_symbol])
		self.sub_mark_price([self.target_symbol])
		self.sub_ticker([self.target_symbol])
		self.sub_position_states()
		self.fetch_positions()
		self.fetch_open_orders()
		self.fetch_tradable_symbols()
		self.fetch_ticker(self.target_symbol)
		self.fetch_balances()
		self.ws_is_open = True

	def on_pong(self, ctx, event):
		None

	def on_error(self, ctx, event):
		pass

	def on_message(self, _ctx, msg):
		msg = json.loads(msg)
		t = msg["type"]
		data = msg["data"]
		if t == 'authenticate':
			if data["message"] == "success":
				self.is_authenticated = True
			else:
				print("Auth Unsuccessful: {}".format(data))
				self.is_authenticated = False
				self.__reset()

		elif t == 'index_values':
			self.current_index_price = float(data["value"])

		elif t == 'mark_prices':
			self.current_mark_price = float(data["price"])

		elif t == 'positions':
			print("Received positions.")
			positions = data["positions"]
			for key, value in positions.items():
				self.positions[key] = Position(msg=value)

		elif t == 'open_orders':
			print("Received open orders")
			open_orders = data["open_orders"]
			for symbol, open_orders in open_orders.items():
				for open_order in open_orders:
					if self.open_orders.get(symbol) is None:
						self.open_orders[symbol] = []
					oo = OpenOrder(msg=open_order)
					self.open_orders[symbol].append(oo)

		elif t == 'tradable_symbols':
			for symbol, contract in data["symbols"].items():
				self.contracts[symbol] = TradableSymbol(msg=contract)
			self.received_tradable_symbols = True

		elif t == 'open':
			open_order = data
			contract = self.get_contract()
			dp = contract.price_dp
			open_order_parsed = OpenOrder(data, dp)
			if self.open_orders.get(open_order_parsed.symbol) is None:
				self.open_orders[open_order_parsed.symbol] = []
			self.open_orders[open_order_parsed.symbol].append(open_order_parsed)
		
		elif t == 'done':
			symbol = data["symbol"]
			order_id = data["order_id"]
			self.open_orders[symbol] = [open_order for open_order in self.open_orders[symbol] if open_order.order_id != order_id]

		elif t == 'fill':
			symbol = msg["symbol"]
			order_id = msg["order_id"]
			quantity = msg["quantity"]
			orders = self.open_orders.get(symbol)
			if orders is None:
				return
			for order in orders:
				if order.order_id == order_id:
					order.quantity -= quantity

		elif t == 'position_states':
			position = Position(msg=data)
			if position.symbol == self.target_symbol:
				self.positions[self.target_symbol] = position

		elif t == 'ticker':
			self.last_ticker = Ticker(msg=data)

		elif t == 'order_invoice':
			print("Received Pay to Trade invoice for: {}".format(data["margin"]))
			res = self.lnd_client.send_payment(data["invoice"])

		elif t == 'settlement_request':
			print("Received settlement Request")
			amount = data["amount"]
			self.make_withdrawal(amount, "Kollider Trade Settlement")

		elif t == 'balances':
			total_balance = 0
			cash_balance = float(data["cash"])
			if cash_balance > 1:
				self.make_withdrawal(cash_balance, "Kollider Payout")
			total_balance += cash_balance
			isolated_margin = data["isolated_margin"].get(self.target_symbol)
			if isolated_margin is not None:
				total_balance += float(isolated_margin)

			order_margin = data["order_margin"].get(self.target_symbol)
			if order_margin is not None:
				total_balance += float(order_margin)
			self.wallet.update_kollider_balance(total_balance)

		elif t == 'error':
			print("ERROR")
			print(data)

	def make_withdrawal(self, amount, message):
		amt = int(amount)
		res = self.lnd_client.add_invoice(amt, message)
		withdrawal_request = {
			"withdrawal_request": {
				"Ln": {
					"payment_request": res.payment_request,
					"amount": amt,
				}
			}
		}
		self.withdrawal_request(withdrawal_request)


	def cancel_all_orders_on_side(self, side):
		orders = self.open_orders.get(self.target_symbol)

		if orders is None:
			return

		for order in orders:
			if order.side == side:
				self.cancel_order({"order_id": order.order_id, "symbol": self.target_symbol, "settlement_type": "Delayed"})

	def calc_contract_value(self):
		if self.contracts.get(self.target_symbol) is not None:
			contract = self.get_contract()
			price = self.current_mark_price
			if contract.is_inverse_priced:
				return contract.contract_size / price * SATOSHI_MULTIPLIER
			else:
				return contract.contract_size * price * SATOSHI_MULTIPLIER
		else:
			raise Exception("Target contract not available")
		
	def calc_number_of_contracts_required(self, value_target):
		try:
			value_per_contract = self.calc_contract_value()
			qty_of_contracts = floor(value_target / value_per_contract)
			return qty_of_contracts
		except Exception as e:
			print(e)

	def get_open_orders(self):
		return self.open_orders.get(self.target_symbol)

	def get_open_position(self):
		return self.positions.get(self.target_symbol)

	def get_contract(self):
		return self.contracts.get(self.target_symbol)

	def get_best_price(self, side):
		if side == "Bid":
			return self.last_ticker.best_bid
		else:
			return self.last_ticker.best_ask
	
	def update_average_funding_rates(self):
		rest_client = KolliderRestClient("http://api.staging.kollider.internal/v1/")
		average_funding_rates = rest_client.get_average_funding_rates()
		for funding_rate in average_funding_rates["data"]:
			self.average_hourly_funding_rates[funding_rate["symbol"]] = funding_rate["mean_funding_rate"]

	def build_target_state(self):
		state = HedgerState()

		target_value = self.wallet.total_ln_balance()
		hedge_value = (target_value * self.hedge_proportion)

		# The number a contracts we need to cover the value.
		target_number_of_contracts = self.calc_number_of_contracts_required(hedge_value)

		# Getting current open orders.
		open_orders = self.get_open_orders()

		open_ask_order_quantity = 0
		open_bid_order_quantity = 0

		current_position_quantity = 0

		if open_orders is not None:
			open_bid_order_quantity = sum([open_order.quantity for open_order in open_orders if open_order.side == "Bid"])
			open_ask_order_quantity = sum([open_order.quantity for open_order in open_orders if open_order.side == "Ask"])

		# Getting current position on target symbol.
		open_position = self.get_open_position()

		if open_position is not None:
			current_position_quantity = open_position.quantity
			state.side = open_position.side
			# If current position is on the wrong side we adding a minus to reflect that.
			if open_position.side != opposite_side(self.hedge_side):
				current_position_quantity = current_position_quantity * -1
			else:
				state.lock_price = open_position.entry_price

		state.target_quantity = target_number_of_contracts
		state.target_value = hedge_value
		state.bid_open_order_quantity = open_bid_order_quantity
		state.ask_open_order_quantity = open_ask_order_quantity
		state.position_quantity = current_position_quantity

		hourly_funding_rate = self.average_hourly_funding_rates.get(self.target_symbol)
		if hourly_funding_rate is not None:
			state.predicted_funding_payment = hedge_value * hourly_funding_rate
		else:
			state.predicted_funding_payment = 0

		self.last_state = state

		return state

	def converge_state(self, state):
		# Nothing needs to be done if target is current.

		target_side = opposite_side(self.hedge_side)

		current = 0
		if target_side == "Bid":
			current = state.bid_open_order_quantity + state.position_quantity
		else:
			current = state.ask_open_order_quantity + state.position_quantity

		target = state.target_quantity

		if target == current:
			self.cancel_all_orders_on_side(self.hedge_side)
			return

		contract = self.get_contract()

		dp = contract.price_dp

		side = None

		if target > current:
			side = opposite_side(self.hedge_side)
			self.cancel_all_orders_on_side(self.hedge_side)

		elif target < current:
			side = self.hedge_side
			if target_side == "Bid" and state.bid_open_order_quantity > 0:
				self.cancel_all_orders_on_side(target_side)
				return
			elif target_side == "Ask" and state.ask_open_order_quantity > 0:
				self.cancel_all_orders_on_side(target_side)
				return

		price = self.get_best_price(side)

		# Adding the order to the top of the book by adding/subtracting one tick.
		if side == "Bid":
			price += contract.tick_size
		else:
			price -= contract.tick_size

		price = int(price * (10**dp))

		qty_required = abs(target - current)

		order = {
			'symbol': self.target_symbol,
			'side': side,
			'quantity': qty_required,
			'leverage': self.target_leverage,
			'price': price,
			'order_type': self.order_type,
			'margin_type': 'Isolated',
			'settlement_type': 'Instant',
			'ext_order_id': str(uuid.uuid4()),
		}

		self.place_order(order)

	def check_state(self, state):
		side = opposite_side(self.hedge_side)
		# If our current position has the right quantity and the right side we are fully locked
		if state.target_quantity == state.position_quantity and state.side == side:
			state.is_locking = False
			self.is_locked = True
		else:
			state.is_locking = True
			self.is_locked = False
		return state

	def print_state(self, state):
		pprint(state.to_dict())
		pprint(self.wallet.to_dict())

	def update_node_info(self):
		node_info = self.lnd_client.get_info()
		self.node_info = {
			"alias": node_info.alias,
			"identity_pubkey": node_info.identity_pubkey,
			"num_active_channels": node_info.num_active_channels,
		}

	def update_wallet_data(self):
		channel_balances = self.lnd_client.get_channel_balances()
		onchain_balances = self.lnd_client.get_onchain_balance()
		self.wallet.update_channel_balance(channel_balances.balance)
		self.wallet.update_onchain_balance(onchain_balances.total_balance)


	def cli_listener(self):
		context = zmq.Context()
		socket = context.socket(zmq.REP)
		socket.bind(SOCKET_ADDRESS)
		while True:
			message = socket.recv_json()
			if message.get("action") is not None:
				action = message.get("action")
				value = message.get("value")
				if action == "set_hedge_proportion":
					print("here")
					self.hedge_proportion = value
			sleep(0.5)
			msg = self.to_dict()
			socket.send_json(msg)
			sleep(0.5)

	def start(self, settings):
		pprint(settings)

		print("Connecting to Kollider websockets..")
		while not self.ws_is_open:
			pass
		print("Connected to websockets.")

		cycle_speed = settings["cycle_speed"]

		self.set_params(**settings)

		self.update_node_info()
		
		cli_listener = threading.Thread(target=self.cli_listener, daemon=False)
		cli_listener.start()

		while True:
			# Don't do anything if we haven't received the contracts.
			if not self.received_tradable_symbols and not self.is_authenticated:
				continue

			# Don't do anything if we haven't received mark or index price.
			if self.current_index_price == 0 or self.current_mark_price == 0:
				continue

			# Don't do anything if we have no ticker price.
			if self.last_ticker.last_side is None:
				continue


			self.update_wallet_data()

			self.update_average_funding_rates()

			# Getting current state.
			state = self.build_target_state()
			self.check_state(state)
			# Printing the state.
			# Converging to that state.
			self.converge_state(state)

			sleep(cycle_speed)



if __name__ in "__main__":

	settings = None
	with open('config.json') as a:
		settings = json.load(a)

	kollider_api_key = settings["kollider"]["api_key"]
	kollider_url = settings["kollider"]["ws_url"]

	node_url = settings["lnd"]["node_url"]
	macaroon_path = settings["lnd"]["admin_macaroon_path"]
	tls_path = settings["lnd"]["tls_path"]

	lnd_client = LndClient(node_url, macaroon_path, tls_path)

	rn_engine = HedgerEngine(lnd_client)

	lock = Lock()

	rn_engine.connect(kollider_url, kollider_api_key)

	rn_engine.start(settings)
