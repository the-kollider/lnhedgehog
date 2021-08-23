import pickle
import zlib

def opposite_side(side):
	if side == "Bid":
		return "Ask"
	else:
		return "Bid"

def sats_to_dollars(sats_amount, price):
	return int((sats_amount / 100000000 * price) * 1000) / 1000