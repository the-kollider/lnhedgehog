SATOSHI_MULTIPLIER = 100000000

def opposite_side(side):
	if side == "Bid":
		return "Ask"
	return "Bid"

def sats_to_dollars(sats_amount, price):
	return int((sats_amount / SATOSHI_MULTIPLIER * price) * 1000) / 1000